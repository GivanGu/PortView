/**
 * 应用 Logo 关联键派生（v1.5.0）
 *
 * 优先级：镜像仓库名 > service_name > port:{端口}
 * 后端视为不透明字符串，前端负责归一化。
 */

import type { PortCard } from '@/api'

/** 从 Docker 镜像名提取仓库短名（去掉 registry/tag/digest）。 */
function imageRepoName(image?: string): string | null {
  if (!image) return null
  // 去掉 digest
  const name = image.split('@')[0]
  // 取最后一段路径（可能是 repo:tag）
  const parts = name.split('/')
  const last = parts[parts.length - 1]
  // 去掉 tag
  const repo = last.split(':')[0]
  // 过滤空 / 纯数字（如 localhost:5000/12345）
  if (!repo || /^\d+$/.test(repo)) return null
  return repo.toLowerCase()
}

/**
 * 为一张端口卡片派生稳定的 app_key。
 *
 * 关键：key 必须是「同一应用」的稳定标识，绝不能是展示用的 service_name
 * （后端对无法识别的主机端口统一填「未知服务」，用它做 key 会让所有未知端口
 * 塌缩成同一个 key，导致一张卡片的 Logo 泄漏到其它卡片）。
 *
 * 优先级：镜像仓库名（Docker 同一应用最可靠）> 端口号（保证每张卡片独立）。
 */
export function appKey(card: PortCard): string {
  // 1. 镜像仓库名（Docker 容器最可靠的「同一应用」标识）
  const repo = imageRepoName(card.image)
  if (repo) return repo

  // 2. 兜底：端口号（保证每张卡片独立，不互相串 Logo）
  if (card.port) return `port:${card.port}`

  // 理论上不会到这里（used 卡片必有 port）
  return `port:${card.port ?? 0}`
}

/**
 * 归一化 service_name（v1.5.13，与后端 default_logos.normalize 一致）：
 * 小写 + 去除所有非字母数字字符。例："SQL Server" → "sqlserver"。
 */
export function normalizeServiceName(name: string): string {
  return (name || '').toLowerCase().replace(/[^a-z0-9]/g, '')
}
