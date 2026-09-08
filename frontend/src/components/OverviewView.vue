<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchPorts, type PortCard } from '@/api'

interface OverviewStats {
  totalUsed: number
  totalAvailable: number
  tcpUsed: number
  udpUsed: number
  dockerContainers: number
  hiddenPorts: number[]
  hostPorts: number
  dockerPorts: number
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
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function countBySource(cards: PortCard[], sources: string[]): number {
  return cards.filter((c) => c.type === 'used' && c.source && sources.includes(c.source)).length
}

async function load() {
  loading.value = true
  error.value = ''
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
    }
    loadedAt.value = new Date()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2>概览</h2>
        <p class="view-desc">端口使用状态总览</p>
      </div>
      <div class="view-header-right">
        <span v-if="loadedAt" class="updated-at">更新于 {{ formatTime(loadedAt) }}</span>
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ total }}</div>
        <div class="stat-label">总端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--green)">{{ stats.totalUsed }}</div>
        <div class="stat-label">已用端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--blue)">{{ stats.totalAvailable }}</div>
        <div class="stat-label">可用端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--cyan)">{{ stats.hostPorts }}</div>
        <div class="stat-label">主机端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--purple)">{{ stats.dockerPorts }}</div>
        <div class="stat-label">Docker 端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--yellow)">{{ stats.hiddenPorts.length }}</div>
        <div class="stat-label">隐藏端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--accent)">{{ stats.tcpUsed }}</div>
        <div class="stat-label">TCP 端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--orange)">{{ stats.udpUsed }}</div>
        <div class="stat-label">UDP 端口</div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="chart-row">
      <div class="chart-card">
        <div class="chart-title">端口占用率</div>
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
        <div class="chart-title">协议分布</div>
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
