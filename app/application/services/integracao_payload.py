"""
Construção (pura) do corpo dos eventos de webhook Engify → Arcaika.

`build_event_data` produz a seção `data` do envelope; o envelope completo
(id/type/created_at/connection) é montado no dispatcher, que conhece a conexão.
"""
from app.domain.entities.obra import Obra, Status
from app.domain.services.integracao_status import arcaika_status_for


def build_event_data(
    obra: Obra,
    public_url: str,
    previous_status: Status | None = None,
) -> dict:
    """Seção `data` de um evento de obra."""
    return {
        "obra_id": str(obra.id),
        "external_ref": {
            "orcamento_id": str(obra.arcaika_orcamento_id) if obra.arcaika_orcamento_id else None,
            "solicitacao_id": str(obra.arcaika_solicitacao_id) if obra.arcaika_solicitacao_id else None,
        },
        "status": obra.status.value,
        # Status Arcaika sugerido (forward-only; o Arcaika valida antes de aplicar).
        "arcaika_status": arcaika_status_for(obra.status),
        "previous_status": previous_status.value if previous_status else None,
        "total_recebido": str(obra.total_recebido),
        "public_url": public_url,
    }


def build_envelope(event, connection) -> dict:
    """Envelope completo assinável a partir de um IntegrationEvent + conexão."""
    return {
        "id": str(event.id),
        "type": event.event_type.value,
        "created_at": event.created_at.isoformat(),
        "connection": {
            "team_id": str(connection.team_id),
            "organizacao_id": str(connection.arcaika_organizacao_id),
        },
        "data": event.payload,
    }
