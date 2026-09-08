<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  fetchPorts,
  hidePort,
  batchHidePorts,
  editPort,
  fetchRanges,
  createRange,
  deleteRange,
  getPrefs,
  type PortAnalysis,
  type PortCard,
  type RangeRead,
} from '@/api'
import { exportPorts, type ExportFormat } from '@/utils/export'
import { Search, Container, Cog, Server, Plus, X, StickyNote } from 'lucide-vue-next'

// ── 状态 ──
const analysis = ref<PortAnalysis | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const protocolFilter = ref('') // '' | 'TCP' | 'UDP'
const sourceFilter = ref('') // '' | 'local' | 'docker'（前端侧按 card.source 归类）
const editingPort = ref<number | null>(null)
const editServiceName = ref('')

// ── 监控区间状态 ──
const ranges = ref<RangeRead[]>([])
const selectedRangeId = ref<number>(0) // 0 = 全部
const newRange = reactive({ name: '', start: 1, end: 65535 })
const rangeBusy = ref(false)
const rangeDialog = ref(false)

async function reloadRanges(merge = false) {
  const resp = await fetchRanges()
  if (resp.success) {
    if (merge) ranges.value = [...resp.data]
    else ranges.value = resp.data
  }
}

async function handleCreateRange() {
  if (!newRange.name || !newRange.name.trim()) return
  if (newRange.start > newRange.end) return
  rangeBusy.value = true
  try {
    await createRange(newRange.name.trim(), newRange.start, newRange.end)
    newRange.name = ''
    newRange.start = 1
    newRange.end = 65535
    rangeDialog.value = false
    await reloadRanges(true)
  } catch (e) {
    console.error('create range failed', e)
  } finally {
    rangeBusy.value = false
  }
}

