<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  fetchPorts,
  hidePort,
  batchHidePorts,
  editPort,
  fetchRanges,
  createRange,
  deleteRange,
  getAccessAddress,
  fetchLogos,
  uploadLogo,
  deleteLogo,
  discoverLogo,
  logoUrl,
  type PortAnalysis,
  type PortCard,
  type RangeRead,
  type LogoMeta,
} from '@/api'
import { appKey } from '@/logo'
import { exportPorts, type ExportFormat } from '@/utils/export'
import usePrefs from '@/store/prefs'
import AccessAddressPrompt from '@/components/AccessAddressPrompt.vue'
import { Search, Container, Cog, Server, Plus, Trash2, StickyNote, SlidersHorizontal } from 'lucide-vue-next'

const { t } = useI18n()

// ── 状态 ──
const analysis = ref<PortAnalysis | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const protocolFilter = ref('') // '' | 'TCP' | 'UDP'
const sourceFilter = ref('') // '' | 'local' | 'docker'（前端侧按 card.source 归类）
const editingPort = ref<number | null>(null)
const editServiceName = ref('')

// ── Logo 状态 (v1.5.0) ──
const logos = ref<Map<string, LogoMeta>>(new Map())
const logoBusy = ref<Set<string>>(new Set())

async function loadLogos() {
  try {
    const resp = await fetchLogos()
    if (resp.success) {
      const m = new Map<string, LogoMeta>()
      for (const meta of resp.data) m.set(meta.app_key, meta)
      logos.value = m
    }
  } catch (e) {
    console.error('加载 Logo 列表失败:', e)
  }
}

function logoStatus(card: PortCard): string | null {
  const key = appKey(card)
  return logos.value.get(key)?.status ?? null
}

function logoSrc(card: PortCard): string | null {
  const key = appKey(card)
  const meta = logos.value.get(key)
  if (meta?.status === 'found') return logoUrl(key)
  return null
}

function isLogoBusy(card: PortCard): boolean {
  return logoBusy.value.has(appKey(card))
}

async function handleDiscoverLogo(card: PortCard) {
  const key = appKey(card)
  if (!card.port) return
  logoBusy.value = new Set(logoBusy.value).add(key)
  try {
    const resp = await discoverLogo(key, card.port)
    if (resp.success) {
      await loadLogos()
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
    }
  } catch (e) {
    console.error('加载端口数据失败:', e)
  } finally {
    if (!silent) loading.value = false
  }
}

function handleExport(format: ExportFormat) {
  if (!analysis.value) return
  exportPorts(analysis.value.port_cards, format)
}

// ── 搜索防抖 ──
let searchTimer: ReturnType<typeof setTimeout>
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadData, 300)
})

watch(protocolFilter, () => {
  loadData()
})

// ── 源类型过滤（本地 / Docker）──────────────
// 后端已把卡片分好：`source === 'docker'` 是 Docker 端；
// `source ∈ {'host','system'}` 是主机/本地端。
// 这里纯前端侧 v-show 即可，无需往返 API。
function cardVisible(card: PortCard): boolean {
  if (!sourceFilter.value) return true
  // gap / unknown_range 卡片没有 source —— 归类筛选时一并隐藏，
  // 让视图聚焦「本地/Docker 端」这一组。
  if (card.type !== 'used') return false
  const s = (card.source || '').toLowerCase()
  if (sourceFilter.value === 'docker') return s === 'docker'
  if (sourceFilter.value === 'local') return s === 'host' || s === 'system'
  return true
}

// ── 端口操作 ──
async function handleHide(card: PortCard) {
  if (card.type === 'unknown_range') {
    // 隐藏整个范围：把区间内所有端口都记入 hidden_ports
    if (card.start_port && card.end_port) {
      const ports: number[] = []
      for (let p = card.start_port; p <= card.end_port; p++) ports.push(p)
      await batchHidePorts(ports)
    }
  } else if (card.port) {
    await hidePort(card.port)
  }
  await loadData()
}



async function handleEditSave() {
  if (editingPort.value === null || !editServiceName.value) return
  await editPort(editingPort.value, editServiceName.value)
  editingPort.value = null
  editServiceName.value = ''
  await loadData()
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
  window.dispatchEvent(new CustomEvent('portview:navigate', { detail: { tab: 'settings' } }))
}

