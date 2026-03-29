from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.user import User
from app.services.usage_service import UsageService
from app.schemas.usage import (
    UsageLogResponse, QuotaLogResponse, 
    DashboardStats, ModelUsageStats, DailyUsageStats
)

router = APIRouter(prefix="/usage", tags=["使用统计"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取仪表盘统计 (管理员)"""
    stats = await UsageService.get_dashboard_stats(db)
    return stats


@router.get("/logs", response_model=List[UsageLogResponse])
async def get_my_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的使用日志"""
    return await UsageService.get_recent_logs(db, user_id=current_user.id, limit=limit)


@router.get("/logs/all", response_model=List[UsageLogResponse])
async def get_all_logs(
    user_id: Optional[int] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取所有使用日志 (管理员)"""
    return await UsageService.get_recent_logs(db, user_id=user_id, limit=limit)


@router.get("/stats/summary")
async def get_usage_summary(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取使用统计摘要"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 管理员可以查看全部，普通用户只能看自己的
    user_id = None if current_user.is_admin else current_user.id
    
    stats = await UsageService.get_usage_stats(
        db, user_id=user_id, start_time=start_date
    )
    
    daily_stats = await UsageService.get_daily_stats(
        db, days=days, user_id=user_id
    )
    
    model_stats = await UsageService.get_model_stats(
        db, days=days, user_id=user_id
    )
    
    return {
        "summary": stats,
        "daily": daily_stats,
        "by_model": model_stats
    }


@router.get("/quota-logs", response_model=List[QuotaLogResponse])
async def get_quota_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取配额变更日志"""
    from sqlalchemy import select
    from app.models.usage import QuotaLog
    
    query = select(QuotaLog).where(
        QuotaLog.user_id == current_user.id
    ).order_by(QuotaLog.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()
