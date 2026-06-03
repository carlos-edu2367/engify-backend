"""Arky Copilot router — /arky/chat and /arky/confirm/{preview_id}."""
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.core.limiter import limiter
from app.http.dependencies.auth import CurrentUser
from app.http.dependencies.services import ArkyCopilotDep
from app.http.schemas.arky import (
    ArkyChatRequest,
    ArkyChatResponse,
    ArkyActionResponse,
    ArkyCardResponse,
    ArkyConfirmResponse,
)
from app.application.services.arky.orchestrator import ArkyChatInput

router = APIRouter(prefix="/arky", tags=["Arky"])


@router.post("/chat", response_model=ArkyChatResponse)
@limiter.limit("20/minute")
async def arky_chat(
    request: Request,
    body: ArkyChatRequest,
    user: CurrentUser,
    copilot: ArkyCopilotDep,
) -> ArkyChatResponse:
    """Send a message to Arky and receive a contextual response."""
    conversation_id: UUID | None = None
    if body.conversation_id:
        try:
            conversation_id = UUID(body.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="conversation_id inválido")

    inp = ArkyChatInput(
        message=body.message,
        user=user,
        team_id=user.team.id,
        conversation_id=conversation_id,
        screen_data=body.screen.model_dump() if body.screen else None,
        selection_data=body.selection.model_dump() if body.selection else None,
        ui_state_data=body.ui_state.model_dump() if body.ui_state else None,
        intent_hint=body.intent_hint,
        screenshot_base64=body.screenshot,
        request_id=str(uuid.uuid4()),
    )

    output = await copilot.chat(inp)

    return ArkyChatResponse(
        conversation_id=output.conversation_id,
        message_id=output.message_id,
        message=output.message,
        intent=output.intent,
        cards=[
            ArkyCardResponse(
                type=c.type,
                title=c.title,
                summary=c.summary,
                risk=c.risk,
                requires_confirmation=c.requires_confirmation,
                action_preview_id=c.action_preview_id,
            )
            for c in output.cards
        ],
        actions=[
            ArkyActionResponse(
                type=a.type,
                label=a.label,
                action_preview_id=a.action_preview_id,
                to=a.to,
            )
            for a in output.actions
        ],
        citations=output.citations,
    )


@router.post("/confirm/{preview_id}", response_model=ArkyConfirmResponse)
@limiter.limit("10/minute")
async def arky_confirm(
    request: Request,
    preview_id: str,
    user: CurrentUser,
    copilot: ArkyCopilotDep,
) -> ArkyConfirmResponse:
    """Confirm a prepared action (human-in-the-loop)."""
    try:
        pid = UUID(preview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="preview_id inválido")

    preview = await copilot._preview_repo.get_by_id(pid, user.team.id, user.id)
    if not preview:
        raise HTTPException(status_code=404, detail="Prévia não encontrada")

    if preview.is_expired() or preview.status in ("expired", "confirmed", "rejected"):
        return ArkyConfirmResponse(
            action_preview_id=str(pid),
            status=preview.status if preview.status != "pending" else "expired",
            message="Esta ação expirou ou já foi processada.",
        )

    try:
        preview.confirm()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await copilot._preview_repo.update(preview)
    await copilot._uow.commit()

    return ArkyConfirmResponse(
        action_preview_id=str(pid),
        status="confirmed",
        message="Ação confirmada com sucesso.",
    )


@router.post("/reject/{preview_id}", response_model=ArkyConfirmResponse)
@limiter.limit("10/minute")
async def arky_reject(
    request: Request,
    preview_id: str,
    user: CurrentUser,
    copilot: ArkyCopilotDep,
) -> ArkyConfirmResponse:
    """Reject a prepared action."""
    try:
        pid = UUID(preview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="preview_id inválido")

    preview = await copilot._preview_repo.get_by_id(pid, user.team.id, user.id)
    if not preview:
        raise HTTPException(status_code=404, detail="Prévia não encontrada")

    if preview.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Ação não pode ser rejeitada no status '{preview.status}'",
        )

    try:
        preview.reject()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await copilot._preview_repo.update(preview)
    await copilot._uow.commit()

    return ArkyConfirmResponse(
        action_preview_id=str(pid),
        status="rejected",
        message="Ação cancelada.",
    )
