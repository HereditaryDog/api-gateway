from fastapi import APIRouter, Depends, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.services.user_service import UserService
from app.services.proxy_service_v2 import ProxyServiceV2

router = APIRouter(prefix="/v1")
proxy_service = ProxyServiceV2()


async def get_user_by_api_key(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> "User":
    """通过 API Key 验证用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # 提取 API Key
    if authorization.lower().startswith("bearer "):
        api_key = authorization[7:]
    else:
        api_key = authorization
    
    user = await UserService.get_user_by_api_key(db, api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    
    return user


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    user = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_db)
):
    """OpenAI 格式的聊天完成接口 (V2 - 支持多种计费模式)"""
    body = await request.json()
    
    return await proxy_service.chat_completions(db, user, request, body)


@router.get("/models")
async def list_models(
    user = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_db)
):
    """获取支持的模型列表"""
    return await proxy_service.models(db)


@router.post("/completions")
async def completions(
    request: Request,
    user = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_db)
):
    """兼容旧版 completions 接口 (转发到 chat/completions)"""
    body = await request.json()
    # 将 prompt 转换为 messages 格式
    if "prompt" in body:
        body["messages"] = [{"role": "user", "content": body.pop("prompt")}]
    
    return await proxy_service.chat_completions(db, user, request, body)


@router.post("/embeddings")
async def embeddings(
    request: Request,
    user = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_db)
):
    """嵌入向量接口"""
    # TODO: 实现嵌入接口
    raise HTTPException(status_code=501, detail="Embeddings not yet implemented")
