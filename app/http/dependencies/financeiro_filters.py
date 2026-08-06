import hashlib
import json
from typing import Annotated, Literal, Optional
from datetime import datetime
from uuid import UUID
from fastapi import Query, Depends
from app.domain.entities.financeiro import PaymentStatus, MovClass
from app.application.dtos.financeiro import PagamentoFiltersDTO, MovimentacaoFiltersDTO


async def get_pagamento_filters(
    status: Annotated[Optional[PaymentStatus], Query(description="Filtro de status do pagamento")] = None,
    obra_id: Annotated[Optional[UUID], Query(description="Filtro por Obra ID")] = None,
    period_start: Annotated[
        Optional[datetime],
        Query(description="Vencimento (data_agendada) a partir de, em ISO8601"),
    ] = None,
    period_end: Annotated[
        Optional[datetime],
        Query(description="Vencimento (data_agendada) até, em ISO8601"),
    ] = None,
) -> PagamentoFiltersDTO:
    return PagamentoFiltersDTO(
        status=status,
        obra_id=obra_id,
        period_start=period_start,
        period_end=period_end,
    )


async def get_pagamento_scope(
    scope: Annotated[
        Literal["mine", "all"],
        Query(description="Escopo de visibilidade para engenheiros: 'mine' (padrão, só os próprios) ou 'all' (todos do time)"),
    ] = "mine",
) -> str:
    return scope


async def get_movimentacao_filters(
    period_start: Annotated[Optional[datetime], Query(description="Início do período em ISO8601")] = None,
    period_end: Annotated[Optional[datetime], Query(description="Fim do período em ISO8601")] = None,
    obra_id: Annotated[Optional[UUID], Query(description="Filtro por Obra ID")] = None,
    classe: Annotated[Optional[MovClass], Query(description="Filtro por classe da movimentação")] = None,
) -> MovimentacaoFiltersDTO:
    return MovimentacaoFiltersDTO(
        period_start=period_start,
        period_end=period_end,
        obra_id=obra_id,
        classe=classe,
    )


PagamentoFiltersDep = Annotated[PagamentoFiltersDTO, Depends(get_pagamento_filters)]
PagamentoScopeDep = Annotated[str, Depends(get_pagamento_scope)]
MovimentacaoFiltersDep = Annotated[MovimentacaoFiltersDTO, Depends(get_movimentacao_filters)]

