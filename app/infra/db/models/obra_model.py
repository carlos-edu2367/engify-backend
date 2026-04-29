import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Boolean, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infra.db.models.base import Base, TimestampMixin
from app.domain.entities.obra import Obra, Status, Item, Image, ItemAttachment, Diaria, MuralPost, MuralAttachment, CategoriaObra
from app.domain.entities.money import Money


class CategoriaObraModel(Base, TimestampMixin):
    __tablename__ = "categorias_obra"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    obras: Mapped[list["ObraModel"]] = relationship(
        back_populates="categoria", lazy="raise"
    )

    __table_args__ = (
        Index("idx_categorias_obra_team_deleted", "team_id", "is_deleted"),
        Index("idx_categorias_obra_team_title", "team_id", "title"),
    )

    def to_domain(self) -> CategoriaObra:
        c = object.__new__(CategoriaObra)
        c.id = self.id
        c.team_id = self.team_id
        c.title = self.title
        c.descricao = self.descricao
        c.cor = self.cor
        c.is_deleted = self.is_deleted
        c.created_at = self.created_at
        return c

    @classmethod
    def from_domain(cls, cat: CategoriaObra) -> "CategoriaObraModel":
        return cls(
            id=cat.id or uuid.uuid4(),
            team_id=cat.team_id,
            title=cat.title,
            descricao=cat.descricao,
            cor=cat.cor,
            is_deleted=cat.is_deleted,
        )

    def update_from_domain(self, cat: CategoriaObra) -> None:
        self.title = cat.title
        self.descricao = cat.descricao
        self.cor = cat.cor
        self.is_deleted = cat.is_deleted


class ObraModel(Base, TimestampMixin):
    __tablename__ = "obras"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    responsavel_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categorias_obra.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    valor_amount: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    valor_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=Status.PLANEJAMENTO.value)
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    data_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_recebido: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False, default=Decimal("0"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    team: Mapped["TeamModel"] = relationship(  # type: ignore[name-defined]
        back_populates="obras", lazy="raise"
    )
    categoria: Mapped["CategoriaObraModel | None"] = relationship(
        back_populates="obras", lazy="raise", foreign_keys=[categoria_id]
    )
    items: Mapped[list["ItemModel"]] = relationship(
        back_populates="obra", lazy="raise"
    )
    images: Mapped[list["ImageModel"]] = relationship(
        back_populates="obra", lazy="raise"
    )
    diarias: Mapped[list["DiaryModel"]] = relationship(
        back_populates="obra", lazy="raise"
    )
    mural_posts: Mapped[list["MuralPostModel"]] = relationship(
        back_populates="obra", lazy="raise"
    )

    __table_args__ = (
        # Consulta principal: obras do time ativas
        Index("idx_obras_team_deleted", "team_id", "is_deleted"),
        # Filtro por status dentro de um time
        Index("idx_obras_team_status", "team_id", "status"),
        # Ordenação por data de criação
        Index("idx_obras_team_created", "team_id", "created_date"),
        Index("idx_obras_categoria_id", "categoria_id"),
        Index("idx_obras_team_categoria_deleted", "team_id", "categoria_id", "is_deleted"),
        Index("idx_obras_team_total_recebido", "team_id", "total_recebido"),
    )

    def to_domain(self) -> Obra:
        obra = object.__new__(Obra)
        obra.id = self.id
        obra.title = self.title
        obra.team_id = self.team_id
        obra.responsavel_id = self.responsavel_id
        obra.categoria_id = self.categoria_id
        obra.description = self.description
        obra.valor = Money(self.valor_amount, self.valor_currency) if self.valor_amount is not None else None
        obra.status = Status(self.status)
        obra.created_date = self.created_date
        obra.data_entrega = self.data_entrega
        obra.total_recebido = self.total_recebido if self.total_recebido is not None else Decimal("0")
        obra.is_deleted = self.is_deleted
        return obra

    @classmethod
    def from_domain(cls, obra: Obra) -> "ObraModel":
        return cls(
            id=obra.id or uuid.uuid4(),
            team_id=obra.team_id,
            responsavel_id=obra.responsavel_id,
            categoria_id=obra.categoria_id,
            title=obra.title,
            description=obra.description,
            valor_amount=obra.valor.amount if obra.valor else None,
            valor_currency=obra.valor.currency if obra.valor else "BRL",
            status=obra.status.value,
            created_date=obra.created_date or datetime.now(timezone.utc),
            data_entrega=obra.data_entrega,
            total_recebido=obra.total_recebido,
            is_deleted=obra.is_deleted,
        )

    def update_from_domain(self, obra: Obra) -> None:
        self.title = obra.title
        self.responsavel_id = obra.responsavel_id
        self.categoria_id = obra.categoria_id
        self.description = obra.description
        self.valor_amount = obra.valor.amount if obra.valor else None
        self.valor_currency = obra.valor.currency if obra.valor else "BRL"
        self.status = obra.status.value
        self.data_entrega = obra.data_entrega
        self.total_recebido = obra.total_recebido
        self.is_deleted = obra.is_deleted


class ItemModel(Base, TimestampMixin):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    obra_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalizado para RLS e consultas por tenant sem join
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    responsavel_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=Status.PLANEJAMENTO.value)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    obra: Mapped["ObraModel"] = relationship(back_populates="items", lazy="raise")
    attachments: Mapped[list["ItemAttachmentModel"]] = relationship(
        back_populates="item", lazy="raise"
    )

    __table_args__ = (
        Index("idx_items_obra_deleted", "obra_id", "is_deleted"),
        Index("idx_items_team_id", "team_id"),
    )

    def to_domain(self) -> Item:
        item = object.__new__(Item)
        item.id = self.id
        item.obra_id = self.obra_id
        item.team_id = self.team_id
        item.responsavel_id = self.responsavel_id
        item.title = self.title
        item.description = self.description
        item.status = Status(self.status)
        item.is_deleted = self.is_deleted
        return item

    @classmethod
    def from_domain(cls, item: Item) -> "ItemModel":
        return cls(
            id=item.id or uuid.uuid4(),
            obra_id=item.obra_id,
            team_id=item.team_id,
            responsavel_id=item.responsavel_id,
            title=item.title,
            description=item.description,
            status=item.status.value,
            is_deleted=item.is_deleted,
        )

    def update_from_domain(self, item: Item) -> None:
        self.responsavel_id = item.responsavel_id
        self.title = item.title
        self.description = item.description
        self.status = item.status.value
        self.is_deleted = item.is_deleted


