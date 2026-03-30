from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.user import UserResponse


class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeResponse(BaseModel):
    message: str
    expires_in_seconds: int
    debug_code: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    phone: str = Field(..., min_length=6, max_length=30)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    email_code: str = Field(..., min_length=4, max_length=16)
    invite_code: str = Field(..., min_length=4, max_length=64)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()

    @field_validator("invite_code")
    @classmethod
    def normalize_invite_code(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class InviteCodeCreateRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=100)
    expires_in_days: Optional[int] = Field(default=7, ge=1, le=365)
    remark: Optional[str] = None


class InviteCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    is_active: bool
    used_by_user_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class InviteCodeBatchResponse(BaseModel):
    codes: List[InviteCodeResponse]
