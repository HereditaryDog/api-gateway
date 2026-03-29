#!/usr/bin/env python3
"""
完整的数据库初始化脚本
创建所有表并初始化默认数据
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# 导入所有模型
from app.core.database import Base
from app.models.user import User
from app.models.upstream import UpstreamProvider, UpstreamKey, ProviderType
from app.models.usage import UsageLog, PointsLog
from app.core.encryption import encrypt_data

# 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/app.db")


async def init_database():
    """初始化数据库"""
    print("[INFO] 正在初始化数据库...")
    
    # 确保数据目录存在
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # 创建引擎
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("[OK] 数据库表创建完成")
    return engine


async def create_default_providers(session: AsyncSession):
    """创建默认提供商"""
    providers = [
        {
            "name": "OpenAI",
            "provider_type": ProviderType.OPENAI,
            "base_url": "https://api.openai.com/v1",
            "model_mapping": {
                "gpt-4": "gpt-4",
                "gpt-4-turbo": "gpt-4-turbo-preview",
                "gpt-4o": "gpt-4o",
                "gpt-4o-mini": "gpt-4o-mini",
                "gpt-3.5-turbo": "gpt-3.5-turbo",
            },
            "priority": 100
        },
        {
            "name": "Anthropic",
            "provider_type": ProviderType.ANTHROPIC,
            "base_url": "https://api.anthropic.com/v1",
            "model_mapping": {
                "claude-3-opus": "claude-3-opus-20240229",
                "claude-3-sonnet": "claude-3-sonnet-20240229",
                "claude-3-haiku": "claude-3-haiku-20240307",
            },
            "priority": 100
        },
        {
            "name": "DeepSeek",
            "provider_type": ProviderType.DEEPSEEK,
            "base_url": "https://api.deepseek.com/v1",
            "model_mapping": {
                "deepseek-chat": "deepseek-chat",
                "deepseek-coder": "deepseek-coder",
                "deepseek-reasoner": "deepseek-reasoner",
            },
            "priority": 100
        },
        {
            "name": "Google Gemini",
            "provider_type": ProviderType.GEMINI,
            "base_url": "https://generativelanguage.googleapis.com/v1",
            "model_mapping": {
                "gemini-pro": "gemini-1.5-pro",
                "gemini-flash": "gemini-1.5-flash",
            },
            "priority": 100
        },
        {
            "name": "SiliconFlow",
            "provider_type": ProviderType.SILICONFLOW,
            "base_url": "https://api.siliconflow.cn/v1",
            "model_mapping": {},
            "priority": 200
        },
        {
            "name": "Moonshot",
            "provider_type": ProviderType.MOONSHOT,
            "base_url": "https://api.moonshot.cn/v1",
            "model_mapping": {
                "moonshot-v1-8k": "moonshot-v1-8k",
                "moonshot-v1-32k": "moonshot-v1-32k",
                "moonshot-v1-128k": "moonshot-v1-128k",
            },
            "priority": 200
        },
    ]
    
    for provider_data in providers:
        # 检查是否已存在
        from sqlalchemy import select
        result = await session.execute(
            select(UpstreamProvider).where(UpstreamProvider.name == provider_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            provider = UpstreamProvider(**provider_data)
            session.add(provider)
            print(f"[OK] 创建提供商: {provider_data['name']}")
        else:
            print(f"[INFO] 提供商已存在: {provider_data['name']}")
    
    await session.commit()


async def create_admin_user(session: AsyncSession):
    """创建管理员账号"""
    import secrets
    import string
    
    from sqlalchemy import select
    
    # 检查是否已有管理员
    result = await session.execute(select(User).where(User.username == "admin"))
    existing = result.scalar_one_or_none()
    
    if existing:
        print("[INFO] 管理员账号已存在，更新密码...")
        existing.hashed_password = pwd_context.hash("admin123")
        existing.is_active = True
        existing.is_admin = True
        if not existing.api_key:
            alphabet = string.ascii_letters + string.digits
            existing.api_key = "sk-" + "".join(secrets.choice(alphabet) for _ in range(48))
    else:
        print("[INFO] 创建管理员账号...")
        # 生成 API Key
        alphabet = string.ascii_letters + string.digits
        api_key = "sk-" + "".join(secrets.choice(alphabet) for _ in range(48))
        
        admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=pwd_context.hash("admin123"),
            api_key=api_key,
            points_balance=10000.0,
            total_quota=0.0,
            used_quota=0.0,
            is_active=True,
            is_admin=True,
            rate_limit=60,
        )
        session.add(admin)
    
    await session.commit()
    print("[OK] 管理员账号创建完成")
    print("   用户名: admin")
    print("   密码: admin123")


async def main():
    """主函数"""
    print("=" * 50)
    print("API Gateway 数据库初始化工具")
    print("=" * 50)
    print()
    
    try:
        # 初始化数据库
        engine = await init_database()
        
        # 创建会话
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # 创建默认提供商
            await create_default_providers(session)
            print()
            
            # 创建管理员
            await create_admin_user(session)
        
        print()
        print("=" * 50)
        print("[OK] 数据库初始化完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"[ERROR] 初始化失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
