# Changelog

所有重要的变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.0.1] - 2026-03-29

### 🔧 修复和改进

#### 配置管理
- **修复** `Settings.from_yaml()` 优先级问题
- 环境变量 (`DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`) 现在优先于 YAML/默认值
- 更适合 Docker 部署场景

#### 启动流程
- **新增** `bootstrap.py` 自动创建管理员账号
- 应用启动时检查并创建默认管理员，避免 fresh deploy 登录失败

#### 错误处理
- **修复** 代理层上游错误处理逻辑
- 统一包装上游错误，正确识别 SSE 非 2xx 和无效 JSON
- 流式和非流式响应都能正确触发计费回滚

#### 代码质量
- **修复** `request_based.py` 缺失 `UpstreamKey` 导入
- **清理** 前端登录页预填账号密码
- **处理** Pydantic v2 警告

#### 测试
- **新增** `pytest.ini` 配置，异步测试正确执行 (4 passed)

#### Docker
- **优化** `Dockerfile` 和 `docker-compose.yml`
- 默认使用 SQLite 持久化
- 添加健康检查
- db 和 redis 改为可选 profile

---

## [2.0.0] - 2026-03-29

### 🚀 重大架构升级 - Coding Plan 支持

#### 新增
- **计费系统重构** - 支持多种计费模式（Token/Request/Subscription）
  - `TokenBasedStrategy` - 按 Token 数量计费（标准厂商）
  - `RequestBasedStrategy` - 按请求次数计费（Coding Plan 厂商）
  - `BillingStrategyFactory` - 自动选择计费策略
  
- **Coding Plan 适配器** - 专用适配器处理订阅制厂商
  - 多账号池管理（PoolManager）
  - 滚动配额追踪（5小时/周/月窗口）
  - 流量整形（QPS 限制 + 随机延迟）
  - 异常检测与自动故障转移
  
- **风控系统** - 完整的风险控制体系
  - 多账号池管理 - 健康评分、动态权重
  - 滚动配额追踪 - 自动重置、配额预警
  - 流量整形 - 突发流量平滑
  - 异常检测 - 连续错误、高延迟、配额耗尽检测
  - 故障转移 - 同厂商切换、跨厂商降级、熔断机制

- **数据库模型扩展**
  - `provider_billing_configs` - 计费配置表
  - `upstream_key_quotas` - 配额追踪表
  - `request_logs` - 请求日志表（支持按请求计费）

#### 变更
- **代理服务升级** - `ProxyServiceV2` 集成新计费系统和风控
- **Provider 模型** - 新增 `adapter_type` 和 `risk_pool_size` 字段
- **API 路由** - 更新为使用 V2 服务

#### 定价策略
- 按请求计费：售价 = 成本 × (1 + 利润率)
- 目标利润率：30% - 50%
- 示例：成本 0.0004 元/请求 → 售价 0.0006 元/请求（50% 利润）

#### 文件结构
```
app/
├── models/billing.py              # 新增计费模型
├── services/billing/              # 新增计费服务
├── services/risk_control/         # 新增风控服务
├── providers/adapters/coding_plan.py  # 新增适配器
└── services/proxy_service_v2.py   # 新版代理服务
```

---

## [1.2.0] - 2026-03-29

### 新增
- 接入 Kimi Code (Moonshot) API
- 支持 8 个 Kimi 模型
- 修复多 Provider 转发逻辑

---

## [1.1.0] - 2026-03-29

### 新增
- 接入火山引擎（豆包大模型）API
- 支持 12 个豆包模型
- 自定义 Provider 配置

### 修复
- 自定义 Provider 转发逻辑

---

## [1.0.0] - 2026-03-29

### 初始版本
- FastAPI + SQLAlchemy 异步架构
- 基于 Token 的积分计费系统
- 双阶段计费（预扣 + 确认/回滚）
- 上游 Provider 管理
- API Key 认证
- 使用日志记录

---

## 版本说明

- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能新增
- **修订号**：向下兼容的问题修复
