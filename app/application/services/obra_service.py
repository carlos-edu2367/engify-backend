from app.domain.entities.obra import Obra, Status, Item, Diaria, Image, ItemAttachment, MuralPost, MuralAttachment, CategoriaObra
from app.domain.entities.financeiro import Movimentacao, MovimentacaoTypes, MovClass, Natureza, PagamentoAgendado
from app.domain.entities.notificacao import Notificacao, TipoNotificacao
from app.domain.errors import DomainError
from app.application.providers.repo.obra_repo import (
    ObraRepository, DiaryRepository, ItemRepository,
    ItemAttachmentRepository, ImageRepository, MuralRepository, CategoriaObraRepository,
)
from app.application.providers.repo.team_repos import DiaristRepository
from app.application.providers.repo.financeiro_repo import (
    MovimentacaoRepository, PagamentoAgendadoRepository,
)
from app.application.providers.repo.notificacao_repo import NotificacaoRepository
from app.application.providers.uow import UOWProvider
from app.application.dtos.obra import (CreateObraDTO, CreateDiary, DiariesResponse,
                                       EditDiary, EditObraInfo, CreateItem, UpdateItem,
                                       CreateMuralPost, CreateMuralAttachment,
                                       CreateItemAttachment, CreateObraImage,
                                       CreateCategoriaObraDTO, UpdateCategoriaObraDTO,
                                       AddRecebimentoDTO, DeleteRecebimentoDTO)
from app.application.providers.utility.pix_provider import generate_pix_copy_and_past
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
            data_entrega=dto.data_entrega,
            categoria_id=dto.categoria_id,
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

    async def update_status(self, obra: Obra, status: Status, caller_role: str | None = None) -> Obra:
        """Atualiza o status da obra.
        A transição para FINALIZADO a partir de FINANCEIRO exige role ADMIN ou FINANCEIRO.
        """
        from app.domain.entities.user import Roles
        
        if (
            obra.status == Status.FINANCEIRO
            and status == Status.FINALIZADO
            and caller_role not in (Roles.ADMIN.value, Roles.FINANCEIRO.value)
        ):
            raise DomainError(
                "Apenas ADMIN ou FINANCEIRO podem finalizar uma obra em status Financeiro"
            )
            
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
        if dtos.remove_categoria:
            obra.categoria_id = None
        elif dtos.categoria_id is not None:
            obra.categoria_id = dtos.categoria_id

        saved = await self.obra_repo.save(obra)
        await self.uow.commit()
        return saved

    async def list_by_categoria(self, categoria_id: UUID, team_id: UUID,
                                page: int, limit: int) -> list[Obra]:
        return await self.obra_repo.get_by_categoria(categoria_id, team_id, page, limit)

    async def count_by_categoria(self, categoria_id: UUID, team_id: UUID) -> int:
        return await self.obra_repo.count_by_categoria(categoria_id, team_id)


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
            pix_copy_and_past=generate_pix_copy_and_past(
                payment_code=diarist.chave_pix,
                amount=(diarist.valor_diaria * saved.quantidade).amount,
                receiver_name=diarist.nome,
                city="GOIANIA",
            ),
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

    async def update_item(self, dtos: UpdateItem, item: Item, caller_role: str | None = None) -> Item:
        if dtos.title:
            item.title = dtos.title
        if dtos.responsavel_id:
            item.responsavel_id = dtos.responsavel_id
        if dtos.descricao:
            item.description = dtos.descricao
        if dtos.status:
            from app.domain.entities.user import Roles
            
            if (
                item.status == Status.FINANCEIRO
                and dtos.status == Status.FINALIZADO
                and caller_role not in (Roles.ADMIN.value, Roles.FINANCEIRO.value)
            ):
                raise DomainError(
                    "Apenas ADMIN ou FINANCEIRO podem finalizar um item em status Financeiro"
                )
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

    async def register_images(self, dtos: list[CreateObraImage]) -> list[Image]:
        """Persiste múltiplos arquivos (imagens/vídeos) em uma única transação."""
        saved_list = []
        for dto in dtos:
            image = Image(
                obra_id=dto.obra_id,
                team_id=dto.team_id,
                file_path=dto.file_path,
                file_name=dto.file_name,
                content_type=dto.content_type,
            )
            saved_list.append(await self.image_repo.save(image))
        await self.uow.commit()
        return saved_list

    async def delete_image(self, image: Image) -> None:
        image.delete()
        await self.image_repo.save(image)
        await self.uow.commit()


