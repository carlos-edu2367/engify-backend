"""Static, safe product knowledge for Arky.

This provider only exposes general product/module guidance. Dynamic tenant data
must still come from backend tools with RBAC and tenant scope applied.
"""
from __future__ import annotations


class ArkyKnowledgeProvider:
    def build_context(self, module: str | None, permission_summary: dict | None) -> str:
        module_key = (module or "geral").lower()
        permissions = permission_summary or {}
        blocks = [_BASE_KNOWLEDGE]

        if module_key == "financeiro":
            blocks.append(_financeiro_context(permissions))
        elif module_key == "rh":
            blocks.append(_rh_context(permissions))
        elif module_key == "obras":
            blocks.append(_OBRAS_KNOWLEDGE)
        else:
            blocks.append(_GENERAL_MODULES)

        return "\n".join(blocks)


_BASE_KNOWLEDGE = (
    "[CONHECIMENTO DO ENGIFY]\n"
    "O Engify organiza operacoes de obras, itens, financeiro, RH, mural, "
    "notificacoes, membros e configuracoes. Esse bloco e conhecimento geral "
    "do produto; dados dinamicos devem vir apenas de tools permitidas."
)

_GENERAL_MODULES = (
    "Modulos principais: Obras acompanha projetos, status e itens; Financeiro "
    "acompanha movimentacoes, pagamentos, anexos e fluxo de caixa; RH acompanha "
    "funcionarios, ponto, ferias, atestados, beneficios, holerites, folha e "
    "auditoria. Quando o usuario pedir dados reais, use tools ou diga que nao "
    "ha evidencia suficiente."
)

_OBRAS_KNOWLEDGE = (
    "Obras: usado para criar e acompanhar obras, responsaveis, status, itens, "
    "diarias, imagens, mural e pagamentos vinculados. Acoes de escrita devem "
    "ser preparadas para confirmacao humana e validadas pelo backend. "
    "Na pagina de Obras, recebimentos da obra devem ser cadastrados na aba "
    "Recebimentos. Notas fiscais, comprovantes e recibos ligados a um "
    "recebimento devem ser anexados no proprio recebimento, pois assim ficam "
    "disponiveis para o cliente no link publico da obra. Essas notas fiscais "
    "nao devem ser anexadas no mural quando a intencao for dar acesso ao "
    "cliente; o mural deve ficar para comunicacao e historico interno da obra."
)


def _financeiro_context(permissions: dict) -> str:
    access = (
        "O usuario tem permissao backend para resumo financeiro permitido."
        if permissions.get("can_read_financeiro")
        else "O usuario esta sem permissao backend para dados financeiros."
    )
    return (
        "Financeiro: usado para movimentacoes, pagamentos agendados, baixas, "
        "anexos, relatorios e fluxo de caixa. Nunca exponha Pix completo, "
        "anexos privados, payloads brutos, dados de outro tenant ou acoes "
        "sensíveis sem validacao backend. "
        f"{access}"
    )


def _rh_context(permissions: dict) -> str:
    admin_access = bool(permissions.get("can_read_rh_admin"))
    me_access = bool(permissions.get("can_read_rh_me"))

    if admin_access:
        access = "O usuario pode consultar apenas resumos administrativos permitidos de RH."
    elif me_access:
        access = (
            "O usuario pode consultar orientacoes e resumo do Meu RH; nao deve acessar "
            "dashboard administrativo."
        )
    else:
        access = "O usuario esta sem permissao backend para dados de RH."

    return (
        "RH: usado para funcionarios, ponto, ajustes, ferias, atestados, "
        "beneficios, holerites, folha, encargos, tabelas progressivas e "
        "auditoria. Evite CPF completo, salario completo, geolocalizacao, "
        "documentos e URLs privadas. "
        f"Meu RH e a area pessoal do funcionario. {access}"
    )
