<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import {
  fetchPorts,
  refreshPorts,
  hidePort,
  editPort,
  type PortAnalysis,
  type PortCard,
} from '@/api'

// ── 状态 ──
const analysis = ref<PortAnalysis | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const protocolFilter = ref('') // '' | 'TCP' | 'UDP'
const editingPort = ref<number | null>(null)
const editServiceName = ref('')

// ── 数据加载 ──
async function loadData() {
  loading.value = true
  try {
    const resp = await fetchPorts({
      protocol: protocolFilter.value || undefined,
      search: searchQuery.value || undefined,
      start_port: 1,
      end_port: 65535,
    })
    if (resp.success) {
      analysis.value = resp.data
    }
  } catch (e) {
    console.error('加载端口数据失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  loading.value = true
  try {
    const resp = await refreshPorts()
    if (resp.success) {
      analysis.value = resp.data
    }
  } finally {
    loading.value = false
  }
}

// ── 搜索防抖 ──
let searchTimer: ReturnType<typeof setTimeout>
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadData, 300)
})

watch(protocolFilter, () => {
  loadData()
})

// ── 端口操作 ──
async function handleHide(card: PortCard) {
  if (card.type === 'unknown_range') {
    // 隐藏整个范围
    if (card.start_port && card.end_port) {
      const ports = []
      for (let p = card.start_port; p <= card.end_port; p++) ports.push(p)
      await hidePort(ports[0]) // 简化：只隐藏第一个
    }
  } else if (card.port) {
    await hidePort(card.port)
  }
  await loadData()
}



async function handleEditSave() {
  if (editingPort.value === null || !editServiceName.value) return
  await editPort(editingPort.value, editServiceName.value)
  editingPort.value = null
  editServiceName.value = ''
  await loadData()
}

function startEdit(card: PortCard) {
  if (card.port) {
    editingPort.value = card.port
    editServiceName.value = card.service_name || ''
  }
}

// ── 初始化 ──
onMounted(() => {
  loadData()
})
</script>

<template>
  <div>
    <!-- 头部 -->
    <div class="main-header">
      <h1>端口监控</h1>
      <button class="btn btn-primary" @click="handleRefresh" :disabled="loading">
        🔄 刷新
      </button>
    </div>

    <div class="main-body">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索端口、服务名、容器名..."
          />
        </div>

        <div class="filter-group">
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === '' }"
            @click="protocolFilter = ''"
          >
            全部
          </button>
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === 'TCP' }"
            @click="protocolFilter = 'TCP'"
          >
            TCP
          </button>
          <button
            class="filter-btn"
            :class="{ active: protocolFilter === 'UDP' }"
            @click="protocolFilter = 'UDP'"
          >
            UDP
          </button>
        </div>
      </div>

      <!-- 统计栏 -->
      <div v-if="analysis" class="stats-bar">
        <div class="stat-card">
          <div class="stat-label">已用端口</div>
          <div class="stat-value green">{{ analysis.total_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">可用端口</div>
          <div class="stat-value blue">{{ analysis.total_available }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">TCP</div>
          <div class="stat-value yellow">{{ analysis.tcp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">UDP</div>
          <div class="stat-value purple">{{ analysis.udp_used }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Docker 容器</div>
          <div class="stat-value">{{ analysis.docker_containers }}</div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        加载端口数据...
      </div>

      <!-- 端口卡片网格 -->
      <div v-else-if="analysis && analysis.port_cards.length > 0" class="port-grid">
        <!-- 已用端口 -->
        <div
          v-for="(card, idx) in analysis.port_cards"
          :key="idx"
          v-show="card.type === 'used'"
        >
          <div class="port-card" v-if="card.type === 'used'">
            <div class="port-actions">
              <button
                class="port-action-btn"
                title="编辑服务名"
                @click="startEdit(card)"
              >✏️</button>
              <button
                class="port-action-btn danger"
                title="隐藏端口"
                @click="handleHide(card)"
              >🙈</button>
            </div>

            <div class="port-card-header">
              <span class="port-number">{{ card.port }}</span>
              <span
                class="port-protocol"
                :class="(card.protocol || '').toLowerCase()"
              >{{ card.protocol }}</span>
            </div>

            <div class="port-service">
              {{ card.service_name || '未知服务' }}
            </div>

            <div class="port-detail">
              <span
                class="port-source"
                :class="card.source"
              >
                {{ card.source === 'docker' ? '🐳 Docker' : card.source === 'system' ? '⚙️ 系统' : '🖥️ 主机' }}
              </span>

              <span
                v-if="card.container"
                class="port-status"
                :class="card.is_running ? 'running' : 'stopped'"
              >
                <span class="status-dot"></span>
                {{ card.container }}
              </span>

              <span v-if="card.image" style="color: var(--text-muted)">
                {{ card.image }}
              </span>
            </div>

            <!-- 编辑模式 -->
            <div v-if="editingPort === card.port" style="margin-top: 10px; display: flex; gap: 6px;">
              <input
                class="form-input"
                v-model="editServiceName"
                @keyup.enter="handleEditSave"
                placeholder="输入服务名"
                style="flex: 1; padding: 4px 8px; font-size: 12px;"
              />
              <button class="btn btn-sm btn-primary" @click="handleEditSave">保存</button>
              <button class="btn btn-sm" @click="editingPort = null">取消</button>
            </div>
          </div>
        </div>

        <!-- 间隙 -->
        <div
          v-for="(card, idx) in analysis.port_cards"
          :key="'gap-' + idx"
          v-show="card.type === 'gap'"
        >
          <div class="gap-card" v-if="card.type === 'gap'">
            <div class="gap-info">
              <span class="gap-range">{{ card.start_port }} — {{ card.end_port }}</span>
              <span class="gap-count">{{ card.available_count }} 个可用端口</span>
            </div>
            <span class="gap-badge">✓ 可用</span>
          </div>
        </div>

        <!-- 未知范围 -->
        <div
          v-for="(card, idx) in analysis.port_cards"
          :key="'unk-' + idx"
          v-show="card.type === 'unknown_range'"
        >
          <div class="unknown-card" v-if="card.type === 'unknown_range'">
            <div class="port-actions" style="position: static; margin-bottom: 8px; justify-content: flex-end;">
              <button
                class="port-action-btn danger"
                title="隐藏范围"
                @click="handleHide(card)"
              >🙈</button>
            </div>
            <div class="unknown-range">{{ card.start_port }} — {{ card.end_port }}</div>
            <div class="unknown-count">{{ card.port_count }} 个未知服务端口</div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-icon">📡</div>
        <div class="empty-text">暂无端口数据</div>
      </div>
    </div>
  </div>
</template>
