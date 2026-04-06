from app.application.dtos import team as team_dtos
from app.application.providers.repo import team_repos
from app.application.providers.repo.user_repos import UserRepository
from app.application.providers.utility.hash_provider import HashProvider
from app.domain.entities.team import Team, Diarist
from app.domain.entities.user import User, Roles
from app.application.providers.uow import UOWProvider
from app.domain.entities.identities import CNPJ, CPF
from app.domain.entities.money import Money
from app.domain import errors
import secrets
from uuid import UUID


class TeamService():
    def __init__(self, team_repo: team_repos.TeamRepository, uow: UOWProvider,
                 user_repo: UserRepository, hash: HashProvider):
        self.team_repo = team_repo
        self.uow = uow
        self.user_repo = user_repo
        self.hash = hash

    async def create_team(self, dto: team_dtos.CreateTeam) -> Team:
        cnpj = CNPJ(dto.cnpj)
        exists = await self.team_repo.get_by_cnpj(cnpj.value)
        if exists:
            raise errors.DomainError("Já existe um time com esse CNPJ")

        new = Team(title=dto.title, cnpj=cnpj)
        key = secrets.token_urlsafe(32)
        new.add_key(key)

        saved = await self.team_repo.save(new)
        await self.uow.commit()
        return saved

    async def create_first_user(self, dto: team_dtos.CreateFirstUser) -> User:
        """Cria o primeiro usuário (admin) do time usando a chave one-time."""
        cnpj = CNPJ(dto.cnpj)
        team = await self.team_repo.get_by_cnpj(cnpj.value)
        if not team:
            raise errors.DomainError("Time não encontrado")

        if not getattr(team, 'key', None):
            raise errors.DomainError("Chave de cadastro já utilizada")
        if team.key != dto.key:
            raise errors.DomainError("Chave de cadastro inválida")

        cpf = CPF(dto.cpf)
        exists = await self.user_repo.get_by_email_or_cpf(dto.email, cpf.value)
        if exists:
            raise errors.DomainError("Usuário com esse e-mail ou CPF já existe")

        User.ensure_password_strenght(dto.senha)
        senha_hash = self.hash.hash(dto.senha)
        new_user = User(nome=dto.nome, email=dto.email, senha_hash=senha_hash,
                        role=Roles.ADMIN, team=team, cpf=cpf)
        team.use_key()

        saved_user = await self.user_repo.save(new_user)
        await self.team_repo.save(team)
        await self.uow.commit()
        return saved_user

    async def update_team(self, team: Team, title: str) -> Team:
        team.title = title
        saved = await self.team_repo.save(team)
        await self.uow.commit()
        return saved

    async def get_days_for_expire(self, team_id: UUID) -> int:
        team = await self.team_repo.get_by_id(team_id)
        return team.get_days_for_expire()


class DiaristService():
    def __init__(self, team_repo: team_repos.TeamRepository,
                 diarist_repo: team_repos.DiaristRepository, uow: UOWProvider):
        self.team_repo = team_repo
        self.diarist_repo = diarist_repo
        self.uow = uow

    async def get_diarist(self, diarist_id: UUID, team_id: UUID | None = None) -> Diarist:
        return await self.diarist_repo.get_by_id(diarist_id, team_id)

    async def create_diarist(self, dtos: team_dtos.CreateDiarist, team_id: UUID) -> Diarist:
        new = Diarist(
            nome=dtos.nome,
            descricao=dtos.descricao,
            valor_diaria=Money(dtos.valor_diaria),
            chave_pix=dtos.chave_pix,
            team_id=team_id
        )
        saved = await self.diarist_repo.save(new)
        await self.uow.commit()
        return saved

    async def edit_diarist(self, diarist: Diarist, dtos: team_dtos.EditDiarist) -> Diarist:
        if not any([dtos.chave_pix, dtos.descricao, dtos.nome, dtos.valor_diaria]):
            raise errors.DomainError("Envie ao menos um campo para editar")

        if dtos.chave_pix:
            diarist.chave_pix = dtos.chave_pix
        if dtos.descricao:
            diarist.descricao = dtos.descricao
        if dtos.nome:
            diarist.nome = dtos.nome
        if dtos.valor_diaria:
            diarist.valor_diaria = Money(dtos.valor_diaria)

        edited = await self.diarist_repo.save(diarist)
        await self.uow.commit()
        return edited

    async def delete_diarist(self, diarist: Diarist) -> None:
        diarist.delete()
        await self.diarist_repo.save(diarist)
        await self.uow.commit()

    async def count_diarists(self, team_id: UUID) -> int:
        return await self.diarist_repo.count_by_team(team_id)

    async def list_diarists_paginated(
        self, team_id: UUID, limit: int, page: int
    ) -> tuple[list[Diarist], int]:
        """Retorna (itens_da_página, total_real) em duas queries paralelas."""
        items = await self.diarist_repo.list_by_team(team_id, page, limit)
        total = await self.diarist_repo.count_by_team(team_id)
        return items, total

    async def list_diarists(self, team_id: UUID, limit: int, page: int) -> list[team_dtos.DiaristResponse]:
        diarists = await self.diarist_repo.list_by_team(team_id, page, limit)
        return [
            team_dtos.DiaristResponse(
                id=d.id,
                nome=d.nome,
                descricao=d.descricao,
                valor_diaria=d.valor_diaria.amount,
                chave_pix=d.chave_pix
            )
            for d in diarists
        ]
