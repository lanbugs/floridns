import asyncio
from typing import Any


async def authenticate_ldap(username: str, password: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Bind to LDAP and validate credentials.
    Returns {username, email, dn, member_of} or None on failure."""
    return await asyncio.to_thread(_sync_auth, username, password, cfg)


def _sync_auth(username: str, password: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import ldap3
        from ldap3.utils.conv import escape_filter_chars
    except ImportError:
        raise RuntimeError("ldap3 is not installed. Add it to your dependencies.")

    url: str = cfg.get("url", "")
    bind_dn: str = cfg.get("bind_dn", "")
    bind_password: str = cfg.get("bind_password", "")
    base_dn: str = cfg.get("base_dn", "")
    user_attr: str = cfg.get("user_attr", "uid")
    email_attr: str = cfg.get("email_attr", "mail")
    group_attr: str = cfg.get("group_attr", "memberOf")
    tls_mode: str = cfg.get("tls", "none")

    use_ssl = tls_mode == "ldaps"
    use_starttls = tls_mode == "starttls"

    server = ldap3.Server(url, use_ssl=use_ssl, get_info=ldap3.ALL)

    try:
        svc_conn = ldap3.Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
    except Exception:
        return None

    if use_starttls:
        svc_conn.start_tls()

    attrs = [user_attr, email_attr]
    if group_attr:
        attrs.append(group_attr)

    search_filter = f"({user_attr}={escape_filter_chars(username)})"
    svc_conn.search(search_base=base_dn, search_filter=search_filter, attributes=attrs)

    if not svc_conn.entries:
        svc_conn.unbind()
        return None

    entry = svc_conn.entries[0]
    user_dn: str = entry.entry_dn
    email: str = str(entry[email_attr]) if email_attr in entry else f"{username}@ldap.local"

    member_of: list[str] = []
    if group_attr and group_attr in entry:
        raw = entry[group_attr].values
        member_of = [str(v) for v in raw] if raw else []

    svc_conn.unbind()

    # Validate user credentials by binding as the user
    try:
        user_conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()
    except Exception:
        return None

    return {"username": username, "email": email, "dn": user_dn, "member_of": member_of}
