import base64
import hashlib
import secrets
import time
from typing import Any

import httpx
from jose import JWTError, jwt

_discovery_cache: dict[str, Any] = {}
_discovery_expiry: float = 0
_CACHE_TTL = 300  # seconds


async def get_discovery(issuer_url: str) -> dict[str, Any]:
    global _discovery_cache, _discovery_expiry
    now = time.time()
    if _discovery_cache and now < _discovery_expiry:
        return _discovery_cache
    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    _discovery_cache = resp.json()
    _discovery_expiry = now + _CACHE_TTL
    return _discovery_cache


def generate_pkce() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge_S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def create_state_token(secret_key: str) -> str:
    payload = {"type": "oidc_state", "exp": time.time() + 600}
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_state_token(token: str, secret_key: str) -> bool:
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload.get("type") == "oidc_state"
    except JWTError:
        return False


def build_auth_url(
    discovery: dict[str, Any],
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scopes: str = "openid email profile",
) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return discovery["authorization_endpoint"] + "?" + urlencode(params)


async def exchange_code(
    discovery: dict[str, Any],
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(discovery["token_endpoint"], data=data)
        resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


async def get_userinfo(discovery: dict[str, Any], access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            discovery["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]