class MuralService():
    def __init__(self, mural_repo: MuralRepository, obra_repo: ObraRepository,
                 uow: UOWProvider, notif_repo: NotificacaoRepository | None = None):
        self.mural_repo = mural_repo
        self.obra_repo = obra_repo
        self.uow = uow
        self.notif_repo = notif_repo

    async def create_post(self, dto: CreateMuralPost) -> MuralPost:
        obra = await self.obra_repo.get_by_id(dto.obra_id, dto.team_id)
        post = MuralPost(
            obra_id=dto.obra_id,
            team_id=dto.team_id,
            author_id=dto.author_id,
            content=dto.content,
            mentions=dto.mentions,
        )
        saved = await self.mural_repo.save_post(post)

        if self.notif_repo and dto.mentions:
            mentioned_users = set(dto.mentions)
            for user_id in mentioned_users:
                if user_id == dto.author_id:
                    continue
                notif = Notificacao(
                    user_id=user_id,
                    team_id=dto.team_id,
                    tipo=TipoNotificacao.MENCAO_MURAL,
                    titulo="Você foi mencionado no mural",
                    mensagem=f"Você foi mencionado em um post na obra \"{obra.title}\".",
                    reference_id=obra.id,
                )
                await self.notif_repo.save(notif)

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

    async def list_attachments_by_obra(self, obra_id: UUID, team_id: UUID) -> list[MuralAttachment]:
        await self.obra_repo.get_by_id(obra_id, team_id)
        return await self.mural_repo.list_attachments_by_obra(obra_id, team_id)

    async def get_attachment(self, attachment_id: UUID, team_id: UUID) -> MuralAttachment:
        return await self.mural_repo.get_attachment(attachment_id, team_id)

    async def delete_attachment(self, attachment: MuralAttachment, post: MuralPost,
                                requester_id: UUID, is_admin: bool) -> None:
        if not is_admin and post.author_id != requester_id:
            raise DomainError("Você só pode remover anexos dos seus próprios posts")
        attachment.delete()
        await self.mural_repo.save_attachment(attachment)
        await self.uow.commit()


class CategoriaObraService():
    def __init__(self, categoria_repo: CategoriaObraRepository,
                 obra_repo: ObraRepository, uow: UOWProvider):
        self.categoria_repo = categoria_repo
        self.obra_repo = obra_repo
        self.uow = uow

    async def create_categoria(self, dto: CreateCategoriaObraDTO) -> CategoriaObra:
        existing = await self.categoria_repo.get_by_nome(dto.title, dto.team_id)
        if existing:
            raise DomainError("Já existe uma categoria com esse nome neste time")
        new = CategoriaObra(
            title=dto.title,
            team_id=dto.team_id,
            descricao=dto.descricao,
            cor=dto.cor,
        )
        saved = await self.categoria_repo.save(new)
        await self.uow.commit()
        return saved

    async def get_categoria(self, categoria_id: UUID, team_id: UUID) -> CategoriaObra:
        return await self.categoria_repo.get_by_id(categoria_id, team_id)

    async def list_categorias(self, team_id: UUID, page: int, limit: int) -> list[CategoriaObra]:
        return await self.categoria_repo.get_by_team(team_id, page, limit)

    async def count_categorias(self, team_id: UUID) -> int:
        return await self.categoria_repo.count_by_team(team_id)

    async def update_categoria(self, categoria: CategoriaObra,
                               dto: UpdateCategoriaObraDTO) -> CategoriaObra:
        if dto.title is not None and dto.title != categoria.title:
            existing = await self.categoria_repo.get_by_nome(dto.title, categoria.team_id)
            if existing and existing.id != categoria.id:
                raise DomainError("Já existe uma categoria com esse nome neste time")
            categoria.title = dto.title
        if dto.descricao is not None:
            categoria.descricao = dto.descricao
        if dto.cor is not None:
            categoria.cor = dto.cor
        saved = await self.categoria_repo.save(categoria)
        await self.uow.commit()
        return saved

    async def delete_categoria(self, categoria: CategoriaObra) -> None:
        # Set null em todas as obras vinculadas antes de excluir a categoria
        obras = await self.obra_repo.get_by_categoria(
            categoria.id, categoria.team_id, page=1, limit=10_000
        )
        for obra in obras:
            obra.categoria_id = None
            await self.obra_repo.save(obra)
        categoria.delete()
        await self.categoria_repo.save(categoria)
        await self.uow.commit()

    async def list_obras_by_categoria(self, categoria_id: UUID, team_id: UUID,
                                      page: int, limit: int) -> list[Obra]:
        return await self.obra_repo.get_by_categoria(categoria_id, team_id, page, limit)

    async def count_obras_by_categoria(self, categoria_id: UUID, team_id: UUID) -> int:
        return await self.obra_repo.count_by_categoria(categoria_id, team_id)


