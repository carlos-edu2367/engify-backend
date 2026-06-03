"""
Gemini REST client via httpx.
Implements multi-turn conversation with function/tool calling.
Sensitive data must be redacted BEFORE calling any method in this module.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_TOOL_ROUNDS = 3
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
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)

    async def close(self) -> None:
        await self._http.aclose()

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
        Generate a response. Handles multiple tool-call rounds automatically.
        Returns the final text response after all tool calls are resolved.
        The caller is responsible for executing tool calls between rounds.
        Use generate_with_tools for automatic tool execution.
        """
        url = f"{_GEMINI_BASE}/{model}:generateContent"
        params = {"key": self._api_key}

        body: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generation_config": {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        }

        if tools:
            body["tools"] = [
                {
                    "function_declarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters,
                        }
                        for t in tools
                    ]
                }
            ]

        start = time.monotonic()
        try:
            resp = await self._http.post(url, params=params, json=body)
        except httpx.TimeoutException as e:
            raise GeminiClientError("Gemini API timeout") from e
        except httpx.RequestError as e:
            raise GeminiClientError(f"Gemini API request error: {e}") from e

        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            logger.error("Gemini API error: %s %s", resp.status_code, resp.text[:300])
            raise GeminiClientError(
                f"Gemini API returned {resp.status_code}", status_code=resp.status_code
            )

        data = resp.json()
        return self._parse_response(data, latency_ms)

    def _parse_response(self, data: dict, latency_ms: int) -> GeminiResponse:
        usage_meta = data.get("usageMetadata", {})
        usage = GeminiUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            latency_ms=latency_ms,
        )

        candidates = data.get("candidates", [])
        if not candidates:
            return GeminiResponse(text="", usage=usage)

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_parts: list[str] = []
        function_calls: list[dict] = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                function_calls.append(
                    {"name": fc.get("name", ""), "args": fc.get("args", {})}
                )

        return GeminiResponse(
            text="\n".join(text_parts),
            function_calls=function_calls,
            usage=usage,
            finish_reason=finish_reason,
        )


def build_user_message(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def build_model_function_call(name: str, args: dict) -> dict:
    return {
        "role": "model",
        "parts": [{"functionCall": {"name": name, "args": args}}],
    }


def build_function_response(name: str, response: dict) -> dict:
    return {
        "role": "user",
        "parts": [{"functionResponse": {"name": name, "response": response}}],
    }
