"""
计费策略基类 - 策略模式实现
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


class BillingStrategy(ABC):
    """计费策略抽象基类"""
    
    def __init__(self, db: AsyncSession = None):
        self.db = db
    
    @abstractmethod
    async def calculate_cost(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算成本（上游成本）
        
        Args:
            model: 模型名称
            tokens: Token 数量（如果是 Token 计费模式）
            **kwargs: 其他参数
        
        Returns:
            成本金额
        """
        pass
    
    @abstractmethod
    async def calculate_price(self, model: str, tokens: int = 0, **kwargs) -> Decimal:
        """
        计算售价（向用户收取的费用）
        
        Args:
            model: 模型名称
            tokens: Token 数量（如果是 Token 计费模式）
            **kwargs: 其他参数
        
        Returns:
            售价金额
        """
        pass
    
    @abstractmethod
    async def pre_charge(self, user_id: int, amount: Decimal) -> bool:
        """
        预扣费
        
        Args:
            user_id: 用户 ID
            amount: 要扣除的金额
        
        Returns:
            True 表示扣减成功，False 表示余额不足
        """
        pass
    
    @abstractmethod
    async def confirm_charge(self, user_id: int, log_id: int, actual_amount: Decimal = None):
        """
        确认扣费
        
        Args:
            user_id: 用户 ID
            log_id: 日志 ID
            actual_amount: 实际扣费金额（如果与预扣不同）
        """
        pass
    
    @abstractmethod
    async def rollback(self, user_id: int, amount: Decimal):
        """
        回滚扣费（调用失败时调用）
        
        Args:
            user_id: 用户 ID
            amount: 要回滚的金额
        """
        pass
    
    @abstractmethod
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
        记录使用日志
        
        Returns:
            日志 ID
        """
        pass


class BillingContext:
    """
    计费上下文
    用于在请求处理过程中传递计费相关信息
    """
    
    def __init__(self):
        self.request_id: str = None
        self.user_id: int = None
        self.model: str = None
        self.provider_type: str = None
        self.billing_mode: str = None
        
        # 计费金额
        self.estimated_cost: Decimal = Decimal("0")
        self.estimated_price: Decimal = Decimal("0")
        self.actual_cost: Decimal = Decimal("0")
        self.actual_price: Decimal = Decimal("0")
        
        # Token 用量
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        
        # 状态
        self.pre_charged: bool = False
        self.confirmed: bool = False
        self.rolled_back: bool = False
        self.log_id: int = None
        
        # 时间
        self.start_time: float = None
        self.end_time: float = None
    
    @property
    def response_time_ms(self) -> int:
        """计算响应时间（毫秒）"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "model": self.model,
            "provider_type": self.provider_type,
            "billing_mode": self.billing_mode,
            "estimated_cost": float(self.estimated_cost),
            "estimated_price": float(self.estimated_price),
            "actual_cost": float(self.actual_cost),
            "actual_price": float(self.actual_price),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "pre_charged": self.pre_charged,
            "confirmed": self.confirmed,
            "rolled_back": self.rolled_back,
            "log_id": self.log_id,
            "response_time_ms": self.response_time_ms,
        }
