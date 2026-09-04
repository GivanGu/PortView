/**
 * API 封装层 — 所有后端接口调用集中在此
 */

// ── 类型定义 ──────────────────────────────────────────

export type PortCardType = 'used' | 'gap' | 'unknown_range'

export interface PortCard {
  type: PortCardType
  // used
  port?: number
  source?: string
  protocol?: string
  container?: string
  service_name?: string
  process?: string
  image?: string
  container_port?: string
  is_running?: boolean
  container_status?: string
  is_host_network?: boolean
  // gap / unknown_range
  start_port?: number
  end_port?: number
  available_count?: number
  port_count?: number
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

export interface ConfigEntry {
  [key: string]: string
}

// ── 通用请求 ──────────────────────────────────────────

async function request<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const resp = await fetch(url, {
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
}

export function fetchPorts(params: PortsParams = {}): Promise<ApiResponse<PortAnalysis>> {
  const qs = new URLSearchParams()
  if (params.protocol) qs.set('protocol', params.protocol)
  if (params.start_port) qs.set('start_port', String(params.start_port))
  if (params.end_port) qs.set('end_port', String(params.end_port))
  if (params.search) qs.set('search', params.search)
  const query = qs.toString()
  return request<PortAnalysis>(`/api/ports${query ? `?${query}` : ''}`)
}

export function refreshPorts(): Promise<ApiResponse<PortAnalysis>> {
  return request<PortAnalysis>('/api/refresh', { method: 'POST' })
}

// ── 配置 ──────────────────────────────────────────────

export function fetchConfig(): Promise<ApiResponse<ConfigEntry>> {
  return request<ConfigEntry>('/api/config')
}

export function saveConfig(config: ConfigEntry): Promise<ApiResponse> {
  return request('/api/config', { method: 'POST', body: JSON.stringify(config) })
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

// ── 健康检查 ──────────────────────────────────────────

export function healthCheck(): Promise<{ status: string; version: string }> {
  return fetch('/api/health').then(r => r.json())
}
