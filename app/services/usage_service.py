from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.usage import UsageLog
from app.models.user import User
from app.models.upstream import UpstreamKey


class UsageService:
    """使用统计服务"""

    @staticmethod
    async def create_usage_log(
        db: AsyncSession,
        user_id: int,
        upstream_key_id: Optional[int],
        request_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        points_consumed: int = 0,
        response_status: int = 200,
        response_time_ms: int = 0,
        error_message: str = None
    ) -> UsageLog:
        """创建使用日志"""
        total_tokens = prompt_tokens + completion_tokens
        
        log = UsageLog(
            user_id=user_id,
            upstream_key_id=upstream_key_id,
            request_id=request_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            points_consumed=points_consumed,
            response_status=response_status,
            response_time_ms=response_time_ms,
            error_message=error_message
        )
        db.add(log)
        await db.flush()
        return log

    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> dict:
        """获取使用统计"""
        query = select(
            func.count(UsageLog.id).label("total_requests"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.points_consumed).label("total_points"),
            func.avg(UsageLog.response_time_ms).label("avg_response_time")
        )
        
        if user_id:
            query = query.where(UsageLog.user_id == user_id)
        
        if start_time:
            query = query.where(UsageLog.created_at >= start_time)
        
        if end_time:
            query = query.where(UsageLog.created_at <= end_time)
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            "total_requests": row.total_requests or 0,
            "total_tokens": row.total_tokens or 0,
            "total_points": row.total_points or 0,
            "total_cost": 0.0,  # 添加缺失的字段
            "avg_response_time": round(row.avg_response_time or 0, 2)
        }

    @staticmethod
    async def get_daily_stats(
        db: AsyncSession,
        days: int = 7,
        user_id: Optional[int] = None
    ) -> List[dict]:
        """获取每日统计"""
        from sqlalchemy import cast, Date
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = select(
            cast(UsageLog.created_at, Date).label("date"),
            func.count(UsageLog.id).label("requests"),
            func.sum(UsageLog.total_tokens).label("tokens"),
            func.sum(UsageLog.points_consumed).label("points")
        ).where(
            UsageLog.created_at >= start_date
        ).group_by(
            cast(UsageLog.created_at, Date)
        ).order_by("date")
        
        if user_id:
            query = query.where(UsageLog.user_id == user_id)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "date": str(row.date),
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "points": row.points or 0
            }
            for row in rows
        ]

    @staticmethod
    async def get_model_stats(
        db: AsyncSession,
        user_id: Optional[int] = None,
        days: int = 7
    ) -> List[dict]:
        """获取模型使用统计"""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = select(
            UsageLog.model,
            func.count(UsageLog.id).label("requests"),
            func.sum(UsageLog.total_tokens).label("tokens"),
            func.sum(UsageLog.points_consumed).label("points"),
            func.avg(UsageLog.response_time_ms).label("avg_response_time")
        ).where(
            UsageLog.created_at >= start_date
        ).group_by(
            UsageLog.model
        )
        
        if user_id:
            query = query.where(UsageLog.user_id == user_id)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "model": row.model,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "points": row.points or 0,
                "avg_response_time": round(row.avg_response_time or 0, 2)
            }
            for row in rows
        ]

    @staticmethod
    async def get_recent_logs(
        db: AsyncSession,
        user_id: Optional[int] = None,
        limit: int = 50
    ) -> List[UsageLog]:
        """获取最近的日志"""
        query = select(UsageLog).order_by(UsageLog.created_at.desc()).limit(limit)
        
        if user_id:
            query = query.where(UsageLog.user_id == user_id)
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> dict:
        """获取仪表盘统计数据"""
        # 总用户数
        user_count_result = await db.execute(select(func.count(User.id)))
        total_users = user_count_result.scalar()
        
        # 上游 Key 统计
        key_count_result = await db.execute(select(func.count(UpstreamKey.id)))
        total_keys = key_count_result.scalar()
        
        active_key_result = await db.execute(
            select(func.count(UpstreamKey.id)).where(
                and_(UpstreamKey.is_active == True, UpstreamKey.is_exhausted == False)
            )
        )
        active_keys = active_key_result.scalar()
        
        # 今日统计
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_stats = await UsageService.get_usage_stats(db, start_time=today_start)
        
        # 系统健康度
        health_score = (active_keys / max(total_keys, 1)) * 100
        
        # 平均响应时间
        avg_time_result = await db.execute(
            select(func.avg(UsageLog.response_time_ms)).where(
                UsageLog.created_at >= today_start
            )
        )
        avg_response_time = round(avg_time_result.scalar() or 0, 2)
        
        # 最近日志
        recent_logs = await UsageService.get_recent_logs(db, limit=10)
        
        return {
            "total_users": total_users,
            "total_upstream_keys": total_keys,
            "active_upstream_keys": active_keys,
            "today_requests": today_stats["total_requests"],
            "today_tokens": today_stats["total_tokens"],
            "today_points": today_stats["total_points"],
            "today_cost": 0.0,  # 添加缺失的字段
            "system_health": round(health_score, 1),
            "avg_response_time": avg_response_time,
            "recent_logs": recent_logs
        }
