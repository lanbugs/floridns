export type UserRole = 'superadmin' | 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  username: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
  totp_enabled: boolean
  totp_required: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string  // deprecated: refresh token is now in httpOnly cookie
  token_type: string
}

export interface LoginResponse {
  token_type: 'bearer' | 'totp_required'
  access_token: string | null
  refresh_token?: string | null  // deprecated: refresh token is now in httpOnly cookie
  totp_token: string | null
}

export interface Zone {
  id: string
  name: string
  kind: 'Native' | 'Master' | 'Slave'
  serial: number | null
  last_check: number | null
  account: string | null
  dnssec: boolean
}

export interface ZoneDetail extends Zone {
  masters: string[]
  rrsets: RRSet[]
  can_edit: boolean
}

export interface RRSet {
  name: string
  type: string
  ttl: number
  records: { content: string; disabled: boolean }[]
  comments: { content: string; account: string }[]
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface AuditLog {
  id: string
  timestamp: string
  username: string
  ip_address: string
  action: string
  resource_type: string
  resource_id: string | null
  before_value: string | null
  after_value: string | null
  comment: string | null
}

export interface ApiKey {
  id: string
  name: string
  scope: string
  zone_restriction: string | null
  is_active: boolean
  created_at: string
}

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  timeout?: number
}

export interface SearchResult {
  object_type: 'zone' | 'record' | 'comment'
  zone_id: string
  zone: string
  name: string
  type: string
  content: string
  disabled: boolean
}

export interface PdnsStat {
  name: string
  type: string
  value: string | number
}

export interface ZonePermissionResponse {
  id: string
  zone_name: string
  role: UserRole
}

export interface AccountUserEntry {
  user_id: string
  username: string
  role: UserRole
}

export interface DirectPermission {
  zone_name: string
  role: UserRole
}

export interface AccountPermission {
  account_id: string
  account_name: string
  member_role: UserRole
  zones: string[]
}

export interface UserPermissionSummary {
  id: string
  username: string
  email: string
  role: UserRole
  is_active: boolean
  direct_permissions: DirectPermission[]
  account_permissions: AccountPermission[]
}

export interface ZoneTemplateRecord {
  id: string
  name: string
  type: string
  ttl: number
  content: string
}

export interface ZoneTemplate {
  id: string
  name: string
  description: string | null
  created_at: string
  records: ZoneTemplateRecord[]
}

export interface Account {
  id: string
  name: string
  description: string | null
  created_at: string
  zone_names: string[]
  users: AccountUserEntry[]
}

export interface DynDnsHost {
  id: string
  hostname: string
  zone_name: string
  description: string | null
  last_ip: string | null
  last_ip6: string | null
  last_update: string | null
  offline: boolean
  is_active: boolean
  created_at: string
}

export interface DynDnsHostCreated extends DynDnsHost {
  token: string
}
