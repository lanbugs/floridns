# FloriDNS

A modern, self-hosted web frontend for managing a [PowerDNS](https://www.powerdns.com/) Authoritative Server.

A fresh take on PowerDNS management — built with a modern stack, strict input validation, and a clean UI for day-to-day DNS operations.

![License](https://img.shields.io/badge/license-MIT-blue)
![PowerDNS](https://img.shields.io/badge/PowerDNS-4.7%2B%20%2F%205.x-green)
![Docker](https://img.shields.io/badge/Docker-lanbugsde%2Ffloridns-blue)

---

## Features

| Area | Highlights |
|---|---|
| **Zones** | Create / edit / delete · Master, Slave, Native · BIND export · Server-side pagination & sorting |
| **Records** | A, AAAA, CNAME, MX, NS, TXT, SRV, CAA, TLSA, PTR, SOA, ALIAS · Inline validation · Atomic rename |
| **DNSSEC** | Enable / disable per zone · Key management · RRSIG expiry alerts (< 7 days warning, < 2 days critical) |
| **Zone history** | Full RRSET snapshot before/after every change · Before/After diff view · One-click rollback |
| **Users & RBAC** | Roles: superadmin · admin · operator · viewer · Per-zone permissions · Account groups |
| **API keys** | Per-user API keys with scope (read-only / read-write / acme) and optional zone restriction |
| **Dynamic DNS** | DynDNS 2 protocol at `/nic/update` · Compatible with FRITZ!Box, Synology, ddclient |
| **Auth** | Local auth · TOTP (2FA) · Passkeys (WebAuthn) · OIDC (SSO) · LDAP |
| **Audit log** | Every change logged with user, IP, before/after values |
| **Monitoring** | Primary + slave server status · PowerDNS statistics view |
| **Settings** | PowerDNS API config · Slave servers · Record type restrictions · Encryption for sensitive settings |

---

## Requirements

- Docker & Docker Compose v2
- A running **PowerDNS Authoritative Server 4.7+** or **5.x** with the HTTP API enabled
- A domain / reverse proxy for TLS termination in production (nginx, Traefik, Caddy, …)

### Enabling the PowerDNS API

Add to your `pdns.conf`:

```ini
api=yes
api-key=your-secret-api-key
webserver=yes
webserver-address=0.0.0.0
webserver-port=8081
webserver-allow-from=127.0.0.1,::1,<floridns-container-ip>/32
```

---

## Quick start

### 1. Create a `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: pdns
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
      POSTGRES_DB: pdnsui
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pdns -d pdnsui"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    image: lanbugsde/floridns-backend:latest
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://pdns:${DB_PASSWORD:-changeme}@db/pdnsui
      PDNS_API_URL: ${PDNS_API_URL}
      PDNS_API_KEY: ${PDNS_API_KEY}
      SECRET_KEY: ${SECRET_KEY}
      INITIAL_ADMIN_USERNAME: ${INITIAL_ADMIN_USERNAME:-admin}
      INITIAL_ADMIN_PASSWORD: ${INITIAL_ADMIN_PASSWORD}
      INITIAL_ADMIN_EMAIL: ${INITIAL_ADMIN_EMAIL}
      COOKIE_SECURE: "true"
      WEBAUTHN_RP_ID: ${WEBAUTHN_RP_ID:-dns.example.com}
      WEBAUTHN_ORIGIN: ${WEBAUTHN_ORIGIN:-https://dns.example.com}
      LOG_FORMAT: json

  frontend:
    image: lanbugsde/floridns-frontend:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### 2. Create a `.env` file

```env
# Database
DB_PASSWORD=a-strong-db-password

# PowerDNS API
PDNS_API_URL=http://your-pdns-host:8081
PDNS_API_KEY=your-pdns-api-key

# Auth — generate with: openssl rand -hex 32
SECRET_KEY=replace-with-a-random-32-char-minimum-string

# Initial admin account (created on first start if no users exist)
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=change-me-after-first-login
INITIAL_ADMIN_EMAIL=admin@example.com
```

### 3. Start

```bash
docker compose up -d
```

Migrations run automatically on startup. The frontend is now available on port `8080` — put a reverse proxy with TLS in front of it.

---

## Production: reverse proxy with TLS

The frontend container speaks plain HTTP on port 80 (internally). TLS must be terminated by an upstream proxy.

### nginx example

```nginx
server {
    listen 443 ssl http2;
    server_name dns.example.com;

    ssl_certificate     /etc/ssl/certs/dns.example.com.crt;
    ssl_certificate_key /etc/ssl/private/dns.example.com.key;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name dns.example.com;
    return 301 https://$host$request_uri;
}
```

### Traefik (Docker labels) example

```yaml
  frontend:
    image: lanbugsde/floridns-frontend:latest
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.floridns.rule=Host(`dns.example.com`)"
      - "traefik.http.routers.floridns.entrypoints=websecure"
      - "traefik.http.routers.floridns.tls.certresolver=letsencrypt"
      - "traefik.http.services.floridns.loadbalancer.server.port=80"
    depends_on:
      - backend
```

---

## Configuration reference

All backend settings are passed as environment variables.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `PDNS_API_URL` | — | PowerDNS HTTP API base URL (e.g. `http://pdns:8081`) |
| `PDNS_API_KEY` | — | PowerDNS API key |
| `PDNS_SERVER_ID` | `localhost` | PowerDNS server ID (usually `localhost`) |
| `PDNS_SSL_VERIFY` | `true` | Verify TLS for PowerDNS API (`false` for self-signed certs) |
| `SECRET_KEY` | — | **Required.** Min. 32 chars. Used for JWT signing. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `COOKIE_SECURE` | `true` | Set `false` only for local HTTP development |
| `SETTINGS_ENCRYPTION_KEY` | `` | Fernet key to encrypt sensitive settings in the DB (LDAP/OIDC secrets, PowerDNS API key). Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `INITIAL_ADMIN_USERNAME` | `` | Admin user created on first start (skipped if any user exists) |
| `INITIAL_ADMIN_PASSWORD` | `` | Password for initial admin |
| `INITIAL_ADMIN_EMAIL` | `` | E-mail for initial admin |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins |
| `DOCS_ENABLED` | `true` | Expose Swagger UI at `/api/v1/docs` (set `false` in production) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_FORMAT` | `json` | `json` (structured) or `console` (human-readable) |
| `OIDC_ENABLED` | `false` | Enable OIDC SSO — further config via the Settings UI after first login |
| `LDAP_ENABLED` | `false` | Enable LDAP auth — further config via the Settings UI after first login |
| `WEBAUTHN_RP_ID` | `localhost` | **Required in production.** The domain users access the app on — no port, no scheme (e.g. `dns.example.com`) |
| `WEBAUTHN_RP_NAME` | `FloriDNS` | Display name shown in the browser passkey dialog |
| `WEBAUTHN_ORIGIN` | `http://localhost:5173` | **Required in production.** Full origin including scheme (e.g. `https://dns.example.com`) |

---

## Dynamic DNS (`/nic/update`)

FloriDNS implements the **DynDNS 2** protocol and is compatible with FRITZ!Box, Synology DSM, ddclient, and OpenWrt.

Enable Dynamic DNS in **Settings → Dynamic DNS** (superadmin), then create a host in the **Dynamic DNS** section of the sidebar.

| Parameter | Value |
|---|---|
| Protocol | DynDNS 2 |
| Update URL | `https://dns.example.com/nic/update?hostname=<domain>&myip=<ipaddr>` |
| Username | FQDN of the registered host (e.g. `home.yourdomain.com`) |
| Password | Token shown at host creation |

> The FQDN is composed of the **hostname label** + **zone** (e.g. label `home` in zone `yourdomain.com` → FQDN `home.yourdomain.com`). Enter the FQDN as-is, without a trailing dot, in your router.

---

## First login & initial setup

1. Open the UI in your browser.
2. Log in with the `INITIAL_ADMIN_*` credentials.
3. Go to **Settings** and configure:
   - **Primary PowerDNS** — URL, API key, SSL verify
   - **Allowed record types** per role (optional)
   - **Zone history** — enable if you want rollback support
4. Create additional users under **Users**.
5. Change the initial admin password under **User Settings → Security**.

---

## Upgrading

```bash
docker compose pull
docker compose up -d
```

Database migrations run automatically on container start.

---

## Development setup

### Prerequisites

- Python 3.12+
- Node.js 22+
- A running PostgreSQL instance (use `docker-compose.dev.yml`)

### Backend

```bash
cd backend
cp .env.example .env          # adjust values
python -m venv .venv
source .venv/bin/activate
pip install uv
uv pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/` to `http://localhost:8000`. Open `http://localhost:5173`.

### Running tests

```bash
cd backend
pytest
```

---

## Architecture

```
Browser
  │
  ▼
Frontend (nginx, :80)
  ├── Static assets (Vue 3 SPA)
  └── /api/* → proxy → Backend (:8000)
                          │
                          ├── FastAPI + SQLAlchemy (async)
                          ├── PostgreSQL (JWT store, settings, users, history)
                          └── PowerDNS REST API
```

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x (async), Pydantic v2, Alembic
- **Frontend**: Vue 3 (Composition API), TypeScript, Vite, Tabler.io v1.4 (Bootstrap)
- **Auth**: JWT (access + refresh token rotation) · httpOnly refresh token cookie · TOTP · Passkeys (WebAuthn) · OIDC · LDAP

---

## Security

- All endpoints require authentication (no public routes except `/health` and `/nic/update`)
- Refresh token stored in `httpOnly; SameSite=Strict` cookie — not accessible to JavaScript
- Access token revocation via token versioning — invalidated immediately on logout and password change
- Account lockout after 5 failed login attempts (15-minute lockout)
- Passkey / WebAuthn support (FIDO2) — phishing-resistant login without passwords
- Bcrypt password hashing (cost factor 12)
- Rate limiting on login (10 req/min/IP) and refresh (30 req/min/IP)
- Optional Fernet encryption for sensitive settings (LDAP/OIDC secrets, PowerDNS API key) stored in the database
- TLS termination expected at the reverse proxy level

---

## License

MIT — see [LICENSE](LICENSE).

---

## Third-party notices

FloriDNS uses the following third-party library under a license different from MIT:

**ldap3** — [https://github.com/cannatag/ldap3](https://github.com/cannatag/ldap3)
Licensed under the [GNU Lesser General Public License v3 (LGPL-3.0)](https://www.gnu.org/licenses/lgpl-3.0.html).
ldap3 is used as an unmodified library for optional LDAP authentication. Users may replace it with any compatible LGPL-3.0 version.
