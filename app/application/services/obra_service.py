from app.domain.entities.obra import Obra, Status, Item, Diaria, Image, ItemAttachment, MuralPost, MuralAttachment
from app.domain.entities.financeiro import PagamentoAgendado, MovClass
from app.domain.errors import DomainError
from app.application.providers.repo.obra_repo import (
    ObraRepository, DiaryRepository, ItemRepository,
    ItemAttachmentRepository, ImageRepository, MuralRepository,
)
from app.application.providers.repo.team_repos import DiaristRepository
from app.application.providers.repo.financeiro_repo import PagamentoAgendadoRepository
from app.application.providers.uow import UOWProvider
from app.application.dtos.obra import (CreateObraDTO, CreateDiary, DiariesResponse,
                                       EditDiary, EditObraInfo, CreateItem, UpdateItem,
                                       CreateMuralPost, CreateMuralAttachment,
                                       CreateItemAttachment, CreateObraImage)
from app.domain.entities.money import Money
from uuid import UUID
from datetime import datetime


class ObraService():
    def __init__(self, obra_repo: ObraRepository, uow: UOWProvider):
        self.obra_repo = obra_repo
        self.uow = uow

    async def create_obra(self, dto: CreateObraDTO) -> Obra:
        valor = Money(dto.valor) if dto.valor is not None else None
        new = Obra(
            title=dto.title,
            team_id=dto.team_id,
            responsavel_id=dto.responsavel_id,
            description=dto.description,
            valor=valor,
            data_entrega=dto.data_entrega
        )
        saved = await self.obra_repo.save(new)
        await self.uow.commit()
        return saved

    async def get_obra(self, obra_id: UUID, team_id: UUID | None = None) -> Obra:
        return await self.obra_repo.get_by_id(obra_id, team_id)

    async def list_obras(self, team_id: UUID, page: int, limit: int) -> list[Obra]:
        return await self.obra_repo.get_by_team(team_id, page, limit)

    async def count_obras(self, team_id: UUID) -> int:
        return await self.obra_repo.count_by_team(team_id)

    async def list_by_status(self, team_id: UUID, status: Status,
                             page: int, limit: int) -> list[Obra]:
        return await self.obra_repo.get_by_status(team_id, status, limit, page)

    async def count_by_status(self, team_id: UUID, status: Status) -> int:
        return await self.obra_repo.count_by_status(team_id, status)

    async def delete_obra(self, obra: Obra) -> None:
        obra.delete()
        await self.obra_repo.save(obra)
        await self.uow.commit()

    async def update_status(self, obra: Obra, status: Status) -> Obra:
        obra.status = status
        saved = await self.obra_repo.save(obra)
        await self.uow.commit()
        return saved

    async def update_obra(self, obra: Obra, dtos: EditObraInfo) -> Obra:
        if dtos.title:
            obra.title = dtos.title
        if dtos.responsavel_id:
            obra.responsavel_id = dtos.responsavel_id
        if dtos.description:
            obra.description = dtos.description
        if dtos.valor is not None:
            obra.valor = Money(dtos.valor)
        if dtos.data_entrega:
            obra.data_entrega = dtos.data_entrega

        saved = await self.obra_repo.save(obra)
        await self.uow.commit()
        return saved


