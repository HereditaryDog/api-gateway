from __future__ import annotations

import json
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.database import AsyncSessionLocal
from app.services.risk_control.identity import RequestIdentityResolver
from app.services.risk_control.limiter import SlidingWindowLimiter, TokenBucketLimiter
from app.services.risk_control.policy import RiskPolicy
from app.services.risk_control.sensitive_words import get_sensitive_words_service


class GatewayRiskMiddleware:
    def __init__(
        self,
        app,
        *,
        policy: RiskPolicy | None = None,
        session_maker=AsyncSessionLocal,
        identity_resolver: RequestIdentityResolver | None = None,
        sensitive_words_service=None,
    ):
        self.app = app
        self.policy = policy or RiskPolicy()
        self.session_maker = session_maker
        self.identity_resolver = identity_resolver or RequestIdentityResolver()
        self.sensitive_words_service = sensitive_words_service or get_sensitive_words_service()
        self.global_limiter = TokenBucketLimiter(self.policy.global_qps, self.policy.global_burst)
        self.ip_limiter = SlidingWindowLimiter(window_seconds=60)
        self.user_limiter = SlidingWindowLimiter(window_seconds=60)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = scope["path"]
        method = scope["method"].upper()

        if self.policy.is_exempt(path):
            await self.app(scope, receive, send)
            return

        if not await self.global_limiter.allow():
            await self._json_error(429, "global_rate_limited", "Global request rate exceeded", scope, receive, send)
            return

        client_ip = self.identity_resolver.get_client_ip(request)
        ip_limit = self.policy.auth_ip_requests_per_minute if self.policy.is_auth_path(path) else self.policy.ip_requests_per_minute
        if not await self.ip_limiter.allow(f"ip:{client_ip}", ip_limit):
            await self._json_error(429, "ip_rate_limited", "IP request rate exceeded", scope, receive, send)
            return

        body_bytes = b""
        async with self.session_maker() as db:
            identity = await self.identity_resolver.resolve(request, db)
            if identity:
                if not await self.user_limiter.allow(
                    f"user:{identity.user_id}",
                    identity.rate_limit or self.policy.default_user_requests_per_minute,
                ):
                    await self._json_error(429, "user_rate_limited", "User request rate exceeded", scope, receive, send)
                    return

            downstream_receive = receive
            if self.policy.should_check_sensitive(path, method):
                body_bytes = await self._read_body(receive)
                try:
                    payload = json.loads(body_bytes.decode("utf-8") or "{}") if body_bytes else {}
                except json.JSONDecodeError:
                    payload = {}

                matches = await self.sensitive_words_service.find_matches(db, payload)
                if matches:
                    await self.sensitive_words_service.record_audit(
                        db,
                        path=path,
                        user_id=identity.user_id if identity else None,
                        client_ip=client_ip,
                        matched_word_ids=[word.id for word in matches],
                    )
                    response = JSONResponse(
                        status_code=400,
                        content={
                            "error": {
                                "message": "Sensitive content blocked",
                                "type": "sensitive_content_blocked",
                                "code": "sensitive_content_blocked",
                                "matched_word_ids": [word.id for word in matches],
                            }
                        },
                    )
                    await response(scope, receive, send)
                    return

                downstream_receive = self._replay_receive(body_bytes, receive)

        await self.app(scope, downstream_receive, send)

    async def _read_body(self, receive: Callable[[], Awaitable[dict]]) -> bytes:
        chunks = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                continue
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    def _replay_receive(self, body: bytes, receive: Callable[[], Awaitable[dict]]):
        replayed = False

        async def inner():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return inner

    async def _json_error(self, status_code: int, code: str, message: str, scope, receive, send):
        response = JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "message": message,
                    "type": code,
                    "code": code,
                }
            },
        )
        await response(scope, receive, send)
