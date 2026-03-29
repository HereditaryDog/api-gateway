from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.user import User
from app.services.user_service import UserService
from app.services.points_service import PointsService
from app.schemas.user import UserCreate, UserResponse, UserUpdate

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
    return await UserService.list_users(db, skip=skip, limit=limit)


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
