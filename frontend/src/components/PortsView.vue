<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  fetchPorts,
  hidePort,
  editPort,
  fetchRanges,
  createRange,
  deleteRange,
  getAccessAddress,
  probeScheme,
  probeSchemes,
  fetchPortSchemes,
  setPortScheme,
  clearPortScheme,
  fetchLogos,
  uploadLogo,
  deleteLogo,
  discoverLogo,
  logoUrl,
  fetchDefaultLogos,
  defaultLogoUrl,
  type PortAnalysis,
  type PortCard,
  type RangeRead,
  type LogoMeta,
  type GridItem,
} from '@/api'
import { appKey, normalizeServiceName } from '@/logo'
import { exportPorts, type ExportFormat } from '@/utils/export'
import usePrefs, { hasPortFavorite, removePortFavorite, uid } from '@/store/prefs'
import { useSearch } from '@/store/search'
import AccessAddressPrompt from '@/components/AccessAddressPrompt.vue'
import PortCardContent from '@/components/PortCardContent.vue'
import { Plus, Trash2, SlidersHorizontal } from 'lucide-vue-next'

const { t } = useI18n()

// ── 状态 ──
const analysis = ref<PortAnalysis | null>(null)
const loading = ref(false)
// v1.6.6：搜索词改由顶栏全局搜索驱动（store 单例，切页自动清空）
const { query: searchQuery, activeTab: searchActiveTab } = useSearch()
const protocolFilter = ref('') // '' | 'TCP' | 'UDP'
const sourceFilter = ref('') // '' | 'local' | 'docker'（前端侧按 card.source 归类）
// v1.6.11：快速筛选（独立 toggle，与协议/来源 AND 叠加）
const unknownFilter = ref(false) // 仅显示「未知服务」端口，方便快速命名
const noLogoFilter = ref(false) // 仅显示未显示 Logo 的卡片，方便逐一上传
const editingPort = ref<number | null>(null)
const editServiceName = ref('')

// ── Logo 状态 (v1.5.0) ──
const logos = ref<Map<string, LogoMeta>>(new Map())
const logoBusy = ref<Set<string>>(new Set())
// v1.5.11：box 模式下 Logo 加载失败的 appKey 集合（用于回退到 🖼 占位符）
const logoError = ref<Set<string>>(new Set())
// v1.5.13：内置默认 Logo 匹配表（用户上传 Logo 缺失时回退）
// ports 优先（知名端口最可靠），names 兜底（按 service_name 归一化匹配）
const defaultLogoPorts = ref<Map<number, string>>(new Map())
const defaultLogoNames = ref<Set<string>>(new Set())

async function loadLogos() {
  try {
    const resp = await fetchLogos()
    if (resp.success) {
      const m = new Map<string, LogoMeta>()
      for (const meta of resp.data) m.set(meta.app_key, meta)
      logos.value = m
      logoError.value = new Set()
    }
  } catch (e) {
    console.error('加载 Logo 列表失败:', e)
  }
  // v1.5.13：内置默认 Logo 匹配表（独立请求，失败不影响用户上传 Logo）
  try {
    const d = await fetchDefaultLogos()
    if (d.success) {
      const pm = new Map<number, string>()
      for (const [p, k] of Object.entries(d.data.ports)) pm.set(Number(p), k)
      defaultLogoPorts.value = pm
      defaultLogoNames.value = new Set(d.data.names)
    }
  } catch (e) {
    console.error('加载默认 Logo 列表失败:', e)
  }
}

function logoStatus(card: PortCard): string | null {
  const key = appKey(card)
  return logos.value.get(key)?.status ?? null
}

/** 匹配内置默认 Logo 的 key：端口优先（知名端口最可靠），service_name 兜底；无匹配返回 null。 */
function defaultLogoKey(card: PortCard): string | null {
  if (card.port != null && defaultLogoPorts.value.has(card.port)) {
    return defaultLogoPorts.value.get(card.port)!
  }
  const name = card.service_name
  if (name) {
    const norm = normalizeServiceName(name)
    if (defaultLogoNames.value.has(norm)) return norm
  }
  return null
}

function logoSrc(card: PortCard): string | null {
  const key = appKey(card)
  const meta = logos.value.get(key)
  // 1. 用户上传 / discover 的 Logo 始终优先
  if (meta?.status === 'found') return logoUrl(key)
  // 2. 回退：内置默认 Logo（按 service_name 匹配）
  const dkey = defaultLogoKey(card)
  if (dkey) return defaultLogoUrl(dkey)
  return null
}

