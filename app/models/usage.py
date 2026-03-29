from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON, ForeignKey, Enum
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class UsageLog(Base):
    """使用日志表"""
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 用户和上游信息
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    upstream_key_id = Column(Integer, ForeignKey("upstream_keys.id"))
    
    # 请求信息
    request_id = Column(String(64), index=True)
    model = Column(String(100), index=True)  # 格式: provider/model
    
    # Token 使用量
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 消耗的积分
    points_consumed = Column(Integer, default=0)
    
    # 请求元数据
    response_status = Column(Integer)
    response_time_ms = Column(Integer)  # 响应时间(毫秒)
    
    # 错误信息
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PointsLogType(str, enum.Enum):
    """积分日志类型"""
    CONSUME = "consume"      # 消费
    RECHARGE = "recharge"    # 充值
    REFUND = "refund"        # 退款
    BONUS = "bonus"          # 奖励


class PointsLog(Base):
    """积分变更日志"""
    __tablename__ = "points_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # 变更金额（正数为增加，负数为减少）
    amount = Column(Integer, nullable=False)
    
    # 变更类型
    log_type = Column(String(20), nullable=False)
    
    # 关联信息
    related_log_id = Column(Integer, ForeignKey("usage_logs.id"))
    model = Column(String(100))  # 使用的模型
    remark = Column(Text)        # 备注
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
