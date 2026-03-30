from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SensitiveWordBase(BaseModel):
    term: str = Field(..., min_length=1, max_length=255)
    scope: str = Field(default="completion", min_length=1, max_length=50)
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    remark: Optional[str] = None


class SensitiveWordCreate(SensitiveWordBase):
    pass


class SensitiveWordUpdate(BaseModel):
    term: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scope: Optional[str] = Field(default=None, min_length=1, max_length=50)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=0, le=10000)
    remark: Optional[str] = None


class SensitiveWordResponse(SensitiveWordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
