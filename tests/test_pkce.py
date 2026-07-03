from app.infra.security.pkce import compute_challenge, verify_code_challenge

# Vetor de exemplo da RFC 7636 (Apêndice B)
RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_s256_matches_rfc_vector():
    assert compute_challenge(RFC_VERIFIER, "S256") == RFC_CHALLENGE
    assert verify_code_challenge(RFC_VERIFIER, RFC_CHALLENGE, "S256") is True


def test_s256_wrong_verifier_fails():
    assert verify_code_challenge("verifier-errado", RFC_CHALLENGE, "S256") is False


def test_plain_method():
    assert verify_code_challenge("abc", "abc", "plain") is True
    assert verify_code_challenge("abc", "xyz", "plain") is False


def test_unsupported_method_fails():
    assert verify_code_challenge(RFC_VERIFIER, RFC_CHALLENGE, "MD5") is False


def test_empty_inputs_fail():
    assert verify_code_challenge("", RFC_CHALLENGE, "S256") is False
    assert verify_code_challenge(RFC_VERIFIER, "", "S256") is False
