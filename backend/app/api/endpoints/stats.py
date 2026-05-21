import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from tenacity import RetryError

from app.api.deps import AdminRequired, CurrentUser, DbDep, PdnsDep
from app.core.config import settings
from app.core.encryption import decrypt_setting
from app.models.setting import Setting
from app.services.pdns_client import PdnsError

router = APIRouter(prefix="/stats", tags=["stats"])


def _pdns_exc(e: Exception) -> HTTPException:
    if isinstance(e, PdnsError):
        return HTTPException(e.status_code, str(e))
    if isinstance(e, RetryError) and e.__cause__ and isinstance(e.__cause__, PdnsError):
        cause: PdnsError = e.__cause__
        return HTTPException(cause.status_code, str(cause))
    return HTTPException(502, "PowerDNS unreachable")


@router.get("/servers")
async def get_server_statuses(
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
) -> list[dict[str, Any]]:
    """Return reachability status for all configured servers. Accessible to all authenticated users."""
    results: list[dict[str, Any]] = []

    try:
        await pdns.get_statistics()
        results.append({"name": "primary", "status": "reachable"})
    except Exception:
        results.append({"name": "primary", "status": "unreachable"})

    row = (await db.execute(select(Setting).where(Setting.key == "slave_servers"))).scalar_one_or_none()
    if row:
        decrypted = decrypt_setting("slave_servers", row.value, settings.SETTINGS_ENCRYPTION_KEY)
        slaves: list[dict[str, Any]] = json.loads(decrypted) or []
        for slave in slaves:
            try:
                await pdns.get_statistics(
                    server_url=slave["url"],
                    api_key=slave.get("api_key"),
                    ssl_verify=slave.get("ssl_verify", True),
                )
                results.append({"name": slave["name"], "status": "reachable"})
            except Exception:
                results.append({"name": slave["name"], "status": "unreachable"})

    return results


@router.get("", dependencies=[AdminRequired])
async def get_statistics(
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    server: str | None = Query(default=None, description="Slave server name from settings"),
) -> list[dict[str, Any]]:
    if server is not None:
        row = (await db.execute(select(Setting).where(Setting.key == "slave_servers"))).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "No slave servers configured")

        decrypted2 = decrypt_setting("slave_servers", row.value, settings.SETTINGS_ENCRYPTION_KEY)
        slaves: list[dict[str, Any]] = json.loads(decrypted2) or []
        match = next((s for s in slaves if s.get("name") == server), None)
        if match is None:
            raise HTTPException(404, f"Slave server {server!r} not found in settings")

        try:
            return await pdns.get_statistics(
                server_url=match["url"],
                api_key=match.get("api_key"),
                ssl_verify=match.get("ssl_verify", True),
            )
        except (PdnsError, RetryError) as e:
            raise _pdns_exc(e)

    try:
        return await pdns.get_statistics()
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)
