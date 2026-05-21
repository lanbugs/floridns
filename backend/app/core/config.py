import warnings

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_KEY = "changeme-please-use-at-least-32-characters-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://pdns:pdns@localhost/pdnsui"

    # PowerDNS API
    PDNS_API_URL: AnyHttpUrl = "http://localhost:8081"  # type: ignore[assignment]
    PDNS_API_KEY: str = "changeme"
    PDNS_SERVER_ID: str = "localhost"
    PDNS_SSL_VERIFY: bool = True

    # Auth
    SECRET_KEY: str = _INSECURE_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Secrets encryption (Fernet key for sensitive DB settings)
    SETTINGS_ENCRYPTION_KEY: str = ""
    # Cookies
    COOKIE_SECURE: bool = True

    # App
    PROJECT_NAME: str = "FloriDNS"
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    DOCS_ENABLED: bool = True

    # Rate limiting
    RATE_LIMIT_LOGIN: str = "10/minute"

    # Optional OIDC
    OIDC_ENABLED: bool = False
    OIDC_ISSUER_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""

    # Optional LDAP
    LDAP_ENABLED: bool = False
    LDAP_URL: str = ""
    LDAP_BIND_DN: str = ""
    LDAP_BIND_PASSWORD: str = ""
    LDAP_BASE_DN: str = ""

    # Initial admin user (created on first start if no users exist)
    INITIAL_ADMIN_USERNAME: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""
    INITIAL_ADMIN_EMAIL: str = ""

    # WebAuthn / Passkeys
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "FloriDNS"
    WEBAUTHN_ORIGIN: str = "http://localhost:5173"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @model_validator(mode="after")
    def warn_insecure_secrets(self) -> "Settings":
        if self.SECRET_KEY == _INSECURE_KEY or len(self.SECRET_KEY) < 32:
            warnings.warn(
                "SECRET_KEY is insecure — set a strong random value in production!",
                stacklevel=2,
            )
        if self.PDNS_API_KEY == "changeme":
            warnings.warn(
                "PDNS_API_KEY is the default 'changeme' — change it in production!",
                stacklevel=2,
            )
        return self


settings = Settings()
