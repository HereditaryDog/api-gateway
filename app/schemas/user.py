"""
用户相关的 Pydantic 模型
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    remark: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    total_quota: float = Field(default=0.0, description="配额，单位：千tokens")
    is_admin: bool = False


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    total_quota: Optional[float] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None
    rate_limit: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    api_key: str
    points_balance: float = 0.0
    total_quota: float = 0.0
    used_quota: float = 0.0
    remaining_quota: float = 0.0
    quota_usage_percent: float = 0.0
    is_active: bool = True
    is_admin: bool = False
    rate_limit: int = 60
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    
    @field_validator('points_balance', 'total_quota', 'used_quota', 'remaining_quota', 'quota_usage_percent', mode='before')
    @classmethod
    def ensure_float(cls, v):
        """确保数值字段为 float 类型"""
        if v is None:
            return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    
    @field_validator('rate_limit', mode='before')
    @classmethod
    def ensure_int(cls, v):
        """确保整数字段为 int 类型"""
        if v is None:
            return 60
        try:
            return int(v)
        except (TypeError, ValueError):
            return 60
    
    @field_validator('is_active', 'is_admin', mode='before')
    @classmethod
    def ensure_bool(cls, v):
        """确保布尔字段为 bool 类型"""
        if v is None:
            return False
        return bool(v)
    
    class Config:
        from_attributes = True
        # 允许从 ORM 模型自动转换
        populate_by_name = True


class UserQuotaInfo(BaseModel):
    total_quota: float = 0.0
    used_quota: float = 0.0
    remaining_quota: float = 0.0
    usage_percent: float = 0.0


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
