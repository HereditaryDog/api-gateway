from __future__ import annotations

import json
from typing import AsyncGenerator, List, Optional

from app.providers.contracts import (
    ChatChunk,
    ChatRequest,
    ChatResponse,
    ModelDescriptor,
    ProviderAdapter,
    ProviderContext,
    ResponseTransformer,
)
from app.providers.contracts.models import ProviderError
from app.providers.transports import HTTPXTransport


class OpenAICompatAdapter(ProviderAdapter):
    """标准 OpenAI 兼容适配器。"""

    def __init__(self, *, transport: Optional[HTTPXTransport] = None, transformer: ResponseTransformer):
        self.transport = transport or HTTPXTransport()
        self.transformer = transformer
        self._capabilities = {"chat", "stream_chat", "list_models"}

    def supports(self, capability: str) -> bool:
        return capability in self._capabilities

    async def list_models(self, ctx: ProviderContext) -> List[ModelDescriptor]:
        provider_type = getattr(ctx.provider_record.provider_type, "value", "custom")
        mapping = ctx.provider_record.model_mapping or {}
        descriptors = []
        for external_model, upstream_model in mapping.items():
            descriptors.append(
                ModelDescriptor(
                    id=external_model,
                    upstream_id=upstream_model,
                    owned_by=provider_type,
                )
            )
        return descriptors

    async def chat(self, ctx: ProviderContext, req: ChatRequest) -> ChatResponse:
        payload = self.transformer.build_request(ctx, req)
        headers = self.transformer.build_headers(ctx, req)
        endpoint = self.transformer.endpoint(ctx, req)
        response = await self.transport.request(
            "POST",
            f"{ctx.provider_record.base_url.rstrip('/')}{endpoint}",
            headers=headers,
            json_body=payload,
        )
        chat_response = self.transformer.to_chat_response(ctx, response.json_data)
        chat_response.upstream_key_id = ctx.upstream_key_id
        return chat_response

    async def stream_chat(
        self,
        ctx: ProviderContext,
        req: ChatRequest,
    ) -> AsyncGenerator[ChatChunk, None]:
        payload = self.transformer.build_request(ctx, req)
        headers = self.transformer.build_headers(ctx, req)
        endpoint = self.transformer.endpoint(ctx, req)

        done_emitted = False
        async for line in self.transport.stream(
            "POST",
            f"{ctx.provider_record.base_url.rstrip('/')}{endpoint}",
            headers=headers,
            json_body=payload,
        ):
            if not line or not line.startswith("data: "):
                continue

            raw = line[6:].strip()
            if raw == "[DONE]":
                yield ChatChunk(is_done=True, upstream_key_id=ctx.upstream_key_id)
                done_emitted = True
                break

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProviderError("Upstream returned invalid stream JSON", status_code=502, retryable=False) from exc

            chunk = self.transformer.to_chat_chunk(ctx, payload)
            chunk.upstream_key_id = ctx.upstream_key_id
            yield chunk

        if not done_emitted:
            yield ChatChunk(is_done=True, upstream_key_id=ctx.upstream_key_id)
