from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List

from app.providers.contracts.models import (
    ChatChunk,
    ChatRequest,
    ChatResponse,
    ModelDescriptor,
    ProviderContext,
)


class ProviderAdapter(ABC):
    """统一 Provider 适配器接口。"""

    @abstractmethod
    async def list_models(self, ctx: ProviderContext) -> List[ModelDescriptor]:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, ctx: ProviderContext, req: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(
        self,
        ctx: ProviderContext,
        req: ChatRequest,
    ) -> AsyncGenerator[ChatChunk, None]:
        raise NotImplementedError

    @abstractmethod
    def supports(self, capability: str) -> bool:
        raise NotImplementedError


class ProviderTransport(ABC):
    """统一 Provider 传输接口。"""

    @abstractmethod
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        json_body: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        json_body: Dict[str, Any],
        timeout: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError


class ResponseTransformer(ABC):
    """请求/响应转换器接口。"""

    def endpoint(self, ctx: ProviderContext, req: ChatRequest) -> str:
        return "/chat/completions"

    def build_headers(self, ctx: ProviderContext, req: ChatRequest) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if ctx.api_key:
            headers["Authorization"] = f"Bearer {ctx.api_key}"
        return headers

    @abstractmethod
    def build_request(self, ctx: ProviderContext, req: ChatRequest) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def to_chat_response(self, ctx: ProviderContext, payload: Dict[str, Any]) -> ChatResponse:
        raise NotImplementedError

    @abstractmethod
    def to_chat_chunk(self, ctx: ProviderContext, payload: Dict[str, Any]) -> ChatChunk:
        raise NotImplementedError

    @abstractmethod
    def extract_usage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def is_retryable(self, error: Exception) -> bool:
        raise NotImplementedError
