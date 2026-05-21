import ipaddress
import re

from fastapi import HTTPException


def _is_fqdn(name: str) -> bool:
    """Check if name is a valid FQDN (optionally with trailing dot)."""
    name = name.rstrip(".")
    if not name or len(name) > 253:
        return False
    label_re = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")
    return all(label_re.match(label) for label in name.split("."))


def _is_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return False


def _is_ipv6(value: str) -> bool:
    try:
        ipaddress.IPv6Address(value)
        return True
    except ValueError:
        return False


VALIDATORS: dict[str, list[tuple[bool, str]]] = {}


def normalize_record_content(record_type: str, content: str) -> str:
    """Add trailing dots to hostname fields where PowerDNS requires them."""
    rtype = record_type.upper()
    if rtype in ("NS", "CNAME", "PTR", "ALIAS"):
        return ensure_trailing_dot(content)
    if rtype == "MX":
        parts = content.split(None, 1)
        if len(parts) == 2:
            return f"{parts[0]} {ensure_trailing_dot(parts[1])}"
    if rtype == "SRV":
        parts = content.split(None, 3)
        if len(parts) == 4:
            return f"{parts[0]} {parts[1]} {parts[2]} {ensure_trailing_dot(parts[3])}"
    return content


def validate_record(record_type: str, content: str, ttl: int) -> None:
    if ttl < 0 or ttl > 2_147_483_647:
        raise HTTPException(422, f"TTL {ttl} out of range (0–2147483647)")

    rtype = record_type.upper()

    if rtype == "A":
        if not _is_ipv4(content):
            raise HTTPException(422, f"Invalid IPv4 address: {content!r}")

    elif rtype == "AAAA":
        if not _is_ipv6(content):
            raise HTTPException(422, f"Invalid IPv6 address: {content!r}")

    elif rtype in ("CNAME", "NS", "PTR", "ALIAS"):
        if not _is_fqdn(content):
            raise HTTPException(422, f"Invalid FQDN for {rtype}: {content!r}")

    elif rtype == "MX":
        parts = content.split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit() or not _is_fqdn(parts[1]):
            raise HTTPException(422, f"Invalid MX record: {content!r} (expected: <prio> <fqdn>)")

    elif rtype == "TXT":
        # Allow quoted or unquoted; PowerDNS accepts both
        pass

    elif rtype == "SRV":
        parts = content.split()
        if len(parts) != 4:
            raise HTTPException(422, f"Invalid SRV record: expected <prio> <weight> <port> <target>")
        for i, field in enumerate(parts[:3]):
            if not field.isdigit():
                raise HTTPException(422, f"SRV field {i} must be numeric")

    elif rtype == "CAA":
        parts = content.split(None, 2)
        if len(parts) != 3 or not parts[0].isdigit() or parts[1] not in ("issue", "issuewild", "iodef"):
            raise HTTPException(422, f"Invalid CAA record: {content!r}")

    elif rtype == "SOA":
        parts = content.split()
        if len(parts) != 7:
            raise HTTPException(422, f"SOA requires exactly 7 fields, got {len(parts)}")

    # Other types (TLSA, NAPTR, SSHFP, DNSKEY, DS, HTTPS, SVCB) are passed through to PowerDNS


def ensure_trailing_dot(name: str) -> str:
    return name if name.endswith(".") else name + "."


def normalize_zone_name(name: str) -> str:
    return ensure_trailing_dot(name.lower())
