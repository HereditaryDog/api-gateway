"""
Token 计费策略 - 按 Token 数量计费
适用于 OpenAI、Anthropic 等标准厂商
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.services.billing.base import BillingStrategy, BillingContext
from app.models.user import User
from app.models.usage import PointsLog
from app.models.billing import RequestLog, BillingMode

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
    "doubao-lite": 1,
    "doubao-pro": 2,
    "doubao-vision": 3,
}

DEFAULT_POINTS_COST = 2  # 默认每 1000 tokens 消耗积分


class TokenBasedBillingStrategy(BillingStrategy):
    """基于 Token 的计费策略"""
    
    def __init__(self, db: AsyncSession = None):
        super().__init__(db)
        self.points_cost = POINTS_COST
        self.default_cost = DEFAULT_POINTS_COST
    
    def _extract_model_name(self, model: str) -> str:
        """提取模型名（去掉 provider 前缀）"""
        if '/' in model:
            return model.split('/', 1)[1]
        return model
    
    def _get_cost_per_1k_tokens(self, model: str) -> int:
        """获取每千 tokens 的积分成本"""
        model_name = self._extract_model_name(model).lower()
        
        for key, value in self.points_cost.items():
            if key in model_name:
                return value
        
        return self.default_cost
    
    async def calculate_cost(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算成本（积分）
        
        Args:
            model: 模型名称
            tokens: Token 数量
        
        Returns:
            积分数量
        """
        cost_per_k = self._get_cost_per_1k_tokens(model)
        points = max(1, int(tokens / 1000 * cost_per_k))
        return Decimal(str(points))
    
    async def calculate_price(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算售价（Token 计费模式下，售价=成本）
        
        Args:
            model: 模型名称
            tokens: Token 数量
        
        Returns:
            积分数量（与成本相同）
        """
        return await self.calculate_cost(model, tokens, **kwargs)
    
    async def pre_charge(self, user_id: int, amount: Decimal) -> bool:
        """
        预扣积分
        
        Args:
            user_id: 用户 ID
            amount: 要扣除的积分数
        
        Returns:
            True 表示扣减成功，False 表示余额不足
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        points = int(amount)
        
        # 原子扣减：UPDATE ... WHERE balance >= amount
        result = await self.db.execute(
            text(
                "UPDATE users SET points_balance = points_balance - :points "
                "WHERE id = :uid AND points_balance >= :points"
            ),
            {"points": points, "uid": user_id}
        )
        await self.db.commit()
        return result.rowcount == 1
    
    async def confirm_charge(self, user_id: int, log_id: int, actual_amount: Decimal = None):
        """
        确认扣费并写积分日志
        
        Args:
            user_id: 用户 ID
            log_id: 日志 ID（在 Token 计费中不使用，但为了接口统一保留）
            actual_amount: 实际扣费金额（如果与预扣不同）
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        # 在 Token 计费中，余额已在 pre_charge 中扣减
        # 这里可以添加额外的日志记录如果需要
        pass
    
    async def rollback(self, user_id: int, amount: Decimal):
        """
        回滚预扣的积分
        
        Args:
            user_id: 用户 ID
            amount: 要回滚的积分数
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        points = int(amount)
        
        await self.db.execute(
            text("UPDATE users SET points_balance = points_balance + :points WHERE id = :uid"),
            {"points": points, "uid": user_id}
        )
        await self.db.commit()
    
    async def record_usage(
        self,
        user_id: int,
        upstream_key_id: Optional[int],
        request_id: str,
        model: str,
        cost_amount: Decimal,
        charge_amount: Decimal,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        response_time_ms: int = 0,
        status: str = "success",
        error_message: str = None
    ) -> int:
        """
        记录使用日志（Token 计费模式）
        
        Returns:
            日志 ID
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        # 创建积分日志
        points_log = PointsLog(
            user_id=user_id,
            amount=-int(cost_amount),  # 扣除为负
            log_type="consume",
            related_log_id=None,
            model=model,
            remark=f"Request: {request_id}, Tokens: {prompt_tokens + completion_tokens}",
        )
        self.db.add(points_log)
        await self.db.flush()
        
        # 创建请求日志
        request_log = RequestLog(
            user_id=user_id,
            upstream_key_id=upstream_key_id,
            request_id=request_id,
            model=model,
            provider_type=None,  # 由调用方填充
            billing_mode=BillingMode.TOKEN,
            cost_amount=cost_amount,
            charge_amount=charge_amount,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            response_time_ms=response_time_ms,
            status=status,
            error_message=error_message,
        )
        self.db.add(request_log)
        await self.db.flush()
        
        return request_log.id
