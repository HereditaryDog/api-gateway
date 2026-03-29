from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    remark: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    total_quota: float = Field(default=1000.0, description="配额，单位：千tokens")
    is_admin: bool = False


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    total_quota: Optional[float] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None
    rate_limit: Optional[int] = None


class UserResponse(UserBase):
    id: int
    api_key: str
    total_quota: float = 0.0
    used_quota: float = 0.0
    remaining_quota: float = 0.0
    quota_usage_percent: float = 0.0
    is_active: bool = True
    is_admin: bool = False
    rate_limit: int = 60
    points_balance: float = 0.0
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserQuotaInfo(BaseModel):
    total_quota: float
    used_quota: float
    remaining_quota: float
    usage_percent: float
