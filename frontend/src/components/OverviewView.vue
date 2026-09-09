<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchPorts, type PortCard } from '@/api'
import usePrefs from '@/store/prefs'

const { t, locale } = useI18n()

interface OverviewStats {
  totalUsed: number
  totalAvailable: number
  tcpUsed: number
  udpUsed: number
  dockerContainers: number
  hiddenPorts: number[]
  hostPorts: number
  dockerPorts: number
  dockerOnline: number
  dockerOffline: number
}

const CIRC = 2 * Math.PI * 52

const stats = ref<OverviewStats>({
  totalUsed: 0,
  totalAvailable: 0,
  tcpUsed: 0,
  udpUsed: 0,
  dockerContainers: 0,
  hiddenPorts: [],
  hostPorts: 0,
  dockerPorts: 0,
  dockerOnline: 0,
  dockerOffline: 0,
})
const loading = ref(true)
const error = ref('')
const loadedAt = ref<Date | null>(null)

const total = computed(() => stats.value.totalUsed + stats.value.totalAvailable)
const usagePct = computed(() => (total.value > 0 ? stats.value.totalUsed / total.value : 0))

const protoTotal = computed(() => stats.value.tcpUsed + stats.value.udpUsed)
const tcpLen = computed(() => (protoTotal.value > 0 ? (stats.value.tcpUsed / protoTotal.value) * CIRC : 0))
const udpLen = computed(() => (protoTotal.value > 0 ? (stats.value.udpUsed / protoTotal.value) * CIRC : 0))
const tcpPct = computed(() => (protoTotal.value > 0 ? (stats.value.tcpUsed / protoTotal.value) * 100 : 0))
const udpPct = computed(() => (protoTotal.value > 0 ? (stats.value.udpUsed / protoTotal.value) * 100 : 0))

function dashoffset(pct: number) {
  const clamped = Math.min(1, Math.max(0, pct))
  return CIRC * (1 - clamped)
}

function formatTime(d: Date) {
  return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function countBySource(cards: PortCard[], sources: string[]): number {
  return cards.filter((c) => c.type === 'used' && c.source && sources.includes(c.source)).length
}

// v1.4.4：Docker 端口的在线/离线计数（is_running 为权威信号）
function countDockerStatus(cards: PortCard[]): { dockerOnline: number; dockerOffline: number } {
  let online = 0
  let offline = 0
  for (const c of cards) {
    if (c.type !== 'used' || c.source !== 'docker') continue
    if (c.is_running === false) offline++
    else online++
  }
  return { dockerOnline: online, dockerOffline: offline }
}

async function load(silent = false) {
  if (!silent) loading.value = true
  if (!silent) error.value = ''
  try {
    const res = await fetchPorts()
    const data = res.data
    stats.value = {
      totalUsed: data.total_used,
      totalAvailable: data.total_available,
      tcpUsed: data.tcp_used,
      udpUsed: data.udp_used,
      dockerContainers: data.docker_containers,
      hiddenPorts: data.hidden_ports,
      hostPorts: countBySource(data.port_cards, ['host', 'system']),
      dockerPorts: countBySource(data.port_cards, ['docker']),
      ...countDockerStatus(data.port_cards),
    }
    loadedAt.value = new Date()
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : t('overview.loadFailed')
  } finally {
    if (!silent) loading.value = false
  }
}

// v1.4.4：自动刷新 + 手动刷新统一走共享 prefs store
const { refreshInterval, refreshTick } = usePrefs()

let pollTimer: ReturnType<typeof setInterval> | null = null

function applyPollTimer() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (refreshInterval.value > 0) {
    pollTimer = setInterval(() => {
      if (!document.hidden && !loading.value) load(true)
    }, refreshInterval.value * 1000)
  }
}

watch(refreshInterval, () => applyPollTimer())
watch(refreshTick, () => {
  if (!loading.value) load(true)
})

onMounted(() => {
  load()
  applyPollTimer()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2>{{ t('overview.title') }}</h2>
        <p class="view-desc">{{ t('overview.subtitle') }}</p>
      </div>
      <div class="view-header-right">
        <span v-if="loadedAt" class="updated-at">{{ t('overview.updated') }} {{ formatTime(loadedAt) }}</span>
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ total }}</div>
        <div class="stat-label">{{ t('overview.totalPorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--green)">{{ stats.totalUsed }}</div>
        <div class="stat-label">{{ t('overview.usedPorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--blue)">{{ stats.totalAvailable }}</div>
        <div class="stat-label">{{ t('overview.availablePorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--cyan)">{{ stats.hostPorts }}</div>
        <div class="stat-label">{{ t('overview.hostPorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--purple)">{{ stats.dockerPorts }}</div>
        <div class="stat-label">{{ t('overview.dockerPorts') }}</div>
        <div class="stat-sub">
          <span class="stat-sub-item online"><span class="sub-dot"></span>{{ stats.dockerOnline }} {{ t('overview.dockerOnline') }}</span>
          <span class="stat-sub-item offline"><span class="sub-dot"></span>{{ stats.dockerOffline }} {{ t('overview.dockerOffline') }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--yellow)">{{ stats.hiddenPorts.length }}</div>
        <div class="stat-label">{{ t('overview.hiddenPorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--accent)">{{ stats.tcpUsed }}</div>
        <div class="stat-label">{{ t('overview.tcpPorts') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--orange)">{{ stats.udpUsed }}</div>
        <div class="stat-label">{{ t('overview.udpPorts') }}</div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="chart-row">
      <div class="chart-card">
        <div class="chart-title">{{ t('overview.usageRate') }}</div>
        <div class="ring-wrap">
          <svg viewBox="0 0 120 120" class="ring-svg">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="12" />
            <circle
              cx="60"
              cy="60"
              r="52"
              fill="none"
              stroke="var(--accent)"
              stroke-width="12"
              :stroke-dasharray="CIRC"
              :stroke-dashoffset="dashoffset(usagePct)"
              stroke-linecap="round"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="ring-center">
            <div class="ring-pct">{{ (usagePct * 100).toFixed(1) }}%</div>
            <div class="ring-sub">{{ stats.totalUsed }} / {{ total }}</div>
          </div>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-title">{{ t('overview.protocolDist') }}</div>
        <div class="pie-wrap">
          <svg viewBox="0 0 120 120" class="pie-svg">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="12" />
            <circle
              cx="60" cy="60" r="52" fill="none"
              stroke="var(--accent)" stroke-width="12"
              :stroke-dasharray="`${tcpLen} ${CIRC - tcpLen}`"
              stroke-dashoffset="0"
              transform="rotate(-90 60 60)"
            />
            <circle
              cx="60" cy="60" r="52" fill="none"
              stroke="var(--orange)" stroke-width="12"
              :stroke-dasharray="`${udpLen} ${CIRC - udpLen}`"
              :stroke-dashoffset="-tcpLen"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="ring-center">
            <div class="ring-pct">{{ protoTotal }}</div>
            <div class="ring-sub">TCP + UDP</div>
          </div>
        </div>
        <div class="pie-legend">
          <div class="pie-legend-item">
            <span class="pie-dot" style="background: var(--accent)" />
            <span class="pie-legend-label">TCP</span>
            <span class="pie-legend-val">{{ stats.tcpUsed }} ({{ tcpPct.toFixed(1) }}%)</span>
          </div>
          <div class="pie-legend-item">
            <span class="pie-dot" style="background: var(--orange)" />
            <span class="pie-legend-label">UDP</span>
            <span class="pie-legend-val">{{ stats.udpUsed }} ({{ udpPct.toFixed(1) }}%)</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
