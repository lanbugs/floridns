"""
Parsers for BIND zone files and CSV zone files.

BIND format: standard RFC 1035 zone file (uses dnspython)
CSV format:  columns name,type,ttl,content  (name may be @, relative, or FQDN)
"""
import csv
import io
from dataclasses import dataclass, field

import dns.exception
import dns.name
import dns.rdatatype
import dns.zone


@dataclass
class ImportRecord:
    name: str   # absolute FQDN with trailing dot
    type: str
    ttl: int
    content: str


@dataclass
class ParsedZone:
    name: str                                  # FQDN with trailing dot
    records: list[ImportRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Record types managed internally by PowerDNS — skip on import
_SKIP_TYPES = frozenset({"RRSIG", "NSEC", "NSEC3", "NSEC3PARAM", "CDS", "CDNSKEY", "TKEY", "TSIG"})


def parse_bind(content: str, hint_zone_name: str | None = None) -> ParsedZone:
    """Parse a BIND-format zone file using dnspython."""
    origin: str | None = hint_zone_name
    if origin and not origin.endswith("."):
        origin += "."

    try:
        zone = dns.zone.from_text(content, origin=origin, relativize=False)
    except dns.exception.DNSException as exc:
        raise ValueError(f"Cannot parse zone file: {exc}") from exc

    zone_name = str(zone.origin)
    result = ParsedZone(name=zone_name)

    for name_obj, node in zone.nodes.items():
        fqdn = str(name_obj.choose_relativity(zone.origin, relativize=False))
        if not fqdn.endswith("."):
            fqdn = fqdn + "."
        for rdataset in node.rdatasets:
            rtype = dns.rdatatype.to_text(rdataset.rdtype)
            if rtype in _SKIP_TYPES:
                continue
            for rdata in rdataset:
                result.records.append(
                    ImportRecord(name=fqdn, type=rtype, ttl=rdataset.ttl, content=rdata.to_text())
                )

    return result


def parse_csv(content: str, zone_name: str) -> ParsedZone:
    """
    Parse a CSV zone file.
    Required columns: name, type, ttl, content
    name: @ | relative label | absolute FQDN with trailing dot
    """
    if not zone_name.endswith("."):
        zone_name += "."

    result = ParsedZone(name=zone_name)
    reader = csv.DictReader(io.StringIO(content.strip()))

    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no header row")

    normalized_fields = {f.lower().strip() for f in reader.fieldnames}
    required = {"name", "type", "ttl", "content"}
    missing = required - normalized_fields
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    for i, raw_row in enumerate(reader, start=2):
        try:
            row = {k.lower().strip(): (v or "").strip() for k, v in raw_row.items()}
            name = row["name"]
            rtype = row["type"].upper()
            ttl = int(row["ttl"])
            record_content = row["content"]

            if not record_content:
                result.errors.append(f"Row {i}: empty content — skipped")
                continue

            if name in ("@", "", zone_name, zone_name.rstrip(".")):
                fqdn = zone_name
            elif name.endswith("."):
                fqdn = name
            else:
                fqdn = f"{name}.{zone_name}"

            result.records.append(ImportRecord(name=fqdn, type=rtype, ttl=ttl, content=record_content))
        except (KeyError, ValueError) as exc:
            result.errors.append(f"Row {i}: {exc} — skipped")

    return result


def to_rrsets(parsed: ParsedZone) -> list[dict]:
    """Convert ParsedZone records to a PowerDNS PATCH rrsets payload."""
    # Group records by (name, type), keeping the first TTL seen
    grouped: dict[tuple[str, str], tuple[int, list[str]]] = {}
    for rec in parsed.records:
        key = (rec.name, rec.type)
        if key not in grouped:
            grouped[key] = (rec.ttl, [])
        grouped[key][1].append(rec.content)

    return [
        {
            "name": name,
            "type": rtype,
            "ttl": ttl,
            "changetype": "REPLACE",
            "records": [{"content": c, "disabled": False} for c in records],
        }
        for (name, rtype), (ttl, records) in grouped.items()
    ]
