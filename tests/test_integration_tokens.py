from uuid import uuid4

import pytest
from jose import JWTError

from app.infra.security.integration_tokens import (
    create_integration_access_token, decode_integration_access_token,
    generate_opaque_secret, hash_secret, verify_secret, INTEGRATION_TOKEN_TYPE,
)
from app.infra.security.jwt import create_access_token


def test_access_token_roundtrip():
    conn_id, team_id = uuid4(), uuid4()
    token = create_integration_access_token(conn_id, team_id, ["obras:read", "obras:write"])
    payload = decode_integration_access_token(token)
    assert payload["type"] == INTEGRATION_TOKEN_TYPE
    assert payload["conn_id"] == str(conn_id)
    assert payload["team_id"] == str(team_id)
    assert payload["scope"] == "obras:read obras:write"


def test_human_token_rejected_as_integration():
    # Um access token humano NÃO pode ser aceito no fluxo de integração.
    human = create_access_token(user_id=uuid4(), team_id=uuid4(), role="admin")
    with pytest.raises(JWTError):
        decode_integration_access_token(human)


def test_opaque_secret_hash_and_verify():
    secret = generate_opaque_secret()
    h = hash_secret(secret)
    assert h != secret
    assert verify_secret(secret, h) is True
    assert verify_secret("errado", h) is False
    assert verify_secret("", h) is False
