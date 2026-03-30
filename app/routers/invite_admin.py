from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.auth import InviteCodeBatchResponse, InviteCodeCreateRequest, InviteCodeResponse
from app.services.registration_service import RegistrationService

router = APIRouter(prefix="/admin/invite-codes", tags=["邀请码管理"])


@router.get("", response_model=List[InviteCodeResponse])
async def list_invite_codes(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await RegistrationService.list_invite_codes(db)


@router.post("", response_model=InviteCodeBatchResponse)
async def create_invite_codes(
    data: InviteCodeCreateRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    codes = await RegistrationService.create_invite_codes(
        db,
        quantity=data.quantity,
        created_by_user_id=current_user.id,
        expires_in_days=data.expires_in_days,
        remark=data.remark,
    )
    return {"codes": codes}
