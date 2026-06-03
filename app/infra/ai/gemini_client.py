"""
Gemini client adapter using the official Google GenAI SDK.

Sensitive data must be redacted BEFORE calling any method in this module.
The adapter preserves Arky's internal response contract while delegating
transport, auth and request serialization to google-genai.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0


@dataclass
class GeminiToolDeclaration:
    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass
class GeminiUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class GeminiResponse:
    text: str
    function_calls: list[dict] = field(default_factory=list)
    usage: GeminiUsage = field(default_factory=GeminiUsage)
    finish_reason: str = "STOP"


class GeminiClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiClient:
    def __init__(self, api_key: str, sdk_client: Any | None = None) -> None:
        self._api_key = api_key
        self._client = sdk_client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(_REQUEST_TIMEOUT * 1000)),
        )

    async def close(self) -> None:
        close = getattr(self._client, "aclose", None)
        if close:
            await close()

    async def generate(
        self,
        *,
        model: str,
        system_instruction: str,
        contents: list[dict],
        tools: list[GeminiToolDeclaration] | None = None,
        temperature: float = 0.1,
        max_output_tokens: int = 2048,
    ) -> GeminiResponse:
        """
        Generate a response with the Google GenAI SDK.
        The SDK's automatic function calling is disabled because Arky executes
        tools through backend policies, tenant scope and audit.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        if tools:
            config.tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in tools
                    ]
                )
            ]

        sdk_contents = [types.Content.model_validate(c) for c in contents]

        start = time.monotonic()
        try:
            resp = await self._client.aio.models.generate_content(
                model=model,
                contents=sdk_contents,
                config=config,
            )
        except Exception as e:
            status_code = getattr(e, "code", None) or getattr(e, "status_code", None)
            message = str(e) or "Gemini SDK error"
            logger.error("Gemini SDK error: %s", message[:300])
            raise GeminiClientError(
                f"Gemini SDK request error: {message}",
                status_code=status_code,
            ) from e

        latency_ms = int((time.monotonic() - start) * 1000)
        return self._parse_response(resp, latency_ms)

    def _parse_response(self, response: Any, latency_ms: int) -> GeminiResponse:
        usage_meta = getattr(response, "usage_metadata", None)
        usage = GeminiUsage(
            prompt_tokens=_get_field(usage_meta, "prompt_token_count", "promptTokenCount", 0),
            completion_tokens=_get_field(usage_meta, "candidates_token_count", "candidatesTokenCount", 0),
            latency_ms=latency_ms,
        )

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return GeminiResponse(text="", usage=usage)

        candidate = candidates[0]
        finish_reason = _get_field(candidate, "finish_reason", "finishReason", "STOP")
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []

        text_parts: list[str] = []
        function_calls: list[dict] = []

        for part in parts:
            text = getattr(part, "text", None)
            function_call = getattr(part, "function_call", None)
            if text:
                text_parts.append(text)
            elif function_call:
                call_data = {
                    "name": getattr(function_call, "name", "") or "",
                    "args": getattr(function_call, "args", {}) or {},
                }
                thought_signature = getattr(part, "thought_signature", None)
                if thought_signature:
                    call_data["thought_signature"] = thought_signature
                function_calls.append(call_data)

        return GeminiResponse(
            text="\n".join(text_parts),
            function_calls=function_calls,
            usage=usage,
            finish_reason=finish_reason,
        )


def _get_field(source: Any, snake_name: str, camel_name: str, default: Any) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(snake_name, source.get(camel_name, default))
    return getattr(source, snake_name, getattr(source, camel_name, default))


def build_user_message(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def build_model_function_call(
    name: str,
    args: dict,
    thought_signature: bytes | None = None,
) -> dict:
    part = {"functionCall": {"name": name, "args": args}}
    if thought_signature:
        part["thoughtSignature"] = thought_signature
    return {
        "role": "model",
        "parts": [part],
    }


def build_function_response(name: str, response: dict) -> dict:
    return {
        "role": "user",
        "parts": [{"functionResponse": {"name": name, "response": response}}],
    }
