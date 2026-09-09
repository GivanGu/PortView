<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  fetchHiddenPorts,
  fetchHiddenPortDetails,
  unhidePort,
  batchUnhidePorts,
  type HiddenPortDetail,
} from '@/api'
import { EyeOff, Eye, Container, Server } from 'lucide-vue-next'

const { t } = useI18n()

const hiddenPorts = ref<number[]>([])
const details = ref<HiddenPortDetail[]>([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    const [portsResp, detailsResp] = await Promise.all([
      fetchHiddenPorts(),
      fetchHiddenPortDetails(),
    ])
    if (portsResp.success) hiddenPorts.value = portsResp.data
    if (detailsResp.success) details.value = detailsResp.data
  } catch (e) {
    console.error('加载隐藏端口失败:', e)
  } finally {
    loading.value = false
  }
}

function getDetail(port: number): HiddenPortDetail | undefined {
  return details.value.find(d => d.port === port)
}

const hiddenItems = computed(() =>
  hiddenPorts.value.map(port => ({ port, detail: getDetail(port) })),
)

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
          v-for="item in hiddenItems"
          :key="item.port"
          class="hidden-item hidden-item-detail"
        >
          <div class="hidden-detail-main">
            <span class="port-label">{{ item.port }}</span>
            <span v-if="item.detail?.service_name" class="hidden-detail-svc">
              {{ item.detail.service_name }}
            </span>
            <span v-if="item.detail?.protocol" class="hidden-detail-proto">
              {{ item.detail.protocol.toUpperCase() }}
            </span>
            <span v-if="item.detail?.source" class="hidden-detail-src" :class="item.detail.source">
              <Container v-if="item.detail.source === 'docker'" :size="12" />
              <Server v-else :size="12" />
              {{ item.detail.source === 'docker' ? t('common.sourceDocker') : t('common.sourceHost') }}
            </span>
            <span v-if="item.detail?.container" class="hidden-detail-container">
              {{ item.detail.container }}
            </span>
            <span v-if="item.detail?.remark" class="hidden-detail-remark">
              {{ item.detail.remark }}
            </span>
            <span v-if="item.detail && !item.detail.is_running" class="hidden-detail-offline">
              {{ t('common.offline') }}
            </span>
          </div>
          <div class="port-actions-inline">
            <button
              class="btn btn-sm"
              :title="t('hidden.unhide')"
              @click="handleUnhide(item.port)"
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
