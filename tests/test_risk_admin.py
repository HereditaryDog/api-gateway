from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_current_admin
from app.routers.risk_admin import router as risk_admin_router
from app.services.risk_control.sensitive_words import get_sensitive_words_service


async def _build_admin_app(tmp_path: Path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'risk-admin.db'}"
    engine = create_async_engine(db_url, future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI()
    app.include_router(risk_admin_router, prefix="/api")

    async def override_get_db():
        async with session_maker() as session:
            yield session

    async def override_admin():
        return type("Admin", (), {"id": 1, "username": "admin", "is_admin": True})()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_admin
    await get_sensitive_words_service().invalidate_cache()
    return app


@pytest.mark.asyncio
async def test_risk_admin_crud(tmp_path):
    app = await _build_admin_app(tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        created = await client.post(
            "/api/risk/sensitive-words",
            json={"term": "forbidden", "scope": "completion", "priority": 10, "is_active": True},
        )
        listed = await client.get("/api/risk/sensitive-words")
        updated = await client.put(
            f"/api/risk/sensitive-words/{created.json()['id']}",
            json={"remark": "updated"},
        )
        deleted = await client.delete(f"/api/risk/sensitive-words/{created.json()['id']}")
        final_list = await client.get("/api/risk/sensitive-words")

    assert created.status_code == 201
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert updated.status_code == 200 and updated.json()["remark"] == "updated"
    assert deleted.status_code == 200
    assert final_list.json() == []
