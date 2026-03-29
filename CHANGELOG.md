# 更新日志 (Changelog)

所有 notable changes 都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [0.0.2] - 2026-03-29

### Bug 修复

#### 数据库兼容性
- **修复 User 模型**: 所有字段添加正确的默认值和 nullable 约束
- **修复 ORM 模型**: 添加 `to_dict()` 方法用于安全序列化
- **修复 Pydantic 验证**: 添加 `field_validator` 处理 None 值和类型转换
- **修复数据库初始化**: 创建完整的数据库初始化脚本 `init_db.py`

#### 登录问题
- **修复登录验证**: 优化错误提示信息（中文）
- **修复用户序列化**: 解决 UserResponse 模型验证失败问题
- **修复默认值**: 所有数值字段默认值为 0，布尔字段默认为 False

#### 其他修复
- 修复 `total_quota` 和 `used_quota` 为 None 导致的计算错误
- 修复 `rate_limit` 为 None 导致的类型错误
- 修复 `is_active` 和 `is_admin` 为 None 时的布尔判断

---

## [0.0.1] - 2026-03-29

### 初始版本发布 🚀

首个可用版本，包含完整的 API 聚合转发功能。

### 新增功能

#### Core Features
- **多厂商 API 聚合**: 支持 OpenAI, Anthropic, DeepSeek, Gemini, SiliconFlow, Moonshot 等主流 LLM 厂商
- **积分计费系统**: 实现预扣+确认双阶段计费，失败自动回滚，精确计费
- **API Key 池管理**: 支持多 Key 自动轮询，失败自动重试，健康度监控
- **智能负载均衡**: 根据权重自动分配请求，避免单点故障

#### 安全特性
- **Fernet 加密**: 使用 Fernet 对称加密算法保护 API Keys
- **SSRF 防护**: 厂商 URL 白名单机制，只允许访问已知地址
- **bcrypt 密码哈希**: 用户密码使用 bcrypt 哈希存储

#### 管理后台
- **运维监控风格 UI**: 深色主题，数据可视化仪表盘
- **实时监控**: 请求数、Token 消耗、积分使用实时统计
- **图表展示**: Chart.js 实现趋势图、分布图
- **Key 池管理**: 可视化管理所有上游 API Keys
- **用户管理**: 支持创建用户、积分充值

#### 技术特性
- **OpenAI 兼容接口**: `/v1/chat/completions` 完全兼容 OpenAI 格式
- **流式响应**: 完整支持 SSE 流式输出
- **异步架构**: FastAPI + SQLAlchemy 异步支持
- **SQLite/PostgreSQL**: 支持两种数据库后端

### 支持的模型

| 厂商 | 模型示例 | 积分/1K tokens |
|------|---------|---------------|
| OpenAI | gpt-4, gpt-4o, gpt-3.5-turbo | 30, 5, 1 |
| Anthropic | claude-3-opus, claude-3-sonnet | 15, 3 |
| DeepSeek | deepseek-chat, deepseek-coder | 1 |
| Gemini | gemini-pro, gemini-flash | 1 |
| SiliconFlow | 多种开源模型 | 1 |
| Moonshot | moonshot-v1 | 1 |

### API 接口

- `POST /api/auth/login` - 用户登录
- `GET /api/users/me` - 获取当前用户信息
- `GET /api/upstream/keys` - 上游 Key 列表
- `POST /v1/chat/completions` - 聊天完成接口
- `GET /v1/models` - 获取支持的模型列表

### 文档

- 完整 API 文档: http://localhost:8080/docs
- 管理后台: http://localhost:8080

---

## 即将发布 (Upcoming)

### [0.1.0] - 计划功能

- [ ] 按 Token 数精确计费（当前按预估）
- [ ] 更多厂商支持 (Azure, Cohere, AI21 等)
- [ ] 用户自助注册功能
- [ ] 积分充值/提现流程
- [ ] 限流优化 (基于 Redis)
- [ ] 多节点部署支持
- [ ] 告警通知系统
- [ ] 使用报表导出

---

## 版本号说明

版本号格式: `MAJOR.MINOR.PATCH`

- **MAJOR**: 重大更新，可能包含破坏性变更
- **MINOR**: 新增功能，向后兼容
- **PATCH**: 问题修复，向后兼容

---

## 如何更新

```bash
# 拉取最新代码
git pull origin main

# 安装新依赖
pip install -r requirements.txt

# 更新数据库 (如有需要)
# 会自动执行

# 重启服务
python run.py
```
