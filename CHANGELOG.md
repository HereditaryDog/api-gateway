# 更新日志 (Changelog)

所有 notable changes 都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [0.1.0] - 2026-03-29

### 🎨 前端重构 - 深色主题双端界面

#### 全新用户端 (index.html)
- **深色主题设计**: 参考 mkmkAPI 专业级深色 UI
- **仪表盘**: 8个统计卡片 + Chart.js 数据可视化
  - 环形饼图：模型分布统计
  - 折线图：Token 使用趋势（7/30/90天）
- **API 密钥管理**: 密钥列表、搜索筛选、一键复制
- **使用记录**: 详细调用日志、分页、导出 CSV
- **兑换码**: 余额充值、兑换历史
- **个人资料**: 账户信息、修改密码

#### 管理端升级 (admin.html)
- **统一深色主题**: 与用户端一致的视觉风格
- **顶部标题栏**: 余额显示、用户菜单、刷新按钮
- **监控大盘**: 实时数据、请求日志
- **Key 池管理**: 上游 API Keys 统一管理
- **用户管理**: 用户列表、积分充值

### 🔧 后端增强

#### 新增 API 接口
- `GET /api/usage/dashboard` - 仪表盘统计数据（支持图表）
- `GET /api/usage/stats` - 使用统计摘要
- `GET /api/usage/logs` - 详细使用日志
- `GET /admin.html` - 管理端页面路由修复

#### 依赖更新
- 升级支持 Python 3.12
- 添加 email-validator 邮箱验证
- 添加 greenlet 异步支持
- 固定 bcrypt==4.0.1 避免兼容性问题

### 🐛 修复
- 修复 `init_admin.py` 缺少 `commit()` 导致用户创建失败
- 修复 `/admin.html` 路由 404 问题
- 修复 UserService 事务提交问题

---

## [0.0.3] - 2026-03-29

### Bug 修复

#### 前端问题
- **修复页面切换**: 重写 admin.html，修复所有页面无法显示的问题
- **添加完整视图**: Key 池管理、用户管理、请求日志页面均可正常显示
- **修复数据加载**: 优化 API 数据加载和错误处理

#### API 修复
- **修复 Dashboard API**: 添加缺失的 `today_cost` 字段
- **修复用户列表**: 正确处理空数据和类型转换

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

### [0.2.0] - 计划功能

- [ ] 按 Token 数精确计费（当前按预估）
- [ ] 更多厂商支持 (Azure, Cohere, AI21 等)
- [ ] 用户自助注册功能
- [ ] 积分充值/提现流程（在线支付）
- [ ] 限流优化 (基于 Redis)
- [ ] 多节点部署支持
- [ ] 告警通知系统（邮件/钉钉/企业微信）
- [ ] 使用报表导出（PDF/Excel）
- [ ] 模型价格管理后台
- [ ] 多语言支持 (i18n)

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
