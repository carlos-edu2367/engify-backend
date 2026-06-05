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


_PAGAMENTOS_SUGESTAO_KNOWLEDGE = (
    "Voce pode ajudar com pagamentos agendados: para saber de atrasados use a "
    "tool financeiro_pagamentos_overview; para o historico/ultimo pagamento de "
    "uma pessoa use financeiro_buscar_pagamentos. Para CADASTRAR pagamentos, "
    "monte uma sugestao com financeiro_prepare_pagamentos (aceita uma LISTA, "
    "pois o usuario costuma enviar varios de uma vez) e deixe o usuario aprovar "
    "ou rejeitar — nada e criado sem confirmacao. Use diaristas_list e obras_list "
    "para resolver nomes em ids quando o usuario citar um diarista ou uma obra. "
    "Para diarias soltas (ex.: '5 diarias para Pedro, 200 cada'), NAO pergunte a "
    "obra nem vincule diarista: lance com classe 'diarista', o nome no titulo e o "
    "codigo Pix em payment_cod. data_agendada vazia significa hoje. A criacao real "
    "e a validacao (incluindo codigo obrigatorio para engenheiro e o carimbo de "
    "autoria) acontecem no backend no momento da confirmacao."
)


def _financeiro_context(permissions: dict) -> str:
    can_full = bool(permissions.get("can_read_financeiro"))
    can_own = bool(permissions.get("can_manage_own_pagamentos"))

    if can_full:
        access = (
            "O usuario tem acesso completo ao modulo financeiro: movimentacoes, "
            "todos os pagamentos agendados do tenant, baixa individual e em lote, "
            "fluxo de caixa e relatorios. "
            "Pagamentos criados por engenheiro exibem badge 'Criado por engenheiro', "
            "nome do criador (campo created_by_name) e data de criacao (created_at) no card. "
            "Registros legados sem autoria continuam visiveis normalmente. "
            f"{_PAGAMENTOS_SUGESTAO_KNOWLEDGE}"
        )
    elif can_own:
        access = (
            "O usuario e engenheiro e acessa o modulo Financeiro apenas pela aba Pagamentos. "
            "Ele so ve, cria, edita e exclui pagamentos agendados criados por ele proprio. "
            "Ao criar um pagamento, o campo 'Codigo de pagamento' (PIX ou codigo de barras "
            "do recebedor) e obrigatorio — sem ele o backend rejeita. "
            "O valor deve ser informado no formato humano brasileiro, por exemplo 190,50. "
            "So e possivel editar ou excluir pagamentos com status 'aguardando'; "
            "pagamentos pagos sao bloqueados para qualquer alteracao. "
            "O engenheiro nao pode marcar pagamentos como pagos, usar baixa em lote, "
            "consultar movimentacoes, fluxo de caixa ou relatorios financeiros. "
            "Se o usuario perguntar sobre pagamentos de outros membros ou dados "
            "financeiros do tenant, informe que essas informacoes nao estao "
            "disponiveis para o perfil dele. "
            f"{_PAGAMENTOS_SUGESTAO_KNOWLEDGE}"
        )
    else:
        access = "O usuario nao tem permissao backend para dados financeiros."

    return (
        "Financeiro: usado para movimentacoes, pagamentos agendados, baixas, "
        "anexos, relatorios e fluxo de caixa. Nunca exponha Pix completo, "
        "anexos privados, payloads brutos, dados de outro tenant ou acoes "
        "sensiveis sem validacao backend. "
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
