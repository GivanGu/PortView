<template>
  <div class="line-chart">
    <div class="chart-header">
      <span class="chart-title">端口动态趋势</span>
      <span class="chart-period">最近 24h</span>
    </div>
    <div class="chart-body">
      <svg
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        class="chart-svg"
        preserveAspectRatio="none"
      >
        <!-- 网格线 -->
        <g v-for="line in gridLines" :key="line.y" stroke="var(--border)" stroke-width="1" stroke-dasharray="2,2">
          <line :x1="0" :y1="line.y" :x2="chartWidth" :y2="line.y" />
        </g>

        <!-- 数据折线 -->
        <polyline
          :points="points"
          fill="none"
          stroke="var(--brand)"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- 数据填充渐变 -->
        <defs>
          <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="var(--brand)" stop-opacity="0.3" />
            <stop offset="1" stop-color="var(--brand)" stop-opacity="0" />
          </linearGradient>
        </defs>
        <polygon
          :points="areaPoints"
          fill="url(#area-gradient)"
        />

        <!-- 数据点 -->
        <g v-for="point in dataPoints" :key="point.x">
          <circle
            :cx="point.x"
            :cy="point.y"
            r="3"
            fill="var(--brand)"
            v-if="point.showDot"
          />
        </g>

        <!-- Y 轴标签 -->
        <!-- X 轴标签 -->
        <!-- ... -->
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: any[]
}>()

const chartWidth = 600
const chartHeight = 120
const padding = { top: 10, right: 10, bottom: 20, left: 30 }

// 只使用最近 24 个数据点
const chartData = computed(() => props.data.slice(-24))

const maxVal = computed(() => {
  const vals = chartData.value.map(d => d.count || 0)
  return vals.reduce((a, b) => Math.max(a, b), 0) || 10
})

const plotHeight = chartHeight - padding.top - padding.bottom
const plotWidth = chartWidth - padding.left - padding.right

const dataPoints = computed(() => {
  const n = chartData.value.length
  if (n === 0) return []
  const step = plotWidth / (n - 1 || 1)
  return chartData.value.map((d, i) => {
    const x = padding.left + step * i
    const y = padding.top + plotHeight - ((d.count || 0) / maxVal.value) * plotHeight
    return { x, y, showDot: i === n - 1 || i === 0 }
  })
})

const points = computed(() =>
  dataPoints.value.map(p => `${p.x},${p.y}`).join(' ')
)

const areaPoints = computed(() => {
  const pts = dataPoints.value.map(p => `${p.x},${p.y}`).join(' ')
  const lastX = dataPoints.value[dataPoints.value.length - 1]?.x ?? 0
  const firstX = dataPoints.value[0]?.x ?? 0
  return `${pts} ${lastX},${chartHeight - padding.bottom} ${firstX},${chartHeight - padding.bottom} Z`
})

const gridLines = computed(() => {
  const count = 4
  const step = plotHeight / count
  return Array.from({ length: count + 1 }, (_, i) => ({
    y: padding.top + step * i,
  }))
})
</script>

<style scoped>
.line-chart {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0.5rem;
  margin-bottom: 0.25rem;
}

.chart-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.chart-period {
  font-size: 0.68rem;
  color: var(--text-muted);
}

.chart-body {
  flex: 1;
}

.chart-svg {
  width: 100%;
  height: 100%;
}
</style>
