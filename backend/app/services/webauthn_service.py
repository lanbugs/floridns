import json
import secrets
import time

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import settings

# In-memory challenge store: session_id -> (challenge_bytes, expiry_monotonic)
_challenges: dict[str, tuple[bytes, float]] = {}
_CHALLENGE_TTL = 300  # 5 minutes


def _store_challenge(challenge: bytes) -> str:
    session_id = secrets.token_urlsafe(24)
    _challenges[session_id] = (challenge, time.monotonic() + _CHALLENGE_TTL)
    _evict_expired()
    return session_id


def _pop_challenge(session_id: str) -> bytes | None:
    _evict_expired()
    entry = _challenges.pop(session_id, None)
    if entry is None:
        return None
    challenge, expiry = entry
    if time.monotonic() > expiry:
        return None
    return challenge


def _evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (_, exp) in _challenges.items() if now > exp]
    for k in expired:
        del _challenges[k]


def registration_options_for_user(
    user_id: str, username: str, existing_credential_ids: list[bytes]
) -> tuple[str, dict]:  # type: ignore[type-arg]
    """Return (session_id, options_dict) for a registration ceremony."""
    exclude = [PublicKeyCredentialDescriptor(id=cid) for cid in existing_credential_ids]
    opts = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id.encode(),
        user_name=username,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    session_id = _store_challenge(opts.challenge)
    return session_id, json.loads(options_to_json(opts))


def verify_registration(
    session_id: str, credential: dict  # type: ignore[type-arg]
) -> tuple[bytes, bytes, int]:
    """Return (credential_id, public_key_bytes, sign_count)."""
    challenge = _pop_challenge(session_id)
    if challenge is None:
        raise ValueError("Challenge expired or not found — please try again")
    verified = verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGIN,
    )
    return verified.credential_id, verified.credential_public_key, verified.sign_count


def authentication_options_discoverable() -> tuple[str, dict]:  # type: ignore[type-arg]
    """Return (session_id, options_dict) for a discoverable-credential login."""
    opts = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session_id = _store_challenge(opts.challenge)
    return session_id, json.loads(options_to_json(opts))


def credential_id_from_response(credential: dict) -> bytes:  # type: ignore[type-arg]
    """Decode the base64url credential ID from a browser authentication response."""
    return base64url_to_bytes(credential["id"])


def verify_authentication(
    session_id: str,
    credential: dict,  # type: ignore[type-arg]
    public_key: bytes,
    current_sign_count: int,
) -> int:
    """Verify an authentication response and return the new sign count."""
    challenge = _pop_challenge(session_id)
    if challenge is None:
        raise ValueError("Challenge expired or not found — please try again")
    verified = verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGIN,
        credential_public_key=public_key,
        credential_current_sign_count=current_sign_count,
    )
    return verified.new_sign_count
