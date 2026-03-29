# API Gateway V2 架构文档

## 概述

API Gateway V2 是一次重大架构升级，主要增加了对 **Coding Plan** 类型厂商的支持，实现了从单一 Token 计费到多种计费模式的演进，并引入了完整的风控体系。

## 核心架构变更

### 1. 计费系统重构

#### 计费策略模式 (Strategy Pattern)

```
┌─────────────────────────────────────────────────────────────┐
│                    Billing Service                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ TokenBased   │  │ RequestBased │  │ Subscription     │  │
│  │ Strategy     │  │ Strategy     │  │ Strategy         │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**支持的计费模式:**

1. **Token Based** - 按 Token 数量计费
   - 适用于: OpenAI, Anthropic, DeepSeek 等标准厂商
   - 计费单位: 积分 (1 积分 = 0.01 元)
   - 示例: GPT-4 = 30 积分/1k tokens

2. **Request Based** - 按请求次数计费
   - 适用于: Coding Plan, 阿里云百炼等订阅制厂商
   - 计费单位: CNY (人民币)
   - 定价公式: `售价 = 成本 × (1 + 利润率)`
   - 目标利润率: 30%-50%

3. **Subscription** - 订阅制计费（预留）
   - 适用于: 固定月费 + 配额模式

### 2. Coding Plan 适配器

**核心功能:**

```python
class CodingPlanAdapter(BaseProvider):
    """
    Coding Plan 专用适配器
    - 多账号池管理
    - 滚动配额追踪
    - 流量整形
    - 异常检测
    - 自动故障转移
    """
```

**工作流程:**

```
1. 账号选择 → 2. 配额检查 → 3. 流量整形 → 4. API 调用 → 5. 健康更新
```

### 3. 风控系统 (Risk Control)

#### 3.1 多账号池管理 (PoolManager)

- **功能:** 管理多个 API Key，动态分配请求
- **选择策略:** 加权随机 + 健康度评分
- **健康评分:** 基于成功率、响应时间、连续错误数

```python
# 配置示例
pool_size = 5  # 账号池大小
health_score_threshold = 50  # 健康度阈值
```

#### 3.2 滚动配额追踪 (QuotaTracker)

**配额窗口:**

| 窗口类型 | 默认限额 | 重置周期 |
|---------|---------|---------|
| 5小时   | 6,000   | 5小时滚动 |
| 周      | 45,000  | 7天滚动   |
| 月      | 90,000  | 30天滚动  |

**配额检查:**

```python
tracker = QuotaTracker(db, key_id)
is_available, details = await tracker.check_quota()
success = await tracker.consume_quota(1)
```

#### 3.3 流量整形 (TrafficShaper)

**控制策略:**

- **QPS 限制:** 0.5-2.0（随机范围内）
- **随机延迟:** 100-500ms
- **突发平滑:** 避免瞬间高峰

```python
config = RateLimitConfig(
    min_qps=0.5,
    max_qps=2.0,
    jitter_ms_min=100,
    jitter_ms_max=500,
)
shaper = TrafficShaper(key_id, config)
wait_time = await shaper.acquire()
```

#### 3.4 异常检测 (AnomalyDetector)

**检测类型:**

| 异常类型 | 触发条件 | 严重级别 |
|---------|---------|---------|
| 连续错误 | >= 5 次 | Medium/High |
| 高延迟 | > 10s | Medium |
| 高错误率 | > 50% | High |
| 配额耗尽 | > 95% | Critical |
| 被限流 | 触发限流 | Medium |

#### 3.5 故障转移 (FailoverManager)

**转移策略:**

1. **同厂商切换:** 尝试同一 Provider 的其他账号
2. **跨厂商降级:** 切换到备用 Provider
3. **熔断机制:** 连续失败时暂停使用该账号

```python
# 熔断器配置
circuit_breaker = CircuitBreaker(
    failure_threshold=5,      # 触发熔断的失败次数
    recovery_timeout=60,      # 恢复时间（秒）
    half_open_max_calls=3,    # 半开状态最大尝试数
)
```

## 定价策略

### 按请求计费定价

```
售价 = 上游成本 × (1 + 利润率)

