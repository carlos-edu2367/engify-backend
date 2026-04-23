from uuid import UUID
from datetime import datetime, timezone

from app.application.providers.repo.financeiro_repo import (
    MovimentacaoRepository, PagamentoAgendadoRepository, MovimentacaoAttachmentRepository
)
from app.application.providers.repo.team_repos import DiaristRepository
from app.application.providers.uow import UOWProvider
from app.application.dtos.financeiro import (
    CreateMovimentacaoDTO, MovimentacaoResponse,
    CreatePagamentoDTO, EditPagamentoDTO, PagamentoReadResponse, PagamentoResponse,
    AddMovimentacaoAttachmentDTO, MovimentacaoFiltersDTO,
    PagamentoFiltersDTO, BaixaLoteDTO, LotePagamentoResultDTO,
)
from app.application.providers.utility.pix_provider import generate_pix_copy_and_past
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
        diarist_repo: DiaristRepository,
        uow: UOWProvider,
    ):
        self.mov_repo = mov_repo
        self.pagamento_repo = pagamento_repo
        self.mov_attachment_repo = mov_attachment_repo
        self.diarist_repo = diarist_repo
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

    async def get_movimentacao_by_team(self, id: UUID, team_id: UUID) -> Movimentacao:
        return await self.mov_repo.get_by_id(id, team_id)

    async def delete_movimentacao(self, movimentacao: Movimentacao) -> None:
        if movimentacao.pagamento_id is not None:
            raise errors.DomainError(
                "NÃ£o Ã© possÃ­vel remover uma movimentaÃ§Ã£o gerada por pagamento"
            )
        if movimentacao.lote_info:
            raise errors.DomainError(
                "NÃ£o Ã© possÃ­vel remover uma movimentaÃ§Ã£o gerada por baixa em lote"
            )
        if movimentacao.natureza != Natureza.MANUAL:
            raise errors.DomainError(
                "NÃ£o Ã© possÃ­vel remover uma movimentaÃ§Ã£o importada automaticamente"
            )
        if movimentacao.type == MovimentacaoTypes.ENTRADA and movimentacao.obra_id is not None:
            raise errors.DomainError(
                "Recebimentos vinculados Ã  obra devem ser gerenciados pelo fluxo de recebimentos"
            )

        movimentacao.delete()
        await self.mov_repo.save(movimentacao)
        await self.uow.commit()

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
        receiver_name = await self._resolve_receiver_name(dto.diarist_id, team_id)
        pag = PagamentoAgendado(
            team_id=team_id,
            title=dto.title,
            details=dto.details,
            valor=Money(dto.valor),
            classe=dto.classe,
            data_agendada=dto.data_agendada,
            payment_cod=dto.payment_cod,
            pix_copy_and_past=generate_pix_copy_and_past(
                payment_code=dto.payment_cod,
                amount=dto.valor,
                receiver_name=receiver_name,
                city="GOIANIA",
            ),
            obra_id=dto.obra_id,
            diarist_id=dto.diarist_id,
        )
        saved = await self.pagamento_repo.save(pag)
        await self.uow.commit()
        return saved

    async def list_pagamentos(
        self, team_id: UUID, page: int, limit: int, filters: PagamentoFiltersDTO | None = None
    ) -> list[PagamentoReadResponse]:
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

        receiver_name = await self._resolve_receiver_name(pagamento.diarist_id, pagamento.team_id)
        amount = dto.valor if dto.valor is not None else pagamento.valor.amount
        pagamento.pix_copy_and_past = generate_pix_copy_and_past(
            payment_code=pagamento.payment_cod,
            amount=amount,
            receiver_name=receiver_name,
            city="GOIANIA",
        )

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

    async def pay_lote(self, dto: BaixaLoteDTO) -> LotePagamentoResultDTO:
        """
        Baixa em lote: valida todos os pagamentos, atualiza status e cria uma
        única Movimentação de saída consolidada. Operação atômica — falha total
        ou sucesso total.
        """
        if not dto.pagamento_ids:
            raise errors.DomainError("A lista de pagamentos não pode ser vazia")

        pagamentos = await self.pagamento_repo.list_by_ids(dto.pagamento_ids, dto.team_id)

        # Valida que todos os IDs foram encontrados no tenant
        encontrados = {p.id for p in pagamentos}
        nao_encontrados = set(dto.pagamento_ids) - encontrados
        if nao_encontrados:
            raise errors.DomainError(
                f"Pagamento(s) não encontrado(s) ou de outro tenant: "
                f"{', '.join(str(i) for i in nao_encontrados)}"
            )

        # Valida status de todos antes de alterar qualquer um
        ja_pagos = [p for p in pagamentos if p.status == PaymentStatus.PAGO]
        if ja_pagos:
            raise errors.DomainError(
                f"Pagamento(s) já efetuado(s): "
                f"{', '.join(str(p.id) for p in ja_pagos)}"
            )

        agora = datetime.now(timezone.utc)
        total = sum(p.valor.amount for p in pagamentos)

        # Marca todos como pagos
        for pag in pagamentos:
            pag.status = PaymentStatus.PAGO
            pag.payment_date = agora
            await self.pagamento_repo.save(pag)

        # Monta descrição e metadados estruturados
        descricao = _build_lote_descricao(pagamentos, total)
        lote_info = _build_lote_info(pagamentos)

        mov = Movimentacao(
            team_id=dto.team_id,
            title=f"Baixa em lote — {len(pagamentos)} pagamento(s)",
            type=MovimentacaoTypes.SAIDA,
            valor=Money(total),
            classe=MovClass.OPERACIONAL,
            natureza=Natureza.MANUAL,
            lote_info=lote_info,
        )
        # Usa o campo details via title (description formatada no lote_info)
        # e sobrescreve title com a descrição legível
        mov.title = descricao[:255]

        saved_mov = await self.mov_repo.save(mov)
        await self.uow.commit()

        return LotePagamentoResultDTO(
            quantidade=len(pagamentos),
            valor_total=total,
            movimentacao_id=saved_mov.id,
        )

    async def _resolve_receiver_name(self, diarist_id: UUID | None, team_id: UUID) -> str:
        if not diarist_id:
            return "Engify Payments"
        try:
            diarist = await self.diarist_repo.get_by_id(diarist_id, team_id)
        except errors.DomainError:
            return "Engify Payments"
        return diarist.nome or "Engify Payments"


