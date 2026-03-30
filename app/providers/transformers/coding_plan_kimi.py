from __future__ import annotations

from app.providers.contracts import ChatRequest, ProviderContext
from app.providers.transformers.base import BaseOpenAITransformer


class CodingPlanKimiTransformer(BaseOpenAITransformer):
    """KimiCode Coding Plan 转换器。"""

    def build_request(self, ctx: ProviderContext, req: ChatRequest) -> dict:
        payload = super().build_request(ctx, req)
        prompt_cache_key = payload.get("prompt_cache_key") or req.extra.get("prompt_cache_key")
        if not prompt_cache_key:
            prompt_cache_key = f"gateway:{ctx.provider_record.id}:{ctx.request_id}"
        payload["prompt_cache_key"] = prompt_cache_key

        if "thinking" in req.extra:
            payload["thinking"] = req.extra["thinking"]
        return payload
