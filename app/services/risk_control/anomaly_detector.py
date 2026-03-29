"""
异常检测服务
检测账号异常行为，触发告警
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio


class AnomalyType(Enum):
    """异常类型"""
    HIGH_ERROR_RATE = "high_error_rate"           # 高错误率
    HIGH_LATENCY = "high_latency"                 # 高延迟
    QUOTA_EXHAUSTED = "quota_exhausted"          # 配额耗尽
    RATE_LIMITED = "rate_limited"                 # 被限流
    CONSECUTIVE_ERRORS = "consecutive_errors"    # 连续错误
    SUSPICIOUS_PATTERN = "suspicious_pattern"    # 可疑模式


@dataclass
class AnomalyEvent:
    """异常事件"""
    key_id: int
    provider_id: int
    anomaly_type: AnomalyType
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    details: dict
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "key_id": self.key_id,
            "provider_id": self.provider_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AnomalyDetector:
    """
    异常检测器
    
    检测指标:
    1. 连续错误数 >= 5
    2. 响应时间 > 10s
    3. 错误率 > 50%
    4. 配额使用速度异常
    """
    
    # 阈值配置
    THRESHOLDS = {
        "consecutive_errors": 5,
        "high_latency_ms": 10000,
        "high_error_rate": 0.5,
        "quota_warning_percent": 80,
        "quota_critical_percent": 95,
    }
    
    def __init__(self):
        self._handlers: List[Callable[[AnomalyEvent], None]] = []
        self._events: List[AnomalyEvent] = []
        self._max_events = 1000
    
    def add_handler(self, handler: Callable[[AnomalyEvent], None]):
        """添加异常处理器"""
        self._handlers.append(handler)
    
    def detect_consecutive_errors(
        self,
        key_id: int,
        provider_id: int,
        consecutive_errors: int
    ) -> Optional[AnomalyEvent]:
        """检测连续错误"""
        if consecutive_errors >= self.THRESHOLDS["consecutive_errors"]:
            event = AnomalyEvent(
                key_id=key_id,
                provider_id=provider_id,
                anomaly_type=AnomalyType.CONSECUTIVE_ERRORS,
                severity="high" if consecutive_errors >= 10 else "medium",
                message=f"Account has {consecutive_errors} consecutive errors",
                details={"consecutive_errors": consecutive_errors},
                timestamp=datetime.now(timezone.utc),
            )
            self._emit(event)
            return event
        return None
    
    def detect_high_latency(
        self,
        key_id: int,
        provider_id: int,
        response_time_ms: float,
        avg_response_time_ms: float
    ) -> Optional[AnomalyEvent]:
        """检测高延迟"""
        if response_time_ms > self.THRESHOLDS["high_latency_ms"]:
            event = AnomalyEvent(
                key_id=key_id,
                provider_id=provider_id,
                anomaly_type=AnomalyType.HIGH_LATENCY,
                severity="medium",
                message=f"High latency detected: {response_time_ms}ms",
                details={
                    "response_time_ms": response_time_ms,
                    "avg_response_time_ms": avg_response_time_ms,
                },
                timestamp=datetime.now(timezone.utc),
            )
            self._emit(event)
            return event
        return None
    
    def detect_high_error_rate(
        self,
        key_id: int,
        provider_id: int,
        success_rate: float,
        total_requests: int
    ) -> Optional[AnomalyEvent]:
        """检测高错误率"""
        # 至少要有10个请求才检测
        if total_requests < 10:
            return None
        
        if success_rate < self.THRESHOLDS["high_error_rate"]:
            event = AnomalyEvent(
                key_id=key_id,
                provider_id=provider_id,
                anomaly_type=AnomalyType.HIGH_ERROR_RATE,
                severity="high" if success_rate < 0.3 else "medium",
                message=f"High error rate detected: {(1-success_rate)*100:.1f}%",
                details={
                    "success_rate": success_rate,
                    "error_rate": 1 - success_rate,
                    "total_requests": total_requests,
                },
                timestamp=datetime.now(timezone.utc),
            )
            self._emit(event)
            return event
        return None
    
    def detect_quota_exhausted(
        self,
        key_id: int,
        provider_id: int,
        window_type: str,
        used: int,
        limit: int
    ) -> Optional[AnomalyEvent]:
        """检测配额耗尽"""
        usage_percent = (used / limit * 100) if limit > 0 else 0
        
        if usage_percent >= self.THRESHOLDS["quota_critical_percent"]:
            event = AnomalyEvent(
                key_id=key_id,
                provider_id=provider_id,
                anomaly_type=AnomalyType.QUOTA_EXHAUSTED,
                severity="critical",
                message=f"Quota nearly exhausted: {usage_percent:.1f}%",
                details={
                    "window_type": window_type,
                    "used": used,
                    "limit": limit,
                    "usage_percent": usage_percent,
                },
                timestamp=datetime.now(timezone.utc),
            )
            self._emit(event)
            return event
        elif usage_percent >= self.THRESHOLDS["quota_warning_percent"]:
            event = AnomalyEvent(
                key_id=key_id,
                provider_id=provider_id,
                anomaly_type=AnomalyType.QUOTA_EXHAUSTED,
                severity="low",
                message=f"Quota warning: {usage_percent:.1f}%",
                details={
                    "window_type": window_type,
                    "used": used,
                    "limit": limit,
                    "usage_percent": usage_percent,
                },
                timestamp=datetime.now(timezone.utc),
            )
            self._emit(event)
            return event
        return None
    
    def detect_rate_limited(
        self,
        key_id: int,
        provider_id: int,
        throttle_until: datetime
    ) -> Optional[AnomalyEvent]:
        """检测被限流"""
        event = AnomalyEvent(
            key_id=key_id,
            provider_id=provider_id,
            anomaly_type=AnomalyType.RATE_LIMITED,
            severity="medium",
            message=f"Account rate limited until {throttle_until.isoformat()}",
            details={"throttle_until": throttle_until.isoformat()},
            timestamp=datetime.now(timezone.utc),
        )
        self._emit(event)
        return event
    
    def _emit(self, event: AnomalyEvent):
        """触发异常事件"""
        self._events.append(event)
        
        # 限制事件数量
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        
        # 调用处理器
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                print(f"Error in anomaly handler: {e}")
    
    def get_recent_events(
        self,
        key_id: int = None,
        severity: str = None,
        limit: int = 100
    ) -> List[AnomalyEvent]:
        """获取最近的异常事件"""
        events = self._events
        
        if key_id:
            events = [e for e in events if e.key_id == key_id]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        return events[-limit:]
    
    def get_stats(self) -> dict:
        """获取异常统计"""
        if not self._events:
            return {
                "total_events": 0,
                "events_by_type": {},
                "events_by_severity": {},
            }
        
        events_by_type = {}
        events_by_severity = {}
        
        for event in self._events:
            type_name = event.anomaly_type.value
            events_by_type[type_name] = events_by_type.get(type_name, 0) + 1
            events_by_severity[event.severity] = events_by_severity.get(event.severity, 0) + 1
        
        return {
            "total_events": len(self._events),
            "events_by_type": events_by_type,
            "events_by_severity": events_by_severity,
        }


# 全局异常检测器实例
_global_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """获取全局异常检测器"""
    global _global_detector
    if _global_detector is None:
        _global_detector = AnomalyDetector()
    return _global_detector
