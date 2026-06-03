"""
ArkyToolRegistry — maps tool names to Gemini function declarations.
Only tools registered here can ever be called by the model.
"""
from app.infra.ai.gemini_client import GeminiToolDeclaration

_TOOL_DECLARATIONS: dict[str, GeminiToolDeclaration] = {
    "obras_get_detail": GeminiToolDeclaration(
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
    "obras_list": GeminiToolDeclaration(
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
    "items_list_by_obra": GeminiToolDeclaration(
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
    "notificacoes_list": GeminiToolDeclaration(
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
    "financeiro_get_fluxo_caixa": GeminiToolDeclaration(
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
    "rh_get_me_resumo": GeminiToolDeclaration(
        name="rh_get_me_resumo",
        description="Busca resumo RH do próprio funcionário autenticado. Apenas para role funcionario.",
        parameters={
            "type": "OBJECT",
            "properties": {},
            "required": [],
        },
    ),
    "rh_get_dashboard": GeminiToolDeclaration(
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
    "obras_prepare_create": GeminiToolDeclaration(
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
    "obras_prepare_update_status": GeminiToolDeclaration(
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
    "items_prepare_create": GeminiToolDeclaration(
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
    "notificacoes_prepare_send": GeminiToolDeclaration(
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
    def get_declaration(self, tool_name: str) -> GeminiToolDeclaration | None:
        return _TOOL_DECLARATIONS.get(tool_name)

    def get_declarations_for(
        self, tool_names: list[str]
    ) -> list[GeminiToolDeclaration]:
        return [
            _TOOL_DECLARATIONS[name]
            for name in tool_names
            if name in _TOOL_DECLARATIONS
        ]
