"""Fernet-based encryption for sensitive settings stored in the DB.

If SETTINGS_ENCRYPTION_KEY is not configured, values are stored and
returned as plaintext with a one-time startup warning.
"""
import warnings

from cryptography.fernet import Fernet, InvalidToken

_ENCRYPTED_KEYS: frozenset[str] = frozenset(
    {"ldap_config", "oidc_config", "slave_servers", "pdns_primary"}
)
_warned_no_key = False


def _get_fernet(key: str) -> Fernet:
    return Fernet(key.encode())


def encrypt_setting(setting_key: str, plaintext: str, enc_key: str) -> str:
    """Return Fernet-encrypted ciphertext if enc_key is set and key is sensitive."""
    if not enc_key or setting_key not in _ENCRYPTED_KEYS:
        return plaintext
    return _get_fernet(enc_key).encrypt(plaintext.encode()).decode()


def decrypt_setting(setting_key: str, value: str, enc_key: str) -> str:
    """Return decrypted plaintext. Falls back to raw value if not encrypted."""
    global _warned_no_key
    if setting_key not in _ENCRYPTED_KEYS:
        return value
    if not enc_key:
        if not _warned_no_key:
            warnings.warn(
                "SETTINGS_ENCRYPTION_KEY is not set — sensitive settings are stored in plaintext!",
                stacklevel=2,
            )
            _warned_no_key = True
        return value
    try:
        return _get_fernet(enc_key).decrypt(value.encode()).decode()
    except InvalidToken:
        return value  # Value was stored before encryption was enabled