class RecebimentoService():
    """Orquestra adição de recebimentos à obra e listagem de entradas financeiras."""

    def __init__(self, obra_repo: ObraRepository,
                 mov_repo: MovimentacaoRepository,
                 uow: UOWProvider):
        self.obra_repo = obra_repo
        self.mov_repo = mov_repo
        self.uow = uow

    async def add_recebimento(self, dto: AddRecebimentoDTO) -> Obra:
        """Adiciona valor recebido à obra e cria movimentação de entrada atomicamente."""
        obra = await self.obra_repo.get_by_id(dto.obra_id, dto.team_id)

        obra.adicionar_recebimento(dto.valor)

        mov = Movimentacao(
            team_id=dto.team_id,
            title=f"Recebimento — {obra.title}",
            type=MovimentacaoTypes.ENTRADA,
            valor=Money(dto.valor),
            classe=MovClass.CONTRATO,
            natureza=Natureza.MANUAL,
            obra_id=obra.id,
        )
        await self.mov_repo.save(mov)
        saved_obra = await self.obra_repo.save(obra)
        await self.uow.commit()
        return saved_obra

    async def delete_recebimento(self, dto: DeleteRecebimentoDTO) -> Obra:
        """
        Remove um recebimento da obra de forma atÃ´mica.
        Reverte total_recebido e faz soft-delete da movimentaÃ§Ã£o de entrada.
        """
        obra = await self.obra_repo.get_by_id(dto.obra_id, dto.team_id)
        mov = await self.mov_repo.get_by_id(dto.recebimento_id, dto.team_id)

        if mov.obra_id != obra.id:
            raise DomainError("Recebimento nÃ£o pertence Ã  obra informada")
        if mov.type != MovimentacaoTypes.ENTRADA:
            raise DomainError("MovimentaÃ§Ã£o informada nÃ£o Ã© um recebimento")
        if mov.pagamento_id is not None:
            raise DomainError("MovimentaÃ§Ã£o informada nÃ£o Ã© um recebimento de obra")
        if mov.natureza != Natureza.MANUAL:
            raise DomainError("NÃ£o Ã© possÃ­vel remover recebimentos importados automaticamente")

        obra.remover_recebimento(mov.valor.amount)
        mov.delete()

        await self.mov_repo.save(mov)
        saved_obra = await self.obra_repo.save(obra)
        await self.uow.commit()
        return saved_obra

    async def list_entradas(self, obra_id: UUID, team_id: UUID,
                            page: int, limit: int) -> list[Movimentacao]:
        return await self.mov_repo.list_entradas_by_obra(obra_id, team_id, page, limit)

    async def count_entradas(self, obra_id: UUID, team_id: UUID) -> int:
        return await self.mov_repo.count_entradas_by_obra(obra_id, team_id)
