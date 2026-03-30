from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class UsageLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    upstream_key_id: Optional[int]
    request_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    response_status: Optional[int]
    response_time_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime

class QuotaLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    change_type: str
    amount: float
    balance_before: float
    balance_after: float
    description: Optional[str]
    created_at: datetime

class DashboardStats(BaseModel):
    # 总体统计
    total_users: int
    total_upstream_keys: int
    active_upstream_keys: int
    
    # 今日统计
    today_requests: int
    today_tokens: float
    today_cost: float
    
    # 系统健康度
    system_health: float
    avg_response_time: float
    
    # 最近使用
    recent_logs: List[UsageLogResponse]


class ModelUsageStats(BaseModel):
    model: str
    total_requests: int
    total_tokens: int
    avg_response_time: float


class DailyUsageStats(BaseModel):
    date: str
    requests: int
    tokens: float
    cost: float