class ItemAttachmentModel(Base, TimestampMixin):
    __tablename__ = "item_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalizado para RLS por tenant
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    item: Mapped["ItemModel"] = relationship(back_populates="attachments", lazy="raise")

    __table_args__ = (
        Index("idx_item_attachments_item", "item_id", "is_deleted"),
        Index("idx_item_attachments_team", "team_id"),
    )

    def to_domain(self) -> ItemAttachment:
        a = object.__new__(ItemAttachment)
        a.id = self.id
        a.item_id = self.item_id
        a.team_id = self.team_id
        a.file_path = self.file_path
        a.file_name = self.file_name
        a.content_type = self.content_type
        a.is_deleted = self.is_deleted
        a.created_at = self.created_at
        return a

    @classmethod
    def from_domain(cls, a: ItemAttachment) -> "ItemAttachmentModel":
        return cls(
            id=a.id or uuid.uuid4(),
            item_id=a.item_id,
            team_id=a.team_id,
            file_path=a.file_path,
            file_name=a.file_name,
            content_type=a.content_type,
            is_deleted=a.is_deleted,
        )

    def update_from_domain(self, a: ItemAttachment) -> None:
        self.is_deleted = a.is_deleted


class ImageModel(Base, TimestampMixin):
    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    obra_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="image/jpeg")
    bucket: Mapped[str] = mapped_column(String(100), nullable=False, default="engify")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    obra: Mapped["ObraModel"] = relationship(back_populates="images", lazy="raise")

    __table_args__ = (
        Index("idx_images_obra", "obra_id", "is_deleted"),
        Index("idx_images_team", "team_id"),
    )

    def to_domain(self) -> Image:
        img = object.__new__(Image)
        img.id = self.id
        img.obra_id = self.obra_id
        img.team_id = self.team_id
        img.file_path = self.file_path
        img.file_name = self.file_name
        img.content_type = self.content_type
        img.bucket = self.bucket
        img.is_deleted = self.is_deleted
        img.created_at = self.created_at
        return img

    @classmethod
    def from_domain(cls, img: Image) -> "ImageModel":
        return cls(
            id=img.id or uuid.uuid4(),
            obra_id=img.obra_id,
            team_id=img.team_id,
            file_path=img.file_path,
            file_name=img.file_name,
            content_type=img.content_type,
            bucket=img.bucket,
            is_deleted=img.is_deleted,
        )


