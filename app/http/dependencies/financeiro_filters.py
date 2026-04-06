import hashlib
import json
from typing import Annotated, Optional
from datetime import datetime
from uuid import UUID
from fastapi import Query, Depends
from app.domain.entities.financeiro import PaymentStatus, MovClass
from app.application.dtos.financeiro import PagamentoFiltersDTO, MovimentacaoFiltersDTO


async def get_pagamento_filters(
    status: Annotated[Optional[PaymentStatus], Query(description="Filtro de status do pagamento")] = None,
) -> PagamentoFiltersDTO:
    return PagamentoFiltersDTO(status=status)


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
MovimentacaoFiltersDep = Annotated[MovimentacaoFiltersDTO, Depends(get_movimentacao_filters)]

