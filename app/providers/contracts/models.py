from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional


STANDARD_REQUEST_FIELDS = {
    "model",
    "messages",
    "stream",
    "temperature",
    "max_tokens",
}


class ProviderError(Exception):
    """统一的 Provider 异常。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        retryable: bool = False,
        upstream_key_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.upstream_key_id = upstream_key_id
        self.payload = payload or {}

    def to_payload(self) -> Dict[str, Any]:
        return {
            "error": {
                "message": self.message,
                "type": "upstream_error",
                "code": self.status_code,
            }
        }


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_ms: tuple[int, int, int] = (200, 400, 800)
    jitter_ms: int = 100


@dataclass
class ModelDescriptor:
    id: str
    upstream_id: str
    owned_by: str

    def to_openai_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "object": "model",
            "created": 1677649963,
            "owned_by": self.owned_by,
        }


@dataclass
class ProviderContext:
    provider_record: Any
    request_id: str
    external_model: str = ""
    actual_model: str = ""
    mapped_model: str = ""
    api_key: Optional[str] = None
    upstream_key_id: Optional[int] = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def clone_with_account(self, *, api_key: str, upstream_key_id: int) -> "ProviderContext":
        return replace(
            self,
            api_key=api_key,
            upstream_key_id=upstream_key_id,
        )


@dataclass
class ChatRequest:
    model: str
    messages: List[Dict[str, Any]]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_http_body(cls, body: Dict[str, Any]) -> "ChatRequest":
        extra = {
            key: value
            for key, value in body.items()
            if key not in STANDARD_REQUEST_FIELDS
        }
        return cls(
            model=body.get("model", ""),
            messages=body.get("messages", []),
            stream=bool(body.get("stream", False)),
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens"),
            extra=extra,
        )


@dataclass
class ChatResponse:
    data: Dict[str, Any]
    usage: Dict[str, Any] = field(default_factory=dict)
    upstream_key_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatChunk:
    data: Optional[Dict[str, Any]] = None
    is_done: bool = False
    is_error: bool = False
    is_valid: bool = False
    token_delta: int = 0
    upstream_key_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        if self.is_done:
            return "data: [DONE]\n\n"
        payload = self.data or {
            "error": {
                "message": "Unknown provider stream error",
                "type": "upstream_error",
                "code": 502,
            }
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass
class ProviderResult:
    payload: Optional[Dict[str, Any]] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    upstream_key_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