async function handleDeleteRange(id: number) {
  await deleteRange(id)
  if (selectedRangeId.value === id) selectedRangeId.value = 0
  await reloadRanges()
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

// ── 初始化 ──
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  loadData()
  void reloadRanges()
  // 从偏好读取刷新间隔（0=手动，10/15/30=秒）
  try {
    const res = await getPrefs()
    if (res.success && res.data.refresh_interval > 0) {
      pollTimer = setInterval(() => {
        if (!document.hidden && !loading.value) loadData(true)
      }, res.data.refresh_interval * 1000)
    }
  } catch { /* ignore */ }
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div>
    <!-- 头部 -->
    <div class="main-header">
      <h1>端口监控</h1>
      <div class="header-actions">
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
            placeholder="搜索端口、服务名、容器名..."
          />
        </div>

        <div class="filter-group">
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === '' }"
            @click="protocolFilter = ''"
          >
            全部
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
            title="全部"
          >
            端口
          </button>
          <button
            class="filter-btn"
            :class="{ active: sourceFilter === 'local' }"
            @click="sourceFilter = 'local'"
            title="只看主机/本地源端口"
          >
            本地
          </button>
          <button
            class="filter-btn"
            :class="{ active: sourceFilter === 'docker' }"
            @click="sourceFilter = 'docker'"
            title="只看 Docker 源端口"
          >
            Docker
          </button>
        </div>

        <!-- v1.2：监控区间选择器 -->
        <div class="range-selector">
          <span class="range-label">区间</span>
          <select
            v-model="selectedRangeId"
            class="range-select"
          >
            <option :value="0">全部</option>
            <option v-for="r in ranges" :key="r.id" :value="r.id">
              {{ r.name }} ({{ r.start_port }}–{{ r.end_port }})
            </option>
          </select>
          <button class="btn btn-tiny" :title="'新建区间'" @click="rangeDialog = true">
            <Plus :size="13" />
          </button>
          <button
            class="btn btn-tiny btn-danger"
            :title="'删除所选区间'"
            :disabled="selectedRangeId === 0"
            @click="handleDeleteRange(selectedRangeId)"
          >
            <X :size="13" />
          </button>
        </div>
      </div>

      <!-- 统计栏 -->
      <div v-if="analysis" class="stats-bar">
        <div class="stat-card">
          <div class="stat-label">已用端口</div>
          <div class="stat-value green">{{ analysis.total_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">可用端口</div>
          <div class="stat-value blue">{{ analysis.total_available }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">TCP</div>
          <div class="stat-value yellow">{{ analysis.tcp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">UDP</div>
          <div class="stat-value purple">{{ analysis.udp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Docker 容器</div>
          <div class="stat-value">{{ analysis.docker_containers }}</div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        加载端口数据...
      </div>

      <!-- 端口卡片网格 -->
      <div v-else-if="analysis && analysis.port_cards.length > 0" class="port-grid">
        <!-- 已用端口 -->
        <div
          v-for="(card, idx) in analysis.port_cards"
          :key="idx"
          v-show="card.type === 'used' && cardVisible(card)"
        >
          <div
            class="port-card"
            :class="{ offline: card.is_running === false }"
            v-if="card.type === 'used'"
          >
            <div class="port-actions">
              <button
                class="port-action-btn"
                title="编辑服务名"
                @click="startEdit(card)"
              >✏️</button>
              <button
                class="port-action-btn danger"
                title="隐藏端口"
                @click="handleHide(card)"
              >🙈</button>
            </div>

            <div class="port-card-header">
              <span class="port-header-left">
                <span
                  class="port-status-dot"
                  :class="card.is_running === false ? 'is-offline' : 'is-online'"
                  :title="card.is_running === false ? '离线' : '在线'"
                  :aria-label="card.is_running === false ? '离线' : '在线'"
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
              {{ card.service_name || '未知服务' }}
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
                <span>{{ card.source === 'docker' ? 'Docker' : card.source === 'system' ? '系统' : '主机' }}</span>
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
              <span class="port-image-label">镜像</span>
              <span class="port-image-value">{{ card.image }}</span>
            </div>

            <!-- 编辑模式 -->
            <div v-if="editingPort === card.port" style="margin-top: 10px; display: flex; gap: 6px;">
              <input
                class="form-input"
                v-model="editServiceName"
                @keyup.enter="handleEditSave"
                placeholder="输入服务名"
                style="flex: 1; padding: 4px 8px; font-size: 12px;"
              />
              <button class="btn btn-sm btn-primary" @click="handleEditSave">保存</button>
              <button class="btn btn-sm" @click="editingPort = null">取消</button>
            </div>
          </div>
        </div>

        <!-- 未知范围：仅在无源类型过滤时显示 -->
        <div
          v-for="(card, idx) in analysis.port_cards"
          :key="'unk-' + idx"
          v-show="card.type === 'unknown_range' && sourceFilter === ''"
        >
          <div class="unknown-card" v-if="card.type === 'unknown_range'">
            <div class="port-actions" style="position: static; margin-bottom: 8px; justify-content: flex-end;">
              <button
                class="port-action-btn danger"
                title="隐藏范围"
                @click="handleHide(card)"
              >🙈</button>
            </div>
            <div class="unknown-range">{{ card.start_port }} — {{ card.end_port }}</div>
            <div class="unknown-count">{{ card.port_count }} 个未知服务端口</div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-icon">📡</div>
        <div class="empty-text">暂无端口数据</div>
      </div>
    </div>

    <!-- v1.2：新建监控区间对话框 -->
    <Teleport to="body">
      <div v-if="rangeDialog" class="range-overlay" @click.self="rangeDialog = false">
        <div class="range-dialog">
          <h3>新建监控区间</h3>
          <label>名称
            <input class="form-input" v-model="newRange.name" placeholder="如 80s / 高段" />
          </label>
          <label>起始端口
            <input class="form-input" type="number" min="0" max="65535" v-model.number="newRange.start" />
          </label>
          <label>结束端口
            <input class="form-input" type="number" min="0" max="65535" v-model.number="newRange.end" />
          </label>
          <div class="range-dialog-actions">
            <button class="btn btn-sm" @click="rangeDialog = false">取消</button>
            <button
              class="btn btn-sm btn-primary"
              :disabled="rangeBusy || !newRange.name.trim()"
              @click="handleCreateRange"
            >
              <Plus :size="13" /> 创建
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
