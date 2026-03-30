"""
OpenAI 兼容格式 Provider
适用于 OpenAI、DeepSeek、SiliconFlow 等 OpenAI 兼容接口的厂商
"""
import httpx
import json
from typing import Dict, Any, AsyncGenerator
from app.providers.base import BaseProvider


class OpenAICompatProvider(BaseProvider):
    """OpenAI 兼容格式 Provider"""

    async def chat_completion(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        """非流式聊天完成"""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "stream": False,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()

    async def chat_completion_stream(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成"""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "stream": True,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, headers=headers, timeout=60) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"

    async def embeddings(
        self,
        model: str,
        input_data: str,
        **kwargs
    ) -> Dict[str, Any]:
        """嵌入接口"""
        url = f"{self.base_url}/embeddings"
        
        payload = {
            "model": model,
            "input": input_data,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
