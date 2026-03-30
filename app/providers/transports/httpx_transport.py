from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

import httpx

from app.providers.contracts.interfaces import ProviderTransport
from app.providers.transports.base import ProviderTransportError, TransportResponse, is_retryable_status


class HTTPXTransport(ProviderTransport):
    """基于 httpx 的默认传输层。"""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        json_body: Dict[str, Any],
        timeout: float = 60.0,
    ) -> TransportResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=timeout,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTransportError("Upstream request timed out", status_code=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportError(str(exc), status_code=502, retryable=True) from exc

        if response.status_code >= 400:
            raise ProviderTransportError(
                response.text or f"Upstream request failed with status {response.status_code}",
                status_code=response.status_code,
                retryable=is_retryable_status(response.status_code),
                body=response.text,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderTransportError(
                "Upstream returned invalid JSON",
                status_code=response.status_code,
                retryable=False,
                body=response.text,
            ) from exc

        return TransportResponse(
            status_code=response.status_code,
            json_data=payload,
            text=response.text,
            headers=dict(response.headers),
        )

    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        json_body: Dict[str, Any],
        timeout: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=timeout,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        text = body.decode("utf-8", errors="ignore")
                        raise ProviderTransportError(
                            text or f"Upstream stream failed with status {response.status_code}",
                            status_code=response.status_code,
                            retryable=is_retryable_status(response.status_code),
                            body=text,
                        )
                    async for line in response.aiter_lines():
                        yield line
        except httpx.TimeoutException as exc:
            raise ProviderTransportError("Upstream stream timed out", status_code=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportError(str(exc), status_code=502, retryable=True) from exc
