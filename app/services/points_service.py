"""
积分服务 - 双阶段计费系统

架构说明：
  - 使用积分作为计费单位（1 积分 = 1000 tokens）
  - 双阶段计费：预扣 + 确认/回滚
  - 支持 SQLite（内存缓存 + 异步 flush）和 PostgreSQL（直接写 DB）两种模式

计费流程：
  1. 预扣（pre_deduct）：调用前扣除积分，如果余额不足则拒绝
  2. 调用：转发请求到上游
  3. 确认（confirm）：调用成功后确认扣费，记录日志
  4. 回滚（rollback）：调用失败时回滚预扣的积分
"""

import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.models.user import User
from app.models.usage import PointsLog
from app.core.config import get_settings

settings = get_settings()

# 积分成本配置（每 1000 tokens 消耗的积分）
POINTS_COST = {
    "gpt-4": 30,
    "gpt-4-turbo": 10,
    "gpt-4o": 5,
    "gpt-4o-mini": 1,
    "gpt-3.5-turbo": 1,
    "claude-3-opus": 15,
    "claude-3-sonnet": 3,
    "claude-3-haiku": 1,
    "deepseek-chat": 1,
    "deepseek-coder": 1,
    "deepseek-reasoner": 2,
    "gemini-pro": 1,
    "gemini-flash": 1,
}

DEFAULT_POINTS_COST = 2  # 默认每 1000 tokens 消耗积分


class PointsService:
    """积分服务"""

    @staticmethod
    def calculate_points_cost(model: str, tokens: int) -> int:
        """
        计算积分消耗
        
        Args:
            model: 模型名称
            tokens: token 数量
        
        Returns:
            需要消耗的积分数
        """
        # 提取模型名（去掉 provider 前缀）
        if '/' in model:
            model = model.split('/', 1)[1]
        
        # 获取每千 tokens 的积分成本
        cost_per_k = DEFAULT_POINTS_COST
        for key, value in POINTS_COST.items():
            if key in model.lower():
                cost_per_k = value
                break
        
        # 计算总成本
        return max(1, int(tokens / 1000 * cost_per_k))

    @staticmethod
    async def get_balance(db: AsyncSession, user_id: int) -> int:
        """获取用户积分余额"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return int(user.points_balance) if user and user.points_balance else 0

    @staticmethod
    async def pre_deduct(db: AsyncSession, user_id: int, points: int) -> bool:
        """
        预扣积分
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            points: 要扣除的积分数
        
        Returns:
            True 表示扣减成功，False 表示余额不足
        """
        # 原子扣减：UPDATE ... WHERE balance >= amount
        result = await db.execute(
            text(
                "UPDATE users SET points_balance = points_balance - :points "
                "WHERE id = :uid AND points_balance >= :points"
            ),
            {"points": points, "uid": user_id}
        )
        await db.commit()
        return result.rowcount == 1

    @staticmethod
    async def rollback(db: AsyncSession, user_id: int, points: int):
        """
        回滚预扣的积分（厂商调用失败时调用）
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            points: 要回滚的积分数
        """
        await db.execute(
            text("UPDATE users SET points_balance = points_balance + :points WHERE id = :uid"),
            {"points": points, "uid": user_id}
        )
        await db.commit()

    @staticmethod
    async def confirm_deduct(
        db: AsyncSession,
        user_id: int,
        points: int,
        log_type: str,
        related_log_id: Optional[int] = None,
        model: Optional[str] = None,
        remark: Optional[str] = None,
    ):
        """
        确认扣费并写积分日志
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            points: 扣除的积分数（正值）
            log_type: 日志类型 (consume, recharge, refund)
            related_log_id: 关联的使用日志 ID
            model: 使用的模型
            remark: 备注
        """
        # 余额已在 pre_deduct 中扣减，这里只需写积分日志
        log = PointsLog(
            user_id=user_id,
            amount=-points,  # 扣除为负
            log_type=log_type,
            related_log_id=related_log_id,
            model=model,
            remark=remark,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def add_points(
        db: AsyncSession,
        user_id: int,
        points: int,
        log_type: str,
        related_log_id: Optional[int] = None,
        model: Optional[str] = None,
        remark: Optional[str] = None,
    ):
        """
        增加积分并写积分日志（管理员充值等）
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            points: 要增加的积分数（正值）
            log_type: 日志类型 (consume, recharge, refund)
            related_log_id: 关联的使用日志 ID
            model: 使用的模型
            remark: 备注
        """
        # 增加积分
        await db.execute(
            text("UPDATE users SET points_balance = points_balance + :points WHERE id = :uid"),
            {"points": points, "uid": user_id}
        )
        
        # 写积分日志
        log = PointsLog(
            user_id=user_id,
            amount=points,  # 增加为正
            log_type=log_type,
            related_log_id=related_log_id,
            model=model,
            remark=remark,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """获取积分明细列表"""
        result = await db.execute(
            select(PointsLog)
            .where(PointsLog.user_id == user_id)
            .order_by(PointsLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
