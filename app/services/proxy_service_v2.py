"""
API 请求转发服务 V2
支持统一 Provider 接入、Coding Plan 适配器和网关风控。
"""
from __future__ import annotations

import json
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.upstream import UpstreamProvider
from app.models.user import User
from app.providers import ProviderFactory, get_provider_from_model, normalize_model_name
from app.providers.contracts import ChatRequest, ProviderError
from app.services.billing import BillingContext, BillingStrategyFactory, TokenBasedBillingStrategy

settings = get_settings()


class ProxyServiceV2:
    def __init__(self):
        self.provider_factory = ProviderFactory()

    def _get_request_id(self) -> str:
        return f"req-{uuid.uuid4().hex[:16]}"

    def _estimate_tokens(self, messages: list) -> int:
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
                        if isinstance(text, str):
                            total_chars += len(text)
        return max(1, total_chars // 4)

    async def _get_provider_record(
        self,
        db: AsyncSession,
        provider_name: str,
        actual_model: str,
        external_model: Optional[str] = None,
    ) -> Optional[UpstreamProvider]:
        result = await db.execute(
            select(UpstreamProvider)
            .where(UpstreamProvider.is_active == True)
            .order_by(UpstreamProvider.priority.asc(), UpstreamProvider.id.asc())
        )
        providers = result.scalars().all()

        if external_model:
            for provider in providers:
                if provider.model_mapping and external_model in provider.model_mapping:
                    return provider

        for provider in providers:
            if provider.model_mapping and actual_model in provider.model_mapping:
                return provider

        for provider in providers:
            if provider.model_mapping:
                for mapped_key, mapped_value in provider.model_mapping.items():
                    if mapped_value == actual_model or actual_model in str(mapped_value):
                        return provider

        for provider in providers:
            if provider.provider_type and provider.provider_type.value == provider_name:
                return provider

        for provider in providers:
            if provider_name.lower() in provider.name.lower():
                return provider

        return None

    def _provider_error_payload(self, exc: Exception) -> bytes:
        if isinstance(exc, ProviderError):
            payload = exc.to_payload()
        else:
            payload = {
                "error": {
                    "message": str(exc),
                    "type": "internal_error",
                    "code": 500,
                }
            }
        return json.dumps(payload, ensure_ascii=False).encode()

    async def chat_completions(
        self,
        db: AsyncSession,
        user: User,
        request: Request,
        body: Dict[str, Any],
    ) -> StreamingResponse:
        request_id = self._get_request_id()
        start_time = time.time()

        billing_ctx = BillingContext()
        billing_ctx.request_id = request_id
        billing_ctx.user_id = user.id
        billing_ctx.start_time = start_time

        raw_model = body.get("model", "openai/gpt-3.5-turbo")
        model = normalize_model_name(raw_model)
        billing_ctx.model = model

        provider_name, actual_model = get_provider_from_model(model)
        provider_record = await self._get_provider_record(db, provider_name, actual_model, model)
        if not provider_record:
            raise HTTPException(status_code=400, detail=f"Provider not found: {provider_name}")

        billing_ctx.provider_type = provider_record.provider_type.value if provider_record.provider_type else provider_name

        strategy, _ = await BillingStrategyFactory.get_strategy_for_model(db, model)
        strategy.db = db
        billing_ctx.billing_mode = "token" if isinstance(strategy, TokenBasedBillingStrategy) else "request"

        chat_request = ChatRequest.from_http_body(body)
        estimated_tokens = self._estimate_tokens(chat_request.messages) + 2000
        estimated_cost = await strategy.calculate_cost(model, estimated_tokens)
        estimated_price = await strategy.calculate_price(model, estimated_tokens)
        billing_ctx.estimated_cost = estimated_cost
        billing_ctx.estimated_price = estimated_price

        has_enough = await strategy.pre_charge(user.id, estimated_price)
        if not has_enough:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient balance. Required: {float(estimated_price):.6f} CNY",
            )
        billing_ctx.pre_charged = True

        adapter, provider_ctx = await self.provider_factory.create(
            db,
            provider_record,
            external_model=model,
            actual_model=actual_model,
            request_id=request_id,
            require_upstream_key=not (provider_record.adapter_type or "").lower().startswith("coding_plan"),
        )

        async def response_generator():
            actual_tokens = 0
            actual_price = estimated_price
            actual_cost = estimated_cost
            upstream_key_id = provider_ctx.upstream_key_id
            error_occurred = False
            partial_error = False
            error_message = ""
            saw_valid_stream_chunk = False

            try:
                if chat_request.stream:
                    async for chunk in adapter.stream_chat(provider_ctx, chat_request):
                        upstream_key_id = chunk.upstream_key_id or upstream_key_id
                        if chunk.is_valid:
                            saw_valid_stream_chunk = True
                            actual_tokens += chunk.token_delta
                        if chunk.is_error:
                            error_occurred = True
                            partial_error = chunk.metadata.get("status") == "partial_error"
                            error_message = chunk.metadata.get("error_message", "Upstream stream error")
                        yield chunk.to_sse().encode()
                else:
                    response = await adapter.chat(provider_ctx, chat_request)
                    upstream_key_id = response.upstream_key_id or upstream_key_id
                    usage = response.usage or response.data.get("usage", {})
                    actual_tokens = usage.get("total_tokens", estimated_tokens)
                    yield json.dumps(response.data, ensure_ascii=False).encode()
            except Exception as exc:
                error_occurred = True
                partial_error = chat_request.stream and saw_valid_stream_chunk
                error_message = str(exc)
                if isinstance(exc, ProviderError):
                    upstream_key_id = exc.upstream_key_id or upstream_key_id
                if partial_error:
                    payload = json.dumps(
                        {
                            "error": {
                                "message": str(exc),
                                "type": "partial_stream_error",
                                "code": getattr(exc, "status_code", 502),
                            }
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                else:
                    yield self._provider_error_payload(exc)
            finally:
                billing_ctx.end_time = time.time()
                response_time_ms = billing_ctx.response_time_ms

                if error_occurred and not partial_error:
                    actual_cost = Decimal("0")
                    actual_price = Decimal("0")
                    billing_ctx.actual_cost = actual_cost
                    billing_ctx.actual_price = actual_price
                    billing_ctx.total_tokens = actual_tokens
                    try:
                        await strategy.rollback(user.id, estimated_price)
                        billing_ctx.rolled_back = True
                        await strategy.record_usage(
                            user_id=user.id,
                            upstream_key_id=upstream_key_id,
                            request_id=request_id,
                            model=model,
                            cost_amount=Decimal("0"),
                            charge_amount=Decimal("0"),
                            prompt_tokens=0,
                            completion_tokens=0,
                            response_time_ms=response_time_ms,
                            status="error",
                            error_message=error_message[:500],
                        )
                    except Exception as finalize_error:
                        print(f"Error in billing finalization: {finalize_error}")
                    return

                if billing_ctx.billing_mode == "token":
                    actual_cost = await strategy.calculate_cost(model, max(actual_tokens, 1))
                    actual_price = await strategy.calculate_price(model, max(actual_tokens, 1))
                else:
                    actual_cost = estimated_cost
                    actual_price = estimated_price

                billing_ctx.actual_cost = actual_cost
                billing_ctx.actual_price = actual_price
                billing_ctx.total_tokens = actual_tokens

                try:
                    if billing_ctx.billing_mode == "token":
                        price_diff = estimated_price - actual_price
                        if price_diff > 0:
                            await strategy.rollback(user.id, price_diff)

                    log_id = await strategy.record_usage(
                        user_id=user.id,
                        upstream_key_id=upstream_key_id,
                        request_id=request_id,
                        model=model,
                        cost_amount=actual_cost,
                        charge_amount=actual_price,
                        prompt_tokens=actual_tokens // 2,
                        completion_tokens=actual_tokens // 2,
                        response_time_ms=response_time_ms,
                        status="partial_error" if partial_error else "success",
                        error_message=error_message[:500] if partial_error else None,
                    )
                    billing_ctx.log_id = log_id
                    billing_ctx.confirmed = True
                except Exception as finalize_error:
                    print(f"Error in billing finalization: {finalize_error}")

        return StreamingResponse(
            response_generator(),
            media_type="text/event-stream" if chat_request.stream else "application/json",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    async def models(self, db: AsyncSession) -> Dict[str, Any]:
        result = await db.execute(
            select(UpstreamProvider)
            .where(UpstreamProvider.is_active == True)
            .order_by(UpstreamProvider.priority.asc(), UpstreamProvider.id.asc())
        )
        providers = result.scalars().all()

        models: Dict[str, Dict[str, Any]] = {}
        for provider in providers:
            try:
                adapter, ctx = await self.provider_factory.create(
                    db,
                    provider,
                    request_id=self._get_request_id(),
                    require_upstream_key=False,
                )
            except Exception:
                continue

            for descriptor in await adapter.list_models(ctx):
                models.setdefault(descriptor.id, descriptor.to_openai_dict())

        return {
            "object": "list",
            "data": sorted(models.values(), key=lambda item: item["id"]),
        }
