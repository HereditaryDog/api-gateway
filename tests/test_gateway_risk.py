from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.middleware.gateway_risk import GatewayRiskMiddleware
from app.models.risk import SensitiveWord
from app.services.risk_control.identity import ResolvedIdentity
from app.services.risk_control.policy import RiskPolicy
from app.services.risk_control.sensitive_words import SensitiveWordsService


class DummyIdentityResolver:
    @staticmethod
    def get_client_ip(request: Request) -> str:
        return request.headers.get("X-Forwarded-For", "127.0.0.1")

    async def resolve(self, request: Request, db):
        user_id = request.headers.get("X-User-Id")
        if not user_id:
            return None
        return ResolvedIdentity(
            user_id=int(user_id),
            username=f"user-{user_id}",
            rate_limit=int(request.headers.get("X-User-Rate", "60")),
            source="test",
        )


async def _build_app(tmp_path: Path, *, policy: RiskPolicy):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'risk-test.db'}"
    engine = create_async_engine(db_url, future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    service = SensitiveWordsService()
    await service.invalidate_cache()

    app = FastAPI()
    app.add_middleware(
        GatewayRiskMiddleware,
        policy=policy,
        session_maker=session_maker,
        identity_resolver=DummyIdentityResolver(),
        sensitive_words_service=service,
    )

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/api/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/api/test")
    async def api_test():
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat():
        return {"ok": True}

    return app, session_maker


@pytest.mark.asyncio
async def test_sensitive_words_block_only_in_inference_routes(tmp_path):
    app, session_maker = await _build_app(
        tmp_path,
        policy=RiskPolicy(global_qps=100, global_burst=100, ip_requests_per_minute=100),
    )
    async with session_maker() as db:
        db.add(SensitiveWord(term="blocked", scope="completion", priority=1, is_active=True))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        blocked = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "this is blocked content"}]},
        )
        login_ok = await client.post("/api/auth/login", json={"username": "blocked"})
        health_ok = await client.get("/health")

    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "sensitive_content_blocked"
    assert login_ok.status_code == 200
    assert health_ok.status_code == 200


@pytest.mark.asyncio
async def test_ip_rate_limit_blocks_repeated_requests(tmp_path):
    app, _ = await _build_app(
        tmp_path,
        policy=RiskPolicy(global_qps=100, global_burst=100, ip_requests_per_minute=1),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.get("/api/test", headers={"X-Forwarded-For": "1.1.1.1"})
        second = await client.get("/api/test", headers={"X-Forwarded-For": "1.1.1.1"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "ip_rate_limited"


@pytest.mark.asyncio
async def test_user_rate_limit_isolated_per_user_even_on_same_ip(tmp_path):
    app, _ = await _build_app(
        tmp_path,
        policy=RiskPolicy(global_qps=100, global_burst=100, ip_requests_per_minute=100, default_user_requests_per_minute=1),
    )

    headers_user_1 = {"X-Forwarded-For": "2.2.2.2", "X-User-Id": "1", "X-User-Rate": "1"}
    headers_user_2 = {"X-Forwarded-For": "2.2.2.2", "X-User-Id": "2", "X-User-Rate": "1"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.get("/api/test", headers=headers_user_1)
        second = await client.get("/api/test", headers=headers_user_1)
        third = await client.get("/api/test", headers=headers_user_2)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "user_rate_limited"
    assert third.status_code == 200