function isLogoBusy(card: PortCard): boolean {
  return logoBusy.value.has(appKey(card))
}

function hasLogoError(card: PortCard): boolean {
  return logoError.value.has(appKey(card))
}

function markLogoError(card: PortCard) {
  logoError.value = new Set(logoError.value).add(appKey(card))
}

async function handleDiscoverLogo(card: PortCard) {
  const key = appKey(card)
  if (!card.port) return
  logoBusy.value = new Set(logoBusy.value).add(key)
  try {
    const resp = await discoverLogo(key, card.port)
    if (resp.success) {
      await loadLogos()
      if (resp.data.status === 'not_found') {
        showToast(t('ports.logoDiscoverFailed', { service: card.service_name || card.port }))
      } else {
        showToast(t('ports.logoAdded'))
      }
    } else {
      showToast(resp.error || t('ports.logoDiscoverFailed', { service: card.service_name || card.port }))
    }
  } catch (e) {
    console.error('Logo 识别失败:', e)
  } finally {
    const s = new Set(logoBusy.value)
    s.delete(key)
    logoBusy.value = s
  }
}

async function handleUploadLogo(card: PortCard) {
  const key = appKey(card)
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/png,image/jpeg,image/svg+xml,image/gif,image/webp,image/x-icon,image/vnd.microsoft.icon'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    if (file.size > 1024 * 1024) {
      showToast(t('ports.logoTooLarge'))
      return
    }
    logoBusy.value = new Set(logoBusy.value).add(key)
    try {
      const reader = new FileReader()
      reader.onload = async () => {
        const base64 = (reader.result as string).split(',')[1]
        await uploadLogo(key, file.type, base64)
        await loadLogos()
        showToast(t('ports.logoAdded'))
      }
      reader.readAsDataURL(file)
    } catch (e) {
      console.error('Logo 上传失败:', e)
    } finally {
      const s = new Set(logoBusy.value)
      s.delete(key)
      logoBusy.value = s
    }
  }
  input.click()
}

async function handleDeleteLogo(card: PortCard) {
  const key = appKey(card)
  logoBusy.value = new Set(logoBusy.value).add(key)
  try {
    await deleteLogo(key)
    await loadLogos()
  } catch (e) {
    console.error('Logo 删除失败:', e)
  } finally {
    const s = new Set(logoBusy.value)
    s.delete(key)
    logoBusy.value = s
  }
}

// ── 卡片设置菜单（右上角 ⚙️ 下拉，Teleport 到 body 避免被卡片 overflow 裁剪）──
// 原 6 个按钮收敛为「🔗 打开服务（快速跳转）+ ⚙️ 设置（分层下拉）」两个。
const settingsMenuPort = ref<number | null>(null)
const settingsMenuPos = ref({ top: 0, right: 0 })

const settingsMenuCard = computed<PortCard | null>(() => {
  if (settingsMenuPort.value == null || !analysis.value) return null
  return (
    analysis.value.port_cards.find((c) => c.type === 'used' && c.port === settingsMenuPort.value) ?? null
  )
})

