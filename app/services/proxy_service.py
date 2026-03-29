"""
API 请求转发服务
支持 provider/model 格式，双阶段积分计费
"""
import time
import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.upstream import UpstreamKey
from app.services.upstream_service import UpstreamService
from app.services.points_service import PointsService
from app.core.encryption import decrypt_data
from app.providers import (
    get_provider_from_model, 
    is_provider_allowed, 
    create_provider,
    normalize_model_name,
    OpenAICompatProvider
)
from app.core.config import get_settings

settings = get_settings()


class ProxyService:
    """API 请求转发服务"""

    def __init__(self):
        self._init_models()

    def _init_models(self):
        """初始化支持的模型列表"""
        self.SUPPORTED_MODELS = [
            # OpenAI
            "openai/gpt-4",
            "openai/gpt-4-turbo",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-3.5-turbo",
            # Anthropic
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
            # DeepSeek
            "deepseek/deepseek-chat",
            "deepseek/deepseek-coder",
            "deepseek/deepseek-reasoner",
            # Gemini
            "gemini/gemini-pro",
            "gemini/gemini-flash",
            # 兼容旧格式
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "deepseek-chat",
        ]

    def _get_request_id(self) -> str:
        """生成请求 ID"""
        return f"req-{uuid.uuid4().hex[:16]}"

    def _estimate_tokens(self, messages: list) -> int:
        """估算 token 数量"""
        if not messages:
            return 0
        
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text", "")
                        total_chars += len(text)
        
        return max(1, total_chars // 4)

    async def _call_provider_with_retry(
        self,
        db: AsyncSession,
        provider_name: str,
        actual_model: str,
        messages: list,
        stream: bool = False,
        **kwargs
    ) -> AsyncGenerator[tuple[str, Optional[UpstreamKey], int], None]:
        """
        调用厂商 API，支持失败重试
        
        Yields:
            (chunk_content, upstream_key, key_id) 或 (error_message, None, None)
        """
        max_retries = settings.MAX_RETRIES
        excluded_key_ids = []
        
        # 首先查找匹配的 provider（在循环外查询一次）
        from sqlalchemy import select
        from app.models.upstream import UpstreamProvider
        
        # 首先尝试通过名称或类型匹配
        provider_result = await db.execute(
            select(UpstreamProvider).where(
                UpstreamProvider.name.ilike(f"%{provider_name}%") |
                (UpstreamProvider.provider_type == provider_name)
            )
        )
        provider_record = provider_result.scalar_one_or_none()
        
        # 如果未找到，尝试通过 model_mapping 匹配
        if not provider_record:
            all_providers_result = await db.execute(select(UpstreamProvider))
            all_providers = all_providers_result.scalars().all()
            for p in all_providers:
                if p.model_mapping and actual_model in p.model_mapping:
                    provider_record = p
                    break
        
        if not provider_record:
            yield (f"Provider not found: {provider_name}", None, None)
            return
        
        # 应用 model_mapping 转换模型名称
        mapped_model = provider_record.model_mapping.get(actual_model, actual_model) if provider_record.model_mapping else actual_model
        
        for attempt in range(max_retries):
            # 获取可用的 keys
            keys = await UpstreamService.list_keys(
                db, 
                provider_id=provider_record.id,
                available_only=True,
                limit=100
            )
            
            if excluded_key_ids:
                keys = [k for k in keys if k.id not in excluded_key_ids]
            
            if not keys:
                yield ("No available upstream key for this provider", None, None)
                return
            
            # 简单选择第一个 key
            upstream_key = keys[0]
            decrypted_key = decrypt_data(upstream_key.encrypted_key)
            if not decrypted_key:
                yield ("Failed to decrypt API key", None, None)
                return
            
            # 创建 provider 实例
            if provider_record and provider_record.base_url:
                # 使用数据库中的自定义配置
                provider = OpenAICompatProvider(api_key=decrypted_key, base_url=provider_record.base_url)
            else:
                # 使用白名单中的标准配置
                provider = create_provider(provider_name, decrypted_key)
            
            if not provider:
                yield (f"Unsupported provider: {provider_name}", None, None)
                return
            
            try:
                if stream:
                    # 流式响应
                    total_tokens = 0
                    async for chunk in provider.chat_completion_stream(
                        model=mapped_model,
                        messages=messages,
                        temperature=kwargs.get("temperature", 0.7),
                        max_tokens=kwargs.get("max_tokens", 2000)
                    ):
                        yield (chunk, upstream_key, upstream_key.id)
                        # 简单估算 token
                        if chunk.startswith("data: "):
                            try:
                                data = json.loads(chunk[6:])
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if delta.get("content"):
                                        total_tokens += len(delta["content"]) // 4
                            except:
                                pass
                    return
                else:
                    # 非流式响应
                    response = await provider.chat_completion(
                        model=mapped_model,
                        messages=messages,
                        temperature=kwargs.get("temperature", 0.7),
                        max_tokens=kwargs.get("max_tokens", 2000)
                    )
                    
                    # 计算实际使用的 tokens
                    usage = response.get("usage", {})
                    total_tokens = usage.get("total_tokens", 0)
                    
                    yield (json.dumps(response), upstream_key, upstream_key.id)
                    return
                    
            except Exception as e:
                # 记录失败的 key，尝试下一个
                excluded_key_ids.append(upstream_key.id)
                if attempt < max_retries - 1:
                    continue
                else:
                    yield (f"All upstream keys failed: {str(e)}", None, None)
                    return

    async def chat_completions(
        self,
        db: AsyncSession,
        user: User,
        request: Request,
        body: Dict[str, Any]
    ) -> StreamingResponse:
        """
        处理聊天完成请求
        
        流程：
        1. 规范化模型名称
        2. 预扣积分
        3. 转发请求到上游
        4. 确认扣费或回滚
        """
        request_id = self._get_request_id()
        start_time = time.time()
        
        # 获取并规范化模型名称
        raw_model = body.get("model", "openai/gpt-3.5-turbo")
        model = normalize_model_name(raw_model)
        
        # 解析 provider 和实际模型名
        provider_name, actual_model = get_provider_from_model(model)
        
        # SSRF 安全检查 - 检查白名单或数据库中的自定义 provider
        if not is_provider_allowed(provider_name):
            # 检查是否是数据库中的自定义 provider
            # 通过 model_mapping 查找匹配的 provider
            from sqlalchemy import select
            from app.models.upstream import UpstreamProvider
            
            # 获取所有自定义 provider
            result = await db.execute(select(UpstreamProvider))
            all_providers = result.scalars().all()
            
            custom_provider = None
            for p in all_providers:
                if p.model_mapping and actual_model in p.model_mapping:
                    custom_provider = p
                    provider_name = p.name  # 更新 provider_name
                    break
            
            if not custom_provider:
                # 再尝试通过名称匹配
                result = await db.execute(
                    select(UpstreamProvider).where(UpstreamProvider.name.ilike(f"%{provider_name}%"))
                )
                custom_provider = result.scalar_one_or_none()
            
            if not custom_provider:
                raise HTTPException(status_code=400, detail=f"Provider not allowed: {provider_name}")
        
        # 获取消息
        messages = body.get("messages", [])
        
        # 估算 tokens 和所需积分
        estimated_tokens = self._estimate_tokens(messages) + 2000  # 预留响应 tokens
        points_needed = PointsService.calculate_points_cost(model, estimated_tokens)
        
        # 预扣积分
        has_enough = await PointsService.pre_deduct(db, user.id, points_needed)
        if not has_enough:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Required: {points_needed}, please recharge."
            )
        
        is_stream = body.get("stream", False)
        
        async def response_generator():
            """响应生成器"""
            actual_tokens = 0
            upstream_key_used = None
            key_id = None
            error_occurred = False
            error_message = ""
            
            async for chunk, upstream_key, k_id in self._call_provider_with_retry(
                db, provider_name, actual_model, messages, is_stream,
                temperature=body.get("temperature"),
                max_tokens=body.get("max_tokens")
            ):
                if upstream_key is None:
                    # 发生错误
                    error_occurred = True
                    error_message = chunk
                    yield json.dumps({
                        "error": {
                            "message": chunk,
                            "type": "upstream_error",
                            "code": 503
                        }
                    }).encode()
                    return
                
                upstream_key_used = upstream_key
                key_id = k_id
                
                if is_stream:
                    yield chunk.encode()
                    # 估算 token
                    try:
                        if chunk.startswith("data: "):
                            data = json.loads(chunk[6:])
                            if "choices" in data:
                                delta = data["choices"][0].get("delta", {})
                                if delta.get("content"):
                                    actual_tokens += len(delta["content"]) // 4
                    except:
                        pass
                else:
                    # 非流式，解析实际用量
                    try:
                        resp_data = json.loads(chunk)
                        usage = resp_data.get("usage", {})
                        actual_tokens = usage.get("total_tokens", estimated_tokens)
                        yield chunk.encode()
                    except:
                        actual_tokens = estimated_tokens
                        yield chunk.encode()
            
            # 计算实际消耗的积分
            response_time = int((time.time() - start_time) * 1000)
            actual_points = PointsService.calculate_points_cost(model, max(actual_tokens, 1))
            
            # 处理积分和日志
            if error_occurred:
                # 回滚积分
                await PointsService.rollback(db, user.id, points_needed)
            else:
                # 计算差额
                points_diff = points_needed - actual_points
                
                if points_diff > 0:
                    # 预扣多了，回滚差额
                    await PointsService.rollback(db, user.id, points_diff)
                elif points_diff < 0:
                    # 预扣少了，需要再扣（这种情况很少见）
                    await PointsService.pre_deduct(db, user.id, abs(points_diff))
                
                # 确认扣费并记录日志
                await PointsService.confirm_deduct(
                    db, user.id, actual_points, "consume",
                    related_log_id=None, model=model,
                    remark=f"Request: {request_id}, Tokens: {actual_tokens}"
                )
                
                # 更新上游 Key 统计
                if upstream_key_used:
                    await UpstreamService.increment_usage(db, upstream_key_used, actual_tokens)
        
        return StreamingResponse(
            response_generator(),
            media_type="text/event-stream" if is_stream else "application/json",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    async def models(self, db: AsyncSession) -> Dict[str, Any]:
        """获取支持的模型列表"""
        return {
            "object": "list",
            "data": [
                {
                    "id": model_id,
                    "object": "model",
                    "created": 1677649963,
                    "owned_by": model_id.split('/')[0] if '/' in model_id else "openai"
                }
                for model_id in self.SUPPORTED_MODELS
            ]
        }
