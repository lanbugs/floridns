import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

import dns.exception
import dns.message
import dns.name
import dns.query
import dns.rdatatype

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WARN_DAYS = 7
CRITICAL_DAYS = 2


def _nameservers_to_try() -> list[str]:
    """Return candidate DNS servers: PowerDNS host first, then system resolvers."""
    candidates: list[str] = []
    try:
        host = urlparse(str(settings.PDNS_API_URL)).hostname
        if host:
            candidates.append(host)
    except Exception:
        pass
    try:
        import dns.resolver
        candidates.extend(dns.resolver.get_default_resolver().nameservers)
    except Exception:
        pass
    # deduplicate while preserving order
    seen: set[str] = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]


def _earliest_rrsig(zone_name: str) -> datetime | None:
    """
    Queries each candidate DNS server for the SOA RRSIG of *zone_name* and
    returns the earliest expiry timestamp found, or None on failure.
    Intended to run in a thread via asyncio.to_thread().
    """
    try:
        qname = dns.name.from_text(zone_name)
    except dns.exception.DNSException:
        return None

    request = dns.message.make_query(qname, dns.rdatatype.SOA, want_dnssec=True)

    for ns in _nameservers_to_try():
        try:
            response = dns.query.udp(request, ns, port=53, timeout=3)
            earliest: datetime | None = None
            for rrset in response.answer:
                if rrset.rdtype == dns.rdatatype.RRSIG:
                    for rrsig in rrset:
                        ts = datetime.fromtimestamp(rrsig.expiration, tz=timezone.utc)
                        if earliest is None or ts < earliest:
                            earliest = ts
            if earliest is not None:
                return earliest
        except Exception as exc:
            logger.debug("dnssec_expiry_query_failed", nameserver=ns, zone=zone_name, error=str(exc))

    return None


async def get_rrsig_expiry(zone_name: str) -> datetime | None:
    return await asyncio.to_thread(_earliest_rrsig, zone_name)


def expiry_summary(expiry: datetime | None) -> dict:
    if expiry is None:
        return {"expiry": None, "days_remaining": None, "warning": False, "critical": False}
    now = datetime.now(timezone.utc)
    days = max(0, (expiry - now).days)
    return {
        "expiry": expiry.isoformat(),
        "days_remaining": days,
        "warning": days < WARN_DAYS,
        "critical": days < CRITICAL_DAYS,
    }
