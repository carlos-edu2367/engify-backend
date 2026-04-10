from enum import Enum
from uuid import UUID, uuid4
from app.domain.entities.money import Money
from app.domain.entities.team import Diarist
from datetime import datetime, timezone
from app.domain.errors import DomainError


class Status(Enum):
    PLANEJAMENTO = "planejamento"
    EM_ANDAMENTO = "em_andamento"
    FINALIZADO = "finalizado"


class Obra():
    def __init__(self, title: str,
                 team_id: UUID, responsavel_id: UUID,
                 description: str, id: UUID = None,
                 valor: Money = None, status: Status = Status.PLANEJAMENTO,
                 created_date: datetime = None, data_entrega: datetime = None):
        self.id = id
        self.title = title
        self.team_id = team_id
        self.responsavel_id = responsavel_id
        self.description = description
        self.valor = valor
        self.status = status
        self.created_date = created_date
        self.data_entrega = data_entrega
        self.is_deleted = False

        if not self.created_date:
            self.created_date = datetime.now(timezone.utc)

    def delete(self):
        self.is_deleted = True


class Item():
    def __init__(self, title: str, obra_id: UUID, team_id: UUID,
                 description: str = None, responsavel_id: UUID = None,
                 status: Status = Status.PLANEJAMENTO, id: UUID = None):
        if not obra_id:
            raise DomainError("Não é possível criar um item sem o ID da obra")
        if not team_id:
            raise DomainError("Não é possível criar um item sem o ID do time")
        self.title = title
        self.description = description
        self.responsavel_id = responsavel_id
        self.status = status
        self.obra_id = obra_id
        self.team_id = team_id  # denormalizado para RLS e isolamento de tenant
        self.id = id
        self.is_deleted = False

    def delete(self):
        self.is_deleted = True


class ItemAttachment():
    """Imagem anexada a um item/tarefa. Upload feito diretamente pelo frontend via signed URL."""
    def __init__(self, item_id: UUID, team_id: UUID, file_path: str,
                 file_name: str, content_type: str, id: UUID = None):
        self.id = id or uuid4()
        self.item_id = item_id
        self.team_id = team_id
        self.file_path = file_path
        self.file_name = file_name
        self.content_type = content_type
        self.is_deleted = False
        self.created_at = datetime.now(timezone.utc)

    def delete(self):
        self.is_deleted = True


class Image():
    """Imagem anexada a uma obra. Upload feito diretamente pelo frontend via signed URL."""
    def __init__(self, obra_id: UUID, team_id: UUID, file_path: str,
                 file_name: str, content_type: str = "image/jpeg",
                 bucket: str = "engify", id: UUID = None):
        self.id = id or uuid4()
        self.obra_id = obra_id
        self.team_id = team_id
        self.file_path = file_path
        self.file_name = file_name
        self.content_type = content_type
        self.bucket = bucket
        self.is_deleted = False
        self.created_at = datetime.now(timezone.utc)

    def delete(self):
        self.is_deleted = True


class MuralPost():
    """Mensagem postada no mural de uma obra. Visível apenas para membros internos do time."""

    MAX_CONTENT_LENGTH = 2000

    def __init__(self, obra_id: UUID, team_id: UUID, author_id: UUID,
                 content: str, mentions: list[UUID] = None,
                 id: UUID = None, created_at: datetime = None):
        if not content or not content.strip():
            raise DomainError("Conteúdo do post não pode ser vazio")
        if len(content) > self.MAX_CONTENT_LENGTH:
            raise DomainError(f"Conteúdo excede {self.MAX_CONTENT_LENGTH} caracteres")
        self.id = id or uuid4()
        self.obra_id = obra_id
        self.team_id = team_id
        self.author_id = author_id
        self.content = content.strip()
        self.mentions = mentions if mentions is not None else []
        self.created_at = created_at or datetime.now(timezone.utc)
        self.is_deleted = False
        # Preenchido pelo repositório via JOIN — não faz parte do estado persistido
        self.author_nome: str | None = None
        self.attachments: list["MuralAttachment"] = []

    def delete(self):
        self.is_deleted = True


class MuralAttachment():
    """Arquivo anexado a um post do mural. Upload feito via signed URL pelo frontend."""

    def __init__(self, post_id: UUID, team_id: UUID, file_path: str,
                 file_name: str, content_type: str, id: UUID = None,
                 created_at: datetime = None):
        self.id = id or uuid4()
        self.post_id = post_id
        self.team_id = team_id
        self.file_path = file_path
        self.file_name = file_name
        self.content_type = content_type
        self.created_at = created_at or datetime.now(timezone.utc)
        self.is_deleted = False

    def delete(self):
        self.is_deleted = True


class Diaria():
    def __init__(self, diarista: Diarist, obra: Obra,
                 descricao_diaria: str = None, quantidade: float = 1,
                 data: datetime = None, id: UUID = None):
        self.id = id
        self.diarista = diarista
        self.obra = obra
        # Denormalizado para isolamento de tenant e RLS
        self.team_id = obra.team_id
        self.descricao_diaria = descricao_diaria
        self.quantidade = quantidade
        self.data = data or datetime.now(timezone.utc)
        self.is_deleted = False

    def delete(self):
        self.is_deleted = True