class DiaryService():
    def __init__(self, obra_repo: ObraRepository, diarist_repo: DiaristRepository,
                 diary_repo: DiaryRepository, pagamento_repo: PagamentoAgendadoRepository,
                 uow: UOWProvider):
        self.obra_repo = obra_repo
        self.diary_repo = diary_repo
        self.diarist_repo = diarist_repo
        self.pagamento_repo = pagamento_repo
        self.uow = uow

    async def create_diary(self, dtos: CreateDiary, team_id: UUID) -> Diaria:
        obra = await self.obra_repo.get_by_id(dtos.obra_id, team_id)
        diarist = await self.diarist_repo.get_by_id(dtos.diarista_id, team_id)
        new = Diaria(
            diarista=diarist,
            obra=obra,
            descricao_diaria=dtos.descricao_diaria,
            quantidade=dtos.quantidade_diaria,
            data=dtos.data,
        )
        saved = await self.diary_repo.save(new)

        # Automação: agenda pagamento para o diarista (será pago pelo módulo financeiro)
        data_ref = saved.data.strftime("%d/%m/%Y")
        qtd = int(saved.quantidade) if saved.quantidade == int(saved.quantidade) else saved.quantidade
        
        details_text = f"{qtd} diária(s) em {data_ref} — obra: {obra.title}"
        if saved.descricao_diaria:
            details_text += f" ({saved.descricao_diaria})"
            
        pag = PagamentoAgendado(
            team_id=saved.team_id,
            title=f"Diarista: {diarist.nome}",
            details=details_text,
            valor=diarist.valor_diaria * saved.quantidade,
            classe=MovClass.DIARISTA,
            data_agendada=dtos.data_pagamento or saved.data,
            diarist_id=diarist.id,
            obra_id=obra.id,
            payment_cod=diarist.chave_pix,
        )
        await self.pagamento_repo.save(pag)

        await self.uow.commit()
        return saved

    async def get_diary(self, diary_id: UUID, team_id: UUID | None = None) -> Diaria:
        return await self.diary_repo.get_by_id(diary_id, team_id)

    async def edit_diary(self, dtos: EditDiary, diary: Diaria) -> Diaria:
        if dtos.data:
            diary.data = dtos.data
        if dtos.descricao_diaria:
            diary.descricao_diaria = dtos.descricao_diaria
        if dtos.quantidade_diaria:
            diary.quantidade = dtos.quantidade_diaria

        saved = await self.diary_repo.save(diary)
        await self.uow.commit()
        return saved

    async def remove_diary(self, diary: Diaria) -> None:
        diary.delete()
        await self.diary_repo.save(diary)
        await self.uow.commit()

    async def count_diaries_by_period(self, init_date: datetime, end_date: datetime,
                                      team_id: UUID,
                                      obra_id: UUID | None = None) -> int:
        return await self.diary_repo.count_by_period(init_date, end_date, team_id, obra_id)

    async def list_diaries_by_period(self, init_date: datetime, end_date: datetime,
                                     team_id: UUID, page: int, limit: int,
                                     obra_id: UUID | None = None) -> list[DiariesResponse]:
        diaries = await self.diary_repo.get_by_period(
            initial_date=init_date, final_date=end_date,
            team_id=team_id, page=page, limit=limit, obra_id=obra_id,
        )
        return [
            DiariesResponse(
                id=d.id,
                diarist_id=d.diarista.id,
                diarist_name=d.diarista.nome,
                descricao_diaria=d.descricao_diaria,
                obra_id=d.obra.id,
                obra_title=d.obra.title,
                quantidade=d.quantidade,
                data=d.data
            )
            for d in diaries
        ]


class ItemService():
    def __init__(self, item_repo: ItemRepository, uow: UOWProvider):
        self.item_repo = item_repo
        self.uow = uow

    async def get_item(self, item_id: UUID, team_id: UUID | None = None) -> Item:
        return await self.item_repo.get_by_id(item_id, team_id)

    async def list_items(self, obra_id: UUID) -> list[Item]:
        return await self.item_repo.list_by_obra(obra_id)

    async def create_item(self, dtos: CreateItem) -> Item:
        new = Item(
            title=dtos.title,
            obra_id=dtos.obra_id,
            team_id=dtos.team_id,
            description=dtos.descricao,
            responsavel_id=dtos.responsavel_id,
        )
        saved = await self.item_repo.save(new)
        await self.uow.commit()
        return saved

    async def update_item(self, dtos: UpdateItem, item: Item) -> Item:
        if dtos.title:
            item.title = dtos.title
        if dtos.responsavel_id:
            item.responsavel_id = dtos.responsavel_id
        if dtos.descricao:
            item.description = dtos.descricao
        if dtos.status:
            item.status = dtos.status

        saved = await self.item_repo.save(item)
        await self.uow.commit()
        return saved

    async def delete_item(self, item: Item) -> None:
        item.delete()
        await self.item_repo.save(item)
        await self.uow.commit()


