# 🔀 API Gateway

[![Version](https://img.shields.io/badge/version-0.0.3-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)

> **轻量级 LLM API 聚合网关** - 统一管理多厂商 API，积分计费，智能负载均衡

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

### 💰 积分计费系统
- **双阶段计费**: 预扣 + 确认/回滚机制
- **失败保护**: 调用失败自动退还积分
- **精确计费**: 不同模型不同积分成本

### 🛡️ 安全特性
- **Fernet 加密** - API Keys 加密存储
- **bcrypt 哈希** - 用户密码安全存储
- **SSRF 防护** - 厂商 URL 白名单机制
- **请求限流** - 防止恶意调用

### 📊 运维监控
- **深色主题** - 专业运维风格界面
- **实时数据** - 请求数、Token、积分实时统计
- **可视化图表** - 趋势图、分布图一目了然
- **Key 池管理** - 多 Key 健康度监控

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
# Windows
python run.py

# 或
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

访问 http://localhost:8080

---

## 📖 使用指南

### 1. 添加上游 API Key

1. 登录管理后台 (http://localhost:8080)
2. 进入「Key 池管理」页面
3. 点击「添加 Key」按钮
4. 选择提供商，粘贴你的 API Key

### 2. 创建用户并充值

1. 进入「用户管理」页面
2. 点击「添加用户」
3. 设置用户名、密码和初始积分

### 3. 调用 API

```python
from openai import OpenAI

client = OpenAI(
    api_key="用户的API Key",  # 从管理后台获取
    base_url="http://localhost:8080/v1",
)

# 非流式调用
response = client.chat.completions.create(
    model="openai/gpt-4",  # 格式: provider/model
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# 流式调用
response = client.chat.completions.create(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="")
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

## 💰 积分成本表

| 模型 | Provider | 积分/1K tokens |
|------|----------|----------------|
| gpt-4 | OpenAI | 30 |
| gpt-4o | OpenAI | 5 |
| gpt-3.5-turbo | OpenAI | 1 |
| claude-3-opus | Anthropic | 15 |
| claude-3-sonnet | Anthropic | 3 |
| deepseek-chat | DeepSeek | 1 |
| gemini-pro | Google | 1 |

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

## 📝 更新日志

查看 [CHANGELOG.md](./CHANGELOG.md) 了解版本更新历史。

---

## 📄 许可证

[MIT License](./LICENSE) © 2026 HereditaryDog

---

## 💬 支持

如有问题，欢迎提交 [Issue](https://github.com/HereditaryDog/api-gateway/issues) 或联系作者。

**Star 🌟 这个项目如果它对你有帮助！**
