from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router


async def build_self_service_app(tmp_path: Path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'self-service.db'}"
    engine = create_async_engine(db_url, future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_user_api_key_and_password_routes(tmp_path):
    app = await build_self_service_app(tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        send_code = await client.post(
            "/api/auth/send-email-code",
            json={"email": "selfservice@example.com"},
            headers={"host": "127.0.0.1:8082"},
        )
        email_code = send_code.json()["debug_code"]

        from app.routers.invite_admin import router as invite_admin_router
        from app.core.security import get_current_admin

        app.include_router(invite_admin_router, prefix="/api")

        async def override_admin():
            return type("Admin", (), {"id": 1, "username": "admin", "is_admin": True})()

        app.dependency_overrides[get_current_admin] = override_admin
        invite = await client.post(
            "/api/admin/invite-codes",
            json={"quantity": 1, "expires_in_days": 7},
        )
        invite_code = invite.json()["codes"][0]["code"]

        register = await client.post(
            "/api/auth/register",
            json={
                "username": "selfservice",
                "email": "selfservice@example.com",
                "phone": "13800138011",
                "password": "secret123",
                "confirm_password": "secret123",
                "email_code": email_code,
                "invite_code": invite_code,
            },
        )
        token = register.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        api_keys = await client.get("/api/users/me/api-keys", headers=headers)
        assert api_keys.status_code == 200
        assert len(api_keys.json()) == 1

        regen = await client.post("/api/users/me/regenerate-api-key", headers=headers)
        assert regen.status_code == 200

        profile = await client.put(
            "/api/users/me/profile",
            headers=headers,
            json={
                "username": "selfservice2",
                "email": "selfservice@example.com",
                "phone": "13800138011",
            },
        )
        assert profile.status_code == 200
        assert profile.json()["username"] == "selfservice2"

        bad_password = await client.post(
            "/api/users/me/change-password",
            headers=headers,
            json={
                "current_password": "wrongpass",
                "new_password": "secret456",
                "confirm_password": "secret456",
            },
        )
        assert bad_password.status_code == 400

        good_password = await client.post(
            "/api/users/me/change-password",
            headers=headers,
            json={
                "current_password": "secret123",
                "new_password": "secret456",
                "confirm_password": "secret456",
            },
        )
        assert good_password.status_code == 200
