"""
Provider 工厂模块
"""
from typing import Optional, Dict
from app.providers.base import BaseProvider
from app.providers.openai_compat import OpenAICompatProvider

# 厂商白名单：provider 名称 → base_url
# 安全策略：只允许访问此处登记的已知厂商地址，防止 SSRF
PROVIDER_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1",
    "azure": "https://api.openai.azure.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "alibaba": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "baidu": "https://qianfan.baidubce.com/v2",
    # mock provider：仅用于开发和测试
    "mock": "http://mock.internal/v1",
}


def is_provider_allowed(provider: str) -> bool:
    """检查 provider 是否在白名单中（安全校验，防止 SSRF）"""
    return provider.lower() in PROVIDER_BASE_URLS


def create_provider(provider: str, api_key: str) -> Optional[BaseProvider]:
    """
    创建 Provider 实例
    
    Args:
        provider: provider 名称，如 "openai", "deepseek"
        api_key: API Key
    
    Returns:
        Provider 实例，如果 provider 不在白名单则返回 None
    """
    provider = provider.lower()
    base_url = PROVIDER_BASE_URLS.get(provider)
    
    if not base_url:
        return None  # provider 不在白名单，拒绝
    
    # 目前所有支持的 provider 都是 OpenAI 兼容格式
    # 如果需要特殊适配，可以在这里添加条件分支
    return OpenAICompatProvider(api_key=api_key, base_url=base_url)


def get_provider_from_model(model: str) -> tuple:
    """
    从模型名称获取 provider 和实际模型名
    
    格式: "provider/model" 或 "provider/org/model"
    例如: "openai/gpt-4", "deepseek/deepseek-chat"
    
    Returns:
        (provider, actual_model)
    """
    if '/' in model:
        parts = model.split('/', 1)
        provider = parts[0].lower()
        actual_model = parts[1]
        return provider, actual_model
    else:
        # 默认使用 openai
        return 'openai', model


def normalize_model_name(model: str) -> str:
    """
    规范化模型名称，添加 provider 前缀（如果没有）
    
    例如: "gpt-4" -> "openai/gpt-4"
    """
    if '/' in model:
        return model
    
    # 根据模型名推断 provider
    model_lower = model.lower()
    
    if 'claude' in model_lower:
        return f"anthropic/{model}"
    elif 'deepseek' in model_lower:
        return f"deepseek/{model}"
    elif 'gemini' in model_lower:
        return f"gemini/{model}"
    else:
        return f"openai/{model}"