function toggleSettingsMenu(card: PortCard, event: MouseEvent) {
  if (settingsMenuPort.value === card.port) {
    settingsMenuPort.value = null
    return
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  // 菜单右边缘对齐按钮右边缘，向下展开；靠近视口底部时向上翻
  const estHeight = 260
  const top =
    rect.bottom + estHeight + 8 > window.innerHeight ? Math.max(8, rect.top - estHeight - 4) : rect.bottom + 4
  // 钳制 right，防止卡片靠近左缘时菜单溢出视口左边界（菜单宽约 180px）
  const menuWidth = 180
  const right = Math.max(8, Math.min(window.innerWidth - rect.right, window.innerWidth - 8 - menuWidth))
  settingsMenuPos.value = { top, right }
  settingsMenuPort.value = card.port ?? null
}

function closeSettingsMenu() {
  settingsMenuPort.value = null
}

// 执行菜单项动作后关闭菜单。
// 注意：必须在 close 之前把 card 捕获出来——close 后 settingsMenuCard
// computed 会失效返回 null，若动作函数内再引用它就会拿到 null 导致动作静默失败。
function runMenuAction(card: PortCard, fn: (card: PortCard) => void) {
  closeSettingsMenu()
  fn(card)
}

// ── 监控区间状态 ──
const ranges = ref<RangeRead[]>([])
const selectedRangeId = ref<number>(0) // 0 = 全部

async function reloadRanges(merge = false) {
  const resp = await fetchRanges()
  if (resp.success) {
    if (merge) ranges.value = [...resp.data]
    else ranges.value = resp.data
  }
}

async function handleDeleteRange(id: number) {
  await deleteRange(id)
  if (selectedRangeId.value === id) selectedRangeId.value = 0
  await reloadRanges()
}

// ── 监控区间：醒目入口 + 批量添加 ──
const quickAddDialog = ref(false)
const rangeInput = ref('')
const rangeName = ref('')
const addRangeBusy = ref(false)
const toast = ref('')
const toastVisible = ref(false)

function showToast(msg: string) {
  toast.value = msg
  toastVisible.value = true
  setTimeout(() => (toastVisible.value = false), 2200)
}

interface ParsedRange {
  name: string
  start: number
  end: number
}

function parseRangeInput(input: string): ParsedRange[] {
  const tokens = input
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  const result: ParsedRange[] = []
  for (const tok of tokens) {
    if (tok.includes('-')) {
      const [a, b] = tok.split('-').map((s) => parseInt(s.trim(), 10))
      if (Number.isNaN(a) || Number.isNaN(b)) throw new Error(t('ports.invalidRange', { tok }))
      if (a < 0 || b > 65535 || a > b) throw new Error(t('ports.invalidRange', { tok }))
      result.push({ name: `${a}-${b}`, start: a, end: b })
    } else {
      const p = parseInt(tok, 10)
      if (Number.isNaN(p) || p < 0 || p > 65535) throw new Error(t('ports.invalidPort', { tok }))
      result.push({ name: String(p), start: p, end: p })
    }
  }
  return result
}

async function handleQuickAdd() {
  const text = rangeInput.value.trim()
  if (!text) return
  let parsed: ParsedRange[]
  try {
    parsed = parseRangeInput(text)
  } catch (e) {
    showToast((e as Error).message)
    return
  }
  if (!parsed.length) return
  addRangeBusy.value = true
  try {
    const name = rangeName.value.trim()
    for (let i = 0; i < parsed.length; i++) {
      const r = parsed[i]
      // 用户填了名称：单个区间直接用；多个区间加序号后缀避免重名冲突
      const finalName = name
        ? (parsed.length === 1 ? name : `${name}-${i + 1}`)
        : r.name
      await createRange(finalName, r.start, r.end)
    }
    rangeInput.value = ''
    rangeName.value = ''
    quickAddDialog.value = false
    await reloadRanges(true)
    showToast(t('ports.addedRanges', { n: parsed.length }))
  } catch (e) {
    console.error('quick add range failed', e)
  } finally {
    addRangeBusy.value = false
  }
}

watch(selectedRangeId, () => { loadData() })

// ── 数据加载 ──
async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const resp = await fetchPorts({
      protocol: protocolFilter.value || undefined,
      search: searchQuery.value || undefined,
      start_port: 1,
      end_port: 65535,
      range_ids: selectedRangeId.value ? [selectedRangeId.value] : undefined,
    })
    if (resp.success) {
      analysis.value = resp.data
      void probeCardSchemes()
      void loadManualSchemes()
    }
  } catch (e) {
    console.error('加载端口数据失败:', e)
  } finally {
    if (!silent) loading.value = false
  }
}

// ── http/https 徽章：批量探测卡片端口协议 ──
// 后端 16 并发探测 + 60s 缓存，重复调用命中缓存，开销很小。
const schemeMap = ref<Record<number, 'http' | 'https' | 'unknown'>>({})
let probingSchemes = false

async function probeCardSchemes() {
  if (!analysis.value || probingSchemes) return
  const items = analysis.value.port_cards
    .filter((c): c is PortCard & { port: number } => c.type === 'used' && c.port != null)
    .map((c) => ({
      port: c.port,
      container_id: c.container_id || null,
      container_port: parseContainerPort(c.container_port),
    }))
  if (!items.length) return
  probingSchemes = true
  try {
    const resp = await probeSchemes(items)
    if (resp.success && resp.data?.schemes) {
      const m: Record<number, 'http' | 'https' | 'unknown'> = {}
      for (const [p, s] of Object.entries(resp.data.schemes)) m[Number(p)] = s
      schemeMap.value = m
    }
  } catch (e) {
    console.error('批量协议探测失败:', e)
  } finally {
    probingSchemes = false
  }
}

