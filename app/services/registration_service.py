from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
import string
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invite import EmailVerificationCode, InviteCode
from app.models.user import User


class RegistrationService:
    EMAIL_CODE_TTL_MINUTES = 10

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def generate_email_code(cls) -> str:
        return "".join(secrets.choice(string.digits) for _ in range(6))

    @classmethod
    def generate_invite_code(cls) -> str:
        alphabet = string.ascii_uppercase + string.digits
        parts = [
            "".join(secrets.choice(alphabet) for _ in range(4)),
            "".join(secrets.choice(alphabet) for _ in range(4)),
            "".join(secrets.choice(alphabet) for _ in range(4)),
        ]
        return "-".join(parts)

    @classmethod
    async def create_email_code(cls, db: AsyncSession, email: str) -> tuple[EmailVerificationCode, str]:
        result = await db.execute(
            select(EmailVerificationCode).where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.consumed_at.is_(None),
            )
        )
        existing_codes = result.scalars().all()
        now = cls._now()
        for item in existing_codes:
            item.consumed_at = now

        code = cls.generate_email_code()
        record = EmailVerificationCode(
            email=email,
            code=code,
            expires_at=now + timedelta(minutes=cls.EMAIL_CODE_TTL_MINUTES),
        )
        db.add(record)
        await db.flush()
        return record, code

    @classmethod
    async def verify_email_code(cls, db: AsyncSession, email: str, code: str) -> EmailVerificationCode:
        result = await db.execute(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.code == code,
                EmailVerificationCode.consumed_at.is_(None),
            )
            .order_by(EmailVerificationCode.id.desc())
        )
        record = result.scalars().first()
        if not record:
            raise ValueError("验证码错误或已失效")
        if cls._ensure_utc(record.expires_at) < cls._now():
            raise ValueError("验证码已过期")
        return record

    @classmethod
    async def consume_email_code(cls, db: AsyncSession, record: EmailVerificationCode):
        record.consumed_at = cls._now()
        await db.flush()

    @classmethod
    async def get_invite_code(cls, db: AsyncSession, code: str) -> Optional[InviteCode]:
        result = await db.execute(select(InviteCode).where(InviteCode.code == code.upper()))
        return result.scalar_one_or_none()

    @classmethod
    async def validate_invite_code(cls, db: AsyncSession, code: str) -> InviteCode:
        invite_code = await cls.get_invite_code(db, code)
        if not invite_code:
            raise ValueError("邀请码不存在")
        if not invite_code.is_active:
            raise ValueError("邀请码不可用")
        if invite_code.used_by_user_id:
            raise ValueError("邀请码已被使用")
        if cls._ensure_utc(invite_code.expires_at) and cls._ensure_utc(invite_code.expires_at) < cls._now():
            raise ValueError("邀请码已过期")
        return invite_code

    @classmethod
    async def consume_invite_code(cls, db: AsyncSession, invite_code: InviteCode, user: User):
        invite_code.used_by_user_id = user.id
        invite_code.used_at = cls._now()
        invite_code.is_active = False
        await db.flush()

    @classmethod
    async def list_invite_codes(cls, db: AsyncSession, limit: int = 100) -> List[InviteCode]:
        result = await db.execute(
            select(InviteCode).order_by(InviteCode.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @classmethod
    async def create_invite_codes(
        cls,
        db: AsyncSession,
        *,
        quantity: int,
        created_by_user_id: Optional[int],
        expires_in_days: Optional[int],
        remark: Optional[str],
    ) -> List[InviteCode]:
        created: List[InviteCode] = []
        expires_at = None
        if expires_in_days:
            expires_at = cls._now() + timedelta(days=expires_in_days)

        existing_codes = {row.code for row in await cls.list_invite_codes(db, limit=1000)}
        while len(created) < quantity:
            code = cls.generate_invite_code()
            if code in existing_codes:
                continue
            existing_codes.add(code)
            invite_code = InviteCode(
                code=code,
                created_by_user_id=created_by_user_id,
                expires_at=expires_at,
                remark=remark,
                is_active=True,
            )
            db.add(invite_code)
            created.append(invite_code)

        await db.flush()
        return created
