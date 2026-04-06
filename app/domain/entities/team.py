from uuid import UUID
from enum import Enum
from datetime import datetime, timedelta, timezone
from app.domain.errors import ExpiredPlan
from app.domain.entities.identities import CNPJ
from app.domain.entities.money import Money

class Plans(Enum):
    TRIAL = "trial"
    BASICO = "basico"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class Team():
    def __init__(self, title: str, cnpj: CNPJ, id: UUID = None, plan: Plans = Plans.TRIAL, expiration_date: datetime = None):
        self.title = title
        self.cnpj = cnpj.value
        self.id = id
        self.plan = plan
        if not expiration_date:
            now = datetime.now(timezone.utc)
            self.expiration_date = now + timedelta(days=7)
        else:
            self.expiration_date = expiration_date

    def ensure_can_operate(self):
        if self.expiration_date < datetime.now(timezone.utc):
            raise ExpiredPlan("O plano contratado pelo time está expirado")
        
    def add_key(self, key: str):
        self.key = key

    def use_key(self):
        self.key = None

    def get_days_for_expire(self) -> int:
        self.ensure_can_operate()
        result = self.expiration_date - datetime.now(timezone.utc)
        return result.days

class Diarist():
    def __init__(self, nome: str, descricao: str, valor_diaria: Money, chave_pix: str, team_id: UUID, id: UUID = None):
        self.nome = nome
        self.descricao = descricao
        self.valor_diaria = valor_diaria
        self.chave_pix = chave_pix
        self.team_id = team_id
        self.id = id
        self.is_deleted = False

    def delete(self):
        self.is_deleted = True