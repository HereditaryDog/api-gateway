#!/usr/bin/env python3
"""
初始化默认提供商配置
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.services.upstream_service import UpstreamService
from app.schemas.upstream import ProviderCreate
from app.models.upstream import ProviderType


async def init_providers():
    """创建默认提供商"""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 默认提供商配置
        default_providers = [
            {
                "name": "OpenAI",
                "provider_type": ProviderType.OPENAI,
                "base_url": "https://api.openai.com",
                "model_mapping": {
                    "gpt-4": "gpt-4",
                    "gpt-4-turbo": "gpt-4-turbo-preview",
                    "gpt-4o": "gpt-4o",
                    "gpt-4o-mini": "gpt-4o-mini",
                    "gpt-3.5-turbo": "gpt-3.5-turbo",
                    "text-embedding-3-small": "text-embedding-3-small",
                    "text-embedding-3-large": "text-embedding-3-large"
                },
                "priority": 100
            },
            {
                "name": "Anthropic Claude",
                "provider_type": ProviderType.ANTHROPIC,
                "base_url": "https://api.anthropic.com",
                "model_mapping": {
                    "claude-3-opus": "claude-3-opus-20240229",
                    "claude-3-sonnet": "claude-3-sonnet-20240229",
                    "claude-3-haiku": "claude-3-haiku-20240307"
                },
                "priority": 100
            },
            {
                "name": "DeepSeek",
                "provider_type": ProviderType.DEEPSEEK,
                "base_url": "https://api.deepseek.com",
                "model_mapping": {
                    "deepseek-chat": "deepseek-chat",
                    "deepseek-coder": "deepseek-coder",
                    "deepseek-reasoner": "deepseek-reasoner"
                },
                "priority": 100
            },
            {
                "name": "Google Gemini",
                "provider_type": ProviderType.GEMINI,
                "base_url": "https://generativelanguage.googleapis.com",
                "model_mapping": {
                    "gemini-pro": "gemini-1.5-pro",
                    "gemini-flash": "gemini-1.5-flash"
                },
                "priority": 100
            }
        ]
        
        # 获取现有提供商
        existing = await UpstreamService.list_providers(db)
        existing_names = {p.name for p in existing}
        
        for provider_data in default_providers:
            if provider_data["name"] not in existing_names:
                try:
                    await UpstreamService.create_provider(
                        db,
                        ProviderCreate(**provider_data)
                    )
                    print(f"✅ 创建提供商: {provider_data['name']}")
                except Exception as e:
                    print(f"❌ 创建 {provider_data['name']} 失败: {e}")
            else:
                print(f"⏭️  提供商已存在: {provider_data['name']}")
        
        print("\n🎉 提供商初始化完成！")
        print("现在可以通过管理界面添加 API Keys 了。")


if __name__ == "__main__":
    asyncio.run(init_providers())
