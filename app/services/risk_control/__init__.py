"""
风险控制服务模块
提供多账号池管理、滚动配额追踪、流量整形、异常检测、故障转移等功能
"""

from app.services.risk_control.pool_manager import PoolManager, AccountInfo
from app.services.risk_control.quota_tracker import QuotaTracker
from app.services.risk_control.traffic_shaper import TrafficShaper, RateLimitConfig, GlobalTrafficShaper
from app.services.risk_control.anomaly_detector import (
    AnomalyDetector, 
    AnomalyEvent, 
    AnomalyType,
    get_anomaly_detector
)
from app.services.risk_control.failover import (
    FailoverManager,
    FailoverResult,
    FailoverStrategy,
    CircuitBreaker,
    get_failover_manager
)

__all__ = [
    # 多账号池管理
    "PoolManager",
    "AccountInfo",
    
    # 滚动配额追踪
    "QuotaTracker",
    
    # 流量整形
    "TrafficShaper",
    "RateLimitConfig",
    "GlobalTrafficShaper",
    
    # 异常检测
    "AnomalyDetector",
    "AnomalyEvent",
    "AnomalyType",
    "get_anomaly_detector",
    
    # 故障转移
    "FailoverManager",
    "FailoverResult",
    "FailoverStrategy",
    "CircuitBreaker",
    "get_failover_manager",
]