_MAX_LOTE_INLINE = 50  # acima disso, detalha só no lote_info (JSONB)


def _fmt_brl(valor) -> str:
    """Formata Decimal como 'R$ 1.234,56'."""
    from decimal import Decimal as _D
    v = _D(str(valor)).quantize(_D("0.01"))
    s = f"{v:,.2f}"              # "1,234.56"
    inteiro, centavos = s.split(".")
    inteiro = inteiro.replace(",", ".")  # "1.234"
    return f"R$ {inteiro},{centavos}"


def _build_lote_descricao(pagamentos: list, total) -> str:
    linhas = ["Baixa em lote de pagamentos:\n"]
    detalhados = pagamentos if len(pagamentos) <= _MAX_LOTE_INLINE else pagamentos[:_MAX_LOTE_INLINE]
    for p in detalhados:
        linhas.append(
            f"- Relacionado ao pagamento de id {p.id}, "
            f"{p.title}, no valor de {_fmt_brl(p.valor.amount)}"
        )
    if len(pagamentos) > _MAX_LOTE_INLINE:
        restantes = len(pagamentos) - _MAX_LOTE_INLINE
        linhas.append(f"- ... e mais {restantes} pagamento(s) (ver lote_info)")
    linhas.append(f"\nTotal: {_fmt_brl(total)}")
    return "\n".join(linhas)


def _build_lote_info(pagamentos: list) -> dict:
    return {
        "lote_ids": [str(p.id) for p in pagamentos],
        "lote_detalhes": [
            {
                "id": str(p.id),
                "descricao": p.title,
                "valor": str(p.valor.amount),
            }
            for p in pagamentos
        ],
    }


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


def _pag_to_response(p: PagamentoAgendado) -> PagamentoReadResponse:
    return PagamentoReadResponse(
        id=p.id,
        title=p.title,
        details=p.details,
        valor=p.valor.amount,
        classe=p.classe,
        status=p.status,
        data_agendada=p.data_agendada,
        payment_cod=p.payment_cod,
        pix_copy_and_past=p.pix_copy_and_past,
        obra_id=p.obra_id,
        diarist_id=p.diarist_id,
        payment_date=p.payment_date,
    )
