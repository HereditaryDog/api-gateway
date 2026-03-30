from __future__ import annotations

from typing import Any, Dict

from app.providers.contracts import ChatChunk, ChatRequest, ChatResponse, ProviderContext, ResponseTransformer
from app.providers.contracts.models import ProviderError
from app.providers.transports.base import ProviderTransportError


def _sanitize_reasoning(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "choices" not in payload:
        return payload

    for choice in payload.get("choices", []):
        message = choice.get("message")
        if isinstance(message, dict):
            message.pop("reasoning_content", None)
        delta = choice.get("delta")
        if isinstance(delta, dict):
            delta.pop("reasoning_content", None)
    return payload


class BaseOpenAITransformer(ResponseTransformer):
    """默认的 OpenAI 兼容转换器。"""

    def build_request(self, ctx: ProviderContext, req: ChatRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": ctx.mapped_model or req.model,
            "messages": req.messages,
            "stream": req.stream,
        }
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        payload.update(req.extra)
        return payload

    def to_chat_response(self, ctx: ProviderContext, payload: Dict[str, Any]) -> ChatResponse:
        if not isinstance(payload, dict) or "choices" not in payload:
            raise ProviderError("Upstream returned invalid chat response", status_code=502, retryable=False)

        normalized = dict(payload)
        normalized.setdefault("id", f"chatcmpl-{ctx.request_id}")
        normalized.setdefault("object", "chat.completion")
        normalized.setdefault("model", ctx.external_model or ctx.mapped_model or ctx.actual_model)
        normalized = _sanitize_reasoning(normalized)
        return ChatResponse(
            data=normalized,
            usage=self.extract_usage(normalized),
            upstream_key_id=ctx.upstream_key_id,
            metadata={},
        )

    def to_chat_chunk(self, ctx: ProviderContext, payload: Dict[str, Any]) -> ChatChunk:
        if not isinstance(payload, dict):
            raise ProviderError("Upstream returned invalid stream chunk", status_code=502, retryable=False)

        if "error" in payload:
            error = payload["error"] or {}
            return ChatChunk(
                data=payload,
                is_error=True,
                upstream_key_id=ctx.upstream_key_id,
                metadata={"error_message": error.get("message", "Unknown upstream error")},
            )

        normalized = dict(payload)
        normalized.setdefault("id", f"chatcmpl-{ctx.request_id}")
        normalized.setdefault("object", "chat.completion.chunk")
        normalized.setdefault("model", ctx.external_model or ctx.mapped_model or ctx.actual_model)
        normalized = _sanitize_reasoning(normalized)

        token_delta = 0
        is_valid = False
        choices = normalized.get("choices") or []
        if choices:
            delta = choices[0].get("delta", {})
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str) and content:
                    token_delta = max(1, len(content) // 4)
                is_valid = bool(content or delta.get("role") or delta.get("tool_calls"))

        return ChatChunk(
            data=normalized,
            is_valid=is_valid,
            token_delta=token_delta,
            upstream_key_id=ctx.upstream_key_id,
        )

    def extract_usage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        usage = payload.get("usage", {})
        return usage if isinstance(usage, dict) else {}

    def is_retryable(self, error: Exception) -> bool:
        if isinstance(error, ProviderTransportError):
            return error.retryable
        if isinstance(error, ProviderError):
            return error.retryable
        return False
