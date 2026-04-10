"""
Port abstrato para envio de emails transacionais.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass
class RecoveryCodeEmailInput:
    destinatario: str
    nome: str
    code: str        # plain code — nunca armazenar este valor
    user_id: UUID    # usado para montar o link de reset no email


@dataclass
class ConviteEmailInput:
    destinatario: str
    team_name: str
    role: str
    solicitacao_id: UUID


class EmailPort(ABC):
    @abstractmethod
    async def enviar_recovery_code(self, input: RecoveryCodeEmailInput) -> None: ...

    @abstractmethod
    async def enviar_convite(self, input: ConviteEmailInput) -> None: ...

    async def fechar(self) -> None:
        """Fecha recursos (ex: HTTP client). Override se necessário."""
