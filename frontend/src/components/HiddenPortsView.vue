<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  fetchHiddenPorts,
  unhidePort,
  batchUnhidePorts,
} from '@/api'
import { EyeOff, Eye } from 'lucide-vue-next'

const { t } = useI18n()

const hiddenPorts = ref<number[]>([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    const resp = await fetchHiddenPorts()
    if (resp.success) hiddenPorts.value = resp.data
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
  if (!confirm(t('hidden.unhideAllConfirm', { n: hiddenPorts.value.length }))) return
  await batchUnhidePorts(hiddenPorts.value)
  await loadData()
}

onMounted(() => loadData())
</script>

<template>
  <div>
    <div class="main-header">
      <h1>{{ t('nav.hidden') }}</h1>
      <div class="header-actions">
        <span class="meta">{{ t('hidden.total', { n: hiddenPorts.length }) }}</span>
        <button
          class="btn"
          @click="handleUnhideAll"
          :disabled="hiddenPorts.length === 0"
        >
          <Eye :size="14" class="btn-icon" />
          {{ t('hidden.unhideAll') }}
        </button>
      </div>
    </div>

    <div class="main-body">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        {{ t('common.loading') }}
      </div>

      <div v-else-if="hiddenPorts.length > 0" class="hidden-list">
        <div
          v-for="port in hiddenPorts"
          :key="port"
          class="hidden-item"
        >
          <span class="port-label">{{ port }}</span>
          <div class="port-actions-inline">
            <button
              class="btn btn-sm"
              :title="t('hidden.unhide')"
              @click="handleUnhide(port)"
            >
              <Eye :size="14" />
              {{ t('hidden.unhide') }}
            </button>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <div class="empty-icon"><EyeOff :size="32" /></div>
        <div class="empty-text">{{ t('hidden.empty') }}</div>
      </div>
    </div>
  </div>
</template>
