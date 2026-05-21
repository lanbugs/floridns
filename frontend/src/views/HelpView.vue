<script setup lang="ts">
import { computed } from 'vue'
import {
  IconWorld,
  IconFileText,
  IconShieldLock,
  IconUsers,
  IconClipboardList,
  IconChartBar,
  IconSettings,
  IconApi,
  IconLock,
} from '@tabler/icons-vue'

const baseUrl = computed(() => window.location.origin)

// Shell variables are escaped as \${} so TS does not interpolate them.
// Only ${baseUrl.value} is a real TS interpolation.
const acmeshScript = computed(() => [
  '#!/bin/bash',
  '# Place at: ~/.acme.sh/dnsapi/dns_floridns.sh',
  '# Usage:',
  `#   export FLORIDNS_URL="${baseUrl.value}"`,
  '#   export FLORIDNS_API_KEY="<your acme-scoped API key>"',
  '#   export FLORIDNS_ZONE_ID="example.com."   # trailing dot required',
  '#',
  '#   acme.sh --dns dns_floridns --dnssleep 5 -d example.com -d "*.example.com"',
  '',
  'dns_floridns_add() {',
  '  local fulldomain="$1"',
  '  local txtvalue="$2"',
  '  local body',
  '  body=$(printf \'{"rrsets":[{"name":"%s.","type":"TXT","ttl":60,"records":[{"content":"\\"%s\\"","disabled":false}]}]}\' "$fulldomain" "$txtvalue")',
  '',
  '  curl -sf -X PATCH \\',
  '    -H "Authorization: Bearer ${FLORIDNS_API_KEY}" \\',
  '    -H "Content-Type: application/json" \\',
  '    "${FLORIDNS_URL}/api/v1/zones/${FLORIDNS_ZONE_ID}/records" \\',
  '    -d "$body"',
  '}',
  '',
  'dns_floridns_rm() {',
  '  local fulldomain="$1"',
  '  local body',
  '  body=$(printf \'{"rrsets":[{"name":"%s.","type":"TXT","changetype":"DELETE"}]}\' "$fulldomain")',
  '',
  '  curl -sf -X PATCH \\',
  '    -H "Authorization: Bearer ${FLORIDNS_API_KEY}" \\',
  '    -H "Content-Type: application/json" \\',
  '    "${FLORIDNS_URL}/api/v1/zones/${FLORIDNS_ZONE_ID}/records" \\',
  '    -d "$body"',
  '}',
].join('\n'))

const certbotAuth = computed(() => [
  '#!/bin/bash',
  '# /etc/letsencrypt/hooks/floridns-auth.sh',
  `FLORIDNS_URL="${baseUrl.value}"`,
  'FLORIDNS_API_KEY="<your acme-scoped API key>"',
  'FLORIDNS_ZONE_ID="example.com."   # trailing dot required',
  '',
  'body=$(printf \'{"rrsets":[{"name":"_acme-challenge.%s.","type":"TXT","ttl":60,"records":[{"content":"\\"%s\\"","disabled":false}]}]}\' "$CERTBOT_DOMAIN" "$CERTBOT_VALIDATION")',
  '',
  'curl -sf -X PATCH \\',
  '  -H "Authorization: Bearer ${FLORIDNS_API_KEY}" \\',
  '  -H "Content-Type: application/json" \\',
  '  "${FLORIDNS_URL}/api/v1/zones/${FLORIDNS_ZONE_ID}/records" \\',
  '  -d "$body"',
  '',
  'sleep 5',
].join('\n'))

const certbotCleanup = computed(() => [
  '#!/bin/bash',
  '# /etc/letsencrypt/hooks/floridns-cleanup.sh',
  `FLORIDNS_URL="${baseUrl.value}"`,
  'FLORIDNS_API_KEY="<your acme-scoped API key>"',
  'FLORIDNS_ZONE_ID="example.com."   # trailing dot required',
  '',
  'body=$(printf \'{"rrsets":[{"name":"_acme-challenge.%s.","type":"TXT","changetype":"DELETE"}]}\' "$CERTBOT_DOMAIN")',
  '',
  'curl -sf -X PATCH \\',
  '  -H "Authorization: Bearer ${FLORIDNS_API_KEY}" \\',
  '  -H "Content-Type: application/json" \\',
  '  "${FLORIDNS_URL}/api/v1/zones/${FLORIDNS_ZONE_ID}/records" \\',
  '  -d "$body"',
].join('\n'))

const certbotCmd = [
  'chmod +x /etc/letsencrypt/hooks/floridns-*.sh',
  '',
  'certbot certonly \\',
  '  --manual \\',
  '  --preferred-challenges dns \\',
  '  --manual-auth-hook /etc/letsencrypt/hooks/floridns-auth.sh \\',
  '  --manual-cleanup-hook /etc/letsencrypt/hooks/floridns-cleanup.sh \\',
  '  -d example.com -d "*.example.com"',
].join('\n')
</script>

