"""
滚动配额追踪服务
管理 Coding Plan 等订阅制厂商的滚动窗口配额

配额规则（Coding Plan 示例）:
- 5小时窗口: 6000 请求
- 周窗口: 45000 请求
- 月窗口: 90000 请求
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import run_with_sqlite_retry
from app.models.billing import UpstreamKeyQuota


def _ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class QuotaTracker:
    """
    滚动配额追踪器
    
    功能:
    1. 追踪多窗口配额使用（5小时/周/月）
    2. 自动重置过期窗口
    3. 配额预警
    """
    
    # 默认配额配置（Coding Plan）
    DEFAULT_QUOTAS = {
        "window_5h": 6000,
        "window_week": 45000,
        "window_month": 90000,
    }
    
    def __init__(self, db: AsyncSession, key_id: int):
        self.db = db
        self.key_id = key_id
        self._quota: Optional[UpstreamKeyQuota] = None
    
    async def get_or_create_quota(self) -> UpstreamKeyQuota:
        """获取或创建配额记录"""
        if self._quota:
            return self._quota
        
        result = await self.db.execute(
            select(UpstreamKeyQuota).where(
                UpstreamKeyQuota.key_id == self.key_id
            )
        )
        quota = result.scalar_one_or_none()
        
        if not quota:
            # 创建新的配额记录
            now = datetime.now(timezone.utc)
            quota = UpstreamKeyQuota(
                key_id=self.key_id,
                window_5h_used=0,
                window_5h_limit=self.DEFAULT_QUOTAS["window_5h"],
                window_5h_reset_at=now + timedelta(hours=5),
                window_week_used=0,
                window_week_limit=self.DEFAULT_QUOTAS["window_week"],
                window_week_reset_at=now + timedelta(weeks=1),
                window_month_used=0,
                window_month_limit=self.DEFAULT_QUOTAS["window_month"],
                window_month_reset_at=now + timedelta(days=30),
                is_throttled=False,
                consecutive_errors=0,
            )
            self.db.add(quota)
            await run_with_sqlite_retry(self.db.commit, session=self.db)
        
        self._quota = quota
        return quota
    
    async def check_quota(self) -> tuple[bool, dict]:
        """
        检查配额状态
        
        Returns:
            (是否可用, 配额详情)
        """
        quota = await self.get_or_create_quota()
        
        # 重置过期窗口
        await self._reset_expired_windows(quota)
        
        now = datetime.now(timezone.utc)
        window_5h_reset_at = _ensure_utc(quota.window_5h_reset_at)
        window_week_reset_at = _ensure_utc(quota.window_week_reset_at)
        window_month_reset_at = _ensure_utc(quota.window_month_reset_at)
        
        # 检查各窗口配额
        window_5h_available = True
        window_week_available = True
        window_month_available = True
        
        if window_5h_reset_at and now < window_5h_reset_at:
            window_5h_available = quota.window_5h_used < quota.window_5h_limit
        
        if window_week_reset_at and now < window_week_reset_at:
            window_week_available = quota.window_week_used < quota.window_week_limit
        
        if window_month_reset_at and now < window_month_reset_at:
            window_month_available = quota.window_month_used < quota.window_month_limit
        
        is_available = window_5h_available and window_week_available and window_month_available
        
        details = {
            "window_5h": {
                "used": quota.window_5h_used,
                "limit": quota.window_5h_limit,
                "remaining": max(0, quota.window_5h_limit - quota.window_5h_used),
                "reset_at": window_5h_reset_at.isoformat() if window_5h_reset_at else None,
                "available": window_5h_available,
            },
            "window_week": {
                "used": quota.window_week_used,
                "limit": quota.window_week_limit,
                "remaining": max(0, quota.window_week_limit - quota.window_week_used),
                "reset_at": window_week_reset_at.isoformat() if window_week_reset_at else None,
                "available": window_week_available,
            },
            "window_month": {
                "used": quota.window_month_used,
                "limit": quota.window_month_limit,
                "remaining": max(0, quota.window_month_limit - quota.window_month_used),
                "reset_at": window_month_reset_at.isoformat() if window_month_reset_at else None,
                "available": window_month_available,
            },
            "overall_available": is_available,
        }
        
        return is_available, details
    
    async def consume_quota(self, count: int = 1) -> bool:
        """
        消耗配额
        
        Args:
            count: 消耗数量（通常为1）
        
        Returns:
            是否成功消耗
        """
        quota = await self.get_or_create_quota()
        
        # 重置过期窗口
        await self._reset_expired_windows(quota)
        
        # 检查是否可用
        is_available, _ = await self.check_quota()
        if not is_available:
            return False
        
        # 消耗配额
        quota.window_5h_used += count
        quota.window_week_used += count
        quota.window_month_used += count
        
        await run_with_sqlite_retry(self.db.commit, session=self.db)
        return True
    
    async def _reset_expired_windows(self, quota: UpstreamKeyQuota):
        """重置过期窗口"""
        now = datetime.now(timezone.utc)
        window_5h_reset_at = _ensure_utc(quota.window_5h_reset_at)
        window_week_reset_at = _ensure_utc(quota.window_week_reset_at)
        window_month_reset_at = _ensure_utc(quota.window_month_reset_at)
        
        # 检查5小时窗口
        if window_5h_reset_at and now >= window_5h_reset_at:
            quota.window_5h_used = 0
            quota.window_5h_reset_at = now + timedelta(hours=5)
        
        # 检查周窗口
        if window_week_reset_at and now >= window_week_reset_at:
            quota.window_week_used = 0
            quota.window_week_reset_at = now + timedelta(weeks=1)
        
        # 检查月窗口
        if window_month_reset_at and now >= window_month_reset_at:
            quota.window_month_used = 0
            quota.window_month_reset_at = now + timedelta(days=30)
        
        await run_with_sqlite_retry(self.db.commit, session=self.db)
    
    async def get_usage_stats(self) -> dict:
        """获取使用统计"""
        quota = await self.get_or_create_quota()
        
        now = datetime.now(timezone.utc)
        window_5h_reset_at = _ensure_utc(quota.window_5h_reset_at)
        window_week_reset_at = _ensure_utc(quota.window_week_reset_at)
        window_month_reset_at = _ensure_utc(quota.window_month_reset_at)
        
        # 计算剩余配额
        window_5h_remaining = quota.window_5h_limit - quota.window_5h_used
        if window_5h_reset_at and now >= window_5h_reset_at:
            window_5h_remaining = quota.window_5h_limit
        
        window_week_remaining = quota.window_week_limit - quota.window_week_used
        if window_week_reset_at and now >= window_week_reset_at:
            window_week_remaining = quota.window_week_limit
        
        window_month_remaining = quota.window_month_limit - quota.window_month_used
        if window_month_reset_at and now >= window_month_reset_at:
            window_month_remaining = quota.window_month_limit
        
        return {
            "key_id": self.key_id,
            "window_5h": {
                "used": quota.window_5h_used,
                "limit": quota.window_5h_limit,
                "remaining": max(0, window_5h_remaining),
                "usage_percent": round(quota.window_5h_used / quota.window_5h_limit * 100, 2) if quota.window_5h_limit > 0 else 0,
                "reset_at": window_5h_reset_at.isoformat() if window_5h_reset_at else None,
            },
            "window_week": {
                "used": quota.window_week_used,
                "limit": quota.window_week_limit,
                "remaining": max(0, window_week_remaining),
                "usage_percent": round(quota.window_week_used / quota.window_week_limit * 100, 2) if quota.window_week_limit > 0 else 0,
                "reset_at": window_week_reset_at.isoformat() if window_week_reset_at else None,
            },
            "window_month": {
                "used": quota.window_month_used,
                "limit": quota.window_month_limit,
                "remaining": max(0, window_month_remaining),
                "usage_percent": round(quota.window_month_used / quota.window_month_limit * 100, 2) if quota.window_month_limit > 0 else 0,
                "reset_at": window_month_reset_at.isoformat() if window_month_reset_at else None,
            },
        }
    
    async def set_quota_limits(
        self,
        window_5h: int = None,
        window_week: int = None,
        window_month: int = None
    ):
        """
        设置配额限制
        
        Args:
            window_5h: 5小时窗口限制
            window_week: 周窗口限制
            window_month: 月窗口限制
        """
        quota = await self.get_or_create_quota()
        
        if window_5h is not None:
            quota.window_5h_limit = window_5h
        if window_week is not None:
            quota.window_week_limit = window_week
        if window_month is not None:
            quota.window_month_limit = window_month
        
        await run_with_sqlite_retry(self.db.commit, session=self.db)
