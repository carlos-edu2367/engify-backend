"""
Assinatura HMAC-SHA256 dos webhooks Engify → Arcaika.

Formato: `X-Engify-Signature: sha256=<hex(hmac(secret, "<timestamp>.<body>"))>`
O timestamp entra na base assinada e também vai no header `X-Engify-Timestamp`,
permitindo ao receptor rejeitar entregas fora de uma janela (anti-replay).
"""
import hashlib
import hmac

SIGNATURE_HEADER = "X-Engify-Signature"
TIMESTAMP_HEADER = "X-Engify-Timestamp"
EVENT_ID_HEADER = "X-Engify-Event-Id"


def _signing_base(timestamp: str, body: str) -> bytes:
    return f"{timestamp}.{body}".encode("utf-8")


def sign_payload(secret: str, timestamp: str, body: str) -> str:
    """Retorna o valor do header de assinatura (`sha256=<hex>`)."""
    digest = hmac.new(
        secret.encode("utf-8"), _signing_base(timestamp, body), hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, timestamp: str, body: str, signature: str) -> bool:
    """Comparação em tempo constante do header de assinatura recebido."""
    if not signature:
        return False
    expected = sign_payload(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)


def build_headers(secret: str, timestamp: str, body: str, event_id: str) -> dict[str, str]:
    """Monta todos os headers de segurança de uma entrega de webhook."""
    return {
        SIGNATURE_HEADER: sign_payload(secret, timestamp, body),
        TIMESTAMP_HEADER: timestamp,
        EVENT_ID_HEADER: event_id,
        "Content-Type": "application/json",
    }
