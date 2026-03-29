"""
Coding Plan 架构测试脚本

测试内容:
1. 数据库模型
2. 计费策略
3. 风控组件
4. Provider 适配器

运行方式:
    cd api-gateway && source venv/bin/activate && python3.12 test_coding_plan.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from decimal import Decimal
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.database import Base, get_db
from app.models.billing import (
    ProviderBillingConfig,
    UpstreamKeyQuota,
    RequestLog,
    BillingMode,
    SubscriptionType,
    QuotaWindowType,
)
from app.models.upstream import UpstreamProvider, UpstreamKey, ProviderType
from app.models.user import User
from app.services.billing import (
    BillingStrategyFactory,
    TokenBasedBillingStrategy,
    RequestBasedBillingStrategy,
)
from app.services.risk_control import (
    PoolManager,
    QuotaTracker,
    TrafficShaper,
    RateLimitConfig,
    AnomalyDetector,
    get_anomaly_detector,
)


# 使用 SQLite 内存数据库测试
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def init_test_db():
    """初始化测试数据库"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return async_session


async def test_billing_models():
    """测试计费模型"""
    print("=" * 60)
    print("Testing Billing Models")
    print("=" * 60)
    
    async_session = await init_test_db()
    
    async with async_session() as db:
        # 创建 Provider
        provider = UpstreamProvider(
            name="Test Coding Plan",
            provider_type=ProviderType.CUSTOM,
            base_url="https://api.example.com",
            adapter_type="coding_plan",
            risk_pool_size=5,
        )
        db.add(provider)
        await db.flush()
        print(f"✓ Created provider: {provider.id}")
        
        # 创建计费配置
        config = ProviderBillingConfig(
            provider_id=provider.id,
            billing_mode=BillingMode.REQUEST,
            cost_per_request=Decimal("0.0004"),
            price_per_request=Decimal("0.0006"),
            subscription_type=SubscriptionType.CODING_PLAN,
            quota_window_type=QuotaWindowType.ROLLING_5H,
            quota_requests=6000,
            enable_risk_control=True,
            min_qps_limit=Decimal("0.5"),
            max_qps_limit=Decimal("2.0"),
            jitter_ms_min=100,
            jitter_ms_max=500,
        )
        db.add(config)
        await db.commit()
        print(f"✓ Created billing config")
        print(f"  - Billing mode: {config.billing_mode.value}")
        print(f"  - Cost per request: {config.cost_per_request} CNY")
        print(f"  - Price per request: {config.price_per_request} CNY")
        print(f"  - Profit margin: {(float(config.price_per_request) / float(config.cost_per_request) - 1) * 100:.1f}%")
        
        # 创建 Key
        key = UpstreamKey(
            provider_id=provider.id,
            encrypted_key="encrypted_test_key",
            weight=100,
            rpm_limit=60,
        )
        db.add(key)
        await db.flush()
        print(f"✓ Created key: {key.id}")
        
        # 创建配额记录
        quota = UpstreamKeyQuota(
            key_id=key.id,
            window_5h_limit=6000,
            window_week_limit=45000,
            window_month_limit=90000,
        )
        db.add(quota)
        await db.commit()
        print(f"✓ Created quota record")
        
        # 验证关系
        result = await db.execute(
            select(ProviderBillingConfig).where(
                ProviderBillingConfig.provider_id == provider.id
            )
        )
        fetched_config = result.scalar_one()
        print(f"✓ Verified billing config relationship")
        
        return provider, config, key, quota


async def test_billing_strategies():
    """测试计费策略"""
    print("\n" + "=" * 60)
    print("Testing Billing Strategies")
    print("=" * 60)
    
    async_session = await init_test_db()
    
    async with async_session() as db:
        # 测试 Token 计费策略
        print("\n1. Token Based Strategy:")
        token_strategy = TokenBasedBillingStrategy(db)
        
        # 计算成本
        cost = await token_strategy.calculate_cost("gpt-4", 1000)
        price = await token_strategy.calculate_price("gpt-4", 1000)
        print(f"  - Model: gpt-4, Tokens: 1000")
        print(f"  - Cost: {cost} points")
        print(f"  - Price: {price} points")
        
        # 测试不同模型
        for model in ["gpt-4o", "deepseek-chat", "claude-3-opus"]:
            cost = await token_strategy.calculate_cost(model, 1000)
            print(f"  - {model}: {cost} points/1k tokens")
        
        # 测试按请求计费策略
        print("\n2. Request Based Strategy:")
        
        # 创建 Provider 和配置
        provider = UpstreamProvider(
            name="Coding Plan Provider",
            provider_type=ProviderType.CUSTOM,
            base_url="https://api.example.com",
        )
        db.add(provider)
        await db.flush()
        
        config = ProviderBillingConfig(
            provider_id=provider.id,
            billing_mode=BillingMode.REQUEST,
            cost_per_request=Decimal("0.0004"),
            price_per_request=Decimal("0.0006"),
        )
        db.add(config)
        await db.commit()
        
        request_strategy = RequestBasedBillingStrategy(db, provider.id)
        
        cost = await request_strategy.calculate_cost("any-model")
        price = await request_strategy.calculate_price("any-model")
        
        print(f"  - Cost per request: {float(cost):.6f} CNY")
        print(f"  - Price per request: {float(price):.6f} CNY")
        print(f"  - Profit margin: {(float(price) / float(cost) - 1) * 100:.1f}%")
        
        # 测试定价信息
        pricing_info = await request_strategy.get_pricing_info()
        print(f"  - Pricing info: {pricing_info}")