async function handleOpenService(card: PortCard) {
  if (!card.port) return
  try {
    const resp = await getAccessAddress()
    if (resp.success && resp.data?.address) {
      const base = resp.data.address.replace(/\/+$/, '')
      window.open(`${base}:${card.port}`, '_blank')
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
const { refreshInterval, refreshTick } = usePrefs()

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

onMounted(() => {
  loadData()
  void reloadRanges()
  void loadLogos()
  applyPollTimer()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
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
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="search-box">
          <span class="search-icon"><Search :size="15" /></span>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('ports.searchPlaceholder')"
          />
        </div>

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
            <div class="port-card" :class="{ offline: card.is_running === false }">
              <div class="port-actions">
              <button
                class="port-action-btn"
                :title="t('ports.openService')"
                @click="handleOpenService(card)"
              >🔗</button>
              <button
                class="port-action-btn"
                :title="t('ports.editService')"
                @click="startEdit(card)"
              >✏️</button>
              <button
                v-if="logoStatus(card) !== 'found'"
                class="port-action-btn"
                :title="t('ports.logoDiscover')"
                :disabled="isLogoBusy(card)"
                @click="handleDiscoverLogo(card)"
              >🔍</button>
              <button
                class="port-action-btn"
                :title="t('ports.logoUpload')"
                :disabled="isLogoBusy(card)"
                @click="handleUploadLogo(card)"
              >🖼</button>
              <button
                v-if="logoStatus(card) === 'found'"
                class="port-action-btn danger"
                :title="t('ports.logoDelete')"
                :disabled="isLogoBusy(card)"
                @click="handleDeleteLogo(card)"
              >🗑</button>
              <button
                class="port-action-btn danger"
                :title="t('ports.hidePort')"
                @click="handleHide(card)"
              >🙈</button>
            </div>

            <div class="port-card-header">
              <span class="port-header-left">
                <span
                  class="port-status-dot"
                  :class="card.is_running === false ? 'is-offline' : 'is-online'"
                  :title="card.is_running === false ? t('common.offline') : t('common.online')"
                  :aria-label="card.is_running === false ? t('common.offline') : t('common.online')"
                  role="img"
                ></span>
                <span class="port-number">{{ card.port }}</span>
              </span>
              <span
                class="port-protocol"
                :class="(card.protocol || '').toLowerCase()"
              >{{ card.protocol }}</span>
            </div>

            <div class="port-service">
              <img
                v-if="logoSrc(card)"
                :src="logoSrc(card)!"
                class="service-logo"
                :alt="card.service_name || 'logo'"
                @error="($event.target as HTMLImageElement).style.display = 'none'"
              />
              <span v-else class="service-logo-placeholder">🖼</span>
              {{ card.service_name || t('ports.unknownService') }}
            </div>

            <!-- v1.2：用户备注 -->
            <div v-if="card.remark" class="port-remark" :title="card.remark">
              <StickyNote :size="11" class="port-remark-icon" />
              <span class="port-remark-text">{{ card.remark }}</span>
            </div>

            <div class="port-detail">
              <span
                class="port-source"
                :class="card.source"
              >
                <Container v-if="card.source === 'docker'" :size="13" class="port-source-icon" />
                <Cog v-else-if="card.source === 'system'" :size="13" class="port-source-icon" />
                <Server v-else :size="13" class="port-source-icon" />
                <span>{{ card.source === 'docker' ? t('common.sourceDocker') : card.source === 'system' ? t('common.sourceSystem') : t('common.sourceHost') }}</span>
              </span>

              <!-- 容器名（在线/离线状态由左上角圆点 + 背景深浅统一表达，
                   底行不再重复「在线/离线」文字，避免两处信号打架）。 -->
              <span
                v-if="card.container"
                class="port-status"
                :title="card.container"
              >
                <span class="port-status-container">{{ card.container }}</span>
              </span>
            </div>

            <!-- 镜像信息独立成一行，不再挤进 port-detail，避免卡片高度不齐 -->
            <div v-if="card.image" class="port-image">
              <span class="port-image-label">{{ t('ports.image') }}</span>
              <span class="port-image-value">{{ card.image }}</span>
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

          <!-- 可用端口间隙：仅在无源类型过滤时显示 -->
          <div v-else-if="card.type === 'gap'" v-show="sourceFilter === ''">
            <div class="gap-card">
              <div class="gap-range">{{ card.start_port }} — {{ card.end_port }}</div>
              <div class="gap-count">{{ t('ports.gapCount', { n: card.available_count }) }}</div>
            </div>
          </div>

          <!-- 未知范围：仅在无源类型过滤时显示 -->
          <div v-else-if="card.type === 'unknown_range'" v-show="sourceFilter === ''">
            <div class="unknown-card">
              <div class="port-actions" style="position: static; margin-bottom: 8px; justify-content: flex-end;">
                <button
                  class="port-action-btn danger"
                  :title="t('ports.hideRange')"
                  @click="handleHide(card)"
                >🙈</button>
              </div>
              <div class="unknown-range">{{ card.start_port }} — {{ card.end_port }}</div>
              <div class="unknown-count">{{ t('ports.unknownCount', { n: card.port_count }) }}</div>
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

    <!-- 未配置访问地址提示 -->
    <AccessAddressPrompt
      v-if="showAddrPrompt"
      @configure="onAddrConfigure"
      @dismissed="onAddrDismissed"
    />
  </div>
</template>
