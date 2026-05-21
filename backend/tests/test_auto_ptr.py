"""Unit tests for the auto_ptr_service (no HTTP, no DB)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auto_ptr_service import _find_best_zone, _ptr_name, apply_auto_ptr


# ---------------------------------------------------------------------------
# _ptr_name
# ---------------------------------------------------------------------------

def test_ptr_name_ipv4() -> None:
    assert _ptr_name("192.168.1.10") == "10.1.168.192.in-addr.arpa."


def test_ptr_name_ipv6_full() -> None:
    result = _ptr_name("2001:db8::1")
    assert result.endswith(".ip6.arpa.")
    assert "1.0.0.0" in result


def test_ptr_name_ipv4_loopback() -> None:
    assert _ptr_name("127.0.0.1") == "1.0.0.127.in-addr.arpa."


# ---------------------------------------------------------------------------
# _find_best_zone
# ---------------------------------------------------------------------------

ZONES = [
    {"id": "1.168.192.in-addr.arpa.", "name": "1.168.192.in-addr.arpa."},
    {"id": "168.192.in-addr.arpa.", "name": "168.192.in-addr.arpa."},
    {"id": "192.in-addr.arpa.", "name": "192.in-addr.arpa."},
]


def test_find_best_zone_picks_longest_match() -> None:
    ptr = _ptr_name("192.168.1.10")
    result = _find_best_zone(ptr, ZONES)
    assert result == "1.168.192.in-addr.arpa."


def test_find_best_zone_fallback() -> None:
    ptr = _ptr_name("192.168.2.10")
    result = _find_best_zone(ptr, ZONES)
    assert result == "168.192.in-addr.arpa."


def test_find_best_zone_no_match() -> None:
    ptr = _ptr_name("10.0.0.1")
    result = _find_best_zone(ptr, ZONES)
    assert result is None


def test_find_best_zone_exact_class_c() -> None:
    zones = [{"id": "1.168.192.in-addr.arpa.", "name": "1.168.192.in-addr.arpa."}]
    ptr = _ptr_name("192.168.1.50")
    assert _find_best_zone(ptr, zones) == "1.168.192.in-addr.arpa."


# ---------------------------------------------------------------------------
# apply_auto_ptr
# ---------------------------------------------------------------------------

def _make_pdns(zones: list[dict] | None = None) -> MagicMock:
    m = MagicMock()
    m.list_zones = AsyncMock(return_value=zones or [
        {"id": "1.168.192.in-addr.arpa.", "name": "1.168.192.in-addr.arpa."},
    ])
    m.patch_rrsets = AsyncMock(return_value=None)
    return m


async def test_apply_auto_ptr_creates_ptr_for_new_ip() -> None:
    pdns = _make_pdns()
    rrsets = [{"name": "host.example.com.", "type": "A", "ttl": 300, "changetype": "REPLACE",
               "records": [{"content": "192.168.1.10", "disabled": False}], "comments": []}]
    snapshot_before: list = []
    await apply_auto_ptr(pdns, "example.com.", rrsets, snapshot_before)
    pdns.patch_rrsets.assert_called_once()
    call_args = pdns.patch_rrsets.call_args
    assert call_args[0][0] == "1.168.192.in-addr.arpa."
    payload = call_args[0][1]
    assert payload["rrsets"][0]["changetype"] == "REPLACE"
    assert payload["rrsets"][0]["name"] == "10.1.168.192.in-addr.arpa."
    assert payload["rrsets"][0]["records"][0]["content"] == "host.example.com."


async def test_apply_auto_ptr_deletes_ptr_for_removed_ip() -> None:
    pdns = _make_pdns()
    rrsets = [{"name": "host.example.com.", "type": "A", "ttl": 300, "changetype": "DELETE",
               "records": [], "comments": []}]
    snapshot_before = [{"name": "host.example.com.", "type": "A", "ttl": 300,
                        "records": [{"content": "192.168.1.10", "disabled": False}], "comments": []}]
    await apply_auto_ptr(pdns, "example.com.", rrsets, snapshot_before)
    pdns.patch_rrsets.assert_called_once()
    payload = pdns.patch_rrsets.call_args[0][1]
    assert payload["rrsets"][0]["changetype"] == "DELETE"


async def test_apply_auto_ptr_no_reverse_zone_skips_silently() -> None:
    pdns = _make_pdns(zones=[])  # no reverse zones
    rrsets = [{"name": "host.example.com.", "type": "A", "ttl": 300, "changetype": "REPLACE",
               "records": [{"content": "10.0.0.1", "disabled": False}], "comments": []}]
    await apply_auto_ptr(pdns, "example.com.", rrsets, [])
    pdns.patch_rrsets.assert_not_called()


async def test_apply_auto_ptr_ignores_non_a_types() -> None:
    pdns = _make_pdns()
    rrsets = [{"name": "example.com.", "type": "MX", "ttl": 300, "changetype": "REPLACE",
               "records": [{"content": "10 mail.example.com.", "disabled": False}], "comments": []}]
    await apply_auto_ptr(pdns, "example.com.", rrsets, [])
    pdns.patch_rrsets.assert_not_called()


async def test_apply_auto_ptr_updates_changed_ip() -> None:
    pdns = _make_pdns()
    snapshot_before = [{"name": "host.example.com.", "type": "A", "ttl": 300,
                        "records": [{"content": "192.168.1.10", "disabled": False}], "comments": []}]
    rrsets = [{"name": "host.example.com.", "type": "A", "ttl": 300, "changetype": "REPLACE",
               "records": [{"content": "192.168.1.20", "disabled": False}], "comments": []}]
    await apply_auto_ptr(pdns, "example.com.", rrsets, snapshot_before)
    # Should call once for the reverse zone (delete old + create new → one patch)
    pdns.patch_rrsets.assert_called_once()
    ops = pdns.patch_rrsets.call_args[0][1]["rrsets"]
    changetypes = {op["changetype"] for op in ops}
    assert "DELETE" in changetypes
    assert "REPLACE" in changetypes


async def test_apply_auto_ptr_pdns_error_swallowed() -> None:
    from app.services.pdns_client import PdnsError
    pdns = _make_pdns()
    pdns.list_zones = AsyncMock(side_effect=PdnsError(502, "unreachable"))
    rrsets = [{"name": "host.example.com.", "type": "A", "ttl": 300, "changetype": "REPLACE",
               "records": [{"content": "192.168.1.10", "disabled": False}], "comments": []}]
    # Should not raise
    await apply_auto_ptr(pdns, "example.com.", rrsets, [])
