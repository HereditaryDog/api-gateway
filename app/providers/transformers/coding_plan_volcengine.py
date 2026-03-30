from __future__ import annotations

from app.providers.contracts import ChatRequest, ProviderContext
from app.providers.transformers.base import BaseOpenAITransformer


class CodingPlanVolcengineTransformer(BaseOpenAITransformer):
    """火山引擎 Coding Plan 转换器。"""

    def build_request(self, ctx: ProviderContext, req: ChatRequest) -> dict:
        payload = super().build_request(ctx, req)
        if "thinking" in req.extra:
            payload["thinking"] = req.extra["thinking"]
        return payload
