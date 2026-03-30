from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin, verify_password, get_password_hash
from app.models.user import User
from app.services.user_service import UserService
from app.services.points_service import PointsService
from app.services.usage_service import UsageService
from app.schemas.user import (
    PasswordChangeRequest,
    ProfileUpdateRequest,
    UserApiKeyResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.get("/me/quota")
async def get_my_quota(current_user: User = Depends(get_current_user)):
    """获取我的配额信息"""
    return {
        "points_balance": current_user.points_balance,
        "total_quota": current_user.total_quota,
        "used_quota": current_user.used_quota,
        "remaining_quota": current_user.remaining_quota,
    }


@router.post("/me/regenerate-api-key")
async def regenerate_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重新生成 API Key"""
    new_key = await UserService.regenerate_api_key(db, current_user)
    return {"api_key": new_key, "message": "API Key regenerated successfully"}


@router.get("/me/api-keys", response_model=List[UserApiKeyResponse])
async def get_my_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的 API Key 列表（当前版本为单密钥模式）。"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = datetime.now(timezone.utc) - timedelta(days=30)
    today_stats = await UsageService.get_usage_stats(
        db,
        user_id=current_user.id,
        start_time=today_start,
    )
    month_stats = await UsageService.get_usage_stats(
        db,
        user_id=current_user.id,
        start_time=month_start,
    )

    api_key = current_user.api_key or ""
    preview = f"{api_key[:16]}..." if api_key else "未生成"
    return [
        UserApiKeyResponse(
            id=f"user-{current_user.id}-primary",
            name="默认密钥",
            api_key=api_key,
            key_preview=preview,
            is_active=current_user.is_active,
            today_cost=float(today_stats.get("total_points", 0.0) or 0.0) * 0.001,
            month_cost=float(month_stats.get("total_points", 0.0) or 0.0) * 0.001,
        )
    ]


@router.put("/me/profile", response_model=UserResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户资料。"""
    existing_user = await UserService.get_user_by_username(db, payload.username)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被占用")

    if payload.email:
        existing_email = await UserService.get_user_by_email_excluding_id(db, str(payload.email), current_user.id)
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被占用")

    if payload.phone:
        existing_phone = await UserService.get_user_by_phone_excluding_id(db, payload.phone, current_user.id)
        if existing_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号已被占用")

    current_user.username = payload.username
    current_user.email = str(payload.email) if payload.email else None
    current_user.phone = payload.phone
    await db.flush()
    return current_user


@router.post("/me/change-password")
async def change_my_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码。"""
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")

    current_user.hashed_password = get_password_hash(payload.new_password)
    await db.flush()
    return {"message": "密码修改成功"}


# ========== 积分相关接口 ==========

@router.get("/me/points")
async def get_my_points(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的积分余额"""
    balance = await PointsService.get_balance(db, current_user.id)
    return {"balance": balance}


@router.get("/me/points/logs")
async def get_my_points_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的积分明细"""
    logs = await PointsService.get_logs(db, current_user.id, limit=limit)
    return logs


# ========== 管理员接口 ==========

@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """列出所有用户 (管理员)"""
    users = await UserService.list_users(db, skip=skip, limit=limit)
    # 转换为 Pydantic 模型
    return [UserResponse.model_validate(user) for user in users]


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建用户 (管理员)"""
    existing = await UserService.get_user_by_username(db, user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    if user_data.email:
        existing_email = await UserService.get_user_by_email(db, str(user_data.email))
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    if user_data.phone:
        existing_phone = await UserService.get_user_by_phone(db, user_data.phone)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already exists"
            )
    return await UserService.create_user(db, user_data)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取用户详情 (管理员)"""
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息 (管理员)"""
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return await UserService.update_user(db, user, user_data)


@router.post("/{user_id}/add-points")
async def add_user_points(
    user_id: int,
    points: int = Query(..., gt=0, description="要增加的积分数"),
    remark: str = Query("", description="充值备注"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """增加用户积分 (管理员)"""
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await PointsService.add_points(
        db, user.id, points, "recharge",
        remark=remark or f"Admin recharge by {current_user.username}"
    )
    
    return {
        "message": f"Added {points} points to user {user.username}",
        "new_balance": user.points_balance + points
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """删除用户 (管理员)"""
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    user.is_active = False
    await db.flush()
    return {"message": "User deleted successfully"}
