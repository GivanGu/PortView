<template>
  <div class="ports-view">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="search-box">
        <Search class="w-4 h-4 search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索端口、服务名、容器名..."
        />
        <kbd class="search-shortcut">/</kbd>
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

        <button
          class="filter-btn"
          :class="{ active: showHidden }"
          @click="showHidden = !showHidden"
          :title="showHidden ? '隐藏已隐藏端口' : '显示已隐藏端口'"
        >
          <Eye v-show="!showHidden" class="w-4 h-4" />
          <EyeOff v-show="showHidden" class="w-4 h-4" />
        </button>
      </div>

      <div class="action-group">
        <button
          class="btn btn--icon"
          :class="{ 'spinning': refreshing }"
          @click="handleRefresh"
          :disabled="loading || refreshing"
          title="刷新 (Ctrl+R)"
        >
          <RefreshCw class="w-4 h-4" />
        </button>
        <button
          class="btn btn--icon"
          @click="exportMenu = true"
          :disabled="!flatCards.length"
          title="导出"
        >
          <Download class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- 统计栏 -->
    <div v-if="stats" class="stats-row">
      <StatCard
        label="已用端口"
        :value="stats.total_used"
        color="green"
        :icon="Activity"
      />
      <StatCard
        label="可用端口"
        :value="stats.total_available"
        color="blue"
        :icon="Zap"
      />
      <StatCard
        label="TCP"
        value="TCP"
        :sub="stats.tcp_used"
        color="amber"
        :icon="Network"
      />
      <StatCard
        label="UDP"
        value="UDP"
        :sub="stats.udp_used"
        color="purple"
        :icon="Wifi"
      />
      <StatCard
        label="容器"
        :value="stats.docker_containers"
        color="cyan"
        :icon="Package"
      />
    </div>

    <!-- 虚拟列表 -->
    <VirtualList
      v-if="flatCards.length > 0"
      :items="flatCards"
      :item-height="88"
      key-field="id"
      class="ports-list"
    >
      <template #default="{ item }">
        <PortCard
          :card="item"
          @edit="startEdit"
          @hide="handleHide"
        />
      </template>
    </VirtualList>

    <!-- 加载状态 -->
    <div v-else-if="loading" class="loading-state">
      <RefreshCw class="w-8 h-8 spinning" />
      <span>加载端口数据...</span>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <Network class="w-16 h-16 text-muted" />
      <p class="empty-text">暂无端口数据</p>
    </div>

    <!-- 编辑弹窗 -->
    <EditPortModal
      v-if="editingCard"
      :card="editingCard"
      @close="editingCard = null"
      @save="handleEditSave"
    />

    <!-- 导出菜单 -->
    <ExportMenu
      v-if="exportMenu"
      @close="exportMenu = false"
      @export="handleExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Search, Eye, EyeOff, RefreshCw, Download,
  Activity, Zap, Network, Wifi, Package,
} from '@/icons'
import VirtualList from '@/components/VirtualList.vue'
import PortCard from '@/components/PortCard.vue'
import EditPortModal from '@/components/EditPortModal.vue'
import ExportMenu from '@/components/ExportMenu.vue'
import StatCard from '@/components/common/StatCard.vue'

import { usePortsStore } from '@/stores/ports'
import { exportPorts, type ExportFormat } from '@/utils/export'
import { hidePort, editPort } from '@/api'

const props = defineProps<{
  refreshing?: boolean
}>()

const ports = usePortsStore()
const searchQuery = ref('')
const protocolFilter = ref('')
const showHidden = ref(false)
const exportMenu = ref(false)
const editingCard = ref<any>(null)

const loading = computed(() => ports.loading)
const stats = computed(() => ports.stats)

async function loadData() {
  await ports.loadData()
}

async function handleRefresh() {
  ports.nextCursor.value = null
  await loadData()
}

// 搜索/筛选同步到 store
watch(searchQuery, (v) => {
  clearTimeout((window as any).__searchTimer)
  ;(window as any).__searchTimer = setTimeout(() => {
    ports.searchQuery = v
    loadData()
  }, 300)
})

watch(protocolFilter, (v) => {
  ports.protocolFilter = v
  loadData()
})

// 扁平化卡片列表 — 供虚拟滚动
const flatCards = computed(() => {
  const cards = ports.portCards.value || []
  return cards.map(c => ({
    id: c.id ?? `${c.type}_${c.port ?? c.start_port}`,
    ...c,
  }))
})

function startEdit(card: any) {
  editingCard.value = card
}

async function handleEditSave(card: any, newName: string) {
  await editPort(card.port, newName)
  loadData()
}

function handleHide(card: any) {
  // 隐藏端口
  if (card.type === 'used' && card.port) {
    hidePort(card.port)
    loadData()
  }
}

function handleExport(format: ExportFormat) {
  if (!ports.portCards.value) return
  exportPorts(ports.portCards.value, format)
  exportMenu.value = false
}

// 键盘快捷键
function onKeyDown(e: KeyboardEvent) {
  if (e.target !== document.body) return
  if (e.ctrlKey && e.key === 'r') {
    e.preventDefault()
    handleRefresh()
  }
}

onMounted(() => {
  loadData()
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
.ports-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
  height: calc(100% - 56px);
}

.toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.search-box {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.5rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.35rem 0.6rem 0.35rem 1.8rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.search-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-soft);
}

.search-shortcut {
  position: absolute;
  right: 0.5rem;
  font-size: 0.65rem;
  color: var(--text-muted);
  pointer-events: none;
}

.filter-group {
  display: flex;
  gap: 0.25rem;
  align-items: center;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.filter-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.filter-btn.active {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
}

.action-group {
  display: flex;
  gap: 0.25rem;
}

btn, .btn {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: 0.85rem;
}

btn, .btn:hover {
  background: var(--bg-hover);
}

.btn--icon {
  padding: 0.3rem 0.5rem;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}

.ports-list {
  flex: 1;
  min-height: 0;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  justify-content: center;
  padding: 2rem;
  color: var(--text-secondary);
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-muted);
}

.empty-text {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}
</style>
