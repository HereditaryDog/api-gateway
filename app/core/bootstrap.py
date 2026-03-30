from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.schemas.user import UserCreate
from app.services.user_service import UserService


async def ensure_admin_user() -> bool:
    """在首次启动时确保管理员账号存在。"""
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        existing = await UserService.get_user_by_username(db, settings.ADMIN_USERNAME)
        if existing:
            return False

        admin = await UserService.create_user(
            db,
            UserCreate(
                username=settings.ADMIN_USERNAME,
                password=settings.ADMIN_PASSWORD,
                email=f"{settings.ADMIN_USERNAME}@example.com",
                total_quota=1000000,
                is_admin=True,
            ),
        )
        admin.points_balance = 10000
        await db.commit()
        return True
