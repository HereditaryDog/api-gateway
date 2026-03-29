"""
计费模型 - 支持多种计费模式
"""
import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Enum, JSON, Numeric, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class BillingMode(str, enum.Enum):
    """计费模式"""
    TOKEN = "token"           # 按 Token 计费
    REQUEST = "request"       # 按请求计费
    SUBSCRIPTION = "subscription"  # 订阅制


class SubscriptionType(str, enum.Enum):
    """订阅类型"""
    CODING_PLAN = "coding_plan"    # Coding Plan 类型
    FIXED_QUOTA = "fixed_quota"    # 固定配额类型


class QuotaWindowType(str, enum.Enum):
    """配额窗口类型"""
    ROLLING_5H = "rolling_5h"         # 5小时滚动窗口
    ROLLING_WEEK = "rolling_week"     # 周滚动窗口
    ROLLING_MONTH = "rolling_month"   # 月滚动窗口
    FIXED = "fixed"                   # 固定配额


class ProviderBillingConfig(Base):
    """厂商计费配置表"""
    __tablename__ = "provider_billing_configs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("upstream_providers.id"), nullable=False, index=True)
    
    # 计费模式
    billing_mode = Column(Enum(BillingMode), nullable=False, default=BillingMode.TOKEN)
    
    # 按请求计费配置
    cost_per_request = Column(Numeric(10, 6), default=0)   # 每次请求成本（上游成本）
    price_per_request = Column(Numeric(10, 6), default=0)  # 每次请求售价
    
    # 订阅制配置（Coding Plan 类型）
    subscription_type = Column(Enum(SubscriptionType), nullable=True)
    quota_window_type = Column(Enum(QuotaWindowType), nullable=True)
    quota_requests = Column(Integer, default=0)            # 配额内请求数
    quota_reset_cron = Column(String(50), nullable=True)   # 配额重置规则
    
    # 风控配置
    enable_risk_control = Column(Boolean, default=False)
    min_qps_limit = Column(Numeric(5, 2), default=0.5)     # 最小 QPS 限制
    max_qps_limit = Column(Numeric(5, 2), default=2.0)     # 最大 QPS 限制
    jitter_ms_min = Column(Integer, default=100)           # 随机延迟最小(ms)
    jitter_ms_max = Column(Integer, default=500)           # 随机延迟最大(ms)
    
    # 元数据
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "billing_mode": self.billing_mode.value if self.billing_mode else None,
            "cost_per_request": float(self.cost_per_request) if self.cost_per_request else 0,
            "price_per_request": float(self.price_per_request) if self.price_per_request else 0,
            "subscription_type": self.subscription_type.value if self.subscription_type else None,
            "quota_window_type": self.quota_window_type.value if self.quota_window_type else None,
            "quota_requests": self.quota_requests,
            "quota_reset_cron": self.quota_reset_cron,
            "enable_risk_control": bool(self.enable_risk_control),
            "min_qps_limit": float(self.min_qps_limit) if self.min_qps_limit else 0.5,
            "max_qps_limit": float(self.max_qps_limit) if self.max_qps_limit else 2.0,
            "jitter_ms_min": self.jitter_ms_min,
            "jitter_ms_max": self.jitter_ms_max,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UpstreamKeyQuota(Base):
    """上游 Key 配额追踪表（多账号配额管理）"""
    __tablename__ = "upstream_key_quotas"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key_id = Column(Integer, ForeignKey("upstream_keys.id"), nullable=False, index=True)
    
    # 滚动窗口配额 - 5小时
    window_5h_used = Column(Integer, default=0)               # 5小时窗口已使用
    window_5h_limit = Column(Integer, default=6000)           # 5小时窗口限额
    window_5h_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # 滚动窗口配额 - 周
    window_week_used = Column(Integer, default=0)             # 周窗口已使用
    window_week_limit = Column(Integer, default=45000)        # 周窗口限额
    window_week_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # 滚动窗口配额 - 月
    window_month_used = Column(Integer, default=0)            # 月窗口已使用
    window_month_limit = Column(Integer, default=90000)       # 月窗口限额
    window_month_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # 状态
    is_throttled = Column(Boolean, default=False)             # 是否被限流
    throttle_until = Column(DateTime(timezone=True), nullable=True)
    consecutive_errors = Column(Integer, default=0)           # 连续错误数
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    
    # 性能指标
    avg_response_time_ms = Column(Float, default=0.0)         # 平均响应时间
    success_rate = Column(Float, default=1.0)                 # 成功率 (0-1)
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    @property
    def health_score(self) -> float:
        """健康度评分 (0-100)"""
        if self.is_throttled and self.throttle_until and self.throttle_until > datetime.now(timezone.utc):
            return 0.0
        
        # 基于成功率和响应时间计算
        score = self.success_rate * 100
        
        # 响应时间惩罚
        if self.avg_response_time_ms > 5000:
            score -= 20
        if self.avg_response_time_ms > 10000:
            score -= 30
        
        # 错误惩罚
        score -= self.consecutive_errors * 10
        
        return max(0.0, min(100.0, score))
    
    @property
    def is_quota_exceeded(self) -> bool:
        """检查是否超出配额"""
        now = datetime.now(timezone.utc)
        
        # 检查5小时窗口
        if self.window_5h_reset_at and now < self.window_5h_reset_at:
            if self.window_5h_used >= self.window_5h_limit:
                return True
        
        # 检查周窗口
        if self.window_week_reset_at and now < self.window_week_reset_at:
            if self.window_week_used >= self.window_week_limit:
                return True
        
        # 检查月窗口
        if self.window_month_reset_at and now < self.window_month_reset_at:
            if self.window_month_used >= self.window_month_limit:
                return True
        
        return False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "key_id": self.key_id,
            "window_5h_used": self.window_5h_used,
            "window_5h_limit": self.window_5h_limit,
            "window_5h_reset_at": self.window_5h_reset_at.isoformat() if self.window_5h_reset_at else None,
            "window_week_used": self.window_week_used,
            "window_week_limit": self.window_week_limit,
            "window_week_reset_at": self.window_week_reset_at.isoformat() if self.window_week_reset_at else None,
            "window_month_used": self.window_month_used,
            "window_month_limit": self.window_month_limit,
            "window_month_reset_at": self.window_month_reset_at.isoformat() if self.window_month_reset_at else None,
            "is_throttled": bool(self.is_throttled),
            "throttle_until": self.throttle_until.isoformat() if self.throttle_until else None,
            "consecutive_errors": self.consecutive_errors,
            "health_score": self.health_score,
            "is_quota_exceeded": self.is_quota_exceeded,
        }


class RequestLog(Base):
    """请求日志表（替代/补充 usage_logs）"""
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    upstream_key_id = Column(Integer, ForeignKey("upstream_keys.id"), nullable=True, index=True)
    
    # 请求信息
    request_id = Column(String(64), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)
    provider_type = Column(String(50), nullable=True, index=True)
    
    # 计费信息
    billing_mode = Column(Enum(BillingMode), nullable=True)
    cost_amount = Column(Numeric(10, 6), default=0)      # 上游成本
    charge_amount = Column(Numeric(10, 6), default=0)    # 向用户收取的费用
    
    # Token 用量（可选，用于统计）
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 性能指标
    response_time_ms = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")       # 'pending', 'success', 'error', 'timeout'
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "upstream_key_id": self.upstream_key_id,
            "request_id": self.request_id,
            "model": self.model,
            "provider_type": self.provider_type,
            "billing_mode": self.billing_mode.value if self.billing_mode else None,
            "cost_amount": float(self.cost_amount) if self.cost_amount else 0,
            "charge_amount": float(self.charge_amount) if self.charge_amount else 0,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "response_time_ms": self.response_time_ms,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
