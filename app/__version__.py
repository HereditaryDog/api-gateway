"""
API Gateway 版本信息
"""
__version__ = "2.0.1"
__title__ = "API Gateway"
__description__ = "LLM API 聚合转发平台"
__author__ = "HereditaryDog"
__license__ = "MIT"
__url__ = "https://github.com/HereditaryDog/api-gateway"

# 版本历史
VERSION_HISTORY = [
    {
        "version": "2.0.1",
        "date": "2026-03-29",
        "changes": [
            "配置管理：环境变量优先于 YAML/默认值",
            "启动流程：自动创建管理员账号",
            "错误处理：修复代理层上游错误处理",
            "代码质量：修复导入问题，处理 Pydantic v2 警告",
            "Docker 部署：优化容器配置，添加健康检查",
            "架构重构：Provider 分层架构、注册系统、风控体系",
            "用户自助服务：API Key 管理、资料更新、密码修改",
        ]
    },
    {
        "version": "2.0.0",
        "date": "2026-03-29",
        "changes": [
            "重大架构升级：Coding Plan 支持",
            "多种计费模式：Token/Request/Subscription",
            "风控系统：多账号池、滚动配额、流量整形、异常检测、故障转移",
            "新增数据库模型：billing_configs, key_quotas, request_logs",
        ]
    },
]
