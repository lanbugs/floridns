from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""  # kept for schema compat; refresh token is now in httpOnly cookie
    token_type: str = "bearer"


# Returned by POST /auth/login when TOTP is required
class LoginResponse(BaseModel):
    token_type: str = "bearer"                # "bearer" or "totp_required"
    access_token: str | None = None
    refresh_token: str | None = None          # no longer set; httpOnly cookie is used instead
    totp_token: str | None = None             # short-lived challenge token


class TotpVerifyRequest(BaseModel):
    totp_token: str
    code: str


class TokenPayload(BaseModel):
    sub: str
    type: str
