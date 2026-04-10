import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.application.dtos import user
from app.application.ports.email_port import EmailPort, RecoveryCodeEmailInput, ConviteEmailInput
from app.application.providers.repo.user_repos import UserRepository, SolicitacaoRepo, RecoveryRepo
from app.application.providers.repo.team_repos import TeamRepository
from app.application.providers.utility.hash_provider import HashProvider
from app.application.providers.uow import UOWProvider
from app.domain import errors
from app.domain.entities.user import User, SolicitacaoCadastro, RecoveryCode, CPF


def _hash_code(plain: str) -> str:
    """Deriva hash SHA-256 do código de recuperação para armazenamento seguro."""
    return hashlib.sha256(plain.encode()).hexdigest()


class UserService():
    def __init__(
        self,
        user_repo: UserRepository,
        hash: HashProvider,
        uow: UOWProvider,
        solicitacao_repo: SolicitacaoRepo,
        team_repo: TeamRepository,
        email_port: EmailPort | None = None,
    ):
        self.user_repo = user_repo
        self.solicitacao_repo = solicitacao_repo
        self.hash = hash
        self.uow = uow
        self.team_repo = team_repo
        self._email = email_port

    async def register(self, dtos: user.RegisterUser) -> User:
        User.ensure_password_strenght(dtos.senha)
        solicitacao = await self.solicitacao_repo.get_by_id(dtos.solicitacao_id)
        solicitacao.ensure_can_use()
        team = await self.team_repo.get_by_id(solicitacao.team_id)
        exists = await self.user_repo.get_by_email_or_cpf(solicitacao.email, dtos.cpf)
        if exists:
            raise errors.DomainError("Já existe um usuário com esse e-mail ou CPF")
        hashed_password = self.hash.hash(dtos.senha)
        cpf = CPF(dtos.cpf)
        new_user = User(nome=dtos.nome, email=solicitacao.email,
                        senha_hash=hashed_password, role=solicitacao.role,
                        cpf=cpf, team=team)
        saved = await self.user_repo.save(new_user)
        solicitacao.use_solicitacao()
        await self.solicitacao_repo.save(solicitacao)
        await self.uow.commit()
        return saved

    async def invite_user(self, dtos: user.CreateSolicitacaoRegistro, current_user: User) -> SolicitacaoCadastro:
        current_user.ensure_can_do_admin()
        new = SolicitacaoCadastro(team_id=current_user.team.id,
                                  email=dtos.email, role=dtos.role)
        invite = await self.solicitacao_repo.save(new)
        await self.uow.commit()

        if self._email:
            try:
                await self._email.enviar_convite(ConviteEmailInput(
                    destinatario=dtos.email,
                    team_name=current_user.team.title,
                    role=dtos.role.value if hasattr(dtos.role, "value") else str(dtos.role),
                    solicitacao_id=invite.id,
                ))
            except Exception:
                pass  # email falhou mas o convite já foi salvo — não reverter

        return invite

    async def login(self, dtos: user.Login) -> User | None:
        cpf = None
        if dtos.cpf:
            cpf = CPF(value=dtos.cpf).value
        found = await self.user_repo.get_by_email_or_cpf(dtos.email, cpf)
        if not found:
            return None
        if not self.hash.verify(hashed=found.senha_hash, value=dtos.senha):
            return None
        return found

    async def change_password(self, current_user: User, new_password: str) -> User:
        User.ensure_password_strenght(new_password)
        hashed = self.hash.hash(new_password)
        current_user.change_password(hashed)
        saved = await self.user_repo.save(current_user)
        await self.uow.commit()
        return saved


class RecoveryPasswordService():
    def __init__(
        self,
        user_repo: UserRepository,
        recovery_repo: RecoveryRepo,
        hash: HashProvider,
        uow: UOWProvider,
        email_port: EmailPort | None = None,
    ):
        self.user_repo = user_repo
        self.recovery_repo = recovery_repo
        self.hash = hash
        self.uow = uow
        self._email = email_port

    async def create_recovery(self, dto: user.CreateRecoveryCode) -> None:
        """
        Gera um código de recuperação e envia por email.
        Não levanta exceção se o usuário não existir — sempre retorna
        sucesso para evitar enumeração de usuários.
        """
        if not dto.email and not dto.cpf:
            return  # nada a fazer sem identificador

        found = await self.user_repo.get_by_email_or_cpf(dto.email, dto.cpf)
        if not found:
            return  # usuário não existe — silenciosamente ignorar

        exists = await self.recovery_repo.get_active_by_user_id(found.id)
        if exists:
            return  # já existe código ativo — silenciosamente ignorar

        plain_code = secrets.token_urlsafe(32)
        hashed_code = _hash_code(plain_code)
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)

        new = RecoveryCode(user_id=found.id, code=hashed_code, expires=expires)
        await self.recovery_repo.save(new)
        await self.uow.commit()

        if self._email:
            try:
                await self._email.enviar_recovery_code(RecoveryCodeEmailInput(
                    destinatario=found.email,
                    nome=found.nome,
                    code=plain_code,  # plain code — apenas no email, nunca no banco
                    user_id=found.id,
                ))
            except Exception:
                pass  # email falhou, código ainda está salvo; usuário pode tentar novamente

    async def verify_recovery(self, user_id: UUID, recovery_code: str) -> RecoveryCode:
        code = await self.recovery_repo.get_active_by_user_id(user_id=user_id)
        if not code:
            raise errors.DomainError("Nenhum código ativo. Solicite um novo código.")
        if code.code != _hash_code(recovery_code):
            raise errors.DomainError("Código inválido")
        return code

    async def update_password(self, user_id: UUID, recovery_code: str, new_password: str) -> User:
        User.ensure_password_strenght(new_password)
        code = await self.verify_recovery(user_id, recovery_code)
        found = await self.user_repo.get_by_id(user_id)
        hashed = self.hash.hash(new_password)
        found.change_password(hashed)
        code.use_code(_hash_code(recovery_code))  # use_code compara com hash armazenado
        saved = await self.user_repo.save(found)
        await self.recovery_repo.save(code)
        await self.uow.commit()
        return saved
