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
 * 同一应用的多张卡片（不同端口）应得到相同 key。
 */
export function appKey(card: PortCard): string {
  // 1. 镜像仓库名（Docker 容器最可靠）
  const repo = imageRepoName(card.image)
  if (repo) return repo

  // 2. 用户自定义服务名（仅保留后端允许的字符：a-z 0-9 . _ : / -）
  if (card.service_name) {
    return card.service_name.trim().toLowerCase().replace(/[^a-z0-9._:/-]/g, '_')
  }

  // 3. 兜底：端口号
  if (card.port) return `port:${card.port}`

  // 理论上不会到这里（used 卡片必有 port）
  return `port:${card.port ?? 0}`
}
