<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchPorts } from '@/api'

interface OverviewStats {
  totalUsed: number
  totalAvailable: number
  tcpUsed: number
  udpUsed: number
  dockerContainers: number
  hiddenPorts: number[]
}

const CIRC = 2 * Math.PI * 52 // 环形图周长（r=52）

const stats = ref<OverviewStats>({
  totalUsed: 0,
  totalAvailable: 0,
  tcpUsed: 0,
  udpUsed: 0,
  dockerContainers: 0,
  hiddenPorts: [],
})
const loading = ref(true)
const error = ref('')
const loadedAt = ref<Date | null>(null)

const total = computed(() => stats.value.totalUsed + stats.value.totalAvailable)
const usagePct = computed(() => (total.value > 0 ? stats.value.totalUsed / total.value : 0))

function dashoffset(pct: number) {
  const clamped = Math.min(1, Math.max(0, pct))
  return CIRC * (1 - clamped)
}

function protoPct(v: number) {
  const m = Math.max(stats.value.tcpUsed, stats.value.udpUsed, 1)
  return (v / m) * 100
}

function formatTime(d: Date) {
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
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
        <button class="btn btn-primary" :disabled="loading" @click="load">
          <span class="btn-icon">🔄</span>
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-value" style="color: var(--green)">{{ stats.totalUsed }}</div>
        <div class="stat-label">已使用端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--blue)">{{ stats.totalAvailable }}</div>
        <div class="stat-label">可用端口</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--cyan)">{{ stats.tcpUsed }}</div>
        <div class="stat-label">TCP 占用</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--orange)">{{ stats.udpUsed }}</div>
        <div class="stat-label">UDP 占用</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--purple)">{{ stats.dockerContainers }}</div>
        <div class="stat-label">Docker 容器</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--yellow)">{{ stats.hiddenPorts.length }}</div>
        <div class="stat-label">隐藏端口</div>
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
        <div class="proto-list">
          <div class="proto-item">
            <div class="proto-head">
              <span class="proto-tag tcp">TCP</span>
              <span class="proto-val">{{ stats.tcpUsed }}</span>
            </div>
            <div class="proto-bar">
              <div class="proto-bar-fill tcp" :style="{ width: protoPct(stats.tcpUsed) + '%' }" />
            </div>
          </div>
          <div class="proto-item">
            <div class="proto-head">
              <span class="proto-tag udp">UDP</span>
              <span class="proto-val">{{ stats.udpUsed }}</span>
            </div>
            <div class="proto-bar">
              <div class="proto-bar-fill udp" :style="{ width: protoPct(stats.udpUsed) + '%' }" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
