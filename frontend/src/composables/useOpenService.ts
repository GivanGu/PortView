import { ref } from 'vue'
import { getAccessAddress, probeScheme, fetchPortSchemes, type PortCard } from '@/api'

// 解析访问地址为 { scheme, host }。裸 IP/域名自动按 http 处理（与后端一致）。
function parseAccessAddress(address: string): { scheme: string; host: string } | null {
  let normalized = address.trim()
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(normalized)) {
    normalized = `http://${normalized}`
  }
  try {
    const u = new URL(normalized)
    if (!u.hostname) return null
    return { scheme: u.protocol.replace(/:$/, ''), host: u.hostname }
  } catch {
    return null
  }
}

// 从 container_port（如 "443/tcp"、"3001"）提取端口号
function parseContainerPort(cp?: string): number | null {
  if (!cp) return null
  const m = cp.match(/(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

// 打开服务（与端口页【打开服务】同效）：
// 无访问地址 → 弹提示；有地址 → 人工指定协议 > 单端口探测 > 端口号推断 > 地址默认协议
export function useOpenService() {
  const showAddrPrompt = ref(false)
  // 人工指定协议（与端口页徽章共享同一份数据）
  const manualSchemes = ref<Record<number, 'http' | 'https'>>({})

  async function loadManualSchemes() {
    try {
      const resp = await fetchPortSchemes()
      if (resp.success) {
        const m: Record<number, 'http' | 'https'> = {}
        for (const [p, s] of Object.entries(resp.data || {})) m[Number(p)] = s
        manualSchemes.value = m
      }
    } catch (e) {
      console.error('加载人工协议失败:', e)
    }
  }

  function navigateToSettings() {
    document.dispatchEvent(new CustomEvent('portview:navigate', {
      detail: { tab: 'settings', anchor: 'settings-access-address' },
    }))
  }

  async function decideScheme(card: PortCard, defaultScheme: string): Promise<string> {
    const manual = card.port != null ? manualSchemes.value[card.port] : undefined
    if (manual === 'http' || manual === 'https') return manual
    if (card.port) {
      try {
        const resp = await probeScheme(card.port, card.container_id, parseContainerPort(card.container_port))
        const s = resp.data?.scheme
        if (resp.success && (s === 'http' || s === 'https')) return s
      } catch {
        /* 探测失败回退默认 */
      }
    }
    // 端口号推断兜底
    const cport = parseContainerPort(card.container_port)
    const hport = card.port ?? null
    if (cport === 443 || hport === 443) return 'https'
    if (cport === 80 || hport === 80) return 'http'
    return defaultScheme
  }

  async function handleOpenService(card: PortCard) {
    if (!card.port) return
    try {
      const resp = await getAccessAddress()
      if (resp.success && resp.data?.address) {
        const parsed = parseAccessAddress(resp.data.address)
        if (!parsed) {
          showAddrPrompt.value = true
          return
        }
        const scheme = await decideScheme(card, parsed.scheme)
        window.open(`${scheme}://${parsed.host}:${card.port}`, '_blank')
      } else {
        showAddrPrompt.value = true
      }
    } catch {
      showAddrPrompt.value = true
    }
  }

  function onAddrConfigure() {
    showAddrPrompt.value = false
    navigateToSettings()
  }

  function onAddrDismissed() {
    showAddrPrompt.value = false
  }

  return { showAddrPrompt, loadManualSchemes, handleOpenService, onAddrConfigure, onAddrDismissed }
}