class DiaryModel(Base, TimestampMixin):
    __tablename__ = "diarias"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Denormalizado para RLS e filtros por tenant/período sem joins extras
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    diarista_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("diarists.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obra_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="RESTRICT"),
        nullable=False,
    )
    descricao_diaria: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    quantidade: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    data: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    obra: Mapped["ObraModel"] = relationship(back_populates="diarias", lazy="raise")
    diarista: Mapped["DiaristModel"] = relationship(lazy="raise")  # type: ignore[name-defined]

    __table_args__ = (
        # Consulta por período dentro de um time (rota principal de listagem)
        Index("idx_diarias_team_data", "team_id", "data"),
        # Filtro por diarista
        Index("idx_diarias_diarista", "diarista_id"),
        # Filtro por obra
        Index("idx_diarias_obra", "obra_id", "is_deleted"),
    )

    def to_domain(self) -> Diaria:
        """Requer diarista e obra carregados (selectinload)."""
        diaria = object.__new__(Diaria)
        diaria.id = self.id
        diaria.team_id = self.team_id
        diaria.diarista = self.diarista.to_domain()
        diaria.obra = self.obra.to_domain()
        diaria.descricao_diaria = self.descricao_diaria
        diaria.quantidade = self.quantidade
        diaria.data = self.data
        diaria.is_deleted = self.is_deleted
        return diaria

    @classmethod
    def from_domain(cls, diaria: Diaria) -> "DiaryModel":
        return cls(
            id=diaria.id or uuid.uuid4(),
            team_id=diaria.team_id,
            diarista_id=diaria.diarista.id,
            obra_id=diaria.obra.id,
            descricao_diaria=diaria.descricao_diaria,
            quantidade=diaria.quantidade,
            data=diaria.data or datetime.now(timezone.utc),
            is_deleted=diaria.is_deleted,
        )

    def update_from_domain(self, diaria: Diaria) -> None:
        self.descricao_diaria = diaria.descricao_diaria
        self.quantidade = diaria.quantidade
        self.data = diaria.data
        self.is_deleted = diaria.is_deleted


class MuralPostModel(Base, TimestampMixin):
    __tablename__ = "mural_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    obra_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalizado para RLS por tenant — evita JOIN com obras em toda consulta
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Lista de UUIDs dos usuários mencionados — JSONB evita tabela de junção para MVP
    mentions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    obra: Mapped["ObraModel"] = relationship(back_populates="mural_posts", lazy="raise")
    attachments: Mapped[list["MuralAttachmentModel"]] = relationship(
        back_populates="post", lazy="raise", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Consulta principal: posts da obra ordenados por data — inclui created_at para sort
        Index("idx_mural_obra_deleted", "obra_id", "is_deleted"),
        Index("idx_mural_team", "team_id"),
    )

    def to_domain(self) -> MuralPost:
        p = object.__new__(MuralPost)
        p.id = self.id
        p.obra_id = self.obra_id
        p.team_id = self.team_id
        p.author_id = self.author_id
        p.content = self.content
        p.mentions = [uuid.UUID(m) for m in (self.mentions or [])]
        p.created_at = self.created_at
        p.is_deleted = self.is_deleted
        p.author_nome = None        # preenchido pelo repositório via JOIN
        p.attachments = []          # preenchido pelo repositório via selectinload
        return p

    @classmethod
    def from_domain(cls, post: MuralPost) -> "MuralPostModel":
        return cls(
            id=post.id,
            obra_id=post.obra_id,
            team_id=post.team_id,
            author_id=post.author_id,
            content=post.content,
            mentions=[str(m) for m in post.mentions],
            is_deleted=post.is_deleted,
        )

    def update_from_domain(self, post: MuralPost) -> None:
        self.is_deleted = post.is_deleted


class MuralAttachmentModel(Base, TimestampMixin):
    __tablename__ = "mural_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mural_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    post: Mapped["MuralPostModel"] = relationship(back_populates="attachments", lazy="raise")

    __table_args__ = (
        Index("idx_mural_attachments_post", "post_id", "is_deleted"),
        Index("idx_mural_attachments_team", "team_id"),
    )

    def to_domain(self) -> MuralAttachment:
        a = object.__new__(MuralAttachment)
        a.id = self.id
        a.post_id = self.post_id
        a.team_id = self.team_id
        a.file_path = self.file_path
        a.file_name = self.file_name
        a.content_type = self.content_type
        a.created_at = self.created_at
        a.is_deleted = self.is_deleted
        return a

    @classmethod
    def from_domain(cls, a: MuralAttachment) -> "MuralAttachmentModel":
        return cls(
            id=a.id,
            post_id=a.post_id,
            team_id=a.team_id,
            file_path=a.file_path,
            file_name=a.file_name,
            content_type=a.content_type,
            is_deleted=a.is_deleted,
        )

    def update_from_domain(self, a: MuralAttachment) -> None:
        self.is_deleted = a.is_deleted
