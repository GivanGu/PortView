<template>
  <div class="hidden-view">
    <div class="hidden-header">
      <h2>隐藏端口</h2>
      <p class="hidden-desc">
        已隐藏的端口将不再在监控视图中显示
      </p>
    </div>

    <div v-if="loading" class="loading-state">
      <RefreshCw class="spinning w-6 h-6" />
      <span>加载...</span>
    </div>

    <div v-else-if="hiddenPorts.length === 0" class="empty-state">
      <EyeOff class="w-16 h-16 text-muted" />
      <p class="empty-text">暂无隐藏的端口</p>
    </div>

    <div v-else class="hidden-list">
      <div class="hidden-port-item" v-for="port in hiddenPorts" :key="port">
        <span class="hidden-port-number">{{ port }}</span>
        <span class="hidden-port-label">{{ getPortLabel(port) }}</span>
        <button
          class="btn btn--icon btn--ghost btn--danger"
          @click="unhidePort(port)"
          title="取消隐藏"
        >
          <Eye class="w-4 h-4" />
        </button>
      </div>

      <div class="hidden-actions">
        <button
          class="btn btn--danger"
          @click="unhideAll"
          :disabled="hiddenPorts.length === 0"
        >
          <Eye class="w-4 h-4" /> 全部取消隐藏
        </button>
        <button
          class="btn"
          @click="refreshHidden"
          title="刷新"
        >
          <RefreshCw class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Eye, EyeOff, RefreshCw } from '@/icons'
import { fetchHiddenPorts, unhidePort, batchUnhidePorts } from '@/api'

const hiddenPorts = ref<number[]>([])
const loading = ref(false)

async function loadHidden() {
  loading.value = true
  try {
    const res = await fetchHiddenPorts()
    if (res.success) hiddenPorts.value = res.data
  } finally {
    loading.value = false
  }
}

function getPortLabel(port: number): string {
  const wellKnown: Record<number, string> = {
    22: 'SSH', 80: 'HTTP', 443: 'HTTPS', 3306: 'MySQL',
    5432: 'PostgreSQL', 6379: 'Redis', 8080: 'HTTP 备用',
    27017: 'MongoDB', 9090: 'Prometheus', 3000: 'Grafana',
  }
  return wellKnown[port] || '自定义端口'
}

async function unhidePort(port: number) {
  const res = await unhidePort(port)
  if (res.success) {
    hiddenPorts.value = hiddenPorts.value.filter(p => p !== port)
  }
}

async function unhideAll() {
  if (!confirm('确定取消隐藏全部端口吗？')) return
  const res = await batchUnhidePorts(hiddenPorts.value)
  if (res.success) hiddenPorts.value = []
}

function refreshHidden() {
  loadHidden()
}

onMounted(() => loadHidden())
</script>

<style scoped>
.hidden-view {
  padding: 1.5rem;
  max-width: 800px;
  margin: 0 auto;
}

.hidden-header {
  margin-bottom: 1.5rem;
}

.hidden-desc {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.hidden-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.hidden-port-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.85rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
}

.hidden-port-number {
  font-family: monospace;
  font-weight: 600;
  color: var(--text-primary);
}

.hidden-port-label {
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.hidden-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
  color: var(--text-secondary);
}

.empty-state {
  text-align: center;
  padding: 2.5rem;
  color: var(--text-muted);
}
</style>
