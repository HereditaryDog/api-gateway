from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from app.core.security import decode_access_token
from app.services.user_service import UserService


@dataclass
class ResolvedIdentity:
    user_id: int
    username: str
    rate_limit: int
    source: str


class RequestIdentityResolver:
    @staticmethod
    def get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def resolve(self, request: Request, db) -> Optional[ResolvedIdentity]:
        authorization = request.headers.get("Authorization", "")
        if not authorization:
            return None

        credential = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
        if not credential:
            return None

        path = request.url.path
        if path.startswith("/v1/"):
            user = await UserService.get_user_by_api_key(db, credential)
            if not user:
                return None
            return ResolvedIdentity(
                user_id=user.id,
                username=user.username,
                rate_limit=user.rate_limit or 60,
                source="api_key",
            )

        payload = decode_access_token(credential)
        if not payload:
            return None

        user_id = payload.get("user_id")
        if not user_id:
            return None

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            return None

        return ResolvedIdentity(
            user_id=user.id,
            username=user.username,
            rate_limit=user.rate_limit or 60,
            source="jwt",
        )
