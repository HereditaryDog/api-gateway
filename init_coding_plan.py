"""
Coding Plan Provider 配置示例

这个脚本演示如何配置一个 Coding Plan 类型的 Provider
包括：
1. Provider 基础配置
2. 计费配置（按请求计费）
3. 多个 API Key（账号池）
4. 风控配置

运行方式:
    cd api-gateway && source venv/bin/activate && python3.12 init_coding_plan.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.upstream import UpstreamProvider, UpstreamKey, ProviderType
from app.models.billing import ProviderBillingConfig, BillingMode, SubscriptionType, QuotaWindowType
from app.models.user import User
from app.core.encryption import encrypt_data


async def create_coding_plan_provider(db: AsyncSession):
    """创建 Coding Plan Provider 示例"""
    
    print("=" * 60)
    print("Coding Plan Provider Configuration")
    print("=" * 60)
    
    # 1. 创建 Provider
    print("\n1. Creating Provider...")
    provider = UpstreamProvider(
        name="阿里云百炼 (Coding Plan)",
        provider_type=ProviderType.CUSTOM,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_mapping={
            "coding-plan/qwen-max": "qwen-max",
            "coding-plan/qwen-plus": "qwen-plus",
            "coding-plan/qwen-turbo": "qwen-turbo",
        },
        adapter_type="coding_plan",  # 关键：使用 Coding Plan 适配器
        risk_pool_size=5,  # 账号池大小
        is_active=True,
    )
    db.add(provider)
    await db.flush()
    print(f"   ✓ Provider created: ID={provider.id}")
    
    # 2. 创建计费配置
    print("\n2. Creating Billing Configuration...")
    billing_config = ProviderBillingConfig(
        provider_id=provider.id,
        billing_mode=BillingMode.REQUEST,
        cost_per_request=Decimal("0.0004"),  # 上游成本：0.0004 元/请求
        price_per_request=Decimal("0.0006"),  # 售价：0.0006 元/请求 (50% 利润)
        subscription_type=SubscriptionType.CODING_PLAN,
        quota_window_type=QuotaWindowType.ROLLING_5H,
        quota_requests=6000,
        enable_risk_control=True,
        min_qps_limit=Decimal("0.5"),
        max_qps_limit=Decimal("2.0"),
        jitter_ms_min=100,
        jitter_ms_max=500,
    )
    db.add(billing_config)
    await db.commit()
    print(f"   ✓ Billing config created")
    print(f"   - Cost per request: {billing_config.cost_per_request} CNY")
    print(f"   - Price per request: {billing_config.price_per_request} CNY")
    print(f"   - Profit margin: 50%")
    print(f"   - Risk control: Enabled")
    
    # 3. 创建多个 API Key（账号池）
    print("\n3. Creating API Key Pool...")
    
    # 示例 API Keys（实际使用时需要替换为真实的阿里云百炼 API Keys）
    api_keys = [
        "sk-your-api-key-1-here",
        "sk-your-api-key-2-here",
        "sk-your-api-key-3-here",
    ]
    
    created_keys = []
    for i, api_key in enumerate(api_keys):
        encrypted_key = encrypt_data(api_key)
        key = UpstreamKey(
            provider_id=provider.id,
            encrypted_key=encrypted_key,
            weight=100,
            priority=i,
            rpm_limit=60,
            tpm_limit=100000,
            is_active=True,
            remark=f"Coding Plan Account {i+1}"
        )
        db.add(key)
        await db.flush()
        created_keys.append(key)
        print(f"   ✓ Key {i+1} created: ID={key.id}")
    
    await db.commit()
    
    # 4. 显示配置摘要
    print("\n4. Configuration Summary:")
    print(f"   Provider ID: {provider.id}")
    print(f"   Provider Name: {provider.name}")
    print(f"   Adapter Type: {provider.adapter_type}")
    print(f"   Pool Size: {len(created_keys)}")
    print(f"   Billing Mode: {billing_config.billing_mode.value}")
    print(f"   Models: {list(provider.model_mapping.keys())}")
    
    print("\n" + "=" * 60)
    print("Coding Plan Provider configured successfully!")
    print("=" * 60)
    
    return provider, billing_config, created_keys


async def update_existing_provider(db: AsyncSession, provider_id: int):
    """更新现有的 Provider 为 Coding Plan 模式"""
    
    print("\nUpdating existing provider to Coding Plan mode...")
    
    result = await db.execute(
        select(UpstreamProvider).where(UpstreamProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        print(f"Provider {provider_id} not found")
        return None
    
    # 更新为 Coding Plan 适配器
    provider.adapter_type = "coding_plan"
    provider.risk_pool_size = 5
    
    # 检查是否已有计费配置
    result = await db.execute(
        select(ProviderBillingConfig).where(
            ProviderBillingConfig.provider_id == provider_id
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        # 创建计费配置
        config = ProviderBillingConfig(
            provider_id=provider_id,
            billing_mode=BillingMode.REQUEST,
            cost_per_request=Decimal("0.0004"),
            price_per_request=Decimal("0.0006"),
            enable_risk_control=True,
        )
        db.add(config)
    
    await db.commit()
    print(f"✓ Provider {provider_id} updated to Coding Plan mode")
    
    return provider


async def list_coding_plan_providers(db: AsyncSession):
    """列出所有 Coding Plan 类型的 Provider"""
    
    print("\nCoding Plan Providers:")
    print("-" * 60)
    
    result = await db.execute(
        select(UpstreamProvider).where(
            UpstreamProvider.adapter_type.in_(["coding_plan", "coding_plan_with_failover"])
        )
    )
    providers = result.scalars().all()
    
    if not providers:
        print("No Coding Plan providers found")
        return
    
    for provider in providers:
        # 获取计费配置
        result = await db.execute(
            select(ProviderBillingConfig).where(
                ProviderBillingConfig.provider_id == provider.id
            )
        )
        config = result.scalar_one_or_none()
        
        # 统计 Key 数量
        result = await db.execute(
            select(UpstreamKey).where(UpstreamKey.provider_id == provider.id)
        )
        keys = result.scalars().all()
        
        print(f"\nProvider: {provider.name}")
        print(f"  ID: {provider.id}")
        print(f"  Adapter: {provider.adapter_type}")
        print(f"  Pool Size: {len(keys)}/{provider.risk_pool_size}")
        print(f"  Base URL: {provider.base_url}")
        
        if config:
            print(f"  Billing: {config.billing_mode.value}")
            if config.billing_mode == BillingMode.REQUEST:
                print(f"  Cost: {config.cost_per_request} CNY/request")
                print(f"  Price: {config.price_per_request} CNY/request")
        
        print(f"  Models: {list(provider.model_mapping.keys()) if provider.model_mapping else 'N/A'}")


async def main():
    """主函数"""
    
    print("\n" + "=" * 60)
    print("Coding Plan Provider Setup Tool")
    print("=" * 60)
    
    async with async_session_maker() as db:
        import sys
        
        if len(sys.argv) > 1:
            if sys.argv[1] == "list":
                await list_coding_plan_providers(db)
            elif sys.argv[1] == "update" and len(sys.argv) > 2:
                provider_id = int(sys.argv[2])
                await update_existing_provider(db, provider_id)
            else:
                print("Usage:")
                print("  python init_coding_plan.py           # Create new provider")
                print("  python init_coding_plan.py list      # List providers")
                print("  python init_coding_plan.py update <id>  # Update provider")
        else:
            # 创建新的 Coding Plan Provider
            await create_coding_plan_provider(db)
            
            # 列出所有 Coding Plan Providers
            print("\n")
            await list_coding_plan_providers(db)


if __name__ == "__main__":
    asyncio.run(main())
