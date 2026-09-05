<template>
  <div class="overview-view">
    <!-- 顶部统计 -->
    <div class="stats-section">
      <div class="stats-grid">
        <StatCard
          label="已用端口"
          :value="stats?.total_used ?? '--'"
          color="green"
          :icon="Activity"
        />
        <StatCard
          label="可用端口"
          :value="stats?.total_available ?? '--'"
          color="blue"
          :icon="Zap"
        />
        <StatCard
          label="TCP"
          :sub="stats?.tcp_used ?? 0"
          value="TCP"
          color="amber"
          :icon="Network"
        />
        <StatCard
          label="UDP"
          :sub="stats?.udp_used ?? 0"
          value="UDP"
          color="purple"
          :icon="Wifi"
        />
          <StatCard
          label="容器"
          :value="stats?.docker_containers ?? 0"
          color="cyan"
          :icon="Package"
        />
        <StatCard
          label="主机"
          :value="stats?.host_count ?? 0"
          color="orange"
          :icon="Server"
        />
      </div>

      <!-- 趋势图 -->
      <div v-if="portHistory.length > 0" class="trend-chart">
        <LineChartWidget :data="portHistory" />
      </div>
    </div>

    <!-- 热门端口 -->
    <div class="section">
      <h3 class="section-title">🔥 热门端口</h3>
      <HotPortsTable :ports="topPorts" />
    </div>

    <!-- 冲突端口 -->
    <div v-if="conflictPorts.length > 0" class="section">
      <h3 class="section-title text-red">⚠️ 端口冲突</h3>
      <ConflictPortsList :ports="conflictPorts" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  Activity, Zap, Network, Wifi,
  Package, Server,
} from '@/icons'
import StatCard from '@/components/common/StatCard.vue'
import HotPortsTable from '@/components/echarts/HotPortsTable.vue'
import LineChartWidget from '@/components/echarts/LineChartWidget.vue'
import ConflictPortsList from '@/components/ConflictPortsList.vue'

import { usePortsStore } from '@/stores/ports'
import { fetchPortStats, fetchPortHistory } from '@/api'

const ports = usePortsStore()

const stats = ref<any>(null)
const portHistory = ref<any[]>([])
const conflictPorts = computed(() =>
  (ports.portCards.value || []).filter(c => c.conflict),
)
const topPorts = computed(() =>
  (ports.portCards.value || [])
    .filter(c => c.type === 'used')
    .sort((a, b) => (b.port || 0) - (a.port || 0))
    .slice(0, 10),
)

async function load() {
  const res = await fetchPortStats()
  if (res.success) stats.value = res.data

  const hist = await fetchPortHistory()
  if (hist.success) portHistory.value = hist.data

  await ports.loadData()
}

onMounted(() => load())
</script>

<style scoped>
.overview-view {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.stats-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}

.trend-chart {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1rem;
  height: 200px;
}

.section {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
  padding: 0 0.25rem;
}

.section-title.text-red {
  color: var(--red);
}
</style>
