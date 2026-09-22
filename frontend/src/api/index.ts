/**
 * API 封装层 — 所有后端接口调用集中在此
 */

// ── 类型定义 ──────────────────────────────────────────

export type PortCardType = 'used' | 'gap'

export interface PortCard {
  type: PortCardType
  // used
  port?: number
  source?: string
  protocol?: string
  container?: string
  container_id?: string
  service_name?: string
  process?: string
  image?: string
  container_port?: string
  is_running?: boolean
  container_status?: string
  is_host_network?: boolean
  // gap
  start_port?: number
  end_port?: number
  available_count?: number
}

export interface PortAnalysis {
  port_cards: PortCard[]
  total_used: number
  total_available: number
  tcp_used: number
  udp_used: number
  docker_containers: number
  hidden_ports: number[]
  protocol_filter: string | null
}

export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error: string | null
  message: string | null
}

// ── 通用请求 ──────────────────────────────────────────

async function request<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const resp = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`)
  }
  return resp.json()
}

// ── 端口 ──────────────────────────────────────────────

export interface PortsParams {
  protocol?: string
  start_port?: number
  end_port?: number
  search?: string
  range_ids?: number[]   // 非空时仅返回区间内的卡片
}

export function fetchPorts(params: PortsParams = {}): Promise<ApiResponse<PortAnalysis>> {
  const qs = new URLSearchParams()
  if (params.protocol) qs.set('protocol', params.protocol)
  if (params.start_port != null) qs.set('start_port', String(params.start_port))
  if (params.end_port != null) qs.set('end_port', String(params.end_port))
  if (params.search) qs.set('search', params.search)
  if (params.range_ids && params.range_ids.length > 0) {
    // FastAPI 期望重复 key
    params.range_ids.forEach((id) => qs.append('range_ids', String(id)))
  }
  const query = qs.toString()
  return request<PortAnalysis>(`/api/ports${query ? `?${query}` : ''}`)
}

export function refreshPorts(): Promise<ApiResponse<PortAnalysis>> {
  return request<PortAnalysis>('/api/refresh', { method: 'POST' })
}

export interface ProbeSchemeResult {
  scheme: 'http' | 'https' | 'unknown'
  host: string
}

export function probeScheme(port: number, containerId?: string, containerPort?: number | null): Promise<ApiResponse<ProbeSchemeResult>> {
  return request<ProbeSchemeResult>('/api/ports/probe_scheme', {
    method: 'POST',
    body: JSON.stringify({ port, container_id: containerId || null, container_port: containerPort ?? null }),
  })
}

export interface ProbeSchemesResult {
  schemes: Record<string, 'http' | 'https' | 'unknown'>
  host: string
}

export interface ProbeSchemeItem {
  port: number
  container_id?: string | null
  container_port?: number | null
}

/** 批量探测端口协议（卡片 http/https 徽章）。 */
export function probeSchemes(items: ProbeSchemeItem[]): Promise<ApiResponse<ProbeSchemesResult>> {
  return request<ProbeSchemesResult>('/api/ports/probe_schemes', {
    method: 'POST',
    body: JSON.stringify({ items }),
  })
}

// ── 人工指定端口协议（探测不准时手动覆盖）─────────────────

/** 获取全部人工指定 {port: 'http'|'https'}（key 为字符串）。 */
export function fetchPortSchemes(): Promise<ApiResponse<Record<string, 'http' | 'https'>>> {
  return request<Record<string, 'http' | 'https'>>('/api/ports/schemes')
}

/** 人工指定某端口协议。 */
export function setPortScheme(port: number, scheme: 'http' | 'https'): Promise<ApiResponse> {
  return request('/api/ports/scheme', {
    method: 'POST',
    body: JSON.stringify({ port, scheme }),
  })
}

/** 清除某端口的人工指定，恢复自动探测。 */
export function clearPortScheme(port: number): Promise<ApiResponse> {
  return request(`/api/ports/scheme/${port}`, { method: 'DELETE' })
}

// ── 访问地址 ──────────────────────────────────────────

export function getAccessAddress(): Promise<ApiResponse<{ address: string }>> {
  return request<{ address: string }>('/api/config/access_address')
}

export function setAccessAddress(address: string): Promise<ApiResponse<{ address: string }>> {
  return request<{ address: string }>('/api/config/access_address', {
    method: 'POST',
    body: JSON.stringify({ address }),
  })
}

export function editPort(port: number, serviceName: string, serviceType: 'docker' | 'host' = 'host'): Promise<ApiResponse> {
  return request('/api/config/edit', {
    method: 'POST',
    body: JSON.stringify({ port, service_name: serviceName, service_type: serviceType }),
  })
}

// ── 隐藏端口 ──────────────────────────────────────────

export function fetchHiddenPorts(): Promise<ApiResponse<number[]>> {
  return request<number[]>('/api/config/hidden')
}

export function hidePort(port: number): Promise<ApiResponse> {
  return request('/api/config/hidden', { method: 'POST', body: JSON.stringify({ port }) })
}

export function unhidePort(port: number): Promise<ApiResponse> {
  return request(`/api/config/hidden/${port}`, { method: 'DELETE' })
}

export function batchHidePorts(ports: number[]): Promise<ApiResponse> {
  return request('/api/config/hidden/batch', { method: 'POST', body: JSON.stringify({ ports }) })
}

export function batchUnhidePorts(ports: number[]): Promise<ApiResponse> {
  return request('/api/config/hidden/unhide/batch', { method: 'POST', body: JSON.stringify({ ports }) })
}

export interface HiddenPortDetail {
  port: number
  service_name: string | null
  protocol: string | null
  source: string | null
  container: string | null
  image: string | null
  is_running: boolean
}

export function fetchHiddenPortDetails(): Promise<ApiResponse<HiddenPortDetail[]>> {
  return request<HiddenPortDetail[]>('/api/config/hidden/details')
}

// ── 健康检查 ──────────────────────────────────────────

export function healthCheck(): Promise<{ status: string; version: string; channel?: string }> {
  return fetch('/api/health').then(r => r.json())
}

// ── 收藏网格（v1.6.5）─────────────────────────────────

/** 收藏条目：port（带在线状态的服务）或 url（外部站点） */
export interface FavEntry {
  id: string
  kind: 'port' | 'url'
  port?: number
  url?: string
  title?: string
  logoKey?: string
}

/** 文件夹（单层，不可嵌套） */
export interface FavFolder {
  id: string
  kind: 'folder'
  name: string
  /** 预设图标名（lucide），缺省为 Folder */
  icon?: string
  items: FavEntry[]
}

export type GridItem = FavEntry | FavFolder

// ── P1-2 用户偏好 ─────────────────────────────────────────

export interface UserPrefs {
  theme: 'dark' | 'light'
  accent: string
  lang: 'zh' | 'en'
  refresh_interval: number
  logo_scrim: 'none' | 'left' | 'overlay' | 'glass'
  logo_display_mode: 'background' | 'box'
  favorites: GridItem[]
  // v1.6.6
  default_tab: 'overview' | 'favorites'
  background_scope: 'favorites' | 'all'
  background_blur: number
}

export interface UserPrefsPatch {
  theme?: 'dark' | 'light'
  accent?: string
  lang?: 'zh' | 'en'
  refresh_interval?: number
  logo_scrim?: 'none' | 'left' | 'overlay' | 'glass'
  logo_display_mode?: 'background' | 'box'
  favorites?: GridItem[]
  // v1.6.6
  default_tab?: 'overview' | 'favorites'
  background_scope?: 'favorites' | 'all'
  background_blur?: number
}

export function getPrefs(): Promise<ApiResponse<UserPrefs>> {
  return request<UserPrefs>('/api/prefs')
}

export function patchPrefs(patch: UserPrefsPatch): Promise<ApiResponse> {
  return request('/api/prefs', { method: 'PATCH', body: JSON.stringify(patch) })
}

export function resetPrefs(): Promise<ApiResponse> {
  return request('/api/prefs/reset', { method: 'POST' })
}

// ── auth (v1.2) ─────────────────────────────────────

export interface AuthMe {
  auth_required: boolean
  logged_in: boolean
  has_password: boolean
}

export function authMe(): Promise<ApiResponse<AuthMe>> {
  return request<AuthMe>('/api/auth/me')
}

export function setPassword(password: string): Promise<ApiResponse> {
  return request('/api/auth/set_password', { method: 'POST', body: JSON.stringify({ password }) })
}

export function login(password: string): Promise<ApiResponse> {
  return request('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) })
}

export function logout(): Promise<ApiResponse> {
  return request('/api/auth/logout', { method: 'POST' })
}

export function setAuthEnabled(enabled: boolean): Promise<ApiResponse> {
  return request('/api/auth/toggle', { method: 'PATCH', body: JSON.stringify({ enabled }) })
}

// ── ranges (v1.2) ───────────────────────────────────

export interface RangeRead {
  id: number
  name: string
  start_port: number
  end_port: number
  created_at: number
}

export function fetchRanges(): Promise<ApiResponse<RangeRead[]>> {
  return request<RangeRead[]>('/api/ranges')
}

export function createRange(name: string, start_port: number, end_port: number): Promise<ApiResponse> {
  return request('/api/ranges', {
    method: 'POST',
    body: JSON.stringify({ name, start_port, end_port }),
  })
}

export function updateRange(id: number, patch: { name?: string; start_port?: number; end_port?: number }): Promise<ApiResponse> {
  return request(`/api/ranges/${id}`, { method: 'PUT', body: JSON.stringify(patch) })
}

export function deleteRange(id: number): Promise<ApiResponse> {
  return request(`/api/ranges/${id}`, { method: 'DELETE' })
}

// ── logos (v1.5.0) ──────────────────────────────────

export interface LogoMeta {
  app_key: string
  status: 'found' | 'not_found'
  mime: string | null
}

export function fetchLogos(): Promise<ApiResponse<LogoMeta[]>> {
  return request<LogoMeta[]>('/api/logos')
}

export function uploadLogo(appKey: string, mime: string, dataBase64: string): Promise<ApiResponse> {
  return request(`/api/logos/${encodeURIComponent(appKey)}`, {
    method: 'PUT',
    body: JSON.stringify({ mime, data: dataBase64 }),
  })
}

export function deleteLogo(appKey: string): Promise<ApiResponse> {
  return request(`/api/logos/${encodeURIComponent(appKey)}`, { method: 'DELETE' })
}

export function discoverLogo(appKey: string, port: number, path = '/'): Promise<ApiResponse<{ status: string; mime: string | null }>> {
  return request<{ status: string; mime: string | null }>('/api/logos/discover', {
    method: 'POST',
    body: JSON.stringify({ app_key: appKey, port, path }),
  })
}

/** 外部 URL favicon 抓取（v1.6.5）：服务端从 URL origin 抓取并存为 app_key（幂等）。 */
export function fetchFavicon(appKey: string, url: string): Promise<ApiResponse<{ status: string; mime: string | null }>> {
  return request<{ status: string; mime: string | null }>('/api/logos/fetch', {
    method: 'POST',
    body: JSON.stringify({ app_key: appKey, url }),
  })
}

/** 构建 logo 图片 URL（供 <img src> 使用）。 */
export function logoUrl(appKey: string): string {
  return `/api/logos/${encodeURIComponent(appKey)}`
}

/** 内置默认 Logo 匹配表（v1.5.13）：ports 优先 + names 兜底。 */
export interface DefaultLogos {
  names: string[]
  ports: Record<string, string>
}

export function fetchDefaultLogos(): Promise<ApiResponse<DefaultLogos>> {
  return request<DefaultLogos>('/api/logos/defaults')
}

/** 构建内置默认 Logo 图片 URL（供 <img src> 使用）。 */
export function defaultLogoUrl(key: string): string {
  return `/api/logos/default/${encodeURIComponent(key)}`
}

// ── 自定义背景图 (v1.6.6) ─────────────────────────────

/** 上传 / 替换背景图（base64 图片字节）。 */
export function setBackground(mime: string, dataBase64: string): Promise<ApiResponse> {
  return request('/api/background', {
    method: 'PUT',
    body: JSON.stringify({ mime, data: dataBase64 }),
  })
}

/** 删除背景图（幂等）。 */
export function deleteBackground(): Promise<ApiResponse> {
  return request('/api/background', { method: 'DELETE' })
}

/** 构建背景图 URL（供 <img src> 使用）。version 非 0 时附加缓存击穿参数。 */
export function backgroundUrl(version = 0): string {
  return version ? `/api/background?v=${version}` : '/api/background'
}

/** 探测背景图是否已设置（404 = 未设置）。 */
export async function hasBackground(): Promise<boolean> {
  try {
    const resp = await fetch('/api/background', { method: 'HEAD', credentials: 'same-origin' })
    return resp.ok
  } catch {
    return false
  }
}
