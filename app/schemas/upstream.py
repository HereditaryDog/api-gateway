from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.upstream import ProviderType


class ProviderBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=50)
    provider_type: ProviderType
    base_url: str = Field(..., description="API 基础 URL")
    model_mapping: Dict[str, str] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0, le=1000)
    remark: Optional[str] = None


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = None
    base_url: Optional[str] = None
    model_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    remark: Optional[str] = None


class ProviderResponse(ProviderBase):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class UpstreamKeyBase(BaseModel):
    provider_id: int
    weight: int = Field(default=100, ge=1, le=1000)
    priority: int = Field(default=100, ge=0, le=1000)
    rpm_limit: int = Field(default=60, ge=1)
    tpm_limit: int = Field(default=100000, ge=1)
    remark: Optional[str] = None


class UpstreamKeyCreate(UpstreamKeyBase):
    api_key: str = Field(..., description="上游 API Key (明文，会被加密存储)")


class UpstreamKeyUpdate(BaseModel):
    weight: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    is_exhausted: Optional[bool] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    remark: Optional[str] = None


class UpstreamKeyResponse(UpstreamKeyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    encrypted_key: str = Field(..., description="加密后的Key (仅显示前8位)")
    is_active: bool
    is_exhausted: bool
    total_requests: int
    total_tokens: float
    health_score: float
    created_at: datetime
    last_used_at: Optional[datetime] = None
