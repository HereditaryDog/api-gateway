from __future__ import annotations

from typing import Optional, Tuple

from app.core.encryption import decrypt_data
from app.providers.adapters import OpenAICompatAdapter
from app.providers.contracts import ProviderContext, ProviderError, RetryPolicy
from app.providers.registry import registry
from app.providers.transformers import OpenAIPassthroughTransformer
from app.providers.transports import HTTPXTransport
from app.services.upstream_service import UpstreamService


class ProviderFactory:
    """创建 Provider 适配器及上下文。"""

    def __init__(self, *, transport: Optional[HTTPXTransport] = None):
        self.transport = transport or HTTPXTransport()

    async def create(
        self,
        db,
        provider_record,
        *,
        external_model: str = "",
        actual_model: str = "",
        request_id: str = "",
        require_upstream_key: bool = True,
    ) -> Tuple[object, ProviderContext]:
        registration = registry.resolve(provider_record)

        context = ProviderContext(
            provider_record=provider_record,
            request_id=request_id,
            external_model=external_model,
            actual_model=actual_model,
            mapped_model=(provider_record.model_mapping or {}).get(
                external_model,
                (provider_record.model_mapping or {}).get(actual_model, actual_model),
            ),
            retry_policy=RetryPolicy(),
        )

        if issubclass(registration.adapter_cls, OpenAICompatAdapter) and registration.adapter_cls is OpenAICompatAdapter:
            adapter = registration.adapter_cls(
                transport=self.transport,
                transformer=OpenAIPassthroughTransformer(),
            )
            if require_upstream_key:
                key = await self._get_standard_key(db, provider_record.id)
                context = context.clone_with_account(
                    api_key=decrypt_data(key.encrypted_key),
                    upstream_key_id=key.id,
                )
        else:
            adapter = registration.adapter_cls(
                db=db,
                provider_record=provider_record,
                transport=self.transport,
            )

        return adapter, context

    async def _get_standard_key(self, db, provider_id: int):
        keys = await UpstreamService.list_keys(
            db,
            provider_id=provider_id,
            available_only=True,
            limit=1,
        )
        if not keys:
            raise ProviderError("No available upstream key for this provider", status_code=502, retryable=False)

        key = keys[0]
        decrypted = decrypt_data(key.encrypted_key)
        if not decrypted:
            raise ProviderError("Unable to decrypt upstream key", status_code=500, retryable=False)
        return key
