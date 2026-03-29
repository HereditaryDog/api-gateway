#!/usr/bin/env python3
"""
初始化管理员账号
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.core.config import get_settings
from app.services.user_service import UserService
from app.schemas.user import UserCreate

settings = get_settings()


async def init_admin():
    """创建管理员账号"""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 检查管理员是否已存在
        existing = await UserService.get_user_by_username(db, settings.ADMIN_USERNAME)
        
        if existing:
            print(f"[INFO] Admin user '{settings.ADMIN_USERNAME}' already exists.")
            return
        
        # 创建管理员
        admin = await UserService.create_user(
            db,
            UserCreate(
                username=settings.ADMIN_USERNAME,
                password=settings.ADMIN_PASSWORD,
                email=f"{settings.ADMIN_USERNAME}@example.com",
                total_quota=1000000,  # 管理员有大量配额
                is_admin=True
            )
        )
        
        print(f"[OK] Admin user created:")
        print(f"   Username: {admin.username}")
        print(f"   API Key: {admin.api_key}")
        print(f"   Points: {admin.points_balance}")


if __name__ == "__main__":
    asyncio.run(init_admin())
