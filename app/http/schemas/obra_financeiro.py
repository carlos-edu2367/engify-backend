from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from typing import Optional
from app.domain.entities.financeiro import MovClass


class CustoPorClasseResponse(BaseModel):
    classe: MovClass
    realizado: Decimal
    comprometido: Decimal


class ObraFinanceiroResumoResponse(BaseModel):
    obra_id: UUID
    contrato: Optional[Decimal] = None
    entradas: Decimal
    saidas: Decimal
    comprometido: Decimal
    resultado_realizado: Decimal
    custo_previsto: Decimal
    margem_projetada: Optional[Decimal] = None
    margem_projetada_pct: Optional[Decimal] = None
    a_receber: Optional[Decimal] = None
    total_recebido_obra: Decimal
    custos_por_classe: list[CustoPorClasseResponse] = []
    qtd_movimentacoes: int
    qtd_pagamentos_aguardando: int
