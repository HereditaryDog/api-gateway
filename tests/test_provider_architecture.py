from types import SimpleNamespace

import pytest

from app.providers.adapters.coding_plan.kimi_code import KimiCodeAdapter
from app.providers.adapters.openai_compat import OpenAICompatAdapter
from app.providers.contracts import ChatRequest, ProviderContext
from app.providers.registry import registry
from app.providers.transformers import CodingPlanKimiTransformer, CodingPlanVolcengineTransformer, OpenAIPassthroughTransformer
from app.providers.transports.base import ProviderTransportError, TransportResponse


class DummyTransport:
    def __init__(self, *, response=None, stream_lines=None, errors=None):
        self.response = response
        self.stream_lines = stream_lines or []
        self.errors = list(errors or [])
        self.request_calls = 0
        self.stream_calls = 0

    async def request(self, method, url, *, headers, json_body, timeout=60.0):
        self.request_calls += 1
        if self.errors:
            error = self.errors.pop(0)
            if error:
                raise error
        return self.response

    async def stream(self, method, url, *, headers, json_body, timeout=60.0):
        self.stream_calls += 1
        for item in self.stream_lines:
            if isinstance(item, Exception):
                raise item
            yield item


def make_provider(**overrides):
    data = {
        "id": 1,
        "name": "OpenAI",
        "provider_type": SimpleNamespace(value="openai"),
        "adapter_type": "standard",
        "base_url": "https://example.com/v1",
        "model_mapping": {"openai/gpt-4o": "gpt-4o"},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_registry_resolves_standard_and_coding_plan_vendors():
    standard = make_provider()
    kimi = make_provider(
        name="Kimi Code",
        provider_type=SimpleNamespace(value="moonshot"),
        adapter_type="coding_plan",
        base_url="https://api.moonshot.cn/v1",
    )
    volcengine = make_provider(
        name="火山引擎 Coding Plan",
        provider_type=SimpleNamespace(value="custom"),
        adapter_type="coding_plan",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

    assert registry.resolve(standard).adapter_cls is OpenAICompatAdapter
    assert registry.resolve(kimi).adapter_cls.__name__ == "KimiCodeAdapter"
    assert registry.resolve(volcengine).adapter_cls.__name__ == "VolcengineCodingPlanAdapter"


def test_kimi_transformer_strips_reasoning_content_and_sets_prompt_cache_key():
    transformer = CodingPlanKimiTransformer()
    provider = make_provider(
        name="Kimi Code",
        provider_type=SimpleNamespace(value="moonshot"),
        adapter_type="coding_plan",
        model_mapping={"coding-plan/kimi-k2": "kimi-k2"},
    )
    ctx = ProviderContext(
        provider_record=provider,
        request_id="req-123",
        external_model="coding-plan/kimi-k2",
        actual_model="coding-plan/kimi-k2",
        mapped_model="kimi-k2",
    )
    req = ChatRequest(
        model="coding-plan/kimi-k2",
        messages=[{"role": "user", "content": "hello"}],
        extra={"thinking": {"type": "enabled"}},
    )

    payload = transformer.build_request(ctx, req)
    assert payload["prompt_cache_key"] == "gateway:1:req-123"
    assert payload["thinking"] == {"type": "enabled"}

    response = transformer.to_chat_response(
        ctx,
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "ok",
                        "reasoning_content": "internal",
                    }
                }
            ],
            "usage": {"total_tokens": 12},
        },
    )
    assert response.data["choices"][0]["message"]["content"] == "ok"
    assert "reasoning_content" not in response.data["choices"][0]["message"]


def test_volcengine_transformer_normalizes_stream_chunks():
    transformer = CodingPlanVolcengineTransformer()
    provider = make_provider(
        name="火山引擎",
        provider_type=SimpleNamespace(value="custom"),
        adapter_type="coding_plan",
        model_mapping={"volcengine/doubao-pro": "doubao-pro-4k"},
    )
    ctx = ProviderContext(
        provider_record=provider,
        request_id="req-456",
        external_model="volcengine/doubao-pro",
        actual_model="volcengine/doubao-pro",
        mapped_model="doubao-pro-4k",
    )

    chunk = transformer.to_chat_chunk(
        ctx,
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "hello",
                    }
                }
            ]
        },
    )
    assert chunk.is_valid is True
    assert chunk.data["object"] == "chat.completion.chunk"
    assert chunk.token_delta >= 1


