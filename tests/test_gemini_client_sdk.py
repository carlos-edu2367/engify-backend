"""Tests for the Gemini SDK adapter used by Arky."""

import pytest
from google.genai import types

from app.infra.ai.gemini_client import (
    GeminiClient,
    GeminiToolDeclaration,
    build_model_function_call,
)


class _FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeAio:
    def __init__(self, response):
        self.models = _FakeModels(response)


class _FakeSdkClient:
    def __init__(self, response):
        self.aio = _FakeAio(response)
        self.closed = False

    async def aclose(self):
        self.closed = True


def _sdk_response(*parts: types.Part):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=list(parts)),
                finish_reason="STOP",
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=7,
            candidates_token_count=3,
        ),
    )


@pytest.mark.asyncio
async def test_generate_uses_google_genai_sdk_config_and_tools():
    fake = _FakeSdkClient(
        _sdk_response(types.Part(text='{"message":"ok"}'))
    )
    client = GeminiClient(api_key="test-key", sdk_client=fake)

    out = await client.generate(
        model="gemini-3.5-flash",
        system_instruction="system",
        contents=[{"role": "user", "parts": [{"text": "hello"}]}],
        tools=[
            GeminiToolDeclaration(
                name="obras_list",
                description="Lista obras",
                parameters={"type": "OBJECT", "properties": {}},
            )
        ],
        temperature=0.2,
        max_output_tokens=128,
    )

    assert out.text == '{"message":"ok"}'
    call = fake.aio.models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert isinstance(call["config"], types.GenerateContentConfig)
    assert call["config"].system_instruction == "system"
    assert call["config"].temperature == 0.2
    assert call["config"].max_output_tokens == 128
    assert call["config"].automatic_function_calling.disable is True
    tool = call["config"].tools[0]
    assert tool.function_declarations[0].name == "obras_list"
    assert tool.function_declarations[0].parameters_json_schema["type"] == "OBJECT"


@pytest.mark.asyncio
async def test_generate_parses_sdk_function_call_and_usage():
    fake = _FakeSdkClient(
        _sdk_response(
            types.Part(
                function_call=types.FunctionCall(
                    name="financeiro_get_fluxo_caixa",
                    args={"mes": 6, "ano": 2026},
                )
            )
        )
    )
    client = GeminiClient(api_key="test-key", sdk_client=fake)

    out = await client.generate(
        model="gemini-3.5-flash",
        system_instruction="system",
        contents=[{"role": "user", "parts": [{"text": "fluxo"}]}],
    )

    assert out.text == ""
    assert out.function_calls == [
        {"name": "financeiro_get_fluxo_caixa", "args": {"mes": 6, "ano": 2026}}
    ]
    assert out.usage.prompt_tokens == 7
    assert out.usage.completion_tokens == 3


@pytest.mark.asyncio
async def test_generate_preserves_function_call_thought_signature():
    signature = b"thought-signature"
    fake = _FakeSdkClient(
        _sdk_response(
            types.Part(
                function_call=types.FunctionCall(
                    name="obras_prepare_create",
                    args={"title": "Teste"},
                ),
                thought_signature=signature,
            )
        )
    )
    client = GeminiClient(api_key="test-key", sdk_client=fake)

    out = await client.generate(
        model="gemini-3.5-flash",
        system_instruction="system",
        contents=[{"role": "user", "parts": [{"text": "crie uma obra"}]}],
    )

    assert out.function_calls == [
        {
            "name": "obras_prepare_create",
            "args": {"title": "Teste"},
            "thought_signature": signature,
        }
    ]


def test_build_model_function_call_preserves_thought_signature():
    content = build_model_function_call(
        "obras_prepare_create",
        {"title": "Teste"},
        thought_signature=b"thought-signature",
    )

    assert content["parts"][0]["functionCall"]["name"] == "obras_prepare_create"
    assert content["parts"][0]["thoughtSignature"] == b"thought-signature"


@pytest.mark.asyncio
async def test_close_closes_sdk_client_when_available():
    fake = _FakeSdkClient(_sdk_response(types.Part(text="ok")))
    client = GeminiClient(api_key="test-key", sdk_client=fake)

    await client.close()

    assert fake.closed is True
