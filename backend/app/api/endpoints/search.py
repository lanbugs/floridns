from typing import Any

from fastapi import APIRouter, HTTPException, Query
from tenacity import RetryError

from app.api.deps import CurrentUser, DbDep, PdnsDep, get_user_accessible_zone_names
from app.services.pdns_client import PdnsError

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    q: str = Query(..., min_length=1, description="Search query"),
    max: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    try:
        results = await pdns.search(q, max)
    except PdnsError as e:
        raise HTTPException(e.status_code, str(e))
    except RetryError as e:
        cause = e.__cause__
        if isinstance(cause, PdnsError):
            raise HTTPException(cause.status_code, str(cause))
        raise HTTPException(502, "PowerDNS unreachable")

    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is None:
        return results

    return [r for r in results if r.get("zone_id") in allowed]
