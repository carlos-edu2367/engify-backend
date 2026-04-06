from uuid import UUID
from datetime import datetime, timezone

from app.application.providers.repo.financeiro_repo import (
    MovimentacaoRepository, PagamentoAgendadoRepository, MovimentacaoAttachmentRepository
)
from app.application.providers.uow import UOWProvider
from app.application.dtos.financeiro import (
    CreateMovimentacaoDTO, MovimentacaoResponse,
    CreatePagamentoDTO, EditPagamentoDTO, PagamentoResponse,
    AddMovimentacaoAttachmentDTO, MovimentacaoFiltersDTO,
    PagamentoFiltersDTO
)
from app.domain.entities.financeiro import (
    Movimentacao, MovimentacaoTypes, MovClass, Natureza,
    PagamentoAgendado, PaymentStatus, MovimentacaoAttachment
)
from app.domain.entities.money import Money
from app.domain import errors


class FinanceiroService():
    def __init__(
        self,
        mov_repo: MovimentacaoRepository,
        pagamento_repo: PagamentoAgendadoRepository,
        mov_attachment_repo: MovimentacaoAttachmentRepository,
        uow: UOWProvider,
    ):
        self.mov_repo = mov_repo
        self.pagamento_repo = pagamento_repo
        self.mov_attachment_repo = mov_attachment_repo
        self.uow = uow

    # ── Movimentações ─────────────────────────────────────────────────────────

    async def create_movimentacao(
        self, dto: CreateMovimentacaoDTO, team_id: UUID
    ) -> Movimentacao:
        mov = Movimentacao(
            team_id=team_id,
            title=dto.title,
            type=dto.type,
            valor=Money(dto.valor),
            classe=dto.classe,
            natureza=Natureza.MANUAL,
            obra_id=dto.obra_id,
        )
        saved = await self.mov_repo.save(mov)
        await self.uow.commit()
        return saved

    async def list_movimentacoes(
        self, team_id: UUID, page: int, limit: int, filters: MovimentacaoFiltersDTO | None = None
    ) -> list[MovimentacaoResponse]:
        movs = await self.mov_repo.list_by_team(team_id, page, limit, filters)
        return [_mov_to_response(m) for m in movs]

    async def count_movimentacoes(self, team_id: UUID, filters: MovimentacaoFiltersDTO | None = None) -> int:
        return await self.mov_repo.count_by_team(team_id, filters)

    async def get_movimentacao(self, id: UUID) -> Movimentacao:
        return await self.mov_repo.get_by_id(id)

    # ── Movimentações Anexos ──────────────────────────────────────────────────

    async def add_attachment(
        self, movimentacao: Movimentacao, dto: AddMovimentacaoAttachmentDTO
    ) -> MovimentacaoAttachment:
        attachment = MovimentacaoAttachment(
            movimentacao_id=movimentacao.id,
            team_id=movimentacao.team_id,
            file_path=dto.file_path,
            file_name=dto.file_name,
            content_type=dto.content_type,
        )
        saved = await self.mov_attachment_repo.save(attachment)
        await self.uow.commit()
        return saved

    async def get_attachments(self, movimentacao_id: UUID) -> list[MovimentacaoAttachment]:
        return await self.mov_attachment_repo.list_by_movimentacao(movimentacao_id)

    async def delete_attachment(self, attachment_id: UUID, team_id: UUID) -> None:
        attachment = await self.mov_attachment_repo.get_by_id(attachment_id)
        if attachment.team_id != team_id:
            raise errors.DomainError("Acesso negado para este anexo", role="FORBIDDEN")
        attachment.delete()
        await self.mov_attachment_repo.save(attachment)
        await self.uow.commit()

    # ── Pagamentos Agendados ───────────────────────────────────────────────────

    async def create_pagamento(
        self, dto: CreatePagamentoDTO, team_id: UUID
    ) -> PagamentoAgendado:
        pag = PagamentoAgendado(
            team_id=team_id,
            title=dto.title,
            details=dto.details,
            valor=Money(dto.valor),
            classe=dto.classe,
            data_agendada=dto.data_agendada,
            payment_cod=dto.payment_cod,
            obra_id=dto.obra_id,
            diarist_id=dto.diarist_id,
        )
        saved = await self.pagamento_repo.save(pag)
        await self.uow.commit()
        return saved

    async def list_pagamentos(
        self, team_id: UUID, page: int, limit: int, filters: PagamentoFiltersDTO | None = None
    ) -> list[PagamentoResponse]:
        pags = await self.pagamento_repo.list_by_team(team_id, page, limit, filters)
        return [_pag_to_response(p) for p in pags]

    async def count_pagamentos(self, team_id: UUID, filters: PagamentoFiltersDTO | None = None) -> int:
        return await self.pagamento_repo.count_by_team(team_id, filters)

    async def get_pagamento(self, id: UUID, team_id: UUID | None = None) -> PagamentoAgendado:
        return await self.pagamento_repo.get_by_id(id, team_id)

    async def edit_pagamento(
        self, pagamento: PagamentoAgendado, dto: EditPagamentoDTO
    ) -> PagamentoAgendado:
        if not any([dto.title, dto.details, dto.valor is not None,
                    dto.data_agendada, dto.payment_cod, dto.obra_id]):
            raise errors.DomainError("Envie ao menos um campo para editar")

        if dto.title:
            pagamento.title = dto.title
        if dto.details:
            pagamento.details = dto.details
        if dto.valor is not None:
            pagamento.valor = Money(dto.valor)
        if dto.data_agendada:
            pagamento.data_agendada = dto.data_agendada
        if dto.payment_cod is not None:
            pagamento.payment_cod = dto.payment_cod
        if dto.obra_id is not None:
            pagamento.obra_id = dto.obra_id

        saved = await self.pagamento_repo.save(pagamento)
        await self.uow.commit()
        return saved

    async def pay_pagamento(
        self, pagamento: PagamentoAgendado
    ) -> Movimentacao:
        """Marca pagamento como pago e cria Movimentação de saída atomicamente."""
        if pagamento.status == PaymentStatus.PAGO:
            raise errors.DomainError("Pagamento já foi efetuado")

        pagamento.status = PaymentStatus.PAGO
        pagamento.payment_date = datetime.now(timezone.utc)
        await self.pagamento_repo.save(pagamento)

        mov = Movimentacao(
            team_id=pagamento.team_id,
            title=pagamento.title,
            type=MovimentacaoTypes.SAIDA,
            valor=pagamento.valor,
            classe=pagamento.classe,
            natureza=Natureza.MANUAL,
            obra_id=pagamento.obra_id,
            pagamento_id=pagamento.id,
        )
        saved_mov = await self.mov_repo.save(mov)
        await self.uow.commit()
        return saved_mov


def _mov_to_response(m: Movimentacao) -> MovimentacaoResponse:
    return MovimentacaoResponse(
        id=m.id,
        title=m.title,
        type=m.type,
        valor=m.valor.amount,
        classe=m.classe,
        natureza=m.natureza,
        obra_id=m.obra_id,
        pagamento_id=m.pagamento_id,
        data_movimentacao=m.data_movimentacao,
    )


def _pag_to_response(p: PagamentoAgendado) -> PagamentoResponse:
    return PagamentoResponse(
        id=p.id,
        title=p.title,
        details=p.details,
        valor=p.valor.amount,
        classe=p.classe,
        status=p.status,
        data_agendada=p.data_agendada,
        payment_cod=p.payment_cod,
        obra_id=p.obra_id,
        diarist_id=p.diarist_id,
        payment_date=p.payment_date,
    )