// ── 人工指定协议：优先级高于自动探测 ──
// manualSchemes[port] = 'http' | 'https'；无条目 = 跟随自动探测。
const manualSchemes = ref<Record<number, 'http' | 'https'>>({})
// 进行中的协议变更（乐观更新尚未被服务端确认）。
// 并发 loadManualSchemes 的旧响应可能不含该端口的最新值，
// 合并 pending 可避免旧响应覆盖未确认的乐观值（修复徽章偶发消失）。
let pendingSchemes: Record<number, 'http' | 'https' | null> = {}
// loadManualSchemes 序号：仅应用最新一次响应，丢弃乱序到达的旧响应。
let schemesLoadSeq = 0

async function loadManualSchemes() {
  const seq = ++schemesLoadSeq
  try {
    const resp = await fetchPortSchemes()
    // 已有更新的加载发起，丢弃本次（乱序旧响应）
    if (seq !== schemesLoadSeq) return
    if (resp.success) {
      const m: Record<number, 'http' | 'https'> = {}
      for (const [p, s] of Object.entries(resp.data || {})) m[Number(p)] = s
      // 合并进行中的乐观更新，避免旧响应覆盖未确认值
      for (const [p, s] of Object.entries(pendingSchemes)) {
        if (s == null) delete m[Number(p)]
        else m[Number(p)] = s
      }
      manualSchemes.value = m
    }
  } catch (e) {
    console.error('加载人工协议失败:', e)
  }
}

// 卡片最终展示的协议：人工指定 > 自动探测
function effectiveScheme(card: PortCard): 'http' | 'https' | 'unknown' | undefined {
  if (card.port == null) return undefined
  const manual = manualSchemes.value[card.port]
  if (manual) return manual
  return schemeMap.value[card.port]
}

function isManualScheme(card: PortCard): boolean {
  return card.port != null && manualSchemes.value[card.port] != null
}

// 点击徽章循环切换：自动 → http → https → 自动（清除人工指定）
async function handleSchemeToggle(card: PortCard) {
  if (card.port == null) return
  const port = card.port
  const current = manualSchemes.value[port]
  let next: 'http' | 'https' | null
  if (current === undefined) next = 'http'
  else if (current === 'http') next = 'https'
  else next = null
  // 乐观更新，失败回滚
  const prev = { ...manualSchemes.value }
  // 标记为进行中：并发 loadManualSchemes 的旧响应合并时会保留该乐观值
  pendingSchemes[port] = next
  if (next) manualSchemes.value = { ...manualSchemes.value, [port]: next }
  else {
    const m = { ...manualSchemes.value }
    delete m[port]
    manualSchemes.value = m
  }
  try {
    if (next) await setPortScheme(port, next)
    else await clearPortScheme(port)
    // 服务端已确认：重新拉取对齐状态，并使在途旧响应因序号过期而失效
    await loadManualSchemes()
  } catch (e) {
    console.error('保存人工协议失败:', e)
    manualSchemes.value = prev
  } finally {
    delete pendingSchemes[port]
  }
}

function handleExport(format: ExportFormat) {
  if (!analysis.value) return
  exportPorts(analysis.value.port_cards, format)
}

// ── 搜索防抖（v1.6.6：词来自顶栏全局搜索，仅本页激活时生效）──
let searchTimer: ReturnType<typeof setTimeout>
watch(searchQuery, () => {
  if (searchActiveTab.value !== 'ports') return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadData, 300)
})

watch(protocolFilter, () => {
  loadData()
})

// ── 前端侧卡片过滤（源类型 / 未知服务 / 无 Logo）──────────────
// 后端已把卡片分好：`source === 'docker'` 是 Docker 端；
// `source ∈ {'host','system'}` 是主机/本地端。
// 这里纯前端侧 v-show 即可，无需往返 API。
// 各条件 AND 叠加；模板仅对 used 卡片调用本函数。
function cardVisible(card: PortCard): boolean {
  if (card.type !== 'used') return false
  // 源类型筛选（本地 / Docker）
  if (sourceFilter.value) {
    const s = (card.source || '').toLowerCase()
    if (sourceFilter.value === 'docker' && s !== 'docker') return false
    if (sourceFilter.value === 'local' && s !== 'host' && s !== 'system') return false
  }
  // 未知服务筛选：service_name 为空或字面量「未知服务」（后端固定值）
  if (unknownFilter.value) {
    const name = card.service_name
    if (name && name !== '未知服务') return false
  }
  // 无 Logo 筛选：卡片实际未显示 Logo（无用户上传、无内置默认）
  if (noLogoFilter.value && logoSrc(card) != null) return false
  return true
}

