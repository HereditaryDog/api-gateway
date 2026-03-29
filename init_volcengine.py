#!/usr/bin/env python3
"""
初始化火山引擎 Provider 和 API Key
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.models.upstream import UpstreamProvider, UpstreamKey, ProviderType
from app.core.encryption import encrypt_data

# 火山引擎配置
VOLCENGINE_CONFIG = {
    "name": "火山引擎 (Volcengine)",
    "provider_type": ProviderType.CUSTOM,  # 使用 CUSTOM 或添加 VOLCENGINE
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "b964b131-db8c-48d9-bc36-89d42c576b9c",
    "model_mapping": {
        # 豆包大模型系列
        "doubao-seed-2-0-lite": "doubao-seed-2-0-lite-260215",
        "doubao-seed-2-0": "doubao-seed-2-0-250128",
        "doubao-seed-1-5": "doubao-seed-1-5-250115",
        "doubao-seed-1-5-lite": "doubao-seed-1-5-lite-250115",
        "doubao-lite": "doubao-lite-4k-240515",
        "doubao-pro": "doubao-pro-4k-240515",
        "doubao-pro-128k": "doubao-pro-128k-240515",
        "doubao-vision": "doubao-vision-lite-240515",
        "doubao-embedding": "doubao-embedding-240515",
        "doubao-text-embedding": "doubao-text-embedding-240515",
        # 其他模型
        "glm-4": "glm-4-9b",
        "glm-4-flash": "glm-4-flash-9b",
    }
}


async def init_volcengine():
    """初始化火山引擎"""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 1. 检查是否已存在
        from sqlalchemy import select
        result = await db.execute(
            select(UpstreamProvider).where(
                UpstreamProvider.name == VOLCENGINE_CONFIG["name"]
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"[INFO] 火山引擎 Provider 已存在 (ID: {existing.id})")
            provider_id = existing.id
        else:
            # 2. 创建 Provider
            provider = UpstreamProvider(
                name=VOLCENGINE_CONFIG["name"],
                provider_type=VOLCENGINE_CONFIG["provider_type"],
                base_url=VOLCENGINE_CONFIG["base_url"],
                model_mapping=VOLCENGINE_CONFIG["model_mapping"],
                is_active=True,
                priority=10,  # 优先级，数字越小越优先
                remark="字节跳动火山引擎 - 豆包大模型"
            )
            db.add(provider)
            await db.flush()
            provider_id = provider.id
            print(f"[OK] 创建 Provider: {provider.name} (ID: {provider_id})")
        
        # 3. 检查 API Key 是否已存在（检查该 provider 下是否有 key）
        result = await db.execute(
            select(UpstreamKey).where(
                UpstreamKey.provider_id == provider_id
            )
        )
        existing_keys = result.scalars().all()
        
        if existing_keys:
            print(f"[INFO] API Key 已存在 (ID: {existing_keys[0].id})")
        else:
            # 4. 创建 API Key（加密存储）
            encrypted_key = encrypt_data(VOLCENGINE_CONFIG["api_key"])
            api_key = UpstreamKey(
                provider_id=provider_id,
                encrypted_key=encrypted_key,  # 加密存储
                is_active=True,
                priority=10,
                weight=100,
                rpm_limit=60,
                tpm_limit=100000,
                remark="火山引擎 Coding Plan API Key"
            )
            db.add(api_key)
            await db.flush()
            print(f"[OK] 创建 API Key (ID: {api_key.id})")
        
        await db.commit()
        print("\n[OK] 火山引擎配置完成！")
        print(f"   Provider ID: {provider_id}")
        print(f"   Base URL: {VOLCENGINE_CONFIG['base_url']}")
        print(f"   支持模型: {list(VOLCENGINE_CONFIG['model_mapping'].keys())}")


if __name__ == "__main__":
    asyncio.run(init_volcengine())
