"""
按请求计费策略 - 每次请求固定费用
适用于 Coding Plan 等订阅制厂商
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.services.billing.base import BillingStrategy
from app.models.user import User
from app.models.billing import RequestLog, BillingMode, ProviderBillingConfig
from app.models.upstream import UpstreamProvider


class RequestBasedBillingStrategy(BillingStrategy):
    """
    基于请求的计费策略
    
    定价公式:
        售价 = 上游成本 × (1 + 利润率)
    
    目标利润率: 30% - 50%
    """
    
    def __init__(self, db: AsyncSession = None, provider_id: int = None):
        super().__init__(db)
        self.provider_id = provider_id
        self._config: Optional[ProviderBillingConfig] = None
    
    async def _get_config(self) -> Optional[ProviderBillingConfig]:
        """获取计费配置"""
        if self._config:
            return self._config
        
        if not self.db or not self.provider_id:
            return None
        
        result = await self.db.execute(
            select(ProviderBillingConfig).where(
                ProviderBillingConfig.provider_id == self.provider_id
            )
        )
        self._config = result.scalar_one_or_none()
        return self._config
    
    async def calculate_cost(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算成本（每次请求）
        
        Args:
            model: 模型名称
            tokens: 忽略（按请求计费不依赖 Token 数）
            **kwargs: 其他参数
        
        Returns:
            成本金额（人民币）
        """
        config = await self._get_config()
        
        if config and config.cost_per_request:
            return Decimal(str(config.cost_per_request))
        
        # 默认成本（Coding Plan 估算）
        # 假设: 月费 30 元，配额 90000 请求
        # 成本 = 30 / 90000 = 0.000333 元/请求
        return Decimal("0.0004")
    
    async def calculate_price(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算售价（每次请求）
        
        公式: 售价 = 成本 × (1 + 利润率)
        默认利润率: 50%
        
        Args:
            model: 模型名称
            tokens: 忽略（按请求计费不依赖 Token 数）
            **kwargs: 其他参数，可传入 profit_margin 覆盖默认利润率
        
        Returns:
            售价金额（人民币），保留6位小数
        """
        cost = await self.calculate_cost(model, tokens, **kwargs)
        
        # 获取利润率
        profit_margin = kwargs.get('profit_margin', Decimal("0.50"))
        
        # 计算售价
        price = cost * (Decimal("1") + profit_margin)
        
        # 四舍五入到6位小数
        return price.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    
    async def pre_charge(self, user_id: int, amount: Decimal) -> bool:
        """
        预扣费用（从用户积分余额转换为人民币）
        
        转换规则:
            1 积分 = 0.01 元 (1分钱)
        
        Args:
            user_id: 用户 ID
            amount: 要扣除的金额（人民币）
        
        Returns:
            True 表示扣减成功，False 表示余额不足
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        # 将人民币转换为积分 (1 元 = 100 积分)
        points_needed = int(amount * Decimal("100"))
        points_needed = max(1, points_needed)  # 至少扣除 1 积分
        
        # 原子扣减
        result = await self.db.execute(
            text(
                "UPDATE users SET points_balance = points_balance - :points "
                "WHERE id = :uid AND points_balance >= :points"
            ),
            {"points": points_needed, "uid": user_id}
        )
        await self.db.commit()
        return result.rowcount == 1
    
    async def confirm_charge(self, user_id: int, log_id: int, actual_amount: Decimal = None):
        """
        确认扣费
        
        Args:
            user_id: 用户 ID
            log_id: 日志 ID
            actual_amount: 实际扣费金额（如果与预扣不同，需要调整）
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        if actual_amount is None:
            return
        
        # 获取原日志
        result = await self.db.execute(
            select(RequestLog).where(RequestLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        
        if not log:
            return
        
        # 计算差额
        original_amount = Decimal(str(log.charge_amount))
        actual_points = int(actual_amount * Decimal("100"))
        original_points = int(original_amount * Decimal("100"))
        
        points_diff = original_points - actual_points
        
        if points_diff > 0:
            # 预扣多了，回滚差额
            await self.db.execute(
                text("UPDATE users SET points_balance = points_balance + :points WHERE id = :uid"),
                {"points": points_diff, "uid": user_id}
            )
        elif points_diff < 0:
            # 预扣少了，需要再扣
            # 这里不应该发生，因为我们是按请求计费
            pass
        
        # 更新日志
        log.charge_amount = actual_amount
        await self.db.commit()
    
    async def rollback(self, user_id: int, amount: Decimal):
        """
        回滚预扣的费用
        
        Args:
            user_id: 用户 ID
            amount: 要回滚的金额（人民币）
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        # 将人民币转换为积分
        points = int(amount * Decimal("100"))
        
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
        记录使用日志（按请求计费模式）
        
        Returns:
            日志 ID
        """
        if not self.db:
            raise ValueError("Database session not set")
        
        # 获取 provider 类型
        provider_type = None
        if upstream_key_id:
            result = await self.db.execute(
                select(UpstreamProvider, UpstreamKey).join(
                    UpstreamKey, 
                    UpstreamProvider.id == UpstreamKey.provider_id
                ).where(UpstreamKey.id == upstream_key_id)
            )
            row = result.one_or_none()
            if row:
                provider_type = row[0].provider_type.value if row[0].provider_type else None
        
        # 创建请求日志
        request_log = RequestLog(
            user_id=user_id,
            upstream_key_id=upstream_key_id,
            request_id=request_id,
            model=model,
            provider_type=provider_type,
            billing_mode=BillingMode.REQUEST,
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
    
    async def get_pricing_info(self) -> dict:
        """获取定价信息"""
        config = await self._get_config()
        
        cost = await self.calculate_cost("")
        price = await self.calculate_price("")
        
        profit_margin = Decimal("0.50")
        if config and config.price_per_request and config.cost_per_request:
            if float(config.cost_per_request) > 0:
                profit_margin = (Decimal(str(config.price_per_request)) / Decimal(str(config.cost_per_request))) - Decimal("1")
        
        return {
            "billing_mode": "request",
            "cost_per_request": float(cost),
            "price_per_request": float(price),
            "profit_margin": float(profit_margin),
            "currency": "CNY",
        }
