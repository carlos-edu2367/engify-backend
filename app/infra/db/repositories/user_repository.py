from uuid import UUID, uuid4
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.application.providers.repo.user_repos import UserRepository, SolicitacaoRepo, RecoveryRepo
from app.application.dtos.user import SimpleUserDisplay
from app.domain.entities.user import User, SolicitacaoCadastro, RecoveryCode
from app.domain.errors import DomainError
from app.infra.db.models.user_model import UserModel, SolicitacaoCadastroModel, RecoveryCodeModel


class UserRepositoryImpl(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> User:
        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.team))
            .where(UserModel.id == id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Usuário não encontrado")
        return model.to_domain()

    async def get_by_email_or_cpf(self, email: str = None, cpf: str = None) -> User | None:
        conditions = []
        if email:
            conditions.append(UserModel.email == email)
        if cpf:
            conditions.append(UserModel.cpf == cpf)
        if not conditions:
            return None

        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.team))
            .where(or_(*conditions))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def save(self, user: User) -> User:
        if user.id is None:
            user.id = uuid4()
            model = UserModel.from_domain(user)
            self._session.add(model)
            await self._session.flush()
            # Recarrega com o team para retornar domínio completo
            return await self.get_by_id(user.id)

        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.team))
            .where(UserModel.id == user.id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Usuário não encontrado para atualização")
        model.update_from_domain(user)
        await self._session.flush()
        return model.to_domain()

    async def get_by_team_id(self, team_id: UUID) -> list[SimpleUserDisplay]:
        stmt = select(UserModel).where(UserModel.team_id == team_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            SimpleUserDisplay(
                user_id=m.id,
                nome=m.nome,
                email=m.email,
                role=m.role,
            )
            for m in models
        ]


class SolicitacaoRepoImpl(SolicitacaoRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> SolicitacaoCadastro:
        stmt = select(SolicitacaoCadastroModel).where(SolicitacaoCadastroModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Solicitação de cadastro não encontrada")
        return model.to_domain()

    async def save(self, solicitacao: SolicitacaoCadastro) -> SolicitacaoCadastro:
        if solicitacao.id is None:
            solicitacao.id = uuid4()
            model = SolicitacaoCadastroModel.from_domain(solicitacao)
            self._session.add(model)
        else:
            stmt = select(SolicitacaoCadastroModel).where(
                SolicitacaoCadastroModel.id == solicitacao.id
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Solicitação não encontrada para atualização")
            model.update_from_domain(solicitacao)
        await self._session.flush()
        return model.to_domain()


class RecoveryRepoImpl(RecoveryRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> RecoveryCode:
        stmt = select(RecoveryCodeModel).where(RecoveryCodeModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Código de recuperação não encontrado")
        return model.to_domain()

    async def get_active_by_user_id(self, user_id: UUID) -> RecoveryCode | None:
        from datetime import datetime, timezone
        stmt = (
            select(RecoveryCodeModel)
            .where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.used == False,  # noqa: E712
                RecoveryCodeModel.expires > datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def save(self, recovery: RecoveryCode) -> RecoveryCode:
        if recovery.id is None:
            recovery.id = uuid4()
            model = RecoveryCodeModel.from_domain(recovery)
            self._session.add(model)
        else:
            stmt = select(RecoveryCodeModel).where(RecoveryCodeModel.id == recovery.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Código não encontrado para atualização")
            model.update_from_domain(recovery)
        await self._session.flush()
        return model.to_domain()