async def test_risk_control_components():
    """测试风控组件"""
    print("\n" + "=" * 60)
    print("Testing Risk Control Components")
    print("=" * 60)
    
    async_session = await init_test_db()
    
    async with async_session() as db:
        # 创建 Provider 和多个 Keys
        provider = UpstreamProvider(
            name="Coding Plan Pool",
            provider_type=ProviderType.CUSTOM,
            base_url="https://api.example.com",
            adapter_type="coding_plan",
            risk_pool_size=3,
        )
        db.add(provider)
        await db.flush()
        
        # 创建多个 Key
        keys = []
        for i in range(3):
            key = UpstreamKey(
                provider_id=provider.id,
                encrypted_key=f"encrypted_key_{i}",
                weight=100,
                priority=i,
            )
            db.add(key)
            await db.flush()
            keys.append(key)
            
            # 创建配额记录
            quota = UpstreamKeyQuota(
                key_id=key.id,
                window_5h_used=i * 100,
                window_5h_limit=6000,
            )
            db.add(quota)
        
        await db.commit()
        
        print(f"\n1. Pool Manager:")
        pool_manager = PoolManager(db, provider.id)
        await pool_manager.refresh_pool()
        
        stats = await pool_manager.get_pool_stats()
        print(f"  - Total accounts: {stats['total_accounts']}")
        print(f"  - Available accounts: {stats['available_accounts']}")
        print(f"  - Average health score: {stats['average_health_score']}")
        
        # 测试账号选择
        account = await pool_manager.select_account()
        if account:
            print(f"  - Selected account: key_id={account.key_id}")
        
        print(f"\n2. Quota Tracker:")
        tracker = QuotaTracker(db, keys[0].id)
        
        # 检查配额
        is_available, details = await tracker.check_quota()
        print(f"  - Quota available: {is_available}")
        print(f"  - 5h window: {details['window_5h']['used']}/{details['window_5h']['limit']}")
        
        # 消耗配额
        success = await tracker.consume_quota(1)
        print(f"  - Consume 1 quota: {success}")
        
        # 获取统计
        stats = await tracker.get_usage_stats()
        print(f"  - Usage stats retrieved")
        
        print(f"\n3. Traffic Shaper:")
        config = RateLimitConfig(
            min_qps=0.5,
            max_qps=2.0,
            jitter_ms_min=100,
            jitter_ms_max=200,
        )
        shaper = TrafficShaper(keys[0].id, config)
        
        # 模拟请求
        wait_times = []
        for _ in range(3):
            wait = await shaper.acquire()
            wait_times.append(wait)
        
        print(f"  - Wait times: {[f'{w:.3f}s' for w in wait_times]}")
        
        stats = shaper.get_stats()
        print(f"  - Current QPS: {stats['current_qps']}")
        
        print(f"\n4. Anomaly Detector:")
        detector = get_anomaly_detector()
        
        # 模拟异常检测
        event = detector.detect_consecutive_errors(
            key_id=keys[0].id,
            provider_id=provider.id,
            consecutive_errors=5
        )
        if event:
            print(f"  - Detected: {event.anomaly_type.value}")
            print(f"  - Severity: {event.severity}")
        
        # 检测配额耗尽
        event = detector.detect_quota_exhausted(
            key_id=keys[0].id,
            provider_id=provider.id,
            window_type="window_5h",
            used=5800,
            limit=6000
        )
        if event:
            print(f"  - Detected: {event.anomaly_type.value}")
            print(f"  - Severity: {event.severity}")
        
        stats = detector.get_stats()
        print(f"  - Total events: {stats['total_events']}")


async def test_pricing_calculation():
    """测试定价计算"""
    print("\n" + "=" * 60)
    print("Testing Pricing Calculation")
    print("=" * 60)
    
    async_session = await init_test_db()
    
    async with async_session() as db:
        # 创建不同定价策略的 Provider
        providers = [
            ("Basic Plan", Decimal("0.0004"), Decimal("0.0006")),   # 50% margin
            ("Premium Plan", Decimal("0.0005"), Decimal("0.0007")), # 40% margin
            ("Economy Plan", Decimal("0.0003"), Decimal("0.0004")), # 33% margin
        ]
        
        print("\nPricing Tiers:")
        for name, cost, price in providers:
            margin = (price / cost - 1) * 100
            print(f"  {name}:")
            print(f"    - Cost: {float(cost):.6f} CNY/request")
            print(f"    - Price: {float(price):.6f} CNY/request")
            print(f"    - Margin: {margin:.1f}%")
        
        # 模拟请求定价
        print("\nExample Request Costs:")
        
        # 创建配置
        provider = UpstreamProvider(
            name="Test Provider",
            provider_type=ProviderType.CUSTOM,
            base_url="https://api.example.com",
        )
        db.add(provider)
        await db.flush()
        
        config = ProviderBillingConfig(
            provider_id=provider.id,
            billing_mode=BillingMode.REQUEST,
            cost_per_request=Decimal("0.0004"),
            price_per_request=Decimal("0.0006"),
        )
        db.add(config)
        await db.commit()
        
        strategy = RequestBasedBillingStrategy(db, provider.id)
        
        # 不同请求量的成本
        for num_requests in [100, 1000, 10000]:
            price = await strategy.calculate_price("any")
            total = float(price) * num_requests
            print(f"  {num_requests} requests: {total:.4f} CNY ({total * 100:.2f} 积分)")


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Coding Plan Architecture Tests")
    print("=" * 60)
    
    try:
        await test_billing_models()
        await test_billing_strategies()
        await test_risk_control_components()
        await test_pricing_calculation()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
