# 🔀 API Gateway

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)

> **专业级 LLM API 聚合网关 V2** - 统一管理多厂商 API，支持 Token/Request 双计费模式，Coding Plan 风控体系，深色主题可视化运维

[English](./README_EN.md) | 中文 | [更新日志](./CHANGELOG.md)

---

## 📸 预览

![Dashboard](https://via.placeholder.com/800x400/1a1f2e/3b82f6?text=Dashboard+Preview)

---

## ✨ 核心特性

### 🔌 多厂商支持
- **OpenAI** - GPT-4, GPT-4o, GPT-3.5-turbo
- **Anthropic** - Claude-3 Opus, Sonnet, Haiku
- **DeepSeek** - DeepSeek Chat, Coder, Reasoner
- **Google** - Gemini Pro, Gemini Flash
- **SiliconFlow** - 多种开源模型
- **Moonshot** - Moonshot AI 系列
- **火山引擎** - 豆包大模型系列
- **Coding Plan** - 订阅制厂商（阿里云百炼等）

### 💰 灵活计费系统
- **双阶段计费**: 预扣 + 确认/回滚机制
- **多种模式**: 支持 Token/Request/Subscription 计费
- **Coding Plan**: 按请求计费，30-50% 利润率
- **失败保护**: 调用失败自动退还

### 🛡️ 风控体系
- **多账号池** - 动态负载均衡，健康度评分
- **滚动配额** - 5小时/周/月窗口管理
- **流量整形** - QPS 限制 + 随机延迟
- **故障转移** - 自动切换 + 熔断机制
- **Fernet 加密** - API Keys 加密存储

### 📊 可视化运维
- **深色主题** - 专业级深色 UI，参考行业标杆设计
- **双端界面** - 用户端 + 管理端双界面
- **数据可视化** - Chart.js 图表（趋势图、环形图）
- **实时监控** - 请求数、Token、积分实时统计

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- (可选) PostgreSQL 14+ / Redis

### 1. 克隆项目

```bash
git clone https://github.com/HereditaryDog/api-gateway.git
cd api-gateway
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，设置安全密钥
# SECRET_KEY=your-secret-key
```

### 4. 初始化数据库

```bash
# 创建管理员账号
python fix_login.py
```

默认管理员账号：
- 用户名: `admin`
- 密码: `admin123`

### 5. 启动服务

```bash
# 使用 Python 3.12+（推荐）
python run.py

# 或指定端口
PORT=8082 python run.py
```

### 6. 访问系统

| 界面 | 地址 | 说明 |
|------|------|------|
| 用户端 | http://localhost:8080 | 普通用户仪表盘 |
| 管理端 | http://localhost:8080/admin.html | 管理员运维监控 |
| API文档 | http://localhost:8080/docs | Swagger 文档 |

**默认账号**: `admin` / `admin123`

---

## 📖 使用指南

### 用户端功能

#### 1. 仪表盘
- 查看余额、API密钥、请求数、消费统计
- Token 使用趋势图表
- 模型分布环形图
- 最近使用记录

#### 2. API 密钥管理
- 创建和管理 API 密钥
- 查看密钥用量统计
- 一键复制密钥

#### 3. 使用记录
- 详细的调用日志
- 支持按时间范围筛选
- 导出 CSV 数据

#### 4. 兑换码充值
- 使用兑换码充值余额
- 查看充值历史

### 管理端功能

#### 1. Key 池管理
- 添加上游 API Keys
- 监控 Key 健康状态
- 多厂商统一管理

#### 2. 用户管理
- 创建和管理用户
- 积分充值和调整
- 查看用户使用情况

### 2. 创建用户并充值

1. 进入「用户管理」页面
2. 点击「添加用户」
3. 设置用户名、密码和初始积分

### 3. 调用 API

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxxxxxxxxxxxx",  # 从用户端获取
    base_url="http://localhost:8080/v1",
)

# 支持的模型格式: provider/model
# - openai/gpt-4
# - anthropic/claude-3-opus
# - deepseek/deepseek-chat

response = client.chat.completions.create(
    model="openai/gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

---

## 🔌 API 接口文档

启动服务后访问：http://localhost:8080/docs

### 主要接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/users/me` | 获取当前用户 |
| GET | `/api/users/me/points` | 查询积分余额 |
| GET | `/api/usage/dashboard` | 仪表盘统计 |
| GET | `/api/usage/logs` | 使用日志 |
| GET | `/api/upstream/keys` | Key 池列表 |
| POST | `/v1/chat/completions` | 聊天完成 |
| GET | `/v1/models` | 模型列表 |

---

## 🏗️ 项目结构

```
api-gateway/
├── app/
│   ├── __version__.py      # 版本信息
│   ├── api/                # API 接口层
│   ├── core/               # 核心配置
│   ├── models/             # 数据库模型
│   ├── providers/          # 厂商适配器
│   ├── routers/            # 路由定义
│   ├── schemas/            # Pydantic 模型
│   ├── services/           # 业务逻辑
│   └── middleware/         # 中间件
├── frontend/               # 前端界面
├── data/                   # 数据库文件
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖列表
└── README.md               # 项目说明
```

---

## 💰 计费模式

### Token 计费（标准厂商）

| 模型 | Provider | 积分/1K tokens |
|------|----------|----------------|
| gpt-4 | OpenAI | 30 |
| gpt-4o | OpenAI | 5 |
| gpt-3.5-turbo | OpenAI | 1 |
| claude-3-opus | Anthropic | 15 |
| claude-3-sonnet | Anthropic | 3 |
| deepseek-chat | DeepSeek | 1 |
| gemini-pro | Google | 1 |

### Request 计费（Coding Plan）

适用于订阅制厂商，按请求次数计费：

```
售价 = 成本 × (1 + 利润率)

示例配置:
- 上游成本: 0.0004 元/请求
- 利润率: 50%
- 售价: 0.0006 元/请求 (约 0.06 积分)
```

**配置 Coding Plan Provider:**

```bash
# 快速配置
python init_coding_plan.py

# 查看配置
python init_coding_plan.py list
```

---

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t api-gateway .

# 运行容器
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e SECRET_KEY=your-secret \
  api-gateway
```

或使用 Docker Compose:

```bash
docker-compose up -d
```

---

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📚 架构文档

- [CHANGELOG.md](./CHANGELOG.md) - 版本更新历史
- [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md) - V2 架构详细设计

---

---

## 📄 许可证

[MIT License](./LICENSE) © 2026 HereditaryDog

---

## 💬 支持

如有问题，欢迎提交 [Issue](https://github.com/HereditaryDog/api-gateway/issues) 或联系作者。

**Star 🌟 这个项目如果它对你有帮助！**
