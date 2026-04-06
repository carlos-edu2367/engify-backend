from slowapi import Limiter
from slowapi.util import get_remote_address

# Singleton do rate limiter — importado por main.py e pelos routers que precisam de limites customizados
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300/minute"],  # limite global por IP
)
