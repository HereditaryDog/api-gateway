from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.services.upstream_service import UpstreamService
from app.schemas.upstream import (
    ProviderCreate, ProviderResponse, ProviderUpdate,
    UpstreamKeyCreate, UpstreamKeyResponse, UpstreamKeyUpdate
)

router = APIRouter(prefix="/upstream", tags=["上游管理"])


# ========== 提供商管理 ==========

@router.get("/providers", response_model=List[ProviderResponse])
async def list_providers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """列出所有提供商"""
    return await UpstreamService.list_providers(db, skip=skip, limit=limit)


@router.post("/providers", response_model=ProviderResponse)
async def create_provider(
    data: ProviderCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建提供商"""
    return await UpstreamService.create_provider(db, data)


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取提供商详情"""
    provider = await UpstreamService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    return provider


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新提供商"""
    provider = await UpstreamService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    return await UpstreamService.update_provider(db, provider, data)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """删除提供商"""
    provider = await UpstreamService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    await UpstreamService.delete_provider(db, provider)
    return {"message": "Provider deleted successfully"}


# ========== API Key 管理 ==========

@router.get("/keys", response_model=List[UpstreamKeyResponse])
async def list_keys(
    provider_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """列出所有上游 Key"""
    return await UpstreamService.list_keys(
        db, provider_id=provider_id, skip=skip, limit=limit
    )


@router.post("/keys", response_model=UpstreamKeyResponse)
async def create_key(
    data: UpstreamKeyCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建上游 Key"""
    # 检查 provider 是否存在
    provider = await UpstreamService.get_provider(db, data.provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider not found"
        )
    return await UpstreamService.create_key(db, data)


@router.get("/keys/{key_id}", response_model=UpstreamKeyResponse)
async def get_key(
    key_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取 Key 详情"""
    key = await UpstreamService.get_key(db, key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found"
        )
    return key


@router.put("/keys/{key_id}", response_model=UpstreamKeyResponse)
async def update_key(
    key_id: int,
    data: UpstreamKeyUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新 Key"""
    key = await UpstreamService.get_key(db, key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found"
        )
    return await UpstreamService.update_key(db, key, data)


@router.post("/keys/{key_id}/toggle")
async def toggle_key(
    key_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """切换 Key 状态"""
    key = await UpstreamService.get_key(db, key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found"
        )
    
    key.is_active = not key.is_active
    await db.flush()
    
    return {
        "message": f"Key {'activated' if key.is_active else 'deactivated'}",
        "is_active": key.is_active
    }
