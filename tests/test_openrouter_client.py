"""Unit tests for OpenRouterClient — fallback, parsing and schema normalization.

Uses httpx.MockTransport so no real network calls are made.
"""
import json

import httpx
import pytest

from app.infra.ai.llm import LLMError, ToolDeclaration
from app.infra.ai.openrouter_client import OpenRouterClient


def _client(handler) -> OpenRouterClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return OpenRouterClient(api_key="test-key", http_client=http_client)


def _ok_body(*, content="ok", tool_calls=None, model="model-x"):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
        message["content"] = None
    return {
        "model": model,
        "choices": [{"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 5},
    }


@pytest.mark.asyncio
async def test_generate_parses_text_usage_and_model_used():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_body(content='{"message":"oi"}', model="real/model"))

    client = _client(handler)
    out = await client.generate(
        models=["any/model"],
        system_instruction="system",
        messages=[{"role": "user", "content": "oi"}],
    )

    assert out.text == '{"message":"oi"}'
    assert out.usage.prompt_tokens == 11
    assert out.usage.completion_tokens == 5
    assert out.model_used == "real/model"


@pytest.mark.asyncio
async def test_generate_parses_tool_calls_with_json_arguments():
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "financeiro_get_fluxo_caixa",
            "arguments": json.dumps({"mes": 6, "ano": 2026}),
        },
    }]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_body(tool_calls=tool_calls))

    client = _client(handler)
    out = await client.generate(
        models=["any/model"],
        system_instruction="system",
        messages=[{"role": "user", "content": "fluxo"}],
    )

    assert out.text == ""
    assert len(out.tool_calls) == 1
    tc = out.tool_calls[0]
    assert tc.id == "call_1"
    assert tc.name == "financeiro_get_fluxo_caixa"
    assert tc.args == {"mes": 6, "ano": 2026}


@pytest.mark.asyncio
async def test_tool_schema_types_are_normalized_to_lowercase():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    client = _client(handler)
    await client.generate(
        models=["any/model"],
        system_instruction="system",
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            ToolDeclaration(
                name="obras_list",
                description="Lista obras",
                parameters={
                    "type": "OBJECT",
                    "properties": {"limit": {"type": "INTEGER"}},
                    "required": [],
                },
            )
        ],
    )

    fn = captured["body"]["tools"][0]["function"]
    assert fn["parameters"]["type"] == "object"
    assert fn["parameters"]["properties"]["limit"]["type"] == "integer"
    assert captured["body"]["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_system_instruction_is_prepended():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    client = _client(handler)
    await client.generate(
        models=["any/model"],
        system_instruction="SISTEMA",
        messages=[{"role": "user", "content": "oi"}],
    )

    msgs = captured["body"]["messages"]
    assert msgs[0] == {"role": "system", "content": "SISTEMA"}
    assert msgs[1]["role"] == "user"


@pytest.mark.asyncio
async def test_falls_back_to_next_model_on_5xx():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body["model"])
        if body["model"] == "first/model":
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json=_ok_body(model="second/model"))

    client = _client(handler)
    out = await client.generate(
        models=["first/model", "second/model"],
        system_instruction="system",
        messages=[{"role": "user", "content": "oi"}],
    )

    assert seen == ["first/model", "second/model"]
    assert out.model_used == "second/model"


@pytest.mark.asyncio
async def test_fatal_auth_error_does_not_try_next_model():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["model"])
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.generate(
            models=["first/model", "second/model"],
            system_instruction="system",
            messages=[{"role": "user", "content": "oi"}],
        )

    assert exc.value.status_code == 401
    assert exc.value.retryable is False
    assert seen == ["first/model"]  # parou no primeiro


@pytest.mark.asyncio
async def test_empty_chain_raises():
    client = _client(lambda r: httpx.Response(200, json=_ok_body()))
    with pytest.raises(LLMError):
        await client.generate(
            models=[],
            system_instruction="system",
            messages=[{"role": "user", "content": "oi"}],
        )


@pytest.mark.asyncio
async def test_skips_known_non_vision_model_when_image_present():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["model"])
        return httpx.Response(200, json=_ok_body(model="google/gemini-3.5-flash"))

    client = _client(handler)
    out = await client.generate(
        # gemma free = sem visão (catálogo); gemini-3.5-flash = com visão
        models=["google/gemma-4-31b-it:free", "google/gemini-3.5-flash"],
        system_instruction="system",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "o que é isso?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}},
            ],
        }],
    )

    assert seen == ["google/gemini-3.5-flash"]  # pulou o modelo sem visão
    assert out.model_used == "google/gemini-3.5-flash"
