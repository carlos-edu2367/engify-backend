from enum import Enum
from uuid import UUID
from app.domain.errors import DomainError, InvalidArgument, WeakArgument
from app.domain.entities.identities import CPF
from app.domain.entities.team import Team
import re
from datetime import datetime, timedelta, timezone

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class Roles(Enum):
    ADMIN = "admin"
    ENGENHEIRO = "engenheiro"
    FINANCEIRO = "financeiro"
    CLIENTE = "cliente"
    SUPER_ADMIN = "super_admin"
    FUNCIONARIO = "funcionario"


class User():
    def __init__(self, nome: str, email: str, senha_hash: str, role: Roles, team: Team, cpf: CPF, id: UUID = None):
        if not EMAIL_REGEX.match(email):
            raise InvalidArgument("E-mail inválido")
        self.nome = nome
        self.email = email
        self.senha_hash = senha_hash
        self.role = role
        self.cpf = cpf
        self.team = team
        self.id = id

    def ensure_password_strenght(password: str):
        if len(password) < 6:
            raise WeakArgument("Senha fraca")
    
    def change_password(self, new_password_hash: str):
        self.senha_hash = new_password_hash

    def ensure_can_do_admin(self):
        if self.role != Roles.ADMIN:
            raise DomainError("Ação restrita a administradores")
        self.team.ensure_can_operate()
        
    def ensure_can_operate(self):
        self.team.ensure_can_operate()


class RecoveryCode():
    def __init__(self, user_id: UUID, code: str, expires: datetime, used: bool = False, id: UUID = None):
        self.user_id = user_id
        self.code = code
        self.expires = expires
        self.used = used
        self.id = id

    def use_code(self, code: str):
        if self.expires < datetime.now(timezone.utc) or self.used:
            raise DomainError("Codigo expirado ou já utilizado")
        if code != self.code:
            raise DomainError("Codigo inválido")
        self.used = True
    
class SolicitacaoCadastro():
    def __init__(self, team_id: UUID, email: str, role: Roles, expiration: datetime = None, id: UUID = None, used: bool = False):
        if not EMAIL_REGEX.match(email):
            raise InvalidArgument("E-mail inválido")
        self.email = email
        self.team_id = team_id
        self.role = role
        self.expiration = expiration
        self.id = id
        self.used = used
        if not self.expiration:
            self.expiration = datetime.now(timezone.utc) + timedelta(days=7)

    def use_solicitacao(self):
        self.used = True

    def ensure_can_use(self):
        if self.used or self.expiration < datetime.now(timezone.utc):
            raise DomainError("Solicitação já utilizada ou expirada")
