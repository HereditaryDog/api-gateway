"""
故障转移服务
自动切换账号、跨厂商降级、熔断机制
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Callable
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.upstream import UpstreamProvider, UpstreamKey
from app.services.risk_control.pool_manager import PoolManager
from app.services.risk_control.anomaly_detector import (
    AnomalyDetector, AnomalyEvent, AnomalyType, get_anomaly_detector
)


class FailoverStrategy(Enum):
    """故障转移策略"""
    SAME_PROVIDER = "same_provider"      # 同厂商切换账号
    DIFFERENT_PROVIDER = "different_provider"  # 跨厂商降级
    CIRCUIT_BREAK = "circuit_break"      # 熔断


@dataclass
class FailoverResult:
    """故障转移结果"""
    success: bool
    strategy: FailoverStrategy
    new_key_id: Optional[int] = None
    new_provider_id: Optional[int] = None
    message: str = ""


class CircuitBreaker:
    """
    熔断器
    
    状态:
    - CLOSED: 正常，请求通过
    - OPEN: 熔断，请求被拒绝
    - HALF_OPEN: 半开，尝试恢复
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._success_count = 0
    
    @property
    def state(self) -> str:
        """获取当前状态"""
        if self._state == "OPEN":
            # 检查是否应该进入半开状态
            if self._last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    self._half_open_calls = 0
                    self._success_count = 0
        return self._state
    
    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        state = self.state
        
        if state == "CLOSED":
            return True
        elif state == "OPEN":
            return False
        elif state == "HALF_OPEN":
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        
        return False
    
    def record_success(self):
        """记录成功"""
        if self._state == "HALF_OPEN":
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                # 恢复成功，关闭熔断
                self._state = "CLOSED"
                self._failure_count = 0
        else:
            self._failure_count = 0
    
    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = datetime.now(timezone.utc)
        
        if self._state == "HALF_OPEN":
            # 半开状态失败，重新熔断
            self._state = "OPEN"
        elif self._failure_count >= self.failure_threshold:
            # 达到阈值，开启熔断
            self._state = "OPEN"


