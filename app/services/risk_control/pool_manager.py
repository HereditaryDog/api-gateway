"""
多账号池管理服务
管理 Coding Plan 等订阅制厂商的多账号池
"""
import random
import asyncio
from typing import List, Optional, Dict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.upstream import UpstreamKey, UpstreamProvider
from app.models.billing import UpstreamKeyQuota
from app.core.encryption import decrypt_data


@dataclass
class AccountInfo:
    """账号信息"""
    key_id: int
    provider_id: int
    encrypted_key: str
    decrypted_key: Optional[str] = None
    weight: int = 100
    priority: int = 100
    health_score: float = 100.0
    is_available: bool = True
    quota_info: Optional[UpstreamKeyQuota] = None
    
    # 统计信息
    consecutive_errors: int = 0
    last_used_at: Optional[datetime] = None
    avg_response_time_ms: float = 0.0
    success_rate: float = 1.0


class PoolManager:
    """
    多账号池管理器
    
    功能:
    1. 维护账号池健康状态
    2. 动态权重调整
    3. 账号轮换策略
    """
    
    def __init__(self, db: AsyncSession, provider_id: int):
        self.db = db
        self.provider_id = provider_id
        self._accounts: Dict[int, AccountInfo] = {}
        self._last_refresh: Optional[datetime] = None
        self._refresh_interval = 60  # 刷新间隔（秒）
    
    async def refresh_pool(self) -> List[AccountInfo]:
        """
        刷新账号池
        
        Returns:
            可用账号列表
        """
        # 获取所有 keys
        result = await self.db.execute(
            select(UpstreamKey).where(
                and_(
                    UpstreamKey.provider_id == self.provider_id,
                    UpstreamKey.is_active == True,
                    UpstreamKey.is_exhausted == False
                )
            )
        )
        keys = result.scalars().all()
        
        accounts = []
        for key in keys:
            # 获取配额信息
            quota_result = await self.db.execute(
                select(UpstreamKeyQuota).where(
                    UpstreamKeyQuota.key_id == key.id
                )
            )
            quota = quota_result.scalar_one_or_none()
            
            # 检查账号是否可用
            is_available = await self._check_account_available(key, quota)
            
            account = AccountInfo(
                key_id=key.id,
                provider_id=self.provider_id,
                encrypted_key=key.encrypted_key,
                decrypted_key=None,  # 延迟解密
                weight=key.weight,
                priority=key.priority,
                health_score=quota.health_score if quota else 100.0,
                is_available=is_available,
                quota_info=quota,
                consecutive_errors=quota.consecutive_errors if quota else 0,
                last_used_at=key.last_used_at,
                avg_response_time_ms=quota.avg_response_time_ms if quota else 0.0,
                success_rate=quota.success_rate if quota else 1.0,
            )
            
            accounts.append(account)
            self._accounts[key.id] = account
        
        self._last_refresh = datetime.now(timezone.utc)
        return accounts
    
    async def _check_account_available(
        self,
        key: UpstreamKey,
        quota: Optional[UpstreamKeyQuota]
    ) -> bool:
        """检查账号是否可用"""
        if not key.is_active or key.is_exhausted:
            return False
        
        if quota:
            # 检查是否被限流
            if quota.is_throttled and quota.throttle_until:
                if quota.throttle_until > datetime.now(timezone.utc):
                    return False
            
            # 检查是否超出配额
            if quota.is_quota_exceeded:
                return False
            
            # 检查连续错误数
            if quota.consecutive_errors >= 5:
                return False
        
        return True
    
    async def select_account(
        self,
        exclude_key_ids: List[int] = None
    ) -> Optional[AccountInfo]:
        """
        选择可用账号
        
        选择策略:
        1. 过滤不可用的账号
        2. 根据健康度和权重排序
        3. 加权随机选择
        
        Args:
            exclude_key_ids: 要排除的 Key ID 列表
        
        Returns:
            选中的账号信息，如果没有可用账号返回 None
        """
        # 刷新账号池（如果需要）
        if self._should_refresh():
            await self.refresh_pool()
        
        # 过滤可用账号
        available_accounts = []
        for account in self._accounts.values():
            if not account.is_available:
                continue
            if exclude_key_ids and account.key_id in exclude_key_ids:
                continue
            available_accounts.append(account)
        
        if not available_accounts:
            # 强制刷新重试
            await self.refresh_pool()
            for account in self._accounts.values():
                if not account.is_available:
                    continue
                if exclude_key_ids and account.key_id in exclude_key_ids:
                    continue
                available_accounts.append(account)
        
        if not available_accounts:
            return None
        
        # 根据健康度调整权重
        weighted_accounts = []
        for account in available_accounts:
            # 权重 = 原始权重 × 健康度
            adjusted_weight = account.weight * (account.health_score / 100.0)
            weighted_accounts.append((account, adjusted_weight))
        
        # 加权随机选择
        total_weight = sum(w for _, w in weighted_accounts)
        if total_weight <= 0:
            # 所有权重为0，均匀随机
            selected = random.choice(available_accounts)
        else:
            r = random.uniform(0, total_weight)
            current_weight = 0
            selected = weighted_accounts[-1][0]  # 默认选最后一个
            for account, weight in weighted_accounts:
                current_weight += weight
                if r <= current_weight:
                    selected = account
                    break
        
        # 延迟解密 API Key
        if selected and not selected.decrypted_key:
            selected.decrypted_key = decrypt_data(selected.encrypted_key)
        
        return selected
    
    async def update_account_health(
        self,
        key_id: int,
        success: bool,
        response_time_ms: int = 0,
        error: Exception = None
    ):
        """
        更新账号健康状态
        
        Args:
            key_id: Key ID
            success: 是否成功
            response_time_ms: 响应时间（毫秒）
            error: 错误信息
        """
        # 获取配额记录
        result = await self.db.execute(
            select(UpstreamKeyQuota).where(
                UpstreamKeyQuota.key_id == key_id
            )
        )
        quota = result.scalar_one_or_none()
        
        if not quota:
            # 创建新的配额记录
            quota = UpstreamKeyQuota(
                key_id=key_id,
                window_5h_used=0,
                window_week_used=0,
                window_month_used=0,
                consecutive_errors=0,
                avg_response_time_ms=0.0,
                success_rate=1.0,
            )
            self.db.add(quota)
        
        # 更新统计
        if success:
            quota.consecutive_errors = 0
            # 更新平均响应时间（指数移动平均）
            alpha = 0.3  # 平滑因子
            quota.avg_response_time_ms = (
                alpha * response_time_ms + 
                (1 - alpha) * quota.avg_response_time_ms
            )
            # 更新成功率
            quota.success_rate = min(1.0, quota.success_rate * 0.95 + 0.05)
        else:
            quota.consecutive_errors += 1
            quota.last_error_at = datetime.now(timezone.utc)
            # 更新成功率
            quota.success_rate = max(0.0, quota.success_rate * 0.95)
            
            # 检查是否需要限流
            if quota.consecutive_errors >= 5:
                quota.is_throttled = True
                # 限流 5 分钟
                from datetime import timedelta
                quota.throttle_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        await self.db.commit()
        
        # 更新内存中的账号信息
        if key_id in self._accounts:
            account = self._accounts[key_id]
            account.consecutive_errors = quota.consecutive_errors
            account.avg_response_time_ms = quota.avg_response_time_ms
            account.success_rate = quota.success_rate
            account.health_score = quota.health_score
            account.is_available = await self._check_account_available(
                await self._get_key(key_id), quota
            )
    
    async def _get_key(self, key_id: int) -> Optional[UpstreamKey]:
        """获取 Key 信息"""
        result = await self.db.execute(
            select(UpstreamKey).where(UpstreamKey.id == key_id)
        )
        return result.scalar_one_or_none()
    
    def _should_refresh(self) -> bool:
        """检查是否需要刷新账号池"""
        if not self._last_refresh:
            return True
        elapsed = (datetime.now(timezone.utc) - self._last_refresh).total_seconds()
        return elapsed > self._refresh_interval
    
    async def get_pool_stats(self) -> dict:
        """获取账号池统计信息"""
        total = len(self._accounts)
        available = sum(1 for a in self._accounts.values() if a.is_available)
        throttled = sum(
            1 for a in self._accounts.values() 
            if a.quota_info and a.quota_info.is_throttled
        )
        
        avg_health = 0.0
        if self._accounts:
            avg_health = sum(a.health_score for a in self._accounts.values()) / total
        
        return {
            "total_accounts": total,
            "available_accounts": available,
            "throttled_accounts": throttled,
            "unavailable_accounts": total - available,
            "average_health_score": round(avg_health, 2),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
        }
