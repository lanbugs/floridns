"""DynDNS 2 protocol endpoint at /nic/update.

Compatible with FRITZ!Box, Synology, OpenWrt, ddclient, and most routers.

Authentication: HTTP Basic Auth
  Username: the registered hostname (e.g. home.example.com.)
  Password: the token shown at host creation

Query parameters:
  hostname  FQDN to update (must match Basic Auth username)
  myip      IPv4 address (optional — defaults to request source IP)
  myip6     IPv6 address (optional)
  offline   "yes" to set IP to 0.0.0.0 / ::
"""
import ipaddress
import json
from base64 import b64decode
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from app.api.deps import DbDep, PdnsDep
from app.core.security import verify_password
from app.models.dyndns import DynDnsHost
from app.models.setting import Setting

router = APIRouter(tags=["dyndns-protocol"])

_OFFLINE_IP = "0.0.0.0"
_OFFLINE_IP6 = "::"


def _plain_text(content: str, status_code: int = 200) -> Response:
    return Response(content=content, media_type="text/plain", status_code=status_code)


def _parse_basic_auth(request: Request) -> tuple[str, str] | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return None
    try:
        decoded = b64decode(auth[6:]).decode()
        username, _, password = decoded.partition(":")
        return username, password
    except Exception:
        return None


def _client_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP") or (request.client.host if request.client else "")


def _validate_ipv4(ip: str) -> bool:
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False


def _validate_ipv6(ip: str) -> bool:
    try:
        ipaddress.IPv6Address(ip)
        return True
    except ValueError:
        return False


@router.get("/nic/update")
async def nic_update(
    request: Request,
    db: DbDep,
    pdns: PdnsDep,
    hostname: str = Query(...),
    myip: str | None = Query(None),
    myip6: str | None = Query(None),
    offline: str | None = Query(None),
) -> Response:
    row = (await db.execute(select(Setting).where(Setting.key == "dyndns_enabled"))).scalar_one_or_none()
    if row and not json.loads(row.value):
        return _plain_text("nohost")

    creds = _parse_basic_auth(request)
    if not creds:
        return _plain_text("badauth", 401)

    auth_username, token = creds

    # Normalize: stored hostnames always have a trailing dot
    if not hostname.endswith("."):
        hostname = hostname + "."

    result = await db.execute(select(DynDnsHost).where(DynDnsHost.hostname == hostname))
    host = result.scalar_one_or_none()

    if not host:
        return _plain_text("nohost")

    if not host.is_active:
        return _plain_text("abuse")

    # Always run bcrypt to prevent hostname enumeration via response-time differences
    token_valid = verify_password(token, host.token_hash)
    hostname_matches = auth_username in (host.hostname, host.hostname.rstrip("."))
    if not hostname_matches or not token_valid:
        return _plain_text("badauth", 401)

    is_offline = offline and offline.lower() == "yes"

    if is_offline:
        new_ip: str | None = _OFFLINE_IP
        new_ip6: str | None = _OFFLINE_IP6
    else:
        new_ip = myip or _client_ip(request) or None
        new_ip6 = myip6

    if new_ip and not _validate_ipv4(new_ip):
        return _plain_text("dnserr")
    if new_ip6 and not _validate_ipv6(new_ip6):
        return _plain_text("dnserr")

    ip_changed = (new_ip and new_ip != host.last_ip) or (new_ip6 and new_ip6 != host.last_ip6)

    if not ip_changed:
        return _plain_text(f"nochg {new_ip or host.last_ip or ''}")

    try:
        rrsets = []
        if new_ip:
            rrsets.append({
                "name": host.hostname,
                "type": "A",
                "ttl": 60,
                "changetype": "REPLACE",
                "records": [{"content": new_ip, "disabled": False}],
            })
        if new_ip6:
            rrsets.append({
                "name": host.hostname,
                "type": "AAAA",
                "ttl": 60,
                "changetype": "REPLACE",
                "records": [{"content": new_ip6, "disabled": False}],
            })
        if rrsets:
            await pdns.patch_rrsets(host.zone_name, {"rrsets": rrsets})
    except Exception:
        return _plain_text("dnserr")

    if new_ip:
        host.last_ip = new_ip
    if new_ip6:
        host.last_ip6 = new_ip6
    host.last_update = datetime.now(UTC)
    host.offline = bool(is_offline)
    await db.commit()

    return _plain_text(f"good {new_ip or new_ip6 or ''}")
