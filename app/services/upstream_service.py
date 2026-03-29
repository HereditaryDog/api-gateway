from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.upstream import UpstreamKey, UpstreamProvider
from app.schemas.upstream import UpstreamKeyCreate, UpstreamKeyUpdate, ProviderCreate, ProviderUpdate
from app.core.encryption import encrypt_data, decrypt_data
import random


class UpstreamService:
    """上游 Key 管理服务"""

    @staticmethod
    def mask_key(key: str) -> str:
        """脱敏显示 API Key"""
        if len(key) <= 8:
            return "****"
        return key[:8] + "****" + key[-4:] if len(key) > 12 else key[:8] + "****"

    # ========== Provider 管理 ==========

    @staticmethod
    async def create_provider(db: AsyncSession, data: ProviderCreate) -> UpstreamProvider:
        """创建提供商"""
        provider = UpstreamProvider(
            name=data.name,
            provider_type=data.provider_type,
            base_url=data.base_url.rstrip('/'),
            model_mapping=data.model_mapping or {},
            priority=data.priority,
            remark=data.remark
        )
        db.add(provider)
        await db.flush()
        return provider

    @staticmethod
    async def get_provider(db: AsyncSession, provider_id: int) -> Optional[UpstreamProvider]:
        """获取提供商"""
        result = await db.execute(
            select(UpstreamProvider).where(UpstreamProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_providers(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = False
    ) -> List[UpstreamProvider]:
        """列出提供商"""
        query = select(UpstreamProvider)
        if active_only:
            query = query.where(UpstreamProvider.is_active == True)
        query = query.order_by(UpstreamProvider.priority).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_provider(
        db: AsyncSession, 
        provider: UpstreamProvider, 
        data: ProviderUpdate
    ) -> UpstreamProvider:
        """更新提供商"""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(provider, field, value)
        await db.flush()
        return provider

    @staticmethod
    async def delete_provider(db: AsyncSession, provider: UpstreamProvider):
        """删除提供商"""
        await db.delete(provider)

    # ========== Upstream Key 管理 ==========

    @classmethod
    async def create_key(cls, db: AsyncSession, data: UpstreamKeyCreate) -> UpstreamKey:
        """创建上游 Key"""
        encrypted = encrypt_data(data.api_key)
        key = UpstreamKey(
            provider_id=data.provider_id,
            encrypted_key=encrypted,
            weight=data.weight,
            priority=data.priority,
            rpm_limit=data.rpm_limit,
            tpm_limit=data.tpm_limit,
            remark=data.remark
        )
        db.add(key)
        await db.flush()
        return key

    @staticmethod
    async def get_key(db: AsyncSession, key_id: int) -> Optional[UpstreamKey]:
        """获取 Key"""
        result = await db.execute(
            select(UpstreamKey).where(UpstreamKey.id == key_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def list_keys(
        cls,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        provider_id: Optional[int] = None,
        active_only: bool = False,
        available_only: bool = False
    ) -> List[UpstreamKey]:
        """列出 Keys"""
        query = select(UpstreamKey)
        
        if provider_id:
            query = query.where(UpstreamKey.provider_id == provider_id)
        
        if active_only:
            query = query.where(UpstreamKey.is_active == True)
        
        if available_only:
            query = query.where(
                and_(
                    UpstreamKey.is_active == True,
                    UpstreamKey.is_exhausted == False
                )
            )
        
        query = query.order_by(UpstreamKey.priority, UpstreamKey.weight.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    @classmethod
    async def get_available_key_by_provider(
        cls,
        db: AsyncSession,
        provider: str,
        exclude_key_id: Optional[int] = None
    ) -> Optional[tuple[UpstreamKey, str]]:
        """
        根据 provider 名称获取可用的上游 Key
        
        Args:
            db: 数据库会话
            provider: provider 名称，如 "openai", "deepseek"
            exclude_key_id: 要排除的 Key ID（用于重试）
        
        Returns:
            (UpstreamKey, 解密后的 API Key) 或 None
        """
        from app.models.upstream import UpstreamProvider
        
        # 查找对应 provider 类型的记录
        provider_result = await db.execute(
            select(UpstreamProvider).where(
                and_(
                    UpstreamProvider.provider_type == provider,
                    UpstreamProvider.is_active == True
                )
            )
        )
        provider_record = provider_result.scalar_one_or_none()
        
        if not provider_record:
            return None
        
        # 获取可用的 keys
        keys = await cls.list_keys(
            db, 
            provider_id=provider_record.id,
            available_only=True,
            limit=100
        )
        
        if exclude_key_id:
            keys = [k for k in keys if k.id != exclude_key_id]
        
        if not keys:
            return None
        
        # 按权重随机选择
        total_weight = sum(k.weight for k in keys)
        if total_weight <= 0:
            selected_key = keys[0]
        else:
            r = random.uniform(0, total_weight)
            current_weight = 0
            selected_key = keys[-1]
            for key in keys:
                current_weight += key.weight
                if r <= current_weight:
                    selected_key = key
                    break
        
        # 解密 API Key
        decrypted_key = decrypt_data(selected_key.encrypted_key)
        if not decrypted_key:
            return None
        
        return selected_key, decrypted_key

    @staticmethod
    async def update_key(
        db: AsyncSession,
        key: UpstreamKey,
        data: UpstreamKeyUpdate
    ) -> UpstreamKey:
        """更新 Key"""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(key, field, value)
        await db.flush()
        return key

    @staticmethod
    async def increment_usage(
        db: AsyncSession,
        key: UpstreamKey,
        tokens: int
    ):
        """增加使用量"""
        key.total_requests += 1
        key.total_tokens += tokens / 1000  # 转换为千tokens
        from datetime import datetime, timezone
        key.last_used_at = datetime.now(timezone.utc)
        await db.flush()
