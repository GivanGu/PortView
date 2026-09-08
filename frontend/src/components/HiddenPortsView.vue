<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
          class="hidden-item hidden-item-detail"
        >
          <div class="hidden-detail-main">
            <span class="port-label">{{ port }}</span>
            <span v-if="getDetail(port)?.service_name" class="hidden-detail-svc">
              {{ getDetail(port)!.service_name }}
            </span>
            <span v-if="getDetail(port)?.protocol" class="hidden-detail-proto">
              {{ getDetail(port)!.protocol.toUpperCase() }}
            </span>
            <span v-if="getDetail(port)?.source" class="hidden-detail-src" :class="getDetail(port)!.source">
              <Container v-if="getDetail(port)!.source === 'docker'" :size="12" />
              <Server v-else :size="12" />
              {{ getDetail(port)!.source === 'docker' ? 'Docker' : '主机' }}
            </span>
            <span v-if="getDetail(port)?.container" class="hidden-detail-container">
              {{ getDetail(port)!.container }}
            </span>
            <span v-if="getDetail(port)?.remark" class="hidden-detail-remark">
              {{ getDetail(port)!.remark }}
            </span>
            <span v-if="getDetail(port) && !getDetail(port)!.is_running" class="hidden-detail-offline">
              离线
            </span>
          </div>
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
