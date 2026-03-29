# API Gateway 开发计划

> 完整计费系统 + API Key 管理 + 兑换码系统

---

## 📋 开发阶段

### 阶段 1: 核心计费系统改造 (2-3天)

#### 1.1 数据库模型更新
```
├── 修改 User 模型
│   ├── points_balance → balance (美元)
│   └── 添加 currency 字段 (USD/CNY)
│
├── 新建 UserApiKey 模型
│   ├── id, user_id
│   ├── name (密钥名称)
│   ├── api_key (密钥值)
│   ├── group_id (分组ID)
│   ├── ip_whitelist (IP白名单JSON)
│   ├── monthly_limit (月度额度限制)
│   ├── total_limit (总额度限制)
│   ├── rate_limit (速率限制)
│   ├── expires_at (过期时间)
│   ├── is_active
│   └── created_at, updated_at
│
├── 新建 ApiKeyGroup 模型
│   ├── id, user_id
│   ├── name (分组名称)
│   └── color (分组颜色)
│
├── 新建 RedeemCode 模型
│   ├── id, code (激活码)
│   ├── amount (金额)
│   ├── is_used
│   ├── used_by (user_id)
│   ├── used_at
│   └── expires_at
│
└── 修改 Pricing 配置
    ├── 从代码移出到数据库/配置文件
    ├── 支持动态修改
    └── 支持多币种
```

#### 1.2 计费逻辑改造
- [ ] 修改 `points_service.py` → `billing_service.py`
- [ ] 支持按 Token 精确计费
- [ ] 支持多模型不同价格
- [ ] 计费日志记录

#### 1.3 API 接口
```
POST /api/billing/calculate    # 计算调用费用
GET  /api/billing/pricing      # 获取定价表
GET  /api/billing/usage        # 获取用量统计
```

---

### 阶段 2: API Key 管理系统 (2-3天)

#### 2.1 后端 API
```
# API Key 管理
GET    /api/keys                    # 获取用户的所有 API Key
POST   /api/keys                    # 创建新的 API Key
GET    /api/keys/{id}               # 获取 Key 详情
PUT    /api/keys/{id}               # 更新 Key 设置
DELETE /api/keys/{id}               # 删除 Key
POST   /api/keys/{id}/regenerate    # 重新生成 Key

# 分组管理
GET    /api/keys/groups             # 获取分组列表
POST   /api/keys/groups             # 创建分组
PUT    /api/keys/groups/{id}        # 更新分组
DELETE /api/keys/groups/{id}        # 删除分组

# Key 统计
GET    /api/keys/{id}/stats         # 获取 Key 使用统计
GET    /api/keys/{id}/logs          # 获取 Key 调用日志
```

#### 2.2 前端界面
- [ ] 创建 Key 弹窗（参考截图）
  - 名称输入
  - 分组选择
  - 自定义密钥开关
  - IP 限制开关
  - 额度限制输入
  - 速率限制开关
  - 有效期开关
  
- [ ] Key 列表页
  - 搜索/筛选
  - 分组标签
  - 用量显示
  - 操作按钮

---

### 阶段 3: 兑换码系统 (1-2天)

#### 3.1 兑换码生成（管理端）
```
POST /api/admin/redeem-codes          # 批量生成兑换码
GET  /api/admin/redeem-codes          # 获取兑换码列表
DELETE /api/admin/redeem-codes/{id}   # 删除兑换码
```

#### 3.2 兑换码验证（对接发卡网）
```
# 给发卡网提供的接口
POST /api/public/verify-redeem-code
Request:
  {
    "code": "XXXX-XXXX-XXXX",
    "signature": "HMAC签名"  // 防止伪造
  }
Response:
  {
    "valid": true,
    "amount": 10.00,
    "message": "兑换码有效，面值 $10"
  }
```

#### 3.3 用户兑换
```
POST /api/redeem          # 用户兑换激活码
GET  /api/redeem/history  # 兑换历史
```

---

### 阶段 4: 代理转发完善 (2-3天)

#### 4.1 API Key 验证中间件
- [ ] 从请求头读取 `Authorization: Bearer sk-xxx`
- [ ] 验证 Key 是否有效
- [ ] 检查 IP 白名单
- [ ] 检查额度限制
- [ ] 检查速率限制