// ── 端口操作 ──
async function handleHide(card: PortCard) {
  if (card.port) {
    await hidePort(card.port)
  }
  // 全局刷新：收藏页/总览页立即同步（本视图由 refreshTick watcher 重载）
  triggerRefresh()
}



async function handleEditSave() {
  if (editingPort.value === null || !editServiceName.value) return
  await editPort(editingPort.value, editServiceName.value)
  editingPort.value = null
  editServiceName.value = ''
  // 服务名变更 → 全局刷新，收藏页立即同步（本视图由 refreshTick watcher 重载）
  triggerRefresh()
}

function startEdit(card: PortCard) {
  if (card.port) {
    editingPort.value = card.port
    editServiceName.value = card.service_name || ''
  }
}

// ── 打开服务 ──
const showAddrPrompt = ref(false)

function navigateToSettings() {
  document.dispatchEvent(new CustomEvent('portview:navigate', {
    detail: { tab: 'settings', anchor: 'settings-access-address' },
  }))
}

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

// 从 container_port（如 "443/tcp"、"3001"、"host模式"）提取端口号
function parseContainerPort(cp?: string): number | null {
  if (!cp) return null
  const m = cp.match(/(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

// 决定服务链接协议：人工指定 > 实时批量探测 > 单端口探测 > 端口号推断 > 默认
async function decideScheme(card: PortCard, defaultScheme: string): Promise<string> {
  const manual = card.port != null ? manualSchemes.value[card.port] : undefined
  if (manual === 'http' || manual === 'https') return manual
  const probed = card.port != null ? schemeMap.value[card.port] : undefined
  if (probed === 'http' || probed === 'https') return probed
  if (card.port) {
    try {
      const resp = await probeScheme(card.port, card.container_id, parseContainerPort(card.container_port))
      const s = resp.data?.scheme
      if (resp.success && (s === 'http' || s === 'https')) return s
    } catch {
      /* 探测失败回退默认 */
    }
  }
  // 端口号推断兜底（批量/单端口探测都不可用时）
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

// ── 初始化 ──
let pollTimer: ReturnType<typeof setInterval> | null = null

// v1.4.4：自动刷新 + 手动刷新统一走共享 prefs store
// v1.5.11：Logo 展示模式（background / box）驱动卡片条件渲染
const { refreshInterval, refreshTick, logoDisplayMode, favorites, saveFavorites, triggerRefresh } = usePrefs()

// ── 收藏（v1.5.6 / v1.6.5 网格模型）：按端口号收藏，存 user_prefs.favorites ──
function isFavorite(card: PortCard): boolean {
  return card.port != null && hasPortFavorite(favorites.value, card.port)
}

async function toggleFavorite(card: PortCard) {
  if (card.port == null) return
  const port = card.port
  const has = hasPortFavorite(favorites.value, port)
  const next: GridItem[] = has
    ? removePortFavorite(favorites.value, port)[0]
    : [...favorites.value, { id: uid('port'), kind: 'port', port }]
  // v1.6.4：串行写入 + 失败回滚（原先并发 PATCH 可能乱序到达互相覆盖）
  const ok = await saveFavorites(next)
  showToast(t(ok ? (has ? 'ports.removedFavorite' : 'ports.addedFavorite') : 'common.saveFailed'))
}

function applyPollTimer() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (refreshInterval.value > 0) {
    pollTimer = setInterval(() => {
      if (!document.hidden && !loading.value) loadData(true)
    }, refreshInterval.value * 1000)
  }
}

watch(refreshInterval, () => applyPollTimer())
watch(refreshTick, () => {
  if (!loading.value) loadData(true)
})

// 滚动 / 缩放 / Esc 时关闭设置菜单（菜单 fixed 定位，视口变化会错位）
function onScrollCloseMenu() {
  if (settingsMenuPort.value != null) closeSettingsMenu()
}

function onKeydownCloseMenu(e: KeyboardEvent) {
  if (e.key === 'Escape' && settingsMenuPort.value != null) closeSettingsMenu()
}

function onResizeCloseMenu() {
  if (settingsMenuPort.value != null) closeSettingsMenu()
}

onMounted(() => {
  loadData()
  void reloadRanges()
  void loadLogos()
  applyPollTimer()
  window.addEventListener('scroll', onScrollCloseMenu, true)
  window.addEventListener('keydown', onKeydownCloseMenu)
  window.addEventListener('resize', onResizeCloseMenu)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  window.removeEventListener('scroll', onScrollCloseMenu, true)
  window.removeEventListener('keydown', onKeydownCloseMenu)
  window.removeEventListener('resize', onResizeCloseMenu)
})
</script>

<template>
  <div>
    <!-- 头部 -->
    <div class="main-header">
      <h1>{{ t('ports.title') }}</h1>
      <div class="header-actions">
        <button class="btn btn-primary range-entry" @click="quickAddDialog = true">
          <SlidersHorizontal :size="15" />
          {{ t('ports.monitorRange') }}
        </button>
        <button
          class="btn btn-danger range-delete"
          :title="t('ports.deleteRangeTitle')"
          :disabled="selectedRangeId === 0"
          @click="handleDeleteRange(selectedRangeId)"
        >
          <Trash2 :size="15" />
          {{ t('ports.deleteRange') }}
        </button>
        <div class="export-group">
          <button class="btn" :disabled="!analysis || loading" @click="handleExport('csv')">
            ⬇ CSV
          </button>
          <button class="btn" :disabled="!analysis || loading" @click="handleExport('json')">
            ⬇ JSON
          </button>
        </div>
      </div>
    </div>

    <div class="main-body">
      <!-- 工具栏（搜索已上移顶栏全局搜索） -->
      <div class="toolbar">
        <div class="filter-group">
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === '' }"
            @click="protocolFilter = ''"
          >
            {{ t('ports.filterAll') }}
          </button>
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === 'TCP' }"
            @click="protocolFilter = 'TCP'"
          >
            TCP
          </button>
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === 'UDP' }"
            @click="protocolFilter = 'UDP'"
          >
            UDP
          </button>
          <span class="filter-divider" aria-hidden="true"></span>
          <button
            class="filter-btn"
            :class="{ active: sourceFilter === '' }"
            @click="sourceFilter = ''"
            :title="t('ports.filterAll')"
          >
            {{ t('ports.filterPorts') }}
          </button>
          <button
            class="filter-btn"
            :class="{ active: sourceFilter === 'local' }"
            @click="sourceFilter = 'local'"
            :title="t('common.sourceHost')"
          >
            {{ t('ports.filterLocal') }}
          </button>
          <button
            class="filter-btn"
            :class="{ active: sourceFilter === 'docker' }"
            @click="sourceFilter = 'docker'"
            :title="t('common.sourceDocker')"
          >
            {{ t('ports.filterDocker') }}
          </button>
          <span class="filter-divider" aria-hidden="true"></span>
          <button
            class="filter-btn"
            :class="{ active: unknownFilter }"
            @click="unknownFilter = !unknownFilter"
            :title="t('ports.filterUnknownTip')"
          >
            {{ t('ports.filterUnknown') }}
          </button>
          <button
            class="filter-btn"
            :class="{ active: noLogoFilter }"
            @click="noLogoFilter = !noLogoFilter"
            :title="t('ports.filterNoLogoTip')"
          >
            {{ t('ports.filterNoLogo') }}
          </button>
        </div>

        <!-- v1.2：监控区间选择器 -->
        <div class="range-selector">
          <span class="range-label">{{ t('ports.rangeLabel') }}</span>
          <select
            v-model="selectedRangeId"
            class="range-select"
          >
            <option :value="0">{{ t('ports.rangeAll') }}</option>
            <option v-for="r in ranges" :key="r.id" :value="r.id">
              {{ r.name }} ({{ r.start_port }}–{{ r.end_port }})
            </option>
          </select>
        </div>
      </div>

      <!-- 统计栏 -->
      <div v-if="analysis" class="stats-bar">
        <div class="stat-card">
          <div class="stat-label">{{ t('ports.statUsed') }}</div>
          <div class="stat-value green">{{ analysis.total_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('ports.statAvailable') }}</div>
          <div class="stat-value blue">{{ analysis.total_available }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('ports.statTcp') }}</div>
          <div class="stat-value yellow">{{ analysis.tcp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('ports.statUdp') }}</div>
          <div class="stat-value purple">{{ analysis.udp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('ports.statDocker') }}</div>
          <div class="stat-value">{{ analysis.docker_containers }}</div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        {{ t('ports.loading') }}
      </div>

      <!-- 端口卡片网格 -->
      <!-- v1.4.4：单一 v-for 按后端返回顺序渲染（已用/间隙/未知交错），
           间隙卡片不再被甩到末尾，而是按端口号插到对应位置。 -->
      <div v-else-if="analysis && analysis.port_cards.length > 0" class="port-grid">
        <template v-for="(card, idx) in analysis.port_cards" :key="idx">
          <!-- 已用端口 -->
          <div v-if="card.type === 'used'" v-show="cardVisible(card)">
            <div class="port-card" :class="{ offline: card.is_running === false, editing: editingPort === card.port }">
              <!-- v1.5.11：Logo 展示模式（background / box），内容统一走 PortCardContent -->
              <template v-if="logoDisplayMode === 'background'">
                <!-- background：Logo 铺满整卡作为背景层（contain 填充，随卡片尺寸自动缩放） -->
                <img
                  v-if="logoSrc(card)"
                  :src="logoSrc(card)!"
                  class="port-card-bg"
                  alt=""
                  @error="($event.target as HTMLImageElement).style.display = 'none'"
                />
                <div v-if="logoSrc(card)" class="port-card-scrim"></div>

                <div class="port-card-content">
                  <PortCardContent
                    :card="card"
                    :scheme="effectiveScheme(card)"
                    :manual="isManualScheme(card)"
                    @scheme-toggle="handleSchemeToggle(card)"
                    @favorite-toggle="toggleFavorite(card)"
                  />
                </div>
              </template>
              <div v-else class="port-card-body">
                <!-- box：上段 64px Logo 框 + 头部信息列，下段 detail/镜像行整宽（与 Logo 左对齐） -->
                <div class="port-card-top">
                  <div class="port-logo">
                    <img
                      v-if="logoSrc(card)"
                      :src="logoSrc(card)!"
                      class="port-logo-img"
                      :style="{ display: hasLogoError(card) ? 'none' : '' }"
                      :alt="card.service_name || 'logo'"
                      @error="markLogoError(card)"
                    />
                    <span v-if="!logoSrc(card) || hasLogoError(card)" class="port-logo-placeholder">🖼</span>
                  </div>
                  <div class="port-info">
                    <PortCardContent
                      :card="card"
                      :scheme="effectiveScheme(card)"
                      :manual="isManualScheme(card)"
                      section="top"
                      @scheme-toggle="handleSchemeToggle(card)"
                      @favorite-toggle="toggleFavorite(card)"
                    />
                  </div>
                </div>
                <PortCardContent
                  :card="card"
                  :scheme="effectiveScheme(card)"
                  :manual="isManualScheme(card)"
                  section="bottom"
                  @scheme-toggle="handleSchemeToggle(card)"
                  @favorite-toggle="toggleFavorite(card)"
                />
              </div>

              <div class="port-actions">
              <!-- 快速跳转：打开服务 -->
              <button
                class="port-action-btn"
                :title="t('ports.openService')"
                @click="handleOpenService(card)"
              >🔗</button>
              <!-- 通用设置：分层下拉（服务 / Logo / 其他） -->
              <button
                class="port-action-btn"
                :class="{ active: settingsMenuPort === card.port }"
                :title="t('ports.cardSettings')"
                @click="toggleSettingsMenu(card, $event)"
              >⚙️</button>
            </div>

            <!-- 编辑模式 -->
            <div v-if="editingPort === card.port" style="margin-top: 10px; display: flex; gap: 6px;">
              <input
                class="form-input"
                v-model="editServiceName"
                @keyup.enter="handleEditSave"
                :placeholder="t('ports.editPlaceholder')"
                style="flex: 1; padding: 4px 8px; font-size: 12px;"
              />
              <button class="btn btn-sm btn-primary" @click="handleEditSave">{{ t('common.save') }}</button>
              <button class="btn btn-sm" @click="editingPort = null">{{ t('common.cancel') }}</button>
            </div>
          </div>
        </div>

          <!-- 可用端口间隙：仅在无源类型/未知服务/无Logo 过滤时显示 -->
          <div v-else-if="card.type === 'gap'" v-show="sourceFilter === '' && !unknownFilter && !noLogoFilter">
            <div class="gap-card">
              <div class="gap-range">{{ card.start_port }} — {{ card.end_port }}</div>
              <div class="gap-count">{{ t('ports.gapCount', { n: card.available_count }) }}</div>
            </div>
          </div>


        </template>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-icon">📡</div>
        <div class="empty-text">{{ t('ports.empty') }}</div>
      </div>
    </div>

    <!-- v1.4.3：监控区间批量添加对话框 -->
    <Teleport to="body">
      <div v-if="quickAddDialog" class="range-overlay" @click.self="quickAddDialog = false">
        <div class="range-dialog">
          <h3>{{ t('ports.dialogTitle') }}</h3>
          <p class="range-hint">{{ t('ports.dialogHint') }}</p>
          <input
            class="form-input"
            v-model="rangeName"
            :placeholder="t('ports.dialogNamePlaceholder')"
          />
          <textarea
            class="form-input range-textarea"
            v-model="rangeInput"
            rows="4"
            :placeholder="t('ports.dialogInputPlaceholder')"
          ></textarea>
          <div class="range-dialog-actions">
            <button class="btn btn-sm" @click="quickAddDialog = false">{{ t('common.cancel') }}</button>
            <button
              class="btn btn-sm btn-primary"
              :disabled="addRangeBusy || !rangeInput.trim()"
              @click="handleQuickAdd"
            >
              <Plus :size="13" /> {{ t('common.add') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 轻提示 -->
    <Teleport to="body">
      <div v-if="toastVisible" class="save-toast">{{ toast }}</div>
    </Teleport>

    <!-- 卡片设置菜单（⚙️ 下拉，按功能分层：服务 / Logo / 其他） -->
    <Teleport to="body">
      <template v-if="settingsMenuCard">
        <div class="settings-menu-overlay" @click="closeSettingsMenu"></div>
        <div
          class="settings-menu"
          :style="{ top: settingsMenuPos.top + 'px', right: settingsMenuPos.right + 'px' }"
        >
          <div class="settings-menu-group">
            <div class="settings-menu-label">{{ t('ports.menuService') }}</div>
            <button
              class="settings-menu-item"
              @click="runMenuAction(settingsMenuCard!, (c) => startEdit(c))"
            >
              <span class="settings-menu-ico">✏️</span>
              <span>{{ t('ports.editService') }}</span>
            </button>
          </div>

          <div class="settings-menu-group">
            <div class="settings-menu-label">{{ t('ports.menuLogo') }}</div>
            <!-- 识别按钮常显：已有 Logo 时作为「重新识别」，避免按钮凭空消失 -->
            <button
              class="settings-menu-item"
              :disabled="isLogoBusy(settingsMenuCard)"
              @click="runMenuAction(settingsMenuCard!, (c) => handleDiscoverLogo(c))"
            >
              <span class="settings-menu-ico">🔍</span>
              <span>{{ t('ports.logoDiscover') }}</span>
            </button>
            <button
              class="settings-menu-item"
              :disabled="isLogoBusy(settingsMenuCard)"
              @click="runMenuAction(settingsMenuCard!, (c) => handleUploadLogo(c))"
            >
              <span class="settings-menu-ico">🖼</span>
              <span>{{ t('ports.logoUpload') }}</span>
            </button>
            <button
              v-if="logoStatus(settingsMenuCard) === 'found'"
              class="settings-menu-item danger"
              :disabled="isLogoBusy(settingsMenuCard)"
              @click="runMenuAction(settingsMenuCard!, (c) => handleDeleteLogo(c))"
            >
              <span class="settings-menu-ico">🗑</span>
              <span>{{ t('ports.logoDelete') }}</span>
            </button>
          </div>

          <div class="settings-menu-group">
            <div class="settings-menu-label">{{ t('ports.menuOther') }}</div>
            <button
              class="settings-menu-item"
              @click="runMenuAction(settingsMenuCard!, (c) => toggleFavorite(c))"
            >
              <span class="settings-menu-ico">{{ isFavorite(settingsMenuCard) ? '★' : '☆' }}</span>
              <span>
                {{ isFavorite(settingsMenuCard) ? t('ports.removeFavorite') : t('ports.addFavorite') }}
              </span>
            </button>
            <button
              class="settings-menu-item danger"
              @click="runMenuAction(settingsMenuCard!, (c) => handleHide(c))"
            >
              <span class="settings-menu-ico">🙈</span>
              <span>{{ t('ports.hidePort') }}</span>
            </button>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 未配置访问地址提示 -->
    <AccessAddressPrompt
      v-if="showAddrPrompt"
      @configure="onAddrConfigure"
      @dismissed="onAddrDismissed"
    />
  </div>
</template>
