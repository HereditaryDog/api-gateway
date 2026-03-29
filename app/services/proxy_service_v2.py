"""
API 请求转发服务 V2
支持多种计费模式和 Coding Plan 风控
"""
import time
import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional
from decimal import Decimal
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.upstream import UpstreamKey, UpstreamProvider
from app.services.upstream_service import UpstreamService
from app.services.billing import (
    BillingStrategyFactory,
    BillingContext,
    TokenBasedBillingStrategy,
    RequestBasedBillingStrategy,
)
from app.services.billing.base import BillingContext
from app.providers import (
    get_provider_from_model,
    is_provider_allowed,
    create_provider,
    normalize_model_name,
    OpenAICompatProvider,
)
from app.providers.adapters import CodingPlanAdapter, CodingPlanAdapterWithFailover
from app.core.config import get_settings

settings = get_settings()


class ProxyServiceV2:
    """
    API 请求转发服务 V2
    
    新特性:
    1. 支持多种计费模式 (Token/Request)
    2. Coding Plan 专用适配器
    3. 集成风控系统
    4. 更精确的计费
    """

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
            # Coding Plan (示例)
            "coding-plan/gpt-4",
            "coding-plan/gpt-3.5-turbo",
            # 兼容旧格式
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "deepseek-chat",
            # 火山引擎 (Volcengine)
            "volcengine/doubao-lite",
            "volcengine/doubao-pro",
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

    async def _get_provider_record(
        self,
        db: AsyncSession,
        provider_name: str,
        actual_model: str
    ) -> Optional[UpstreamProvider]:
        """
        获取 Provider 记录
        
        查找逻辑:
        1. 通过 model_mapping 查找
        2. 通过 provider_type 查找
        3. 通过名称查找
        """
        from sqlalchemy import select

        # 获取所有自定义 provider
        result = await db.execute(select(UpstreamProvider))
        all_providers = result.scalars().all()

        # 先通过 model_mapping 查找
        for p in all_providers:
            if p.model_mapping and actual_model in p.model_mapping:
                return p
            # 检查反向映射
            if p.model_mapping:
                for mapped_key, mapped_value in p.model_mapping.items():
                    if mapped_value == actual_model or actual_model in mapped_value:
                        return p

        # 通过 provider_type 查找
        for p in all_providers:
            if p.provider_type and p.provider_type.value == provider_name:
                return p

        # 通过名称查找
        for p in all_providers:
            if provider_name.lower() in p.name.lower():
                return p

        return None

    async def _create_provider_instance(
        self,
        db: AsyncSession,
        provider_record: UpstreamProvider,
        actual_model: str
    ):
        """
        创建 Provider 实例
        
        根据 adapter_type 选择不同的适配器
        """
        adapter_type = provider_record.adapter_type or "standard"

        if adapter_type == "coding_plan":
            # 使用 Coding Plan 专用适配器
            return CodingPlanAdapter(
                db=db,
                provider_id=provider_record.id,
                provider_name=provider_record.provider_type.value if provider_record.provider_type else "coding_plan",
                base_url=provider_record.base_url,
            )
        elif adapter_type == "coding_plan_with_failover":
            return CodingPlanAdapterWithFailover(
                db=db,
                provider_id=provider_record.id,
                provider_name=provider_record.provider_type.value if provider_record.provider_type else "coding_plan",
                base_url=provider_record.base_url,
            )
        else:
            # 标准适配器（需要获取 API Key）
            keys = await UpstreamService.list_keys(
                db,
                provider_id=provider_record.id,
                available_only=True,
                limit=1
            )

            if not keys:
                return None

            from app.core.encryption import decrypt_data
            decrypted_key = decrypt_data(keys[0].encrypted_key)

            if not decrypted_key:
                return None

            return OpenAICompatProvider(
                api_key=decrypted_key,
                base_url=provider_record.base_url
            )

    async def _call_provider_with_retry(
        self,
        db: AsyncSession,
        provider_record: UpstreamProvider,
        actual_model: str,
        messages: list,
        stream: bool = False,
        **kwargs
    ) -> AsyncGenerator[tuple[str, Optional[UpstreamKey], int], None]:
        """
        调用厂商 API，支持失败重试
        """
        max_retries = settings.MAX_RETRIES
        excluded_key_ids = []

        if not provider_record:
            yield ("Provider not found", None, None)
            return

        # 应用 model_mapping 转换模型名称
        mapped_model = provider_record.model_mapping.get(actual_model, actual_model) if provider_record.model_mapping else actual_model

        for attempt in range(max_retries):
            try:
                # 创建 provider 实例
                provider = await self._create_provider_instance(
                    db, provider_record, actual_model
                )

                if not provider:
                    yield ("No available upstream key for this provider", None, None)
                    return

                # 对于 Coding Plan 适配器，不需要额外处理 key
                if isinstance(provider, (CodingPlanAdapter, CodingPlanAdapterWithFailover)):
                    if stream:
                        total_tokens = 0
                        async for chunk in provider.chat_completion_stream(
                            model=mapped_model,
                            messages=messages,
                            temperature=kwargs.get("temperature", 0.7),
                            max_tokens=kwargs.get("max_tokens", 2000)
                        ):
                            yield (chunk, None, None)
                            # 估算 token
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
                        response = await provider.chat_completion(
                            model=mapped_model,
                            messages=messages,
                            temperature=kwargs.get("temperature", 0.7),
                            max_tokens=kwargs.get("max_tokens", 2000)
                        )
                        usage = response.get("usage", {})
                        total_tokens = usage.get("total_tokens", 0)
                        yield (json.dumps(response), None, None)
                        return
                else:
                    # 标准适配器处理
                    if stream:
                        total_tokens = 0
                        async for chunk in provider.chat_completion_stream(
                            model=mapped_model,
                            messages=messages,
                            temperature=kwargs.get("temperature", 0.7),
                            max_tokens=kwargs.get("max_tokens", 2000)
                        ):
                            yield (chunk, None, None)
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
                        response = await provider.chat_completion(
                            model=mapped_model,
                            messages=messages,
                            temperature=kwargs.get("temperature", 0.7),
                            max_tokens=kwargs.get("max_tokens", 2000)
                        )
                        usage = response.get("usage", {})
                        total_tokens = usage.get("total_tokens", 0)
                        yield (json.dumps(response), None, None)
                        return

            except Exception as e:
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

        流程:
        1. 规范化模型名称
        2. 获取计费策略
        3. 预扣费
        4. 转发请求到上游
        5. 确认扣费或回滚
        """
        request_id = self._get_request_id()
        start_time = time.time()

        # 创建计费上下文
        billing_ctx = BillingContext()
        billing_ctx.request_id = request_id
        billing_ctx.user_id = user.id
        billing_ctx.start_time = start_time

        # 获取并规范化模型名称
        raw_model = body.get("model", "openai/gpt-3.5-turbo")
        model = normalize_model_name(raw_model)
        billing_ctx.model = model

        # 解析 provider 和实际模型名
        provider_name, actual_model = get_provider_from_model(model)

        # 查找 Provider 记录
        provider_record = await self._get_provider_record(db, provider_name, actual_model)

        if not provider_record:
            raise HTTPException(status_code=400, detail=f"Provider not found: {provider_name}")

        billing_ctx.provider_type = provider_record.provider_type.value if provider_record.provider_type else provider_name

        # 获取计费策略
        strategy, _ = await BillingStrategyFactory.get_strategy_for_model(db, model)
        strategy.db = db

        billing_ctx.billing_mode = "token" if isinstance(strategy, TokenBasedBillingStrategy) else "request"

        # 获取消息
        messages = body.get("messages", [])

        # 估算 Token 数
        estimated_tokens = self._estimate_tokens(messages) + 2000

        # 计算预估费用
        estimated_cost = await strategy.calculate_cost(model, estimated_tokens)
        estimated_price = await strategy.calculate_price(model, estimated_tokens)

        billing_ctx.estimated_cost = estimated_cost
        billing_ctx.estimated_price = estimated_price

        # 预扣费
        has_enough = await strategy.pre_charge(user.id, estimated_price)
        if not has_enough:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient balance. Required: {float(estimated_price):.6f} CNY"
            )

        billing_ctx.pre_charged = True

        is_stream = body.get("stream", False)

        async def response_generator():
            """响应生成器"""
            actual_tokens = 0
            error_occurred = False
            error_message = ""
            actual_price = estimated_price

            try:
                async for chunk, upstream_key, k_id in self._call_provider_with_retry(
                    db, provider_record, actual_model, messages, is_stream,
                    temperature=body.get("temperature"),
                    max_tokens=body.get("max_tokens")
                ):
                    if upstream_key is None and chunk.startswith('{"error"'):
                        # 发生错误
                        error_occurred = True
                        error_message = chunk
                        yield chunk.encode()
                        return

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

            except Exception as e:
                error_occurred = True
                error_message = str(e)
                yield json.dumps({
                    "error": {
                        "message": str(e),
                        "type": "internal_error",
                        "code": 500
                    }
                }).encode()

            finally:
                # 计算实际费用
                billing_ctx.end_time = time.time()
                response_time_ms = billing_ctx.response_time_ms

                if billing_ctx.billing_mode == "token":
                    # Token 计费：基于实际 Token 数
                    actual_cost = await strategy.calculate_cost(model, max(actual_tokens, 1))
                    actual_price = await strategy.calculate_price(model, max(actual_tokens, 1))
                else:
                    # 请求计费：固定费用
                    actual_cost = estimated_cost
                    actual_price = estimated_price

                billing_ctx.actual_cost = actual_cost
                billing_ctx.actual_price = actual_price
                billing_ctx.total_tokens = actual_tokens

                # 处理计费
                try:
                    if error_occurred:
                        # 回滚费用
                        await strategy.rollback(user.id, estimated_price)
                        billing_ctx.rolled_back = True

                        # 记录失败日志
                        await strategy.record_usage(
                            user_id=user.id,
                            upstream_key_id=None,
                            request_id=request_id,
                            model=model,
                            cost_amount=Decimal("0"),
                            charge_amount=Decimal("0"),
                            prompt_tokens=0,
                            completion_tokens=0,
                            response_time_ms=response_time_ms,
                            status="error",
                            error_message=error_message[:500]
                        )
                    else:
                        # 计算差额
                        if billing_ctx.billing_mode == "token":
                            price_diff = estimated_price - actual_price
                            if price_diff > 0:
                                # 预扣多了，回滚差额
                                await strategy.rollback(user.id, price_diff)

                        # 记录使用日志
                        log_id = await strategy.record_usage(
                            user_id=user.id,
                            upstream_key_id=None,
                            request_id=request_id,
                            model=model,
                            cost_amount=actual_cost,
                            charge_amount=actual_price,
                            prompt_tokens=actual_tokens // 2,  # 估算
                            completion_tokens=actual_tokens // 2,
                            response_time_ms=response_time_ms,
                            status="success"
                        )

                        billing_ctx.log_id = log_id
                        billing_ctx.confirmed = True

                except Exception as e:
                    print(f"Error in billing finalization: {e}")

        return StreamingResponse(
            response_generator(),
            media_type="text/event-stream" if is_stream else "application/json",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
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
