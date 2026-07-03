from app.infra.security.webhook_signing import (
    sign_payload, verify_signature, build_headers,
    SIGNATURE_HEADER, TIMESTAMP_HEADER, EVENT_ID_HEADER,
)

SECRET = "whsec_abc123"


def test_sign_verify_roundtrip():
    ts, body = "1720000000", '{"a":1}'
    sig = sign_payload(SECRET, ts, body)
    assert sig.startswith("sha256=")
    assert verify_signature(SECRET, ts, body, sig) is True


def test_verify_fails_on_tampered_body():
    ts, body = "1720000000", '{"a":1}'
    sig = sign_payload(SECRET, ts, body)
    assert verify_signature(SECRET, ts, '{"a":2}', sig) is False


def test_verify_fails_on_tampered_timestamp():
    body = '{"a":1}'
    sig = sign_payload(SECRET, "1720000000", body)
    assert verify_signature(SECRET, "1720000001", body, sig) is False


def test_verify_fails_on_wrong_secret():
    ts, body = "1720000000", '{"a":1}'
    sig = sign_payload(SECRET, ts, body)
    assert verify_signature("outro", ts, body, sig) is False


def test_verify_empty_signature():
    assert verify_signature(SECRET, "1", "{}", "") is False


def test_build_headers_contains_all():
    headers = build_headers(SECRET, "1720000000", "{}", "evt_1")
    assert headers[SIGNATURE_HEADER] == sign_payload(SECRET, "1720000000", "{}")
    assert headers[TIMESTAMP_HEADER] == "1720000000"
    assert headers[EVENT_ID_HEADER] == "evt_1"
    assert headers["Content-Type"] == "application/json"