class ItemAttachmentService():
    def __init__(self, attachment_repo: ItemAttachmentRepository,
                 item_repo: ItemRepository, uow: UOWProvider):
        self.attachment_repo = attachment_repo
        self.item_repo = item_repo
        self.uow = uow

    async def register(self, dto: CreateItemAttachment) -> ItemAttachment:
        # Garante que o item existe e pertence ao team antes de registrar o anexo
        item = await self.item_repo.get_by_id(dto.item_id, dto.team_id)
        attachment = ItemAttachment(
            item_id=item.id,
            team_id=dto.team_id,
            file_path=dto.file_path,
            file_name=dto.file_name,
            content_type=dto.content_type,
        )
        saved = await self.attachment_repo.save(attachment)
        await self.uow.commit()
        return saved

    async def list_by_item(self, item_id: UUID) -> list[ItemAttachment]:
        return await self.attachment_repo.list_by_item(item_id)

    async def get(self, attachment_id: UUID) -> ItemAttachment:
        return await self.attachment_repo.get_by_id(attachment_id)

    async def delete(self, attachment: ItemAttachment) -> None:
        attachment.delete()
        await self.attachment_repo.save(attachment)
        await self.uow.commit()


class ObraImageService():
    def __init__(self, image_repo: ImageRepository, uow: UOWProvider):
        self.image_repo = image_repo
        self.uow = uow

    async def list_by_obra(self, obra_id: UUID) -> list[Image]:
        return await self.image_repo.list_by_obra(obra_id)

    async def register_image(self, dto: CreateObraImage) -> Image:
        image = Image(
            obra_id=dto.obra_id,
            team_id=dto.team_id,
            file_path=dto.file_path,
            file_name=dto.file_name,
            content_type=dto.content_type,
        )
        saved = await self.image_repo.save(image)
        await self.uow.commit()
        return saved

    async def delete_image(self, image: Image) -> None:
        image.delete()
        await self.image_repo.save(image)
        await self.uow.commit()


class MuralService():
    def __init__(self, mural_repo: MuralRepository, obra_repo: ObraRepository,
                 uow: UOWProvider):
        self.mural_repo = mural_repo
        self.obra_repo = obra_repo
        self.uow = uow

    async def create_post(self, dto: CreateMuralPost) -> MuralPost:
        # Valida que a obra existe e pertence ao time
        await self.obra_repo.get_by_id(dto.obra_id, dto.team_id)
        post = MuralPost(
            obra_id=dto.obra_id,
            team_id=dto.team_id,
            author_id=dto.author_id,
            content=dto.content,
            mentions=dto.mentions,
        )
        saved = await self.mural_repo.save_post(post)
        await self.uow.commit()
        return saved

    async def get_post(self, post_id: UUID, team_id: UUID) -> MuralPost:
        return await self.mural_repo.get_post_by_id(post_id, team_id)

    async def list_posts(self, obra_id: UUID, page: int, limit: int) -> list[MuralPost]:
        return await self.mural_repo.list_posts(obra_id, page, limit)

    async def count_posts(self, obra_id: UUID) -> int:
        return await self.mural_repo.count_posts(obra_id)

    async def delete_post(self, post: MuralPost, requester_id: UUID,
                          is_admin: bool) -> None:
        if not is_admin and post.author_id != requester_id:
            raise DomainError("Você só pode remover seus próprios posts")
        post.delete()
        await self.mural_repo.save_post(post)
        await self.uow.commit()

    async def add_attachment(self, dto: CreateMuralAttachment) -> MuralAttachment:
        attachment = MuralAttachment(
            post_id=dto.post_id,
            team_id=dto.team_id,
            file_path=dto.file_path,
            file_name=dto.file_name,
            content_type=dto.content_type,
        )
        saved = await self.mural_repo.save_attachment(attachment)
        await self.uow.commit()
        return saved

    async def list_attachments(self, post_id: UUID) -> list[MuralAttachment]:
        return await self.mural_repo.list_attachments(post_id)

    async def get_attachment(self, attachment_id: UUID, team_id: UUID) -> MuralAttachment:
        return await self.mural_repo.get_attachment(attachment_id, team_id)

    async def delete_attachment(self, attachment: MuralAttachment, post: MuralPost,
                                requester_id: UUID, is_admin: bool) -> None:
        if not is_admin and post.author_id != requester_id:
            raise DomainError("Você só pode remover anexos dos seus próprios posts")
        attachment.delete()
        await self.mural_repo.save_attachment(attachment)
        await self.uow.commit()
