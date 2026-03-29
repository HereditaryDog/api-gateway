"""
流量整形服务
实施 QPS 限制、随机延迟等流量控制策略
"""
import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from collections import deque


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    min_qps: float = 0.5      # 最小 QPS
    max_qps: float = 2.0      # 最大 QPS
    jitter_ms_min: int = 100  # 最小随机延迟（毫秒）
    jitter_ms_max: int = 500  # 最大随机延迟（毫秒）
    burst_size: int = 3       # 突发请求数


class TrafficShaper:
    """
    流量整形器
    
    功能:
    1. QPS 限制（可配置范围内随机）
    2. 请求间随机延迟
    3. 突发流量平滑
    """
    
    # 全局请求时间记录（用于计算当前 QPS）
    _request_times: Dict[int, deque] = {}
    _locks: Dict[int, asyncio.Lock] = {}
    
    def __init__(self, key_id: int, config: Optional[RateLimitConfig] = None):
        self.key_id = key_id
        self.config = config or RateLimitConfig()
        self._last_request_time: Optional[float] = None
        
        # 初始化请求时间记录
        if key_id not in self._request_times:
            self._request_times[key_id] = deque(maxlen=100)
        if key_id not in self._locks:
            self._locks[key_id] = asyncio.Lock()
    
    async def acquire(self) -> float:
        """
        获取请求许可
        
        实现:
        1. 计算当前 QPS
        2. 如果超过限制，等待
        3. 添加随机延迟
        
        Returns:
            实际等待时间（秒）
        """
        async with self._locks[self.key_id]:
            wait_time = await self._calculate_wait_time()
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # 添加随机延迟（抖动）
            jitter_ms = random.randint(
                self.config.jitter_ms_min,
                self.config.jitter_ms_max
            )
            jitter_sec = jitter_ms / 1000.0
            await asyncio.sleep(jitter_sec)
            
            # 记录请求时间
            now = time.time()
            self._request_times[self.key_id].append(now)
            self._last_request_time = now
            
            total_wait = wait_time + jitter_sec
            return total_wait
    
    async def _calculate_wait_time(self) -> float:
        """计算需要等待的时间"""
        now = time.time()
        
        # 清理过期的请求记录（1分钟前）
        cutoff_time = now - 60
        request_times = self._request_times[self.key_id]
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # 计算当前 QPS
        current_qps = len(request_times) / 60.0 if request_times else 0
        
        # 在配置范围内随机选择一个目标 QPS
        target_qps = random.uniform(self.config.min_qps, self.config.max_qps)
        
        # 如果当前 QPS 低于目标，不需要等待
        if current_qps < target_qps:
            return 0
        
        # 计算需要等待的时间
        # 目标间隔 = 1 / target_qps
        target_interval = 1.0 / target_qps
        
        # 如果上次请求时间存在，计算距离上次请求的时间
        if self._last_request_time:
            elapsed = now - self._last_request_time
            if elapsed < target_interval:
                return target_interval - elapsed
        
        return 0
    
    async def try_acquire(self, timeout: float = 0) -> bool:
        """
        尝试获取请求许可（非阻塞）
        
        Args:
            timeout: 超时时间（秒），0 表示立即返回
        
        Returns:
            是否成功获取许可
        """
        try:
            await asyncio.wait_for(self.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    def get_current_qps(self) -> float:
        """获取当前 QPS"""
        now = time.time()
        cutoff_time = now - 60
        request_times = self._request_times[self.key_id]
        
        # 统计1分钟内的请求数
        recent_requests = sum(1 for t in request_times if t >= cutoff_time)
        return recent_requests / 60.0
    
    def get_stats(self) -> dict:
        """获取流量整形统计"""
        return {
            "key_id": self.key_id,
            "current_qps": round(self.get_current_qps(), 2),
            "target_qps_range": [self.config.min_qps, self.config.max_qps],
            "jitter_ms_range": [self.config.jitter_ms_min, self.config.jitter_ms_max],
            "recent_requests": len(self._request_times.get(self.key_id, [])),
            "last_request_at": datetime.fromtimestamp(
                self._last_request_time, tz=timezone.utc
            ).isoformat() if self._last_request_time else None,
        }


class GlobalTrafficShaper:
    """
    全局流量整形器
    用于控制整个系统的请求速率
    """
    
    def __init__(self, max_global_qps: float = 10.0):
        self.max_global_qps = max_global_qps
        self._request_times: deque = deque(maxlen=1000)
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """获取全局请求许可"""
        async with self._lock:
            now = time.time()
            
            # 清理过期记录
            cutoff_time = now - 60
            while self._request_times and self._request_times[0] < cutoff_time:
                self._request_times.popleft()
            
            # 计算当前 QPS
            current_qps = len(self._request_times) / 60.0 if self._request_times else 0
            
            wait_time = 0
            if current_qps >= self.max_global_qps:
                # 需要等待
                target_interval = 1.0 / self.max_global_qps
                wait_time = target_interval
                await asyncio.sleep(wait_time)
            
            # 记录请求时间
            self._request_times.append(time.time())
            
            return wait_time
    
    def get_stats(self) -> dict:
        """获取全局统计"""
        now = time.time()
        cutoff_time = now - 60
        recent_requests = sum(1 for t in self._request_times if t >= cutoff_time)
        
        return {
            "max_global_qps": self.max_global_qps,
            "current_qps": round(recent_requests / 60.0, 2),
            "recent_requests": recent_requests,
        }
