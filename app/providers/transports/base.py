from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.providers.contracts.interfaces import ProviderTransport


def is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500


@dataclass
class TransportResponse:
    status_code: int
    json_data: Dict[str, Any]
    text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)


class ProviderTransportError(Exception):
    """传输层异常。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        retryable: Optional[bool] = None,
        body: str = "",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = is_retryable_status(status_code) if retryable is None else retryable
        self.body = body


__all__ = [
    "ProviderTransport",
    "ProviderTransportError",
    "TransportResponse",
    "is_retryable_status",
]
