from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import ProviderBillingConfig
from app.models.upstream import UpstreamKey
from app.providers.adapters.openai_compat import OpenAICompatAdapter
from app.providers.contracts import ChatChunk, ChatRequest, ChatResponse, ProviderContext
from app.providers.contracts.models import ProviderError
from app.services.risk_control import FailoverManager, PoolManager, QuotaTracker, RateLimitConfig, TrafficShaper, get_anomaly_detector


class CodingPlanBaseAdapter(OpenAICompatAdapter):
    """Coding Plan 通用适配器基类。"""

    def __init__(
        self,
        *,
        db: AsyncSession,
        provider_record,
        transformer,
        transport=None,
    ):
        super().__init__(transport=transport, transformer=transformer)
        self.db = db
        self.provider_record = provider_record
        self.pool_manager = PoolManager(db, provider_record.id)
        self.anomaly_detector = get_anomaly_detector()
        self.failover_manager = FailoverManager(db)
        self.config: Optional[ProviderBillingConfig] = None
        self.rate_limit_config: Optional[RateLimitConfig] = None
        self._traffic_shapers: Dict[int, TrafficShaper] = {}

    async def _load_config(self):
        if self.config:
            return

        result = await self.db.execute(
            select(ProviderBillingConfig).where(
                ProviderBillingConfig.provider_id == self.provider_record.id
            )
        )
        self.config = result.scalar_one_or_none()
        if self.config:
            self.rate_limit_config = RateLimitConfig(
                min_qps=float(self.config.min_qps_limit) if self.config.min_qps_limit else 0.5,
                max_qps=float(self.config.max_qps_limit) if self.config.max_qps_limit else 2.0,
                jitter_ms_min=self.config.jitter_ms_min or 100,
                jitter_ms_max=self.config.jitter_ms_max or 500,
            )

    def _get_traffic_shaper(self, key_id: int) -> TrafficShaper:
        if key_id not in self._traffic_shapers:
            self._traffic_shapers[key_id] = TrafficShaper(key_id, self.rate_limit_config or RateLimitConfig())
        return self._traffic_shapers[key_id]

    async def _prepare_attempt_context(
        self,
        ctx: ProviderContext,
        excluded_key_ids: List[int],
    ) -> Tuple[ProviderContext, int]:
        await self._load_config()

        while True:
            account = await self.pool_manager.select_account(excluded_key_ids)
            if not account:
                raise ProviderError("No available account in pool", status_code=502, retryable=False)

            circuit_breaker = self.failover_manager.get_circuit_breaker(account.key_id)
            if not circuit_breaker.can_execute():
                excluded_key_ids.append(account.key_id)
                continue

            quota_tracker = QuotaTracker(self.db, account.key_id)
            is_available, quota_details = await quota_tracker.check_quota()
            if not is_available:
                await self.pool_manager.update_account_health(account.key_id, success=False)
                for window_type, details in quota_details.items():
                    if window_type != "overall_available" and not details.get("available"):
                        self.anomaly_detector.detect_quota_exhausted(
                            account.key_id,
                            self.provider_record.id,
                            window_type,
                            details["used"],
                            details["limit"],
                        )
                excluded_key_ids.append(account.key_id)
                continue

            await self._get_traffic_shaper(account.key_id).acquire()

            if not await quota_tracker.consume_quota(1):
                excluded_key_ids.append(account.key_id)
                continue

            return ctx.clone_with_account(
                api_key=account.decrypted_key,
                upstream_key_id=account.key_id,
            ), account.key_id

    async def _record_success(self, key_id: int, response_time_ms: int):
        self.failover_manager.get_circuit_breaker(key_id).record_success()
        await self.pool_manager.update_account_health(key_id, success=True, response_time_ms=response_time_ms)

    async def _record_failure(self, key_id: Optional[int], error: Exception, response_time_ms: int = 0):
        if not key_id:
            return

        self.failover_manager.get_circuit_breaker(key_id).record_failure()
        await self.pool_manager.update_account_health(key_id, success=False, response_time_ms=response_time_ms, error=error)

        if response_time_ms > 10000:
            self.anomaly_detector.detect_high_latency(
                key_id,
                self.provider_record.id,
                response_time_ms,
                0,
            )

    async def _sleep_backoff(self, attempt: int, ctx: ProviderContext):
        index = min(attempt, len(ctx.retry_policy.backoff_ms) - 1)
        delay_ms = ctx.retry_policy.backoff_ms[index] + random.randint(0, ctx.retry_policy.jitter_ms)
        await asyncio.sleep(delay_ms / 1000.0)

    async def chat(self, ctx: ProviderContext, req: ChatRequest) -> ChatResponse:
        excluded_key_ids: List[int] = []
        last_error: Optional[Exception] = None

        for attempt in range(ctx.retry_policy.max_attempts):
            key_id: Optional[int] = None
            start_time = time.time()
            try:
                attempt_ctx, key_id = await self._prepare_attempt_context(ctx, excluded_key_ids)
                response = await super().chat(attempt_ctx, req)
                await self._record_success(key_id, int((time.time() - start_time) * 1000))
                response.upstream_key_id = key_id
                return response
            except Exception as exc:
                last_error = exc
                excluded_key_ids.append(key_id) if key_id else None
                await self._record_failure(key_id, exc, int((time.time() - start_time) * 1000))
                if attempt < ctx.retry_policy.max_attempts - 1 and self.transformer.is_retryable(exc):
                    await self._sleep_backoff(attempt, ctx)
                    continue
                raise ProviderError(
                    str(exc),
                    status_code=getattr(exc, "status_code", 502),
                    retryable=self.transformer.is_retryable(exc),
                    upstream_key_id=key_id,
                ) from exc

        raise ProviderError(str(last_error or "Unknown coding plan error"), status_code=502, retryable=False)

    async def stream_chat(
        self,
        ctx: ProviderContext,
        req: ChatRequest,
    ) -> AsyncGenerator[ChatChunk, None]:
        excluded_key_ids: List[int] = []

        for attempt in range(ctx.retry_policy.max_attempts):
            key_id: Optional[int] = None
            saw_valid_chunk = False
            start_time = time.time()
            try:
                attempt_ctx, key_id = await self._prepare_attempt_context(ctx, excluded_key_ids)
                async for chunk in super().stream_chat(attempt_ctx, req):
                    chunk.upstream_key_id = key_id
                    if chunk.is_error:
                        raise ProviderError(
                            chunk.metadata.get("error_message", "Upstream stream error"),
                            status_code=502,
                            retryable=True,
                            upstream_key_id=key_id,
                        )
                    if chunk.is_valid:
                        saw_valid_chunk = True
                    if chunk.is_done:
                        await self._record_success(key_id, int((time.time() - start_time) * 1000))
                    yield chunk
                return
            except Exception as exc:
                excluded_key_ids.append(key_id) if key_id else None
                await self._record_failure(key_id, exc, int((time.time() - start_time) * 1000))

                if saw_valid_chunk:
                    yield ChatChunk(
                        data={
                            "error": {
                                "message": str(exc),
                                "type": "partial_stream_error",
                                "code": getattr(exc, "status_code", 502),
                            }
                        },
                        is_error=True,
                        upstream_key_id=key_id,
                        metadata={"status": "partial_error", "error_message": str(exc)},
                    )
                    yield ChatChunk(is_done=True, upstream_key_id=key_id)
                    return

                if attempt < ctx.retry_policy.max_attempts - 1 and self.transformer.is_retryable(exc):
                    await self._sleep_backoff(attempt, ctx)
                    continue

                yield ChatChunk(
                    data={
                        "error": {
                            "message": str(exc),
                            "type": "upstream_error",
                            "code": getattr(exc, "status_code", 502),
                        }
                    },
                    is_error=True,
                    upstream_key_id=key_id,
                    metadata={"status": "error", "error_message": str(exc)},
                )
                yield ChatChunk(is_done=True, upstream_key_id=key_id)
                return
