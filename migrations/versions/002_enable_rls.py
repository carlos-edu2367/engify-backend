"""enable row level security

Revision ID: 002
Revises: 001
Create Date: 2026-04-04
"""
from typing import Sequence, Union
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tabelas com team_id direto que receberão RLS
_TENANT_TABLES = [
    "diarists",
    "users",
    "solicitacoes_cadastro",
    "obras",
    "items",
    "item_attachments",
    "images",
    "diarias",
    "pagamentos_agendados",
    "movimentacoes",
    "pagamento_attachments",
]

# Policy USING: permite acesso quando:
# 1. app.current_tenant não está definido (migrações, admin direto)
# 2. team_id bate com o tenant da sessão
_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    for table in _TENANT_TABLES:
        # Habilita RLS — afeta SELECTs e DMLs de usuários não-superuser
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # Força a policy mesmo para o owner da tabela (o role da aplicação)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Policy de tenant isolation para SELECT
        op.execute(f"""
            CREATE POLICY tenant_select ON {table}
            FOR SELECT
            USING ({_POLICY_USING})
        """)

        # Policy de tenant isolation para INSERT (WITH CHECK garante inserção no tenant correto)
        op.execute(f"""
            CREATE POLICY tenant_insert ON {table}
            FOR INSERT
            WITH CHECK ({_POLICY_USING})
        """)

        # Policy de tenant isolation para UPDATE e DELETE
        op.execute(f"""
            CREATE POLICY tenant_update ON {table}
            FOR UPDATE
            USING ({_POLICY_USING})
        """)

        op.execute(f"""
            CREATE POLICY tenant_delete ON {table}
            FOR DELETE
            USING ({_POLICY_USING})
        """)


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
