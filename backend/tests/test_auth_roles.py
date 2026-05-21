"""Tests for OIDC/LDAP role resolution helpers."""
import pytest

from app.api.endpoints.auth import _resolve_ldap_role, _resolve_oidc_role
from app.models.user import UserRole

GROUP_MAPPING = [
    {"group_dn": "CN=DNS-Admins,DC=example,DC=com", "role": "admin"},
    {"group_dn": "CN=DNS-Operators,DC=example,DC=com", "role": "operator"},
    {"group_dn": "CN=Superadmins,DC=example,DC=com", "role": "superadmin"},
]

OIDC_MAPPING = [
    {"claim_value": "dns-admin", "role": "admin"},
    {"claim_value": "dns-operator", "role": "operator"},
]


# ---------------------------------------------------------------------------
# LDAP role resolution
# ---------------------------------------------------------------------------

def test_ldap_resolve_single_group_match() -> None:
    member_of = ["CN=DNS-Admins,DC=example,DC=com"]
    result = _resolve_ldap_role(member_of, GROUP_MAPPING)
    assert result == UserRole.admin


def test_ldap_resolve_highest_rank_wins() -> None:
    member_of = [
        "CN=DNS-Admins,DC=example,DC=com",
        "CN=Superadmins,DC=example,DC=com",
    ]
    result = _resolve_ldap_role(member_of, GROUP_MAPPING)
    assert result == UserRole.superadmin


def test_ldap_resolve_case_insensitive() -> None:
    member_of = ["cn=dns-admins,dc=example,dc=com"]  # lowercase
    result = _resolve_ldap_role(member_of, GROUP_MAPPING)
    assert result == UserRole.admin


def test_ldap_resolve_no_match_returns_viewer() -> None:
    member_of = ["CN=SomeOtherGroup,DC=example,DC=com"]
    result = _resolve_ldap_role(member_of, GROUP_MAPPING)
    # No match → best_rank stays 0 → returns viewer default
    assert result == UserRole.viewer


def test_ldap_resolve_empty_mapping_returns_none() -> None:
    result = _resolve_ldap_role(["CN=DNS-Admins,DC=example,DC=com"], [])
    assert result is None


def test_ldap_resolve_empty_member_of_returns_viewer() -> None:
    result = _resolve_ldap_role([], GROUP_MAPPING)
    assert result == UserRole.viewer


# ---------------------------------------------------------------------------
# OIDC role resolution
# ---------------------------------------------------------------------------

def test_oidc_resolve_string_claim_match() -> None:
    userinfo = {"roles": "dns-admin"}
    result = _resolve_oidc_role(userinfo, "roles", OIDC_MAPPING)
    assert result == UserRole.admin


def test_oidc_resolve_list_claim_match() -> None:
    userinfo = {"roles": ["dns-operator", "other-group"]}
    result = _resolve_oidc_role(userinfo, "roles", OIDC_MAPPING)
    assert result == UserRole.operator


def test_oidc_resolve_list_picks_highest_rank() -> None:
    mapping = [
        {"claim_value": "dns-admin", "role": "admin"},
        {"claim_value": "dns-superadmin", "role": "superadmin"},
    ]
    userinfo = {"roles": ["dns-admin", "dns-superadmin"]}
    result = _resolve_oidc_role(userinfo, "roles", mapping)
    assert result == UserRole.superadmin


def test_oidc_resolve_claim_missing_returns_viewer() -> None:
    userinfo = {}  # "roles" key not present
    result = _resolve_oidc_role(userinfo, "roles", OIDC_MAPPING)
    assert result == UserRole.viewer


def test_oidc_resolve_empty_mapping_returns_none() -> None:
    userinfo = {"roles": "dns-admin"}
    result = _resolve_oidc_role(userinfo, "roles", [])
    assert result is None


def test_oidc_resolve_empty_role_claim_returns_none() -> None:
    userinfo = {"roles": "dns-admin"}
    result = _resolve_oidc_role(userinfo, "", OIDC_MAPPING)
    assert result is None


def test_oidc_resolve_no_match_in_list_returns_viewer() -> None:
    userinfo = {"roles": ["unknown-group"]}
    result = _resolve_oidc_role(userinfo, "roles", OIDC_MAPPING)
    assert result == UserRole.viewer
