import pytest
from fastapi import HTTPException

from app.services.dns_validator import normalize_record_content, validate_record


# ---------------------------------------------------------------------------
# A records
# ---------------------------------------------------------------------------

def test_valid_a_record() -> None:
    validate_record("A", "1.2.3.4", 300)


def test_invalid_a_record_octet_out_of_range() -> None:
    with pytest.raises(HTTPException):
        validate_record("A", "999.0.0.1", 300)


def test_invalid_a_record_hostname() -> None:
    with pytest.raises(HTTPException):
        validate_record("A", "not-an-ip", 300)


def test_invalid_a_record_ipv6() -> None:
    with pytest.raises(HTTPException):
        validate_record("A", "2001:db8::1", 300)


# ---------------------------------------------------------------------------
# AAAA records
# ---------------------------------------------------------------------------

def test_valid_aaaa() -> None:
    validate_record("AAAA", "2001:db8::1", 300)


def test_invalid_aaaa_ipv4() -> None:
    with pytest.raises(HTTPException):
        validate_record("AAAA", "1.2.3.4", 300)


def test_invalid_aaaa_garbage() -> None:
    with pytest.raises(HTTPException):
        validate_record("AAAA", "not-an-ip", 300)


# ---------------------------------------------------------------------------
# MX records
# ---------------------------------------------------------------------------

def test_valid_mx() -> None:
    validate_record("MX", "10 mail.example.com.", 300)


def test_invalid_mx_no_priority() -> None:
    with pytest.raises(HTTPException):
        validate_record("MX", "mail.example.com.", 300)


def test_invalid_mx_negative_priority() -> None:
    with pytest.raises(HTTPException):
        validate_record("MX", "-1 mail.example.com.", 300)


# ---------------------------------------------------------------------------
# CNAME records
# ---------------------------------------------------------------------------

def test_valid_cname() -> None:
    validate_record("CNAME", "alias.example.com.", 300)


def test_cname_normalize_adds_dot() -> None:
    result = normalize_record_content("CNAME", "alias.example.com")
    assert result.endswith(".")


# ---------------------------------------------------------------------------
# NS records
# ---------------------------------------------------------------------------

def test_valid_ns() -> None:
    validate_record("NS", "ns1.example.com.", 300)


# ---------------------------------------------------------------------------
# TXT records
# ---------------------------------------------------------------------------

def test_valid_txt_unquoted() -> None:
    validate_record("TXT", "v=spf1 include:example.com ~all", 300)


def test_valid_txt_quoted() -> None:
    validate_record("TXT", '"v=spf1 include:example.com ~all"', 300)


# ---------------------------------------------------------------------------
# SRV records
# ---------------------------------------------------------------------------

def test_valid_srv() -> None:
    validate_record("SRV", "10 20 443 target.example.com.", 300)


def test_invalid_srv_missing_parts() -> None:
    with pytest.raises(HTTPException):
        validate_record("SRV", "10 443 target.example.com.", 300)


# ---------------------------------------------------------------------------
# CAA records
# ---------------------------------------------------------------------------

def test_valid_caa() -> None:
    validate_record("CAA", '0 issue "letsencrypt.org"', 300)


def test_invalid_caa_missing_parts() -> None:
    with pytest.raises(HTTPException):
        validate_record("CAA", "letsencrypt.org", 300)


# ---------------------------------------------------------------------------
# TLSA records
# ---------------------------------------------------------------------------

def test_valid_tlsa() -> None:
    validate_record("TLSA", "3 1 1 " + "a" * 64, 300)


def test_tlsa_passes_through_to_pdns() -> None:
    # TLSA records are not locally validated — they pass through to PowerDNS
    validate_record("TLSA", "3 1 x not-hex-data!!!", 300)


# ---------------------------------------------------------------------------
# PTR records
# ---------------------------------------------------------------------------

def test_valid_ptr() -> None:
    validate_record("PTR", "host.example.com.", 300)


# ---------------------------------------------------------------------------
# SOA records
# ---------------------------------------------------------------------------

def test_valid_soa() -> None:
    validate_record("SOA", "ns1.example.com. admin.example.com. 2024010101 3600 900 604800 300", 300)


# ---------------------------------------------------------------------------
# TTL bounds
# ---------------------------------------------------------------------------

def test_ttl_zero_valid() -> None:
    validate_record("A", "1.2.3.4", 0)


def test_ttl_negative_invalid() -> None:
    with pytest.raises(HTTPException):
        validate_record("A", "1.2.3.4", -1)


def test_ttl_max_valid() -> None:
    validate_record("A", "1.2.3.4", 2147483647)


def test_ttl_too_large_invalid() -> None:
    with pytest.raises(HTTPException):
        validate_record("A", "1.2.3.4", 2147483648)


# ---------------------------------------------------------------------------
# normalize_record_content
# ---------------------------------------------------------------------------

def test_normalize_mx_adds_dot() -> None:
    assert normalize_record_content("MX", "10 mail.example.com").endswith(".")


def test_normalize_a_unchanged() -> None:
    assert normalize_record_content("A", "1.2.3.4") == "1.2.3.4"


def test_normalize_txt_preserves_quotes() -> None:
    val = normalize_record_content("TXT", '"hello"')
    assert '"' in val
