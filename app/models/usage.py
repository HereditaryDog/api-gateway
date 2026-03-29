"""
使用日志和积分日志模型
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from app.core.database import Base


class UsageLog(Base):
    """使用日志表"""
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 用户和上游信息
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    upstream_key_id = Column(Integer, ForeignKey("upstream_keys.id"), nullable=True)
    
    # 请求信息
    request_id = Column(String(64), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)  # 格式: provider/model
    
    # Token 使用量
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    
    # 消耗的积分
    points_consumed = Column(Integer, default=0, nullable=False)
    
    # 请求元数据
    response_status = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)  # 响应时间(毫秒)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "upstream_key_id": self.upstream_key_id,
            "request_id": self.request_id,
            "model": self.model,
            "prompt_tokens": int(self.prompt_tokens or 0),
            "completion_tokens": int(self.completion_tokens or 0),
            "total_tokens": int(self.total_tokens or 0),
            "points_consumed": int(self.points_consumed or 0),
            "response_status": self.response_status,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PointsLogType(str, enum.Enum):
    """积分日志类型"""
    CONSUME = "consume"      # 消费
    RECHARGE = "recharge"    # 充值
    REFUND = "refund"        # 退款
    BONUS = "bonus"          # 奖励


class PointsLog(Base):
    """积分变更日志"""
    __tablename__ = "points_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 变更金额（正数为增加，负数为减少）
    amount = Column(Integer, nullable=False)
    
    # 变更类型
    log_type = Column(String(20), nullable=False)
    
    # 关联信息
    related_log_id = Column(Integer, ForeignKey("usage_logs.id"), nullable=True)
    model = Column(String(100), nullable=True)  # 使用的模型
    remark = Column(Text, nullable=True)        # 备注
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": int(self.amount or 0),
            "log_type": self.log_type,
            "related_log_id": self.related_log_id,
            "model": self.model,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