示例:
- 上游成本: 0.0004 元/请求 (月费 30 元 / 75000 请求)
- 利润率: 50%
- 售价: 0.0004 × 1.5 = 0.0006 元/请求
```

### 定价配置示例

```python
# 不同档次定价
PRICING_TIERS = {
    "basic": {
        "cost_per_request": 0.0004,
        "price_per_request": 0.0006,
        "margin": 0.50,
    },
    "premium": {
        "cost_per_request": 0.0005,
        "price_per_request": 0.0007,
        "margin": 0.40,
    },
}
```

## 数据库模型

### 新增表

1. **provider_billing_configs** - 计费配置
2. **upstream_key_quotas** - 配额追踪
3. **request_logs** - 请求日志（支持按请求计费）

### 修改表

1. **upstream_providers** - 新增 `adapter_type`, `risk_pool_size`

## 使用示例

### 配置 Coding Plan Provider

```python
# 1. 创建 Provider
provider = UpstreamProvider(
    name="阿里云百炼",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    adapter_type="coding_plan",  # 关键配置
    risk_pool_size=5,
)

# 2. 配置计费
billing = ProviderBillingConfig(
    provider_id=provider.id,
    billing_mode=BillingMode.REQUEST,
    cost_per_request=Decimal("0.0004"),
    price_per_request=Decimal("0.0006"),
    enable_risk_control=True,
)

# 3. 添加多个 API Key
for i in range(5):
    key = UpstreamKey(
        provider_id=provider.id,
        encrypted_key=encrypt_data(f"sk-api-key-{i}"),
    )
```

### API 调用

```bash
# 使用 Coding Plan 模型
curl http://localhost:8082/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "coding-plan/qwen-max",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 文件结构

```
api-gateway/
├── app/
│   ├── models/
│   │   ├── billing.py              # 计费模型
│   │   ├── upstream.py             # 上游 Provider（已更新）
│   │   └── usage.py                # 使用日志
│   ├── services/
│   │   ├── billing/                # 计费服务
│   │   │   ├── base.py             # 计费策略基类
│   │   │   ├── token_based.py      # Token 计费
│   │   │   ├── request_based.py    # 请求计费
│   │   │   └── factory.py          # 策略工厂
│   │   ├── risk_control/           # 风控服务
│   │   │   ├── pool_manager.py     # 账号池管理
│   │   │   ├── quota_tracker.py    # 配额追踪
│   │   │   ├── traffic_shaper.py   # 流量整形
│   │   │   ├── anomaly_detector.py # 异常检测
│   │   │   └── failover.py         # 故障转移
│   │   └── proxy_service_v2.py     # 新版转发服务
│   └── providers/
│       └── adapters/
│           └── coding_plan.py      # Coding Plan 适配器
├── migrate_coding_plan.py          # 数据库迁移脚本
├── init_coding_plan.py             # 配置示例脚本
└── test_coding_plan.py             # 测试脚本
```

## 测试

```bash
# 运行测试
cd api-gateway
source venv/bin/activate
python3.12 test_coding_plan.py

# 配置示例 Provider
python3.12 init_coding_plan.py

# 查看所有 Coding Plan Provider
python3.12 init_coding_plan.py list
```

## 性能优化建议

1. **账号池大小:** 建议 5-10 个账号，根据并发需求调整
2. **QPS 限制:** 根据厂商限制设置，避免触发限流
3. **随机延迟:** 100-500ms，平滑请求分布
4. **熔断阈值:** 连续 5 次失败触发熔断，5分钟后尝试恢复

## 监控指标

| 指标 | 说明 | 告警阈值 |
|-----|------|---------|
| Pool Health | 账号池健康度 | < 50% |
| Quota Usage | 配额使用率 | > 80% |
| Error Rate | 错误率 | > 10% |
| Response Time | 响应时间 | > 5s |
| Active Accounts | 可用账号数 | < 2 |

## 回滚计划

如需回滚到 V1 版本:

```bash
# 1. 还原数据库
python migrate_coding_plan.py rollback

# 2. 切换路由
# 修改 app/routers/proxy.py
# 使用 ProxyService 替代 ProxyServiceV2

# 3. 重启服务
```

## 总结

API Gateway V2 通过引入策略模式计费、Coding Plan 专用适配器和完整的风控体系，实现了：

1. **灵活的计费模式:** 支持 Token/Request/Subscription 多种计费
2. **高可用架构:** 多账号池、自动故障转移、熔断机制
3. **风控能力:** 滚动配额、流量整形、异常检测
4. **盈利保障:** 30-50% 利润率，精准成本控制

适用于 Coding Plan、阿里云百炼等订阅制厂商的接入和管理。
