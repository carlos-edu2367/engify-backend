from app.domain.entities.obra import Status
from app.domain.entities.integracao import IntegrationEventType
from app.domain.services.integracao_status import (
    arcaika_status_for, webhook_event_type_for, is_forward_transition,
)


def test_status_mapping_completo():
    assert arcaika_status_for(Status.PLANEJAMENTO) == "em_contato"
    assert arcaika_status_for(Status.EM_ANDAMENTO) == "em_execucao"
    assert arcaika_status_for(Status.FINANCEIRO) == "em_execucao"
    assert arcaika_status_for(Status.FINALIZADO) == "finalizado"


def test_event_type_finalizado_vs_status_changed():
    assert webhook_event_type_for(Status.FINALIZADO) == IntegrationEventType.OBRA_FINALIZED
    assert webhook_event_type_for(Status.EM_ANDAMENTO) == IntegrationEventType.OBRA_STATUS_CHANGED
    assert webhook_event_type_for(Status.PLANEJAMENTO) == IntegrationEventType.OBRA_STATUS_CHANGED


def test_forward_only_transition():
    assert is_forward_transition("orcamento_aceito", "em_execucao") is True
    assert is_forward_transition("em_execucao", "em_execucao") is True
    assert is_forward_transition("em_execucao", "em_contato") is False  # regressão
    assert is_forward_transition("finalizado", "em_execucao") is False
    assert is_forward_transition("desconhecido", "em_execucao") is False