@pytest.mark.asyncio
async def test_openai_compat_adapter_streams_standard_done_marker():
    provider = make_provider()
    ctx = ProviderContext(
        provider_record=provider,
        request_id="req-openai",
        external_model="openai/gpt-4o",
        actual_model="openai/gpt-4o",
        mapped_model="gpt-4o",
        api_key="secret",
        upstream_key_id=9,
    )
    adapter = OpenAICompatAdapter(
        transport=DummyTransport(
            stream_lines=[
                'data: {"choices":[{"delta":{"role":"assistant","content":"hello"}}]}',
                "data: [DONE]",
            ]
        ),
        transformer=OpenAIPassthroughTransformer(),
    )

    chunks = [chunk async for chunk in adapter.stream_chat(ctx, ChatRequest(model="openai/gpt-4o", messages=[]))]
    assert chunks[0].is_valid is True
    assert chunks[-1].is_done is True


@pytest.mark.asyncio
async def test_coding_plan_adapter_retries_before_first_response(monkeypatch):
    provider = make_provider(
        name="Kimi Code",
        provider_type=SimpleNamespace(value="moonshot"),
        adapter_type="coding_plan",
        model_mapping={"coding-plan/kimi-k2": "kimi-k2"},
    )
    transport = DummyTransport(
        response=TransportResponse(
            status_code=200,
            json_data={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 10},
            },
        ),
        errors=[ProviderTransportError("temporary", retryable=True), None],
    )
    adapter = KimiCodeAdapter(db=None, provider_record=provider, transport=transport)
    ctx = ProviderContext(
        provider_record=provider,
        request_id="req-retry",
        external_model="coding-plan/kimi-k2",
        actual_model="coding-plan/kimi-k2",
        mapped_model="kimi-k2",
    )

    async def fake_prepare(base_ctx, excluded):
        return base_ctx.clone_with_account(api_key="secret", upstream_key_id=1), 1

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(adapter, "_prepare_attempt_context", fake_prepare)
    monkeypatch.setattr(adapter, "_record_success", noop)
    monkeypatch.setattr(adapter, "_record_failure", noop)
    monkeypatch.setattr(adapter, "_sleep_backoff", noop)

    response = await adapter.chat(ctx, ChatRequest(model="coding-plan/kimi-k2", messages=[]))
    assert response.data["choices"][0]["message"]["content"] == "ok"
    assert transport.request_calls == 2


@pytest.mark.asyncio
async def test_coding_plan_stream_stops_retrying_after_first_valid_chunk(monkeypatch):
    provider = make_provider(
        name="Kimi Code",
        provider_type=SimpleNamespace(value="moonshot"),
        adapter_type="coding_plan",
        model_mapping={"coding-plan/kimi-k2": "kimi-k2"},
    )
    transport = DummyTransport(
        stream_lines=[
            'data: {"choices":[{"delta":{"role":"assistant","content":"hel"}}]}',
            ProviderTransportError("stream dropped", retryable=True),
        ]
    )
    adapter = KimiCodeAdapter(db=None, provider_record=provider, transport=transport)
    ctx = ProviderContext(
        provider_record=provider,
        request_id="req-stream",
        external_model="coding-plan/kimi-k2",
        actual_model="coding-plan/kimi-k2",
        mapped_model="kimi-k2",
    )

    async def fake_prepare(base_ctx, excluded):
        return base_ctx.clone_with_account(api_key="secret", upstream_key_id=7), 7

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(adapter, "_prepare_attempt_context", fake_prepare)
    monkeypatch.setattr(adapter, "_record_success", noop)
    monkeypatch.setattr(adapter, "_record_failure", noop)
    monkeypatch.setattr(adapter, "_sleep_backoff", noop)

    chunks = [chunk async for chunk in adapter.stream_chat(ctx, ChatRequest(model="coding-plan/kimi-k2", messages=[]))]
    assert chunks[0].is_valid is True
    assert chunks[1].is_error is True
    assert chunks[1].metadata["status"] == "partial_error"
    assert chunks[-1].is_done is True
    assert transport.stream_calls == 1
