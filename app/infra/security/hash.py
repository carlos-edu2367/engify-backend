from passlib.context import CryptContext
from app.application.providers.utility.hash_provider import HashProvider

_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


class Argon2HashProvider(HashProvider):
    def hash(self, value: str) -> str:
        return _ctx.hash(value)

    def verify(self, hashed: str, value: str) -> bool:
        return _ctx.verify(value, hashed)
