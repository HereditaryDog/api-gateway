# 🔀 API Gateway - LLM API 聚合转发平台

轻量级 LLM API 聚合网关，支持多厂商 API 统一接入、积分计费、智能负载均衡。

> **关键词**：LLM 网关 · API 聚合 · 积分计费 · 密钥池路由 · OpenAI 兼容

---

## 💡 项目介绍

API Gateway 是一个开源的 LLM API 聚合转发平台，帮助你：

- **托管低价 API**：收集各大平台的 Coding Plan / 开发者计划 API Keys
- **统一管理**：一个平台管理所有上游 Keys，自动负载均衡
- **积分计费**：使用积分系统对用户进行计费，支持预扣+确认双阶段
- **转售盈利**：创建用户账号，分配积分，赚取差价

---

## 🚀 快速开始

### 环境要求

- Python 3.11+

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制配置文件
cp .env.example .env
# 编辑 .env 设置密钥
```

### 3. 初始化数据库

```bash
# 创建管理员账号
python fix_login.py
```

### 4. 启动服务

```bash
# Windows
python run.py

# 或
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

访问 http://localhost:8080

默认账号：
- 用户名: `admin`
- 密码: `admin123`

---

## 📡 使用指南

### 1. 添加上游 API Key

1. 登录管理后台
2. 进入「Key 池管理」页面
3. 点击「添加 Key」
4. 选择提供商，输入你的 API Key

支持的提供商：
- OpenAI (gpt-4, gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet)
- DeepSeek (deepseek-chat, deepseek-coder)
- Google (gemini-pro, gemini-flash)
- SiliconFlow
- Moonshot

### 2. 创建用户并充值

1. 进入「用户管理」页面
2. 点击「添加用户」，设置初始积分

### 3. 调用 API

```python
from openai import OpenAI

client = OpenAI(
    api_key="用户的 API Key",
    base_url="http://localhost:8080/v1",
)

response = client.chat.completions.create(
    model="openai/gpt-4",  # 格式: provider/model
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

---

## 🏗️ 项目结构

```
api-gateway/
├── app/
│   ├── api/            # HTTP 接口层
│   ├── core/           # 核心配置
│   ├── models/         # 数据库模型
│   ├── providers/      # 厂商适配器
│   ├── routers/        # API 路由
│   ├── schemas/        # Pydantic 模型
│   ├── services/       # 业务逻辑
│   └── middleware/     # 中间件
├── frontend/           # 前端界面
├── data/               # 数据库文件
├── config.yaml         # 配置文件
└── README.md
```

---

## 🔐 安全说明

- 厂商密钥使用 **Fernet 加密** 存储，明文不入库
- 用户密码使用 **bcrypt** 哈希，不可逆
- **SSRF 防护**：只允许访问白名单中的厂商地址
- 生产环境请修改所有默认密码和密钥

---

## 📄 License

MIT License
