"""Auto-PTR service: create/update/delete PTR records when A/AAAA records change."""
import ipaddress
from typing import Any

from app.services.pdns_client import PdnsClient, PdnsError


def _ptr_name(ip: str) -> str:
    """Return fully-qualified PTR record name for an IP address."""
    return ipaddress.ip_address(ip).reverse_pointer + "."


def _find_best_zone(ptr_name: str, zones: list[dict[str, Any]]) -> str | None:
    """Return the zone ID of the longest matching reverse zone."""
    name_nod = ptr_name.rstrip(".")
    best_id: str | None = None
    best_len = 0
    for z in zones:
        zone_suffix = z["name"].rstrip(".")
        if name_nod.endswith("." + zone_suffix) or name_nod == zone_suffix:
            if len(zone_suffix) > best_len:
                best_id = z["id"]
                best_len = len(zone_suffix)
    return best_id


async def apply_auto_ptr(
    pdns: PdnsClient,
    forward_zone_id: str,
    patched_rrsets: list[dict[str, Any]],
    snapshot_before: list[dict[str, Any]],
) -> None:
    """After a record patch, sync PTR records in any matching reverse zones.

    patched_rrsets: the rrsets list we sent to PowerDNS (already normalised).
    snapshot_before: the full zone rrsets captured before the patch.
    """
    # Index before-snapshot by (name, type)
    before: dict[tuple[str, str], list[str]] = {}
    for rs in snapshot_before:
        key = (rs["name"].rstrip("."), rs["type"].upper())
        before[key] = [r["content"] for r in rs.get("records", [])]

    # Collect all PTR operations keyed by reverse zone
    # structure: {zone_id: {ptr_name: fqdn | None}}  (None = DELETE)
    ops: dict[str, dict[str, str | None]] = {}

    try:
        all_zones = await pdns.list_zones()
    except PdnsError:
        return  # best-effort; don't break the main request

    for rs in patched_rrsets:
        rtype = rs.get("type", "").upper()
        if rtype not in ("A", "AAAA"):
            continue
        fwd_name = rs["name"].rstrip(".")
        changetype = rs.get("changetype", "REPLACE").upper()

        old_ips: set[str] = set(before.get((fwd_name, rtype), []))

        if changetype == "DELETE":
            new_ips: set[str] = set()
        else:
            new_ips = {r["content"] for r in rs.get("records", [])}

        for ip in old_ips - new_ips:
            ptr = _ptr_name(ip)
            zone_id = _find_best_zone(ptr, all_zones)
            if not zone_id:
                continue
            ops.setdefault(zone_id, {})
            ops[zone_id][ptr] = None  # delete

        for ip in new_ips - old_ips:
            ptr = _ptr_name(ip)
            zone_id = _find_best_zone(ptr, all_zones)
            if not zone_id:
                continue
            ops.setdefault(zone_id, {})
            fqdn = fwd_name + "."
            existing = ops[zone_id].get(ptr)
            # don't overwrite a delete with a create (edge case: two records same IP)
            if existing is None and ptr not in ops[zone_id]:
                ops[zone_id][ptr] = fqdn
            elif existing is not None:
                ops[zone_id][ptr] = fqdn

    for zone_id, ptr_map in ops.items():
        rrsets: list[dict[str, Any]] = []
        for ptr_name_fqdn, fqdn in ptr_map.items():
            if fqdn is None:
                rrsets.append({"name": ptr_name_fqdn, "type": "PTR", "changetype": "DELETE"})
            else:
                rrsets.append({
                    "name": ptr_name_fqdn,
                    "type": "PTR",
                    "ttl": 3600,
                    "changetype": "REPLACE",
                    "records": [{"content": fqdn, "disabled": False}],
                    "comments": [],
                })
        if rrsets:
            try:
                await pdns.patch_rrsets(zone_id, {"rrsets": rrsets})
            except PdnsError:
                pass  # best-effort
