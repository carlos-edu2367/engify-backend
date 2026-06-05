"""
ArkyToolRegistry — maps tool names to provider-agnostic function declarations.
Only tools registered here can ever be called by the model.

Os tipos de schema abaixo estao em uppercase (heranca do formato Gemini); o
OpenRouterClient normaliza para JSON Schema padrao (lowercase) antes de enviar.
"""
from app.domain.entities.financeiro import MovClass
from app.infra.ai.llm import ToolDeclaration

# Valores válidos de classe de pagamento, derivados do domínio (fonte única).
_VALID_CLASSES_FOR_SCHEMA = [c.value for c in MovClass]

_TOOL_DECLARATIONS: dict[str, ToolDeclaration] = {
    "obras_get_detail": ToolDeclaration(
        name="obras_get_detail",
        description="Busca detalhes completos de uma obra pelo ID. Use quando o usuário perguntar sobre uma obra específica.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "obra_id": {"type": "STRING", "description": "UUID da obra"},
            },
            "required": ["obra_id"],
        },
    ),
    "obras_list": ToolDeclaration(
        name="obras_list",
        description="Lista obras do time do usuário. Use para responder perguntas sobre obras em geral, pendências ou status.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "status": {
                    "type": "STRING",
                    "description": "Filtro de status: planejamento, em_andamento, financeiro, finalizado",
                    "enum": ["planejamento", "em_andamento", "financeiro", "finalizado"],
                },
                "limit": {"type": "INTEGER", "description": "Máximo de resultados (padrão 10, máx 20)"},
            },
            "required": [],
        },
    ),
    "items_list_by_obra": ToolDeclaration(
        name="items_list_by_obra",
        description="Lista itens/tarefas de uma obra. Use para verificar pendências, progresso ou checklist da obra.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "obra_id": {"type": "STRING", "description": "UUID da obra"},
            },
            "required": ["obra_id"],
        },
    ),
    "notificacoes_list": ToolDeclaration(
        name="notificacoes_list",
        description="Lista notificações recentes do usuário. Use para verificar alertas e pendências de comunicação.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Máximo de notificações (padrão 10)"},
                "only_unread": {"type": "BOOLEAN", "description": "Listar apenas não lidas"},
            },
            "required": [],
        },
    ),
    "financeiro_get_fluxo_caixa": ToolDeclaration(
        name="financeiro_get_fluxo_caixa",
        description="Busca resumo do fluxo de caixa do time. Apenas para roles admin ou financeiro. Não expõe Pix nem anexos.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "mes": {"type": "INTEGER", "description": "Mês (1-12). Se omitido, usa o mês atual."},
                "ano": {"type": "INTEGER", "description": "Ano (ex: 2025). Se omitido, usa o ano atual."},
            },
            "required": [],
        },
    ),
    "financeiro_pagamentos_overview": ToolDeclaration(
        name="financeiro_pagamentos_overview",
        description=(
            "Lista pagamentos agendados ATRASADOS (aguardando e vencidos) e o "
            "total em atraso. Use quando o usuário perguntar sobre pagamentos "
            "atrasados/pendentes. Engenheiro vê apenas os próprios. Não expõe Pix."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Máximo de itens (padrão 15, máx 30)"},
            },
            "required": [],
        },
    ),
    "financeiro_buscar_pagamentos": ToolDeclaration(
        name="financeiro_buscar_pagamentos",
        description=(
            "Busca pagamentos agendados por nome/texto no título ou descrição. "
            "Use para responder 'quando foi o último pagamento para a pessoa X' "
            "ou consultar o histórico de pagamentos de alguém. Engenheiro vê "
            "apenas os próprios. Não expõe Pix nem código do recebedor."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Nome da pessoa ou texto a buscar (mín. 2 caracteres)"},
                "limit": {"type": "INTEGER", "description": "Máximo de resultados (padrão 10, máx 20)"},
            },
            "required": ["query"],
        },
    ),
    "diaristas_list": ToolDeclaration(
        name="diaristas_list",
        description=(
            "Lista diaristas cadastrados do time (id, nome, valor da diária) para "
            "ajudar a vincular pagamentos a um diarista. Não retorna a chave Pix."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Máximo de diaristas (padrão 30, máx 50)"},
            },
            "required": [],
        },
    ),
    "financeiro_prepare_pagamentos": ToolDeclaration(
        name="financeiro_prepare_pagamentos",
        description=(
            "Prepara uma LISTA de pagamentos agendados para o usuário aprovar ou "
            "rejeitar. NÃO cria nada — apenas gera uma prévia. Use quando o usuário "
            "pedir para cadastrar/agendar um ou vários pagamentos. Suporta vários "
            "pagamentos de uma vez. Vincule diarist_id/obra_id apenas quando o "
            "usuário deixar claro; para diárias soltas (ex.: '5 diárias para Pedro') "
            "NÃO vincule diarista nem obra — use classe 'diarista', coloque o nome "
            "no título e o código Pix em payment_cod. data_agendada vazia = hoje."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "pagamentos": {
                    "type": "ARRAY",
                    "description": "Lista de pagamentos a agendar",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "Título/descrição curta do pagamento (inclua o nome da pessoa quando aplicável)"},
                            "valor": {"type": "NUMBER", "description": "Valor do pagamento em reais"},
                            "classe": {
                                "type": "STRING",
                                "description": "Categoria do pagamento",
                                "enum": sorted(_VALID_CLASSES_FOR_SCHEMA),
                            },
                            "details": {"type": "STRING", "description": "Detalhes adicionais (opcional)"},
                            "data_agendada": {"type": "STRING", "description": "Data agendada ISO 8601 (opcional; vazio = hoje)"},
                            "payment_cod": {"type": "STRING", "description": "Código Pix ou de barras do recebedor (obrigatório para engenheiro)"},
                            "obra_id": {"type": "STRING", "description": "UUID da obra vinculada (opcional)"},
                            "diarist_id": {"type": "STRING", "description": "UUID do diarista vinculado (opcional)"},
                        },
                        "required": ["title", "valor", "classe"],
                    },
                },
            },
            "required": ["pagamentos"],
        },
    ),
    "rh_get_me_resumo": ToolDeclaration(
        name="rh_get_me_resumo",
        description="Busca resumo RH do próprio funcionário autenticado. Apenas para role funcionario.",
        parameters={
            "type": "OBJECT",
            "properties": {},
            "required": [],
        },
    ),
    "rh_get_dashboard": ToolDeclaration(
        name="rh_get_dashboard",
        description="Busca dashboard RH do time. Apenas para roles admin ou financeiro. Não expõe CPF, salário completo nem documentos.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "mes": {"type": "INTEGER", "description": "Mês (1-12). Se omitido, usa o mês atual."},
                "ano": {"type": "INTEGER", "description": "Ano (ex: 2025). Se omitido, usa o ano atual."},
            },
            "required": [],
        },
    ),
    "obras_prepare_create": ToolDeclaration(
        name="obras_prepare_create",
        description="Prepara uma nova obra para confirmação humana. NÃO cria a obra - apenas gera um preview para o usuário confirmar.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Título da obra"},
                "description": {"type": "STRING", "description": "Descrição da obra"},
                "responsavel_id": {"type": "STRING", "description": "UUID do responsável pela obra"},
                "valor": {"type": "NUMBER", "description": "Valor estimado da obra"},
                "data_entrega": {"type": "STRING", "description": "Data de entrega estimada (ISO 8601)"},
            },
            "required": ["title", "description", "responsavel_id"],
        },
    ),
    "obras_prepare_update_status": ToolDeclaration(
        name="obras_prepare_update_status",
        description="Prepara mudança de status de uma obra para confirmação humana. NÃO altera o status - apenas gera preview.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "obra_id": {"type": "STRING", "description": "UUID da obra"},
                "novo_status": {
                    "type": "STRING",
                    "description": "Novo status desejado",
                    "enum": ["planejamento", "em_andamento", "financeiro", "finalizado"],
                },
                "motivo": {"type": "STRING", "description": "Motivo da mudança de status"},
            },
            "required": ["obra_id", "novo_status"],
        },
    ),
    "items_prepare_create": ToolDeclaration(
        name="items_prepare_create",
        description="Prepara criação de item/tarefa em uma obra para confirmação humana. NÃO cria o item.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "obra_id": {"type": "STRING", "description": "UUID da obra"},
                "title": {"type": "STRING", "description": "Título do item/tarefa"},
                "description": {"type": "STRING", "description": "Descrição do item"},
            },
            "required": ["obra_id", "title"],
        },
    ),
    "notificacoes_prepare_send": ToolDeclaration(
        name="notificacoes_prepare_send",
        description="Prepara envio de notificação para destinatários para confirmação humana. NÃO envia a notificação.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "mensagem": {"type": "STRING", "description": "Texto da notificação"},
                "obra_id": {"type": "STRING", "description": "UUID da obra relacionada (opcional)"},
            },
            "required": ["mensagem"],
        },
    ),
}


class ArkyToolRegistry:
    def get_declaration(self, tool_name: str) -> ToolDeclaration | None:
        return _TOOL_DECLARATIONS.get(tool_name)

    def get_declarations_for(
        self, tool_names: list[str]
    ) -> list[ToolDeclaration]:
        return [
            _TOOL_DECLARATIONS[name]
            for name in tool_names
            if name in _TOOL_DECLARATIONS
        ]
