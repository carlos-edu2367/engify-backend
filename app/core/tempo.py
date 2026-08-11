"""Traducao entre instantes UTC e o calendario local da aplicacao.

O banco guarda instantes em UTC. Dia e hora de parede, porem, sao conceitos
locais: uma batida as 23h30 em Sao Paulo pertence ao dia de hoje, ainda que
em UTC ja seja amanha. Todo lugar que precisa de "que dia foi isso" deve
passar por aqui em vez de chamar .date() sobre um datetime UTC.
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def to_local(value: datetime) -> datetime:
    return _aware(value).astimezone(local_tz())


def local_date_of(value: datetime) -> date:
    return to_local(value).date()


def local_time_of(value: datetime) -> time:
    return to_local(value).time()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Primeiro e ultimo instante do dia local, devolvidos em UTC."""
    tz = local_tz()
    inicio = datetime.combine(day, time.min, tzinfo=tz)
    fim = datetime.combine(day, time.max, tzinfo=tz)
    return inicio.astimezone(timezone.utc), fim.astimezone(timezone.utc)


def combine_local(day: date, hora: time) -> datetime:
    """Data e hora de parede locais para o instante UTC correspondente."""
    return datetime.combine(day, hora, tzinfo=local_tz()).astimezone(timezone.utc)


def date_marker_of(value: datetime) -> date:
    """Dia denotado por um campo que carrega uma DATA, e nao um instante.

    data_referencia de um ajuste e um exemplo: ela nomeia um dia do calendario,
    mas o banco a guarda como datetime. Registros antigos gravaram meia-noite
    UTC (2026-04-28T00:00:00Z) e os novos gravam meia-noite local
    (2026-04-28T03:00:00Z). Lidas em UTC, as duas formas apontam para o dia 28;
    lida no fuso local, a forma antiga cairia no dia 27 e quebraria a aprovacao
    de ajustes que ja estao na fila. Por isso marcador se le em UTC, enquanto
    instante de verdade — uma batida — se le com local_date_of.
    """
    return _aware(value).astimezone(timezone.utc).date()


def marker_bounds(day: date) -> tuple[datetime, datetime]:
    """Janela que cobre qualquer marcador de data do dia informado.

    Cobre o dia inteiro em UTC, entao alcanca tanto marcadores gravados a
    meia-noite UTC quanto a meia-noite local.
    """
    inicio = datetime.combine(day, time.min, tzinfo=timezone.utc)
    fim = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return inicio, fim


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
