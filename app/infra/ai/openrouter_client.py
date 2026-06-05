"""
Implementacao de `LLMClient` sobre o OpenRouter (API estilo OpenAI Chat
Completions: POST /chat/completions).

Responsabilidades:
- Montar o payload (system + mensagens + tools) e os headers do OpenRouter.
- Iterar a cadeia de fallback `models`: tenta cada modelo em ordem e retorna a
  primeira resposta bem-sucedida. Erros transitorios (timeout, 429, 5xx, modelo
  indisponivel) avancam para o proximo modelo; erros fatais (401/402/403)
  abortam a requisicao inteira.
- Pular modelos sem visao quando a mensagem contem imagem (best-effort, baseado
  no catalogo; ids desconhecidos passam).

Dados sensiveis devem ser redatados ANTES de chamar este modulo.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.infra.ai import model_catalog as catalog
from app.infra.ai.llm import (
    LLMClient,
    LLMError,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolDeclaration,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0
# Tipos JSON Schema validos (lowercase). Declaracoes de tools podem vir em
# uppercase (heranca do formato Gemini); normalizamos antes de enviar.
_JSON_SCHEMA_TYPES = {
    "object", "array", "string", "number", "integer", "boolean", "null",
}


class OpenRouterClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str | None = None,
        app_name: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = _REQUEST_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._site_url = site_url
        self._app_name = app_name
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate(
        self,
        *,
        models: list[str],
        system_instruction: str,
        messages: list[dict],
        tools: list[ToolDeclaration] | None = None,
        temperature: float = 0.1,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        if not models:
            raise LLMError("Nenhum modelo na cadeia de fallback", retryable=False)

        payload_messages = [
            {"role": "system", "content": system_instruction},
            *messages,
        ]
        tool_payload = (
            [self._tool_to_payload(t) for t in tools] if tools else None
        )
        has_image = _messages_have_image(messages)

        last_error: LLMError | None = None
        for model in models:
            if has_image and catalog.suporta_vision(model) is False:
                logger.info("Pulando modelo sem visao para entrada multimodal: %s", model)
                continue
            try:
                return await self._call_once(
                    model=model,
                    messages=payload_messages,
                    tools=tool_payload,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            except LLMError as e:
                last_error = e
                if not e.retryable:
                    raise
                logger.warning(
                    "OpenRouter modelo '%s' falhou (%s); tentando proximo da cadeia.",
                    model,
                    e,
                )
                continue

        raise last_error or LLMError(
            "Todos os modelos da cadeia de fallback falharam", retryable=True
        )

    async def _call_once(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        start = time.monotonic()
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers=self._headers(),
            )
        except httpx.TimeoutException as e:
            raise LLMError(f"OpenRouter timeout: {e}", retryable=True) from e
        except httpx.RequestError as e:
            raise LLMError(f"OpenRouter erro de conexao: {e}", retryable=True) from e

        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 400:
            self._raise_for_status(resp)

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMError("OpenRouter retornou JSON invalido", retryable=True) from e

        return self._parse_response(data, model, latency_ms)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        # Headers opcionais de atribuicao do OpenRouter (rankings/limites).
        if self._site_url:
            headers["HTTP-Referer"] = self._site_url
        if self._app_name:
            headers["X-Title"] = self._app_name
        return headers

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        code = resp.status_code
        # 401/402/403: chave invalida, sem credito, proibido — fatal, nao adianta
        # tentar outro modelo com a mesma conta.
        fatal = code in (401, 402, 403)
        detail = _safe_error_detail(resp)
        raise LLMError(
            f"OpenRouter HTTP {code}: {detail}",
            status_code=code,
            retryable=not fatal,
        )

    def _parse_response(
        self, data: dict, requested_model: str, latency_ms: int
    ) -> LLMResponse:
        # Alguns erros do OpenRouter vem com 200 + corpo {"error": {...}}.
        if isinstance(data.get("error"), dict):
            err = data["error"]
            raise LLMError(
                f"OpenRouter erro no corpo: {err.get('message', err)}",
                status_code=err.get("code"),
                retryable=True,
            )

        choices = data.get("choices") or []
        usage_raw = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
            latency_ms=latency_ms,
        )
        model_used = data.get("model") or requested_model

        if not choices:
            return LLMResponse(text="", usage=usage, model_used=model_used)

        choice = choices[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        finish_reason = choice.get("finish_reason") or "stop"

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id") or "",
                    name=fn.get("name") or "",
                    args=_parse_arguments(fn.get("arguments")),
                )
            )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model_used=model_used,
        )

    @staticmethod
    def _tool_to_payload(tool: ToolDeclaration) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _normalize_json_schema(tool.parameters),
            },
        }


def _parse_arguments(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_json_schema(schema: Any) -> Any:
    """Lowercase recursivo dos valores de `type` para JSON Schema valido.

    Declaracoes de tools no projeto usam tipos em uppercase (ex: "OBJECT",
    "STRING") por heranca do formato Gemini. OpenRouter/OpenAI exigem JSON Schema
    padrao (lowercase). Esta funcao normaliza sem alterar o restante do schema.
    """
    if isinstance(schema, dict):
        out: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "type":
                out[key] = _lower_type(value)
            else:
                out[key] = _normalize_json_schema(value)
        return out
    if isinstance(schema, list):
        return [_normalize_json_schema(v) for v in schema]
    return schema


def _lower_type(value: Any) -> Any:
    if isinstance(value, str) and value.lower() in _JSON_SCHEMA_TYPES:
        return value.lower()
    if isinstance(value, list):
        return [_lower_type(v) for v in value]
    return value


def _messages_have_image(messages: list[dict]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def _safe_error_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return str(err.get("message", err))[:300]
            if err:
                return str(err)[:300]
        return str(data)[:300]
    except (json.JSONDecodeError, ValueError):
        return (resp.text or "")[:300]
