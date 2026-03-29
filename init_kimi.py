#!/usr/bin/env python3
"""
初始化 Kimi Code (Moonshot) Provider 和 API Key
"""
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.upstream import UpstreamProvider, UpstreamKey, ProviderType
from app.core.encryption import encrypt_data

# Kimi Code 配置
KIMI_CONFIG = {
    "name": "Kimi Code (Moonshot)",
    "provider_type": ProviderType.MOONSHOT,
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": "sk-kimi-FSRENCKqGxRPiL1TbhYf9517zo2elIxuZmfa2A4xYgyyZx3RBk6XiejQJrXlbyFN",
    "model_mapping": {
        # Kimi 模型系列
        "kimi-k2-5": "kimi-k2-5",
        "kimi-k2": "kimi-k2",
        "kimi-k1-5": "kimi-k1-5",
        "kimi-k1": "kimi-k1",
        "kimi-latest": "kimi-latest",
        "moonshot-v1-8k": "moonshot-v1-8k",
        "moonshot-v1-32k": "moonshot-v1-32k",
        "moonshot-v1-128k": "moonshot-v1-128k",
    }
}


async def init_kimi():
    """初始化 Kimi Code"""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 1. 检查是否已存在
        result = await db.execute(
            select(UpstreamProvider).where(
                UpstreamProvider.name == KIMI_CONFIG["name"]
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"[INFO] Kimi Provider 已存在 (ID: {existing.id})")
            provider_id = existing.id
        else:
            # 2. 创建 Provider
            provider = UpstreamProvider(
                name=KIMI_CONFIG["name"],
                provider_type=KIMI_CONFIG["provider_type"],
                base_url=KIMI_CONFIG["base_url"],
                model_mapping=KIMI_CONFIG["model_mapping"],
                is_active=True,
                priority=10,
                remark="Moonshot Kimi - 长文本大模型"
            )
            db.add(provider)
            await db.flush()
            provider_id = provider.id
            print(f"[OK] 创建 Provider: {provider.name} (ID: {provider_id})")
        
        # 3. 检查 API Key 是否已存在
        result = await db.execute(
            select(UpstreamKey).where(UpstreamKey.provider_id == provider_id)
        )
        existing_keys = result.scalars().all()
        
        if existing_keys:
            print(f"[INFO] API Key 已存在 (ID: {existing_keys[0].id})")
        else:
            # 4. 创建 API Key（加密存储）
            encrypted_key = encrypt_data(KIMI_CONFIG["api_key"])
            api_key = UpstreamKey(
                provider_id=provider_id,
                encrypted_key=encrypted_key,
                is_active=True,
                priority=10,
                weight=100,
                rpm_limit=60,
                tpm_limit=100000,
                remark="Kimi Code API Key"
            )
            db.add(api_key)
            await db.flush()
            print(f"[OK] 创建 API Key (ID: {api_key.id})")
        
        await db.commit()
        print("\n[OK] Kimi Code 配置完成！")
        print(f"   Provider ID: {provider_id}")
        print(f"   Base URL: {KIMI_CONFIG['base_url']}")
        print(f"   支持模型: {list(KIMI_CONFIG['model_mapping'].keys())}")


if __name__ == "__main__":
    asyncio.run(init_kimi())
