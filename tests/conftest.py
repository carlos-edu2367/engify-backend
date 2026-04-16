"""
Fixtures compartilhadas. Todos os testes são unitários puros (sem DB, sem HTTP).
"""
import pytest


@pytest.fixture
def team_id():
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def outro_team_id():
    from uuid import uuid4
    return uuid4()
