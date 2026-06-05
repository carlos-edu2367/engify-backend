"""
Camada de IA abstraida — contrato provider-agnostico.

O restante do sistema (orchestrator, tool_registry) depende APENAS deste modulo,
nunca de um SDK concreto. Implementacoes de provedor vivem em modulos irmaos
(ex: openrouter_client.py). Trocar de provedor = nova implementacao de
`LLMClient`, sem tocar na logica de negocio do Arky.

Formato de mensagens: estilo OpenAI Chat Completions (roles user/assistant/tool
+ tool_calls com id), que e o formato nativo do OpenRouter. A continuidade de
function calling e feita via `tool_call_id` — nao ha conceito de thought
signature (especifico do Gemini).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolDeclaration:
    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str = "stop"
    # Id concreto do modelo que efetivamente respondeu. Pode diferir do primeiro
    # da cadeia quando houve fallback. Usado na auditoria.
    model_used: str = ""


class LLMError(Exception):
    """Erro de transporte/execucao de um provedor de IA.

    `retryable=True` indica que vale a pena tentar o proximo modelo da cadeia de
    fallback (timeout, rate limit, 5xx, modelo indisponivel). `retryable=False`
    e fatal para a requisicao inteira (chave invalida, sem credito).
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class LLMClient(ABC):
    """Contrato unico que o orchestrator conhece.

    `models` e a cadeia de fallback (preferido -> ultimo recurso). A
    implementacao tenta cada modelo em ordem e retorna a primeira resposta
    bem-sucedida, registrando em `LLMResponse.model_used` qual respondeu.
    """

    @abstractmethod
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
        ...

    async def close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Construtores de mensagens — formato OpenAI/OpenRouter Chat Completions.
# ---------------------------------------------------------------------------
def user_message(
    text: str,
    *,
    image_base64: str | None = None,
    image_mime: str = "image/jpeg",
) -> dict:
    if image_base64:
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime};base64,{image_base64}"},
                },
            ],
        }
    return {"role": "user", "content": text}


def assistant_text_message(text: str) -> dict:
    return {"role": "assistant", "content": text}


def assistant_tool_calls_message(tool_calls: list[ToolCall]) -> dict:
    """Mensagem do assistente que solicitou uma ou mais tools no round atual.

    Deve conter TODAS as tool calls do round; cada `tool_result_message` seguinte
    referencia uma delas por `tool_call_id`.
    """
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.args, ensure_ascii=False),
                },
            }
            for tc in tool_calls
        ],
    }


def tool_result_message(tool_call_id: str, name: str, result: Any) -> dict:
    content = (
        result
        if isinstance(result, str)
        else json.dumps(result, ensure_ascii=False, default=str)
    )
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }
