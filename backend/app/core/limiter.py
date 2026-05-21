from fastapi import Request
from slowapi import Limiter


def _real_ip(request: Request) -> str:
    # Prefer X-Real-IP set by nginx; fall back to direct connection address
    return request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")


limiter = Limiter(key_func=_real_ip)
