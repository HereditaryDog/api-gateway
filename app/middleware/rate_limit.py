import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
import asyncio


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
        self.lock = asyncio.Lock()
    
    async def dispatch(self, request: Request, call_next):
        # 获取客户端标识
        client_id = self._get_client_id(request)
        
        async with self.lock:
            now = time.time()
            
            # 清理过期记录
            if client_id in self.requests:
                self.requests[client_id] = [
                    ts for ts in self.requests[client_id] 
                    if now - ts < 60
                ]
            else:
                self.requests[client_id] = []
            
            # 检查限流
            if len(self.requests[client_id]) >= self.requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Try again later."
                )
            
            # 记录请求
            self.requests[client_id].append(now)
        
        response = await call_next(request)
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用 API Key
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return f"apikey:{auth[7:16]}"
        
        # 使用 IP 地址
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        client = request.client
        if client:
            return f"ip:{client.host}"
        
        return "unknown"