<template>
  <div>
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Documentation</div>
            <h2 class="page-title">Help</h2>
          </div>
          <div class="col-auto ms-auto d-print-none">
            <div class="btn-list">
              <a href="/api/v1/docs" target="_blank" rel="noopener" class="btn btn-secondary d-inline-flex align-items-center gap-1">
                <IconApi :size="16" />
                API Docs (Swagger)
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">
        <div class="row g-3">

          <!-- Zone Management -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconWorld :size="20" class="text-blue" />
                  Zone Management
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">Manage DNS zones on your PowerDNS authoritative server.</p>
                <ul class="list-unstyled mb-0">
                  <li class="mb-2"><strong>Create zone</strong> — Enter the zone name (e.g. <code>example.com</code>), choose a type and provide nameservers. Trailing dots are added automatically.</li>
                  <li class="mb-2"><strong>Zone types</strong> — <span class="badge bg-blue text-blue-fg">Native</span> for single-server setups, <span class="badge bg-green text-green-fg">Master</span> for primary with secondaries, <span class="badge bg-yellow text-yellow-fg">Slave</span> for secondary zones.</li>
                  <li class="mb-2"><strong>DNSSEC</strong> — Enable or disable per zone. DS records are displayed for hand-off to the registrar.</li>
                  <li class="mb-0"><strong>Export</strong> — Download the zone as a BIND-compatible zone file.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Record Management -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconFileText :size="20" class="text-green" />
                  Record Management
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">Add, edit and delete DNS records within a zone.</p>
                <ul class="list-unstyled mb-0">
                  <li class="mb-2"><strong>Name</strong> — Use <code>@</code> or leave empty for the zone apex. Relative names are automatically completed with the zone name.</li>
                  <li class="mb-2"><strong>Multiple values</strong> — Click <em>Add value</em> to create records with multiple content entries (e.g. round-robin A records).</li>
                  <li class="mb-2"><strong>TTL presets</strong> — Quick-select 60s, 5m, 1h or 24h, or type a custom value in seconds.</li>
                  <li class="mb-0"><strong>Rename</strong> — Changing the name of an existing record deletes the old RRset and creates the new one atomically.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- RBAC -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconShieldLock :size="20" class="text-red" />
                  Roles &amp; Permissions
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">FloriDNS uses role-based access control (RBAC).</p>
                <div class="table-responsive">
                  <table class="table table-sm table-vcenter mb-0">
                    <thead>
                      <tr>
                        <th>Role</th>
                        <th>Capabilities</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><span class="badge bg-red text-red-fg">superadmin</span></td>
                        <td>Full access including user and system management</td>
                      </tr>
                      <tr>
                        <td><span class="badge bg-blue text-blue-fg">admin</span></td>
                        <td>Manage zones, records, users and settings</td>
                      </tr>
                      <tr>
                        <td><span class="badge bg-green text-green-fg">operator</span></td>
                        <td>Create and edit records in assigned zones</td>
                      </tr>
                      <tr>
                        <td><span class="badge bg-secondary text-secondary-fg">viewer</span></td>
                        <td>Read-only access to assigned zones</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p class="text-muted small mt-3 mb-0">Zone-level permissions override the global role for specific zones. Assign them via the shield icon in the Users view.</p>
              </div>
            </div>
          </div>

          <!-- Accounts -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconUsers :size="20" class="text-azure" />
                  Accounts
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">Accounts group users and zones together for easier access management.</p>
                <ul class="list-unstyled mb-0">
                  <li class="mb-2"><strong>Create account</strong> — Give it a name and optionally a description.</li>
                  <li class="mb-2"><strong>Add members</strong> — Assign users to an account with a role (operator or viewer). Members inherit access to all zones in the account.</li>
                  <li class="mb-0"><strong>Add zones</strong> — Assign zones to an account. All account members automatically gain access to these zones.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Audit Log -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconClipboardList :size="20" class="text-orange" />
                  Audit Log
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">Every change is recorded with timestamp, user, IP address and action.</p>
                <ul class="list-unstyled mb-0">
                  <li class="mb-2"><strong>Filter</strong> — Filter by action keyword (e.g. <code>zone.create</code>, <code>records.patch</code>) or username.</li>
                  <li class="mb-2"><strong>Details</strong> — Click any row to expand the before/after payload for that change.</li>
                  <li class="mb-0"><strong>Export</strong> — Download the full log as CSV or JSON for external analysis or archiving.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Statistics -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconChartBar :size="20" class="text-purple" />
                  Statistics
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted">Live statistics from the PowerDNS authoritative server.</p>
                <ul class="list-unstyled mb-0">
                  <li class="mb-2"><strong>Primary server</strong> — Key metrics such as uptime, query counts, cache hit ratio and latency.</li>
                  <li class="mb-0"><strong>Secondary servers</strong> — If secondary servers are configured in Settings, you can switch between them using the server selector.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Settings -->
          <div class="col-12 col-lg-6">
            <div class="card h-100">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconSettings :size="20" class="text-muted" />
                  Settings
                </div>
              </div>
              <div class="card-body">
                <div class="row g-3">
                  <div class="col-md-4">
                    <h4 class="subheader">Primary PowerDNS Server</h4>
                    <p class="text-muted small">Override the API URL and key configured via environment variables. Enable or disable SSL certificate verification (use <em>skip</em> for self-signed certificates).</p>
                  </div>
                  <div class="col-md-4">
                    <h4 class="subheader">Operator Record Types</h4>
                    <p class="text-muted small">Restrict which DNS record types operators are allowed to create or edit. Admins and superadmins always have access to all types.</p>
                  </div>
                  <div class="col-md-4">
                    <h4 class="subheader">Secondary Servers</h4>
                    <p class="text-muted small">Register additional PowerDNS servers. Their statistics are then accessible in the Statistics view. Each server can have individual SSL verification settings.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- ACME DNS-01 -->
          <div class="col-12">
            <div class="card">
              <div class="card-header">
                <div class="card-title d-flex align-items-center gap-2">
                  <IconLock :size="20" class="text-green" />
                  ACME DNS-01 (Let's Encrypt / certbot / acme.sh)
                </div>
              </div>
              <div class="card-body">
                <p class="text-muted mb-4">
                  FloriDNS can serve as the DNS backend for ACME DNS-01 challenges. This lets certbot or acme.sh automatically
                  create and remove <code>_acme-challenge</code> TXT records when renewing TLS certificates — including wildcard certificates.
                  Use an <span class="badge bg-orange text-orange-fg">acme</span>-scoped API key: it is restricted to
                  <code>_acme-challenge</code> TXT records only and cannot modify any other DNS data.
                </p>

                <div class="row g-4">
                  <!-- Step 1 -->
                  <div class="col-12">
                    <h4 class="subheader">Step 1 — Create an ACME API Key</h4>
                    <p class="text-muted small mb-0">
                      Go to <strong>User Settings → API Keys</strong>, create a new key and select scope
                      <strong>acme — ACME DNS-01 challenges only</strong>.
                      The key is shown once — copy it immediately.
                      Grant the key's owner (your user) at least operator access to the zone.
                    </p>
                  </div>

                  <!-- acme.sh -->
                  <div class="col-12">
                    <h4 class="subheader">acme.sh</h4>
                    <p class="text-muted small">
                      Save the script below as <code>~/.acme.sh/dnsapi/dns_floridns.sh</code>, then run the
                      <code>acme.sh</code> command. The <code>FLORIDNS_ZONE_ID</code> must match the zone name
                      in FloriDNS exactly, including the trailing dot.
                    </p>
                    <pre class="bg-dark text-white rounded p-3 overflow-auto" style="font-size:0.78rem;max-height:22rem;">{{ acmeshScript }}</pre>
                  </div>

                  <!-- certbot -->
                  <div class="col-12">
                    <h4 class="subheader">certbot</h4>
                    <p class="text-muted small">Save the two hook scripts, make them executable and run certbot with the <code>--manual</code> authenticator.</p>

                    <p class="text-muted small fw-medium mb-1">Auth hook — <code>/etc/letsencrypt/hooks/floridns-auth.sh</code></p>
                    <pre class="bg-dark text-white rounded p-3 overflow-auto mb-3" style="font-size:0.78rem;">{{ certbotAuth }}</pre>

                    <p class="text-muted small fw-medium mb-1">Cleanup hook — <code>/etc/letsencrypt/hooks/floridns-cleanup.sh</code></p>
                    <pre class="bg-dark text-white rounded p-3 overflow-auto mb-3" style="font-size:0.78rem;">{{ certbotCleanup }}</pre>

                    <p class="text-muted small fw-medium mb-1">Run certbot</p>
                    <pre class="bg-dark text-white rounded p-3 overflow-auto" style="font-size:0.78rem;">{{ certbotCmd }}</pre>
                  </div>

                  <!-- Notes -->
                  <div class="col-12">
                    <div class="alert alert-info mb-0">
                      <strong>Notes</strong>
                      <ul class="mb-0 mt-1">
                        <li>Set <code>FLORIDNS_ZONE_ID</code> to the parent zone that FloriDNS manages — e.g. <code>example.com.</code> even when issuing a certificate for <code>sub.example.com</code>.</li>
                        <li>The <span class="badge bg-orange text-orange-fg">acme</span> key is rejected by the API for any record name that does not start with <code>_acme-challenge.</code> or any type other than <code>TXT</code>.</li>
                        <li>For automatic renewal add the hook flags to <code>/etc/letsencrypt/renewal/example.com.conf</code> under <code>[renewalparams]</code>.</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>
