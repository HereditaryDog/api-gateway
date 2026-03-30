from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password, generate_api_key


class UserService:
    """用户管理服务"""

    @staticmethod
    async def create_user(db: AsyncSession, data: UserCreate) -> User:
        """创建用户"""
        user = User(
            username=data.username,
            email=data.email,
            phone=data.phone,
            hashed_password=get_password_hash(data.password),
            api_key=generate_api_key(),
            points_balance=0,  # 默认 0 积分
            total_quota=data.total_quota,
            is_admin=data.is_admin,
            email_verified=getattr(data, "email_verified", False),
            remark=data.remark
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """通过 ID 获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_api_key(db: AsyncSession, api_key: str) -> Optional[User]:
        """通过 API Key 获取用户"""
        result = await db.execute(select(User).where(User.api_key == api_key))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[User]:
        """列出用户"""
        query = select(User)
        if active_only:
            query = query.where(User.is_active == True)
        query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[User]:
        """验证用户密码"""
        user = await UserService.get_user_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def get_user_by_email_excluding_id(
        db: AsyncSession,
        email: str,
        user_id: int,
    ) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.email == email, User.id != user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_phone_excluding_id(
        db: AsyncSession,
        phone: str,
        user_id: int,
    ) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.phone == phone, User.id != user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user: User,
        data: UserUpdate
    ) -> User:
        """更新用户信息"""
        update_data = data.model_dump(exclude_unset=True)
        
        if 'password' in update_data:
            update_data['hashed_password'] = get_password_hash(update_data.pop('password'))
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.flush()
        return user

    @staticmethod
    async def regenerate_api_key(db: AsyncSession, user: User) -> str:
        """重新生成 API Key"""
        new_key = generate_api_key()
        user.api_key = new_key
        await db.flush()
        return new_key

    @staticmethod
    async def update_last_used(db: AsyncSession, user: User):
        """更新最后使用时间"""
        from datetime import datetime, timezone
        user.last_used_at = datetime.now(timezone.utc)
        await db.flush()
