"""
Mapa de status Engify (`Obra.Status`) → Arcaika (`SolicitacaoOrcamento.status`).

Regras (do plano de integração, §2.2):
- planejamento          → em_contato       (obra criada / sendo preparada)
- em_andamento          → em_execucao
- financeiro            → em_execucao      (execução / faturamento)
- finalizado            → finalizado

O mapa é **forward-only**: o Arcaika, ao receber, só deve aplicar se for um
avanço; nunca regride uma solicitação. A ordem abaixo permite ao Arcaika (ou a
testes) validar monotonicidade.
"""
from app.domain.entities.obra import Status
from app.domain.entities.integracao import IntegrationEventType


# Status Arcaika alvo por status Engify.
_ARCAIKA_STATUS: dict[Status, str] = {
    Status.PLANEJAMENTO: "em_contato",
    Status.EM_ANDAMENTO: "em_execucao",
    Status.FINANCEIRO: "em_execucao",
    Status.FINALIZADO: "finalizado",
}

# Ordem canônica (para o Arcaika validar que só avança).
ARCAIKA_STATUS_ORDER: list[str] = [
    "orcamento_aceito",
    "em_contato",
    "em_execucao",
    "finalizado",
]


def arcaika_status_for(status: Status) -> str:
    """Status da solicitação Arcaika correspondente a um status de obra."""
    try:
        return _ARCAIKA_STATUS[status]
    except KeyError:  # defensivo: enum novo sem mapeamento
        raise ValueError(f"Sem mapeamento Arcaika para status de obra: {status}")


def webhook_event_type_for(status: Status) -> IntegrationEventType:
    """Tipo de evento de webhook para uma mudança de status de obra."""
    if status == Status.FINALIZADO:
        return IntegrationEventType.OBRA_FINALIZED
    return IntegrationEventType.OBRA_STATUS_CHANGED


def is_forward_transition(current: str, target: str) -> bool:
    """
    True se `target` é igual ou posterior a `current` na ordem canônica.
    Usado para garantir que a sincronização nunca regride a solicitação.
    Status desconhecidos (fora da ordem) são tratados como não-avanço.
    """
    try:
        return ARCAIKA_STATUS_ORDER.index(target) >= ARCAIKA_STATUS_ORDER.index(current)
    except ValueError:
        return False
