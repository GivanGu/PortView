/**
 * 端口数据导出 — CSV / JSON
 * 数据来自前端已加载的 analysis，所见即所得（含当前过滤）。
 */

import type { PortCard } from '@/api'

export type ExportFormat = 'csv' | 'json'

interface UsedPort {
  port: number
  protocol: string
  source: string
  service_name: string
  process: string
  container: string
  image: string
  container_port: string
  is_running: boolean
}

/** 从卡片列表里抽取"已使用端口"并按端口号升序。 */
function extractUsedPorts(cards: PortCard[]): UsedPort[] {
  return cards
    .filter((c) => c.type === 'used' && c.port != null)
    .sort((a, b) => (a.port ?? 0) - (b.port ?? 0))
    .map((c) => ({
      port: c.port as number,
      protocol: c.protocol || '',
      source: c.source || '',
      service_name: c.service_name || '',
      process: c.process || '',
      container: c.container || '',
      image: c.image || '',
      container_port: c.container_port || '',
      is_running: c.is_running ?? false,
    }))
}

function toCsv(rows: UsedPort[]): string {
  const headers = ['端口', '协议', '来源', '服务名', '进程', '容器', '镜像', '容器端口', '运行状态']
  const escape = (v: string | number | boolean): string => {
    const s = String(v ?? '')
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [headers.join(',')]
  for (const r of rows) {
    lines.push(
      [
        r.port,
        r.protocol,
        r.source,
        r.service_name,
        r.process,
        r.container,
        r.image,
        r.container_port,
        r.is_running ? '是' : '否',
      ]
        .map(escape)
        .join(','),
    )
  }
  // BOM 让 Excel 正确识别 UTF-8 中文
  return '\uFEFF' + lines.join('\r\n')
}

function toJson(rows: UsedPort[]): string {
  return JSON.stringify(
    {
      exported_at: new Date().toISOString(),
      count: rows.length,
      ports: rows,
    },
    null,
    2,
  )
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function timestamp(): string {
  const d = new Date()
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}_${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`
}

function download(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 导出端口数据，返回导出的行数。
 */
export function exportPorts(cards: PortCard[], format: ExportFormat): number {
  const rows = extractUsedPorts(cards)
  if (format === 'csv') {
    download(`portview_${timestamp()}.csv`, toCsv(rows), 'text/csv;charset=utf-8')
  } else {
    download(`portview_${timestamp()}.json`, toJson(rows), 'application/json;charset=utf-8')
  }
  return rows.length
}
