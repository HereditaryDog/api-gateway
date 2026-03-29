"""
Provider 适配器基类
统一不同厂商的 API 接口格式
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator


class BaseProvider(ABC):
    """基础厂商适配器（全异步接口）"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    @abstractmethod
    async def chat_completion(
        self, 
        model: str, 
        messages: list, 
        **kwargs
    ) -> Dict[str, Any]:
        """聊天完成接口"""
        pass

    @abstractmethod
    async def chat_completion_stream(
        self, 
        model: str, 
        messages: list, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """聊天完成接口（流式）"""
        pass

    @abstractmethod
    async def embeddings(
        self, 
        model: str, 
        input_data: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """嵌入接口"""
        pass

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量（粗略估计）"""
        return max(1, len(text) // 4)
