"""
Verificação de PKCE (RFC 7636) para o fluxo OAuth Authorization Code.

Suporta os métodos `S256` (obrigatório) e `plain` (aceito só por compatibilidade;
o cliente Arcaika deve usar S256).
"""
import base64
import hashlib
import hmac

SUPPORTED_METHODS = ("S256", "plain")


def _b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def compute_challenge(verifier: str, method: str = "S256") -> str:
    """Deriva o `code_challenge` a partir de um `code_verifier`."""
    if method == "plain":
        return verifier
    if method == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return _b64url_no_pad(digest)
    raise ValueError(f"Método PKCE não suportado: {method}")


def verify_code_challenge(verifier: str, challenge: str, method: str = "S256") -> bool:
    """True se o `verifier` corresponde ao `challenge` armazenado."""
    if not verifier or not challenge or method not in SUPPORTED_METHODS:
        return False
    try:
        expected = compute_challenge(verifier, method)
    except ValueError:
        return False
    return hmac.compare_digest(expected, challenge)
