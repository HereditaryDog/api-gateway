from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_current_admin
from app.routers.auth import router as auth_router
from app.routers.invite_admin import router as invite_admin_router
from app.services.risk_control.sensitive_words import get_sensitive_words_service


async def build_test_app(tmp_path: Path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'registration.db'}"
    engine = create_async_engine(db_url, future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(invite_admin_router, prefix="/api")

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_admin():
        return type("Admin", (), {"id": 1, "username": "admin", "is_admin": True})()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_admin
    await get_sensitive_words_service().invalidate_cache()
    return app


@pytest.mark.asyncio
async def test_full_registration_flow(tmp_path):
    app = await build_test_app(tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8082") as client:
        invite_res = await client.post(
            "/api/admin/invite-codes",
            json={"quantity": 1, "expires_in_days": 7, "remark": "test"},
        )
        invite_code = invite_res.json()["codes"][0]["code"]

        code_res = await client.post(
            "/api/auth/send-email-code",
            json={"email": "newuser@example.com"},
            headers={"host": "127.0.0.1:8082"},
        )
        email_code = code_res.json()["debug_code"]

        register_res = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "phone": "13800138000",
                "password": "secret123",
                "confirm_password": "secret123",
                "email_code": email_code,
                "invite_code": invite_code,
            },
        )

    assert invite_res.status_code == 200
    assert code_res.status_code == 200
    assert register_res.status_code == 200
    body = register_res.json()
    assert body["user"]["username"] == "newuser"
    assert body["user"]["email"] == "newuser@example.com"
    assert body["user"]["phone"] == "13800138000"
    assert body["user"]["email_verified"] is True


@pytest.mark.asyncio
async def test_register_rejects_invalid_invite_code(tmp_path):
    app = await build_test_app(tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8082") as client:
        code_res = await client.post(
            "/api/auth/send-email-code",
            json={"email": "invalidinvite@example.com"},
            headers={"host": "127.0.0.1:8082"},
        )
        email_code = code_res.json()["debug_code"]

        register_res = await client.post(
            "/api/auth/register",
            json={
                "username": "invalidinvite",
                "email": "invalidinvite@example.com",
                "phone": "13900139000",
                "password": "secret123",
                "confirm_password": "secret123",
                "email_code": email_code,
                "invite_code": "NOPE-0000-NOPE",
            },
        )

    assert register_res.status_code == 400
    assert register_res.json()["detail"] == "邀请码不存在"
