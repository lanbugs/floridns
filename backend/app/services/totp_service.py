import pyotp


def generate_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, username: str, issuer: str = "FloriDNS") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Accept current window ±1 interval (90 s tolerance for clock drift)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
