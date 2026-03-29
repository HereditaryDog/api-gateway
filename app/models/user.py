from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    
    # API Key（用于调用转发接口）
    api_key = Column(String(100), unique=True, index=True)
    
    # 积分余额
    points_balance = Column(Float, default=0.0, nullable=False)
    
    # Token 配额（备用字段）
    total_quota = Column(Float, default=1000.0, nullable=False)
    used_quota = Column(Float, default=0.0, nullable=False)
    
    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # 限速配置 (requests per minute)
    rate_limit = Column(Integer, default=60, nullable=False)
    
    # 元数据
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True))
    
    @property
    def remaining_quota(self) -> float:
        """剩余配额"""
        return max(0, self.total_quota - self.used_quota)
    
    @property
    def quota_usage_percent(self) -> float:
        """配额使用百分比"""
        if self.total_quota <= 0:
            return 100.0
        return (self.used_quota / self.total_quota) * 100
