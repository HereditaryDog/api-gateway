from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Type

from app.providers.adapters import KimiCodeAdapter, OpenAICompatAdapter, VolcengineCodingPlanAdapter
from app.providers.transformers import OpenAIPassthroughTransformer


@dataclass
class ProviderRegistration:
    name: str
    adapter_cls: Type
    matcher: Callable[[object], bool]


class ProviderRegistry:
    """Provider 注册表。"""

    def __init__(self):
        self._registrations: List[ProviderRegistration] = []

    def register(self, registration: ProviderRegistration):
        self._registrations.append(registration)

    def resolve(self, provider_record):
        for registration in self._registrations:
            if registration.matcher(provider_record):
                return registration
        raise ValueError(f"No provider adapter registered for provider {provider_record.name}")


def _is_kimi_coding_plan(provider_record) -> bool:
    adapter_type = (provider_record.adapter_type or "").lower()
    provider_type = getattr(provider_record.provider_type, "value", "").lower()
    base_url = (provider_record.base_url or "").lower()
    name = (provider_record.name or "").lower()
    return adapter_type.startswith("coding_plan") and (
        provider_type == "moonshot"
        or "moonshot" in base_url
        or "moonshot" in name
        or "kimi" in name
    )


def _is_volcengine_coding_plan(provider_record) -> bool:
    adapter_type = (provider_record.adapter_type or "").lower()
    base_url = (provider_record.base_url or "").lower()
    name = (provider_record.name or "").lower()
    return adapter_type.startswith("coding_plan") and (
        "volces" in base_url
        or "volcengine" in name
        or "火山" in name
        or "doubao" in name
    )


def _is_standard_provider(provider_record) -> bool:
    adapter_type = (provider_record.adapter_type or "standard").lower()
    return not adapter_type.startswith("coding_plan")


registry = ProviderRegistry()
registry.register(
    ProviderRegistration(
        name="coding_plan_kimi",
        adapter_cls=KimiCodeAdapter,
        matcher=_is_kimi_coding_plan,
    )
)
registry.register(
    ProviderRegistration(
        name="coding_plan_volcengine",
        adapter_cls=VolcengineCodingPlanAdapter,
        matcher=_is_volcengine_coding_plan,
    )
)
registry.register(
    ProviderRegistration(
        name="standard_openai_compat",
        adapter_cls=OpenAICompatAdapter,
        matcher=_is_standard_provider,
    )
)
