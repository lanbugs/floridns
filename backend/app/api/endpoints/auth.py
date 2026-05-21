import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbDep, CurrentUser, get_client_ip
from app.core.config import settings
from app.core.encryption import decrypt_setting
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_totp_challenge_token,
    decode_token,
    verify_password,
)
from app.models.passkey import Passkey
from app.models.refresh_token import RefreshTokenDenylist
from app.models.setting import Setting
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, LoginResponse, TokenResponse, TotpVerifyRequest
from app.schemas.passkey import (
    PasskeyLoginBeginResponse,
    PasskeyLoginCompleteRequest,
    PasskeyRegisterBeginResponse,
    PasskeyRegisterCompleteRequest,
    PasskeyResponse,
)
from app.schemas.user import UserResponse
from app.services.ldap_service import authenticate_ldap
from app.services.oidc_service import (
    build_auth_url,
    create_state_token,
    exchange_code,
    generate_pkce,
    get_discovery,
    get_userinfo,
    verify_state_token,
)
from app.services.totp_service import verify_totp
from app.services.webauthn_service import (
    authentication_options_discoverable,
    credential_id_from_response,
    registration_options_for_user,
    verify_authentication,
    verify_registration,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_ROLE_RANK: dict[str, int] = {
    "superadmin": 4, "admin": 3, "operator": 2, "viewer": 1,
}

_LOGIN_MAX_ATTEMPTS = 5
_LOCK_DURATION_MINUTES = 15


def _resolve_ldap_role(member_of: list[str], group_mapping: list[dict]) -> UserRole | None:
    """Return the highest role matched by group_mapping, or None if mapping is empty."""
    if not group_mapping:
        return None
    member_lower = {dn.lower() for dn in member_of}
    best_rank = 0
    best_role: UserRole = UserRole.viewer
    for entry in group_mapping:
        if entry.get("group_dn", "").lower() in member_lower:
            rank = _ROLE_RANK.get(entry.get("role", ""), 0)
            if rank > best_rank:
                best_rank = rank
                best_role = UserRole(entry["role"])
    return best_role


def _resolve_oidc_role(userinfo: dict, role_claim: str, role_mapping: list[dict]) -> UserRole | None:
    """Return the highest role matched by role_mapping, or None if mapping is empty."""
    if not role_claim or not role_mapping:
        return None
    raw = userinfo.get(role_claim)
    if raw is None:
        return UserRole.viewer
    values: set[str] = {raw} if isinstance(raw, str) else set(raw)
    best_rank = 0
    best_role: UserRole = UserRole.viewer
    for entry in role_mapping:
        if entry.get("claim_value", "") in values:
            rank = _ROLE_RANK.get(entry.get("role", ""), 0)
            if rank > best_rank:
                best_rank = rank
                best_role = UserRole(entry["role"])
    return best_role


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="fdns_rt",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="fdns_rt", path="/api/v1/auth")


def _full_tokens(response: Response, user_id: str, token_version: int) -> LoginResponse:
    refresh_token = create_refresh_token(user_id)
    _set_refresh_cookie(response, refresh_token)
    return LoginResponse(
        token_type="bearer",
        access_token=create_access_token(user_id, token_version=token_version),
    )


async def _get_ldap_cfg(db: AsyncSession) -> dict | None:
    row = (await db.execute(select(Setting).where(Setting.key == "ldap_config"))).scalar_one_or_none()
    if not row:
        return None
    decrypted = decrypt_setting("ldap_config", row.value, settings.SETTINGS_ENCRYPTION_KEY)
    cfg: dict = json.loads(decrypted)
    return cfg if cfg.get("enabled") else None


async def _get_oidc_cfg(db: AsyncSession) -> dict | None:
    row = (await db.execute(select(Setting).where(Setting.key == "oidc_config"))).scalar_one_or_none()
    if not row:
        return None
    decrypted = decrypt_setting("oidc_config", row.value, settings.SETTINGS_ENCRYPTION_KEY)
    cfg: dict = json.loads(decrypted)
    return cfg if cfg.get("enabled") else None