#### 4.2 计费中间件
- [ ] 预估 Token 数预扣费
- [ ] 实际 Token 数多退少补
- [ ] 失败请求自动退款

#### 4.3 支持的模型
```
OpenAI:
  - gpt-4o, gpt-4o-mini
  - gpt-4-turbo, gpt-4
  - gpt-3.5-turbo
  - text-embedding-3

Anthropic:
  - claude-3-opus
  - claude-3-sonnet
  - claude-3-haiku
  - claude-3-5-sonnet

DeepSeek:
  - deepseek-chat
  - deepseek-coder
  - deepseek-reasoner

国内厂商:
  - 智谱 GLM-4, GLM-4-Flash
  - 阿里通义千问
  - 百度文心一言
  - Moonshot
  - 豆包
  - 硅基流动
```

---

### 阶段 5: 用户自助注册 (1天)

#### 5.1 注册功能
```
POST /api/auth/register
{
  "username": "",
  "email": "",
  "password": "",
  "invite_code": ""  // 可选
}
```

#### 5.2 新用户福利
- 注册送 $1 体验金
- 首次充值优惠

---

## 📁 文件变更清单

### 后端
```
app/
├── models/
│   ├── user.py              # 修改: balance 字段
│   ├── user_api_key.py      # 新增: API Key 模型
│   ├── api_key_group.py     # 新增: 分组模型
│   ├── redeem_code.py       # 新增: 兑换码模型
│   └── pricing.py           # 新增: 定价配置模型
│
├── services/
│   ├── billing_service.py   # 新增: 计费服务
│   ├── api_key_service.py   # 新增: API Key 服务
│   └── redeem_service.py    # 新增: 兑换码服务
│
├── routers/
│   ├── keys.py              # 新增: API Key 路由
│   ├── billing.py           # 新增: 计费路由
│   └── redeem.py            # 新增: 兑换码路由
│
├── middleware/
│   ├── api_key_auth.py      # 新增: API Key 认证
│   └── billing_middleware.py # 新增: 计费中间件
│
└── config/
    └── pricing.yaml         # 新增: 定价配置
```

### 前端
```
frontend/
├── index.html               # 修改: 集成新 API
├── admin.html               # 修改: 添加兑换码生成
└── components/              # 新增: 可复用组件
    ├── CreateKeyModal.js
    └── RedeemModal.js
```

---

## 🔐 安全考虑

### API Key 安全
- [ ] Key 只显示一次，数据库只存哈希
- [ ] 支持 IP 白名单
- [ ] 支持额度限制（防刷）
- [ ] 速率限制（防 DDoS）

### 兑换码安全
- [ ] HMAC 签名验证（对接发卡网）
- [ ] 一次性使用
- [ ] 过期时间限制
- [ ] 使用记录追溯

### 计费安全
- [ ] 预扣费 + 确认机制
- [ ] 异常自动退款
- [ ] 余额不足自动拒绝

---

## 📊 数据结构示例

### API Key 创建请求
```json
{
  "name": "Claude Code 专用",
  "group_id": 1,
  "custom_key": false,
  "ip_whitelist": ["192.168.1.1", "10.0.0.0/8"],
  "monthly_limit": 50.00,
  "rate_limit": 60,
  "expires_at": "2026-12-31"
}
```

### 兑换码生成请求（管理端）
```json
{
  "count": 100,
  "amount": 10.00,
  "prefix": "VIP",
  "expires_at": "2026-12-31"
}
```

### 兑换码响应
```json
{
  "codes": [
    "VIP-A7X9-K2M4-P8Q1",
    "VIP-B3Y2-L7N9-R4W5",
    "..."
  ]
}
```

---

## 🚀 实施建议

### 优先级
1. **P0 (必做)**: 计费系统改造、API Key 创建
2. **P1 (重要)**: 兑换码系统、代理转发
3. **P2 (可选)**: 用户注册、统计报表

### 测试策略
- 单元测试: 计费计算准确性
- 集成测试: API Key 全流程
- 压力测试: 并发兑换、高频率调用

### 上线 checklist
- [ ] 定价配置审核
- [ ] 测试环境完整测试
- [ ] 发卡网对接测试
- [ ] 监控告警配置
- [ ] 数据备份策略

---

*计划制定: 2026-03-29*
