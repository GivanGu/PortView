<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  fetchHiddenPorts,
  unhidePort,
  batchUnhidePorts,
} from '@/api'

const hiddenPorts = ref<number[]>([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    const resp = await fetchHiddenPorts()
    if (resp.success) {
      hiddenPorts.value = resp.data
    }
  } catch (e) {
    console.error('加载隐藏端口失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleUnhide(port: number) {
  await unhidePort(port)
  await loadData()
}

async function handleUnhideAll() {
  if (hiddenPorts.value.length === 0) return
  if (!confirm(`确定取消隐藏所有 ${hiddenPorts.value.length} 个端口？`)) return
  await batchUnhidePorts(hiddenPorts.value)
  await loadData()
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div>
    <div class="main-header">
      <h1>隐藏端口</h1>
      <div style="display: flex; gap: 8px;">
        <span style="font-size: 13px; color: var(--text-muted); align-self: center;">
          共 {{ hiddenPorts.length }} 个
        </span>
        <button
          class="btn"
          @click="handleUnhideAll"
          :disabled="hiddenPorts.length === 0"
        >
          全部取消隐藏
        </button>
      </div>
    </div>

    <div class="main-body">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        加载中...
      </div>

      <div v-else-if="hiddenPorts.length > 0" class="hidden-list">
        <div
          v-for="port in hiddenPorts"
          :key="port"
          class="hidden-item"
        >
          <span class="port-label">{{ port }}</span>
          <div class="port-actions-inline">
            <button class="btn btn-sm" @click="handleUnhide(port)">
              👁️ 取消隐藏
            </button>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <div class="empty-icon">🙈</div>
        <div class="empty-text">没有隐藏的端口</div>
      </div>
    </div>
  </div>
</template>
