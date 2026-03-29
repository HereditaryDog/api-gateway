"""
API Gateway 版本信息
"""
__version__ = "0.0.1"
__title__ = "API Gateway"
__description__ = "LLM API 聚合转发平台"
__author__ = "HereditaryDog"
__license__ = "MIT"
__url__ = "https://github.com/HereditaryDog/api-gateway"

# 版本历史
VERSION_HISTORY = [
    {
        "version": "0.0.1",
        "date": "2026-03-29",
        "changes": [
            "初始版本发布",
            "支持多厂商 API 聚合 (OpenAI, Anthropic, DeepSeek, Gemini 等)",
            "实现积分计费系统 (预扣+确认双阶段)",
            "添加运维监控风格管理后台",
            "支持流式响应 (SSE)",
            "实现 API Key 池管理和负载均衡",
            "添加 Fernet 加密保护敏感数据",
            "实现 SSRF 安全防护",
        ]
    }
]
