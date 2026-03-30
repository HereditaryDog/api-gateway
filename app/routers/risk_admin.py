from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.risk import SensitiveWordCreate, SensitiveWordResponse, SensitiveWordUpdate
from app.services.risk_control.sensitive_words import get_sensitive_words_service

router = APIRouter(prefix="/risk", tags=["风控管理"])
service = get_sensitive_words_service()


@router.get("/sensitive-words", response_model=List[SensitiveWordResponse])
async def list_sensitive_words(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_words(db)


@router.post("/sensitive-words", response_model=SensitiveWordResponse, status_code=status.HTTP_201_CREATED)
async def create_sensitive_word(
    data: SensitiveWordCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing_words = await service.list_words(db)
    if any(word.term.lower() == data.term.lower() for word in existing_words):
        raise HTTPException(status_code=400, detail="Sensitive word already exists")
    return await service.create_word(db, data)


@router.put("/sensitive-words/{word_id}", response_model=SensitiveWordResponse)
async def update_sensitive_word(
    word_id: int,
    data: SensitiveWordUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    word = await service.get_word(db, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Sensitive word not found")
    return await service.update_word(db, word, data)


@router.delete("/sensitive-words/{word_id}")
async def delete_sensitive_word(
    word_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    word = await service.get_word(db, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Sensitive word not found")
    await service.delete_word(db, word)
    return {"message": "Sensitive word deleted successfully"}
