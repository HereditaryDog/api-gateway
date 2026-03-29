"""
Coding Plan 适配器
专门用于处理 Coding Plan 类型的订阅制厂商

特性:
1. 多账号池管理
2. 滚动配额追踪
3. 流量整形
4. 异常检测
5. 自动故障转移
"""
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import BaseProvider
from app.providers.openai_compat import OpenAICompatProvider
from app.services.risk_control import (
    PoolManager,
    QuotaTracker,
    TrafficShaper,
    RateLimitConfig,
    AnomalyDetector,
    get_anomaly_detector,
    FailoverManager,
)
from app.services.risk_control.anomaly_detector import AnomalyType
from app.models.billing import ProviderBillingConfig
from app.core.encryption import decrypt_data


class CodingPlanAdapter(BaseProvider):
    """
    Coding Plan 专用适配器
    
    使用 OpenAI 兼容协议，但增加了:
    - 多账号池管理
    - 滚动配额追踪
    - 流量整形
    - 异常检测
    """
    
    def __init__(
        self,
        db: AsyncSession,
        provider_id: int,
        provider_name: str = "coding_plan",
        base_url: str = None,
    ):
        # 注意: 这个 provider 不使用固定的 api_key
        # 而是从账号池中动态选择
        super().__init__(api_key="", base_url=base_url or "")
        
        self.db = db
        self.provider_id = provider_id
        self.provider_name = provider_name
        
        # 初始化风控组件
        self.pool_manager = PoolManager(db, provider_id)
        self.anomaly_detector = get_anomaly_detector()
        self.failover_manager = FailoverManager(db)
        
        # 加载配置
        self.config: Optional[ProviderBillingConfig] = None
        self.rate_limit_config: Optional[RateLimitConfig] = None
        
        # 流量整形器缓存
        self._traffic_shapers: Dict[int, TrafficShaper] = {}
    
    async def _load_config(self):
        """加载计费配置"""
        if self.config:
            return
        
        from sqlalchemy import select
        result = await self.db.execute(
            select(ProviderBillingConfig).where(
                ProviderBillingConfig.provider_id == self.provider_id
            )
        )
        self.config = result.scalar_one_or_none()
        
        if self.config:
            self.rate_limit_config = RateLimitConfig(
                min_qps=float(self.config.min_qps_limit) if self.config.min_qps_limit else 0.5,
                max_qps=float(self.config.max_qps_limit) if self.config.max_qps_limit else 2.0,
                jitter_ms_min=self.config.jitter_ms_min or 100,
                jitter_ms_max=self.config.jitter_ms_max or 500,
            )
    
    def _get_traffic_shaper(self, key_id: int) -> TrafficShaper:
        """获取流量整形器"""
        if key_id not in self._traffic_shapers:
            config = self.rate_limit_config or RateLimitConfig()
            self._traffic_shapers[key_id] = TrafficShaper(key_id, config)
        return self._traffic_shapers[key_id]
    
    async def _select_and_prepare_account(
        self,
        exclude_key_ids: list = None
    ) -> tuple[str, int, QuotaTracker]:
        """
        选择并准备账号
        
        Returns:
            (api_key, key_id, quota_tracker)
        """
        await self._load_config()
        
        # 从账号池选择
        account = await self.pool_manager.select_account(exclude_key_ids or [])
        
        if not account:
            raise Exception("No available account in pool")
        
        # 检查配额
        quota_tracker = QuotaTracker(self.db, account.key_id)
        is_available, quota_details = await quota_tracker.check_quota()
        
        if not is_available:
            # 配额不足，标记账号不可用
            await self.pool_manager.update_account_health(
                account.key_id, success=False
            )
            
            # 检测配额耗尽异常
            for window_type, details in quota_details.items():
                if window_type != "overall_available" and not details.get("available"):
                    self.anomaly_detector.detect_quota_exhausted(
                        account.key_id,
                        self.provider_id,
                        window_type,
                        details["used"],
                        details["limit"]
                    )
            
            # 递归重试
            exclude_key_ids = exclude_key_ids or []
            exclude_key_ids.append(account.key_id)
            return await self._select_and_prepare_account(exclude_key_ids)
        
        # 解密 API Key
        if not account.decrypted_key:
            account.decrypted_key = decrypt_data(account.encrypted_key)
        
        return account.decrypted_key, account.key_id, quota_tracker
    
    async def _apply_traffic_shaping(self, key_id: int):
        """应用流量整形"""
        if not self.config or not self.config.enable_risk_control:
            return
        
        shaper = self._get_traffic_shaper(key_id)
        await shaper.acquire()
    
    async def chat_completion(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        """
        聊天完成接口（非流式）
        """
        start_time = time.time()
        
        # 选择账号
        api_key, key_id, quota_tracker = await self._select_and_prepare_account()
        
        # 应用流量整形
        await self._apply_traffic_shaping(key_id)
        
        # 消耗配额
        if not await quota_tracker.consume_quota(1):
            raise Exception("Quota exceeded")
        
        # 创建底层 provider
        provider = OpenAICompatProvider(
            api_key=api_key,
            base_url=self.base_url
        )
        
        try:
            # 调用 API
            response = await provider.chat_completion(model, messages, **kwargs)
            
            # 记录成功
            response_time_ms = int((time.time() - start_time) * 1000)
            await self.pool_manager.update_account_health(
                key_id, success=True, response_time_ms=response_time_ms
            )
            
            return response
            
        except Exception as e:
            # 记录失败
            await self.pool_manager.update_account_health(
                key_id, success=False, error=e
            )
            
            # 检测高延迟
            response_time_ms = int((time.time() - start_time) * 1000)
            if response_time_ms > 10000:
                self.anomaly_detector.detect_high_latency(
                    key_id, self.provider_id, response_time_ms, 0
                )
            
            raise
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        聊天完成接口（流式）
        """
        start_time = time.time()
        
        # 选择账号
        api_key, key_id, quota_tracker = await self._select_and_prepare_account()
        
        # 应用流量整形
        await self._apply_traffic_shaping(key_id)
        
        # 消耗配额
        if not await quota_tracker.consume_quota(1):
            yield 'data: {"error": {"message": "Quota exceeded", "type": "quota_error"}}\n\n'
            return
        
        # 创建底层 provider
        provider = OpenAICompatProvider(
            api_key=api_key,
            base_url=self.base_url
        )
        
        success = False
        try:
            # 调用 API
            async for chunk in provider.chat_completion_stream(model, messages, **kwargs):
                yield chunk
            
            success = True
            
        except Exception as e:
            # 记录失败
            await self.pool_manager.update_account_health(
                key_id, success=False, error=e
            )
            
            # 返回错误
            yield f'data: {{"error": {{"message": "{str(e)}", "type": "upstream_error"}}}}\n\n'
        
        finally:
            # 记录结果
            response_time_ms = int((time.time() - start_time) * 1000)
            await self.pool_manager.update_account_health(
                key_id, success=success, response_time_ms=response_time_ms
            )
    
    async def embeddings(
        self,
        model: str,
        input_data: str,
        **kwargs
    ) -> Dict[str, Any]:
        """嵌入接口"""
        # 选择账号
        api_key, key_id, quota_tracker = await self._select_and_prepare_account()
        
        # 应用流量整形
        await self._apply_traffic_shaping(key_id)
        
        # 消耗配额
        if not await quota_tracker.consume_quota(1):
            raise Exception("Quota exceeded")
        
        # 创建底层 provider
        provider = OpenAICompatProvider(
            api_key=api_key,
            base_url=self.base_url
        )
        
        return await provider.embeddings(model, input_data, **kwargs)
    
    async def get_pool_stats(self) -> dict:
        """获取账号池统计"""
        return await self.pool_manager.get_pool_stats()
    
    async def get_quota_stats(self, key_id: int) -> dict:
        """获取配额统计"""
        tracker = QuotaTracker(self.db, key_id)
        return await tracker.get_usage_stats()


class CodingPlanAdapterWithFailover(CodingPlanAdapter):
    """
    带故障转移的 Coding Plan 适配器
    
    在 CodingPlanAdapter 基础上增加了:
    - 自动重试
    - 同厂商切换
    - 跨厂商降级
    """
    
    async def chat_completion(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        """带故障转移的聊天完成"""
        
        async def operation(api_key: str, key_id: int) -> Dict[str, Any]:
            provider = OpenAICompatProvider(
                api_key=api_key,
                base_url=self.base_url
            )
            return await provider.chat_completion(model, messages, **kwargs)
        
        success, result = await self.failover_manager.execute_with_failover(
            provider_id=self.provider_id,
            operation=operation,
            max_retries=3,
            enable_cross_provider=True
        )
        
        if success:
            return result
        else:
            raise Exception(f"All failover attempts failed: {result}")
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """带故障转移的流式聊天完成"""
        # 流式响应的故障转移比较复杂
        # 这里简化处理，先尝试一次，失败则返回错误
        try:
            async for chunk in super().chat_completion_stream(model, messages, **kwargs):
                yield chunk
        except Exception as e:
            # 尝试故障转移
            exclude_keys = []
            for attempt in range(3):
                try:
                    api_key, key_id, quota_tracker = await self._select_and_prepare_account(exclude_keys)
                    
                    await self._apply_traffic_shaping(key_id)
                    
                    if not await quota_tracker.consume_quota(1):
                        exclude_keys.append(key_id)
                        continue
                    
                    provider = OpenAICompatProvider(api_key=api_key, base_url=self.base_url)
                    
                    async for chunk in provider.chat_completion_stream(model, messages, **kwargs):
                        yield chunk
                    
                    return
                    
                except Exception as retry_error:
                    exclude_keys.append(key_id)
                    continue
            
            yield f'data: {{"error": {{"message": "All failover attempts failed: {str(e)}", "type": "failover_error"}}}}\n\n'