async def _provision_external_user(
    db: AsyncSession,
    username: str,
    email: str,
    *,
    ldap_dn: str | None = None,
    oidc_sub: str | None = None,
    resolved_role: UserRole | None = None,
) -> User:
    """Find or create a user from an external auth provider.

    resolved_role: if not None the role is always updated (group/claim mapping active).
                   if None the role is set to viewer on creation only, never changed.
    """
    user: User | None = None

    if oidc_sub:
        user = (await db.execute(select(User).where(User.oidc_sub == oidc_sub))).scalar_one_or_none()

    if user is None:
        user = (
            await db.execute(select(User).where(User.username == username, User.is_active == True))  # noqa: E712
        ).scalar_one_or_none()

    if user is None:
        user = User(
            username=username,
            email=email,
            role=resolved_role if resolved_role is not None else UserRole.viewer,
            is_active=True,
            ldap_dn=ldap_dn,
            oidc_sub=oidc_sub,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = email
        if resolved_role is not None:
            user.role = resolved_role
        if ldap_dn:
            user.ldap_dn = ldap_dn
        if oidc_sub:
            user.oidc_sub = oidc_sub

    return user


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(body: LoginRequest, request: Request, response: Response, db: DbDep) -> LoginResponse:
    user: User | None = None

    # Try LDAP if configured
    ldap_cfg = await _get_ldap_cfg(db)
    if ldap_cfg:
        try:
            ldap_info = await authenticate_ldap(body.username, body.password, ldap_cfg)
        except Exception:
            ldap_info = None
        if ldap_info:
            resolved_role = _resolve_ldap_role(
                ldap_info.get("member_of", []),
                ldap_cfg.get("group_mapping", []),
            )
            user = await _provision_external_user(
                db,
                ldap_info["username"],
                ldap_info["email"],
                ldap_dn=ldap_info["dn"],
                resolved_role=resolved_role,
            )
            await db.commit()

    # Fall back to local auth
    if user is None:
        db_user = (
            await db.execute(
                select(User).where(User.username == body.username, User.is_active == True)  # noqa: E712
            )
        ).scalar_one_or_none()

        if db_user:
            # Check account lock
            if db_user.locked_until and db_user.locked_until > datetime.now(UTC):
                remaining = int((db_user.locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Account locked due to too many failed attempts. Try again in {remaining} minute(s).",
                )

        if not db_user or not db_user.hashed_password or not verify_password(body.password, db_user.hashed_password):
            # Increment failure counter on the found user
            if db_user:
                db_user.failed_login_attempts += 1
                if db_user.failed_login_attempts >= _LOGIN_MAX_ATTEMPTS:
                    db_user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCK_DURATION_MINUTES)
                await db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

        # Successful local auth — reset failure counter
        if db_user.failed_login_attempts or db_user.locked_until:
            db_user.failed_login_attempts = 0
            db_user.locked_until = None
            await db.commit()

        user = db_user

    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")

    if user.totp_enabled and user.totp_secret:
        return LoginResponse(
            token_type="totp_required",
            totp_token=create_totp_challenge_token(str(user.id)),
        )

    return _full_tokens(response, str(user.id), user.token_version)


@router.post("/totp", response_model=LoginResponse)
async def verify_totp_login(body: TotpVerifyRequest, response: Response, db: DbDep) -> LoginResponse:
    payload = decode_token(body.totp_token)
    if not payload or payload.get("type") != "totp_challenge":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "TOTP session expired — please log in again")

    user = (
        await db.execute(
            select(User).where(User.id == uuid.UUID(payload["sub"]), User.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if not user or not user.totp_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    if not verify_totp(user.totp_secret, body.code.strip()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid TOTP code — please try again")

    return _full_tokens(response, str(user.id), user.token_version)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: DbDep,
    fdns_rt: str | None = Cookie(default=None),
) -> TokenResponse:
    token = fdns_rt
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    denied = (await db.execute(
        select(RefreshTokenDenylist).where(RefreshTokenDenylist.jti == jti)
    )).scalar_one_or_none()
    if denied:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")

    user = (
        await db.execute(
            select(User).where(User.id == uuid.UUID(payload["sub"]), User.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    db.add(RefreshTokenDenylist(jti=jti, expires_at=exp))
    await db.commit()

    new_refresh = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, new_refresh)

    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token="",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: CurrentUser,
    db: DbDep,
    fdns_rt: str | None = Cookie(default=None),
) -> None:
    if fdns_rt:
        payload = decode_token(fdns_rt)
        if payload and payload.get("type") == "refresh":
            jti = payload.get("jti")
            if jti:
                exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
                existing = (await db.execute(
                    select(RefreshTokenDenylist).where(RefreshTokenDenylist.jti == jti)
                )).scalar_one_or_none()
                if not existing:
                    db.add(RefreshTokenDenylist(jti=jti, expires_at=exp))

    # Increment token_version to invalidate all existing access tokens
    current_user.token_version += 1
    await db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> User:
    return current_user


# ---------------------------------------------------------------------------
# OIDC endpoints
# ---------------------------------------------------------------------------

class OidcAuthorizeResponse(BaseModel):
    auth_url: str
    code_verifier: str


class OidcCallbackRequest(BaseModel):
    code: str
    state: str
    code_verifier: str
    redirect_uri: str


@router.get("/oidc/info")
async def oidc_info(db: DbDep) -> dict:
    """Public endpoint — tells the login page whether OIDC is available."""
    cfg = await _get_oidc_cfg(db)
    return {"enabled": cfg is not None}


@router.get("/oidc/authorize", response_model=OidcAuthorizeResponse)
async def oidc_authorize(db: DbDep) -> OidcAuthorizeResponse:
    cfg = await _get_oidc_cfg(db)
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC not configured or not enabled")

    discovery = await get_discovery(cfg["issuer_url"])
    code_verifier, code_challenge = generate_pkce()
    state = create_state_token(settings.SECRET_KEY)

    redirect_uri: str = cfg.get("redirect_uri", "")
    if not redirect_uri:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "OIDC redirect_uri not configured")

    auth_url = build_auth_url(
        discovery,
        cfg["client_id"],
        redirect_uri,
        state,
        code_challenge,
        cfg.get("scopes", "openid email profile"),
    )
    return OidcAuthorizeResponse(auth_url=auth_url, code_verifier=code_verifier)


@router.post("/oidc/callback", response_model=LoginResponse)
async def oidc_callback(body: OidcCallbackRequest, response: Response, db: DbDep) -> LoginResponse:
    if not verify_state_token(body.state, settings.SECRET_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid OIDC state — possible CSRF")

    cfg = await _get_oidc_cfg(db)
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC not configured")

    configured_uri = cfg.get("redirect_uri", "")
    if body.redirect_uri != configured_uri:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "redirect_uri mismatch")

    try:
        discovery = await get_discovery(cfg["issuer_url"])
        tokens = await exchange_code(
            discovery,
            body.code,
            body.redirect_uri,
            cfg["client_id"],
            cfg["client_secret"],
            body.code_verifier,
        )
        userinfo = await get_userinfo(discovery, tokens["access_token"])
    except Exception as exc:
        logger.warning("OIDC provider error", error=str(exc))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OIDC provider returned an error — check server logs") from exc

    sub: str = userinfo.get("sub", "")
    email: str = userinfo.get("email", "")
    username: str = (
        userinfo.get("preferred_username")
        or userinfo.get("nickname")
        or userinfo.get("name")
        or (email.split("@")[0] if email else sub)
    )

    if not sub:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OIDC provider did not return a subject claim")

    resolved_role = _resolve_oidc_role(
        userinfo,
        cfg.get("role_claim", ""),
        cfg.get("role_mapping", []),
    )
    user = await _provision_external_user(db, username, email, oidc_sub=sub, resolved_role=resolved_role)
    await db.commit()

    if user.totp_enabled and user.totp_secret:
        return LoginResponse(
            token_type="totp_required",
            totp_token=create_totp_challenge_token(str(user.id)),
        )

    return _full_tokens(response, str(user.id), user.token_version)


# ---------------------------------------------------------------------------
# Passkey / WebAuthn endpoints
# ---------------------------------------------------------------------------

@router.get("/passkey/register/begin", response_model=PasskeyRegisterBeginResponse)
async def passkey_register_begin(current_user: CurrentUser, db: DbDep) -> PasskeyRegisterBeginResponse:
    existing = list(
        (await db.execute(
            select(Passkey.credential_id).where(Passkey.user_id == current_user.id)
        )).scalars()
    )
    session_id, opts = registration_options_for_user(str(current_user.id), current_user.username, existing)
    return PasskeyRegisterBeginResponse(session_id=session_id, options=opts)


@router.post("/passkey/register/complete", response_model=PasskeyResponse, status_code=status.HTTP_201_CREATED)
async def passkey_register_complete(
    body: PasskeyRegisterCompleteRequest,
    current_user: CurrentUser,
    db: DbDep,
) -> Passkey:
    try:
        cred_id, pub_key, sign_count = verify_registration(body.session_id, body.credential)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    transports_list: list[str] = body.credential.get("response", {}).get("transports", [])
    passkey = Passkey(
        user_id=current_user.id,
        credential_id=cred_id,
        public_key=pub_key,
        sign_count=sign_count,
        name=body.name or None,
        transports=",".join(transports_list) if transports_list else None,
    )
    db.add(passkey)
    await db.commit()
    await db.refresh(passkey)
    return passkey


@router.get("/passkey/login/begin", response_model=PasskeyLoginBeginResponse)
async def passkey_login_begin() -> PasskeyLoginBeginResponse:
    session_id, opts = authentication_options_discoverable()
    return PasskeyLoginBeginResponse(session_id=session_id, options=opts)


@router.post("/passkey/login/complete", response_model=LoginResponse)
async def passkey_login_complete(
    body: PasskeyLoginCompleteRequest,
    response: Response,
    db: DbDep,
) -> LoginResponse:
    try:
        cred_id_bytes = credential_id_from_response(body.credential)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid credential ID") from exc

    passkey = (
        await db.execute(select(Passkey).where(Passkey.credential_id == cred_id_bytes))
    ).scalar_one_or_none()
    if not passkey:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Passkey not registered")

    user = (
        await db.execute(
            select(User).where(User.id == passkey.user_id, User.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    try:
        new_sign_count = verify_authentication(
            body.session_id, body.credential, passkey.public_key, passkey.sign_count
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    passkey.sign_count = new_sign_count
    passkey.last_used_at = datetime.now(UTC)
    await db.commit()

    return _full_tokens(response, str(user.id), user.token_version)
