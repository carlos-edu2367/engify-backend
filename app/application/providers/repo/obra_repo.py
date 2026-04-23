from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.obra import Obra, Status, Diaria, Item, ItemAttachment, Image, MuralPost, MuralAttachment, CategoriaObra
from datetime import datetime


class ObraRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Obra:
        pass

    @abstractmethod
    async def get_by_team(self, team_id: UUID, page: int, limit: int) -> list[Obra]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def get_by_status(self, team_id: UUID, status: Status, limit: int, page: int) -> list[Obra]:
        pass

    @abstractmethod
    async def count_by_status(self, team_id: UUID, status: Status) -> int:
        pass

    @abstractmethod
    async def get_by_categoria(self, categoria_id: UUID, team_id: UUID, page: int, limit: int) -> list[Obra]:
        pass

    @abstractmethod
    async def count_by_categoria(self, categoria_id: UUID, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def save(self, obra: Obra) -> Obra:
        pass


class CategoriaObraRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> CategoriaObra:
        pass

    @abstractmethod
    async def get_by_team(self, team_id: UUID, page: int, limit: int) -> list[CategoriaObra]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def get_by_nome(self, title: str, team_id: UUID) -> CategoriaObra | None:
        pass

    @abstractmethod
    async def save(self, categoria: CategoriaObra) -> CategoriaObra:
        pass


class DiaryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Diaria:
        pass

    @abstractmethod
    async def get_by_period(self, initial_date: datetime, final_date: datetime,
                            team_id: UUID, page: int, limit: int,
                            obra_id: UUID | None = None) -> list[Diaria]:
        pass

    @abstractmethod
    async def count_by_period(self, initial_date: datetime, final_date: datetime,
                              team_id: UUID, obra_id: UUID | None = None) -> int:
        pass

    @abstractmethod
    async def get_by_diarist(self, diarist_id: UUID, page: int, limit: int) -> list[Diaria]:
        pass

    @abstractmethod
    async def save(self, diary: Diaria) -> Diaria:
        pass


class ItemRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Item:
        pass

    @abstractmethod
    async def list_by_obra(self, obra_id: UUID) -> list[Item]:
        pass

    @abstractmethod
    async def save(self, item: Item) -> Item:
        pass


class ItemAttachmentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> ItemAttachment:
        pass

    @abstractmethod
    async def list_by_item(self, item_id: UUID) -> list[ItemAttachment]:
        pass

    @abstractmethod
    async def save(self, attachment: ItemAttachment) -> ItemAttachment:
        pass


class ImageRepository(ABC):
    @abstractmethod
    async def list_by_obra(self, obra_id: UUID) -> list[Image]:
        pass

    @abstractmethod
    async def save(self, image: Image) -> Image:
        pass


class MuralRepository(ABC):
    @abstractmethod
    async def save_post(self, post: MuralPost) -> MuralPost:
        pass

    @abstractmethod
    async def get_post_by_id(self, post_id: UUID, team_id: UUID) -> MuralPost:
        pass

    @abstractmethod
    async def list_posts(self, obra_id: UUID, page: int, limit: int) -> list[MuralPost]:
        pass

    @abstractmethod
    async def count_posts(self, obra_id: UUID) -> int:
        pass

    @abstractmethod
    async def save_attachment(self, attachment: MuralAttachment) -> MuralAttachment:
        pass

    @abstractmethod
    async def list_attachments(self, post_id: UUID) -> list[MuralAttachment]:
        pass

    @abstractmethod
    async def list_attachments_by_obra(self, obra_id: UUID, team_id: UUID) -> list[MuralAttachment]:
        pass

    @abstractmethod
    async def get_attachment(self, attachment_id: UUID, team_id: UUID) -> MuralAttachment:
        pass
