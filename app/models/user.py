"""
用户模型
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(30), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # API Key（用于调用转发接口）
    api_key = Column(String(100), unique=True, index=True, nullable=True)
    
    # 积分余额 - 默认 0，不能为空
    points_balance = Column(Float, default=0.0, nullable=False)
    
    # Token 配额（备用字段）- 默认 0
    total_quota = Column(Float, default=0.0, nullable=False)
    used_quota = Column(Float, default=0.0, nullable=False)
    
    # 状态 - 默认激活
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # 限速配置 (requests per minute) - 默认 60
    rate_limit = Column(Integer, default=60, nullable=False)
    
    # 元数据
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    @property
    def remaining_quota(self) -> float:
        """剩余配额"""
        return max(0.0, float(self.total_quota or 0) - float(self.used_quota or 0))
    
    @property
    def quota_usage_percent(self) -> float:
        """配额使用百分比"""
        total = float(self.total_quota or 0)
        if total <= 0:
            return 0.0
        return (float(self.used_quota or 0) / total) * 100
    
    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "email_verified": bool(self.email_verified) if self.email_verified is not None else False,
            "api_key": self.api_key,
            "points_balance": float(self.points_balance or 0),
            "total_quota": float(self.total_quota or 0),
            "used_quota": float(self.used_quota or 0),
            "remaining_quota": self.remaining_quota,
            "quota_usage_percent": self.quota_usage_percent,
            "is_active": bool(self.is_active) if self.is_active is not None else True,
            "is_admin": bool(self.is_admin) if self.is_admin is not None else False,
            "rate_limit": int(self.rate_limit or 60),
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