class FailoverManager:
    """
    故障转移管理器
    
    功能:
    1. 同厂商账号切换
    2. 跨厂商降级
    3. 熔断管理
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._pool_managers: Dict[int, PoolManager] = {}
        self._circuit_breakers: Dict[int, CircuitBreaker] = {}
        self._anomaly_detector = get_anomaly_detector()
    
    def _get_pool_manager(self, provider_id: int) -> PoolManager:
        """获取账号池管理器"""
        if provider_id not in self._pool_managers:
            self._pool_managers[provider_id] = PoolManager(self.db, provider_id)
        return self._pool_managers[provider_id]
    
    def _get_circuit_breaker(self, key_id: int) -> CircuitBreaker:
        """获取熔断器"""
        if key_id not in self._circuit_breakers:
            self._circuit_breakers[key_id] = CircuitBreaker()
        return self._circuit_breakers[key_id]
    
    async def execute_with_failover(
        self,
        provider_id: int,
        operation: Callable,
        max_retries: int = 3,
        enable_cross_provider: bool = True
    ) -> tuple[bool, any]:
        """
        执行操作，支持故障转移
        
        Args:
            provider_id: 首选 Provider ID
            operation: 要执行的操作（接收 key_id 参数）
            max_retries: 最大重试次数
            enable_cross_provider: 是否允许跨厂商降级
        
        Returns:
            (是否成功, 结果或错误信息)
        """
        excluded_keys = []
        last_error = None
        
        # 首先尝试同厂商切换
        for attempt in range(max_retries):
            # 选择账号
            pool_manager = self._get_pool_manager(provider_id)
            account = await pool_manager.select_account(excluded_keys)
            
            if not account:
                break  # 没有可用账号了
            
            # 检查熔断器
            cb = self._get_circuit_breaker(account.key_id)
            if not cb.can_execute():
                excluded_keys.append(account.key_id)
                continue
            
            try:
                # 执行操作
                result = await operation(account.decrypted_key, account.key_id)
                
                # 记录成功
                cb.record_success()
                await pool_manager.update_account_health(
                    account.key_id, success=True
                )
                
                return True, result
                
            except Exception as e:
                last_error = e
                
                # 记录失败
                cb.record_failure()
                await pool_manager.update_account_health(
                    account.key_id, success=False, error=e
                )
                
                excluded_keys.append(account.key_id)
                
                # 检测异常
                self._anomaly_detector.detect_consecutive_errors(
                    account.key_id, provider_id, 
                    self._get_consecutive_errors(account.key_id)
                )
        
        # 同厂商失败，尝试跨厂商降级
        if enable_cross_provider:
            fallback_result = await self._try_fallback_provider(
                operation, excluded_keys
            )
            if fallback_result[0]:
                return fallback_result
        
        return False, last_error
    
    async def _try_fallback_provider(
        self,
        operation: Callable,
        excluded_keys: List[int]
    ) -> tuple[bool, any]:
        """
        尝试备用 Provider
        
        查找同类型或通用类型的 Provider
        """
        # 获取所有激活的 Provider
        result = await self.db.execute(
            select(UpstreamProvider).where(
                UpstreamProvider.is_active == True
            )
        )
        providers = result.scalars().all()
        
        for provider in providers:
            # 跳过没有可用 key 的 provider
            keys_result = await self.db.execute(
                select(UpstreamKey).where(
                    and_(
                        UpstreamKey.provider_id == provider.id,
                        UpstreamKey.is_active == True,
                        UpstreamKey.is_exhausted == False
                    )
                )
            )
            keys = keys_result.scalars().all()
            available_keys = [k for k in keys if k.id not in excluded_keys]
            
            if not available_keys:
                continue
            
            # 尝试这个 provider
            pool_manager = self._get_pool_manager(provider.id)
            account = await pool_manager.select_account(excluded_keys)
            
            if not account:
                continue
            
            try:
                result = await operation(account.decrypted_key, account.key_id)
                
                # 记录跨厂商降级事件
                event = AnomalyEvent(
                    key_id=account.key_id,
                    provider_id=provider.id,
                    anomaly_type=AnomalyType.SUSPICIOUS_PATTERN,
                    severity="medium",
                    message="Cross-provider fallback executed",
                    details={"original_provider_exhausted": True},
                    timestamp=datetime.now(timezone.utc),
                )
                self._anomaly_detector._emit(event)
                
                return True, result
                
            except Exception:
                excluded_keys.append(account.key_id)
                continue
        
        return False, None
    
    async def _get_consecutive_errors(self, key_id: int) -> int:
        """获取连续错误数"""
        from app.models.billing import UpstreamKeyQuota
        
        result = await self.db.execute(
            select(UpstreamKeyQuota).where(
                UpstreamKeyQuota.key_id == key_id
            )
        )
        quota = result.scalar_one_or_none()
        return quota.consecutive_errors if quota else 0
    
    async def get_health_status(self, provider_id: int) -> dict:
        """获取健康状态"""
        pool_manager = self._get_pool_manager(provider_id)
        pool_stats = await pool_manager.get_pool_stats()
        
        # 获取熔断器状态
        cb_states = {}
        for key_id, cb in self._circuit_breakers.items():
            cb_states[key_id] = {
                "state": cb.state,
                "failure_count": cb._failure_count,
            }
        
        return {
            "provider_id": provider_id,
            "pool_stats": pool_stats,
            "circuit_breakers": cb_states,
        }


# 全局故障转移管理器
_global_failover_manager: Optional[FailoverManager] = None


def get_failover_manager(db: AsyncSession) -> FailoverManager:
    """获取全局故障转移管理器"""
    global _global_failover_manager
    if _global_failover_manager is None:
        _global_failover_manager = FailoverManager(db)
    return _global_failover_manager
