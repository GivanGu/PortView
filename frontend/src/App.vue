<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { healthCheck } from '@/api'
import PortsView from '@/components/PortsView.vue'
import HiddenPortsView from '@/components/HiddenPortsView.vue'

const activeTab = ref<'ports' | 'hidden'>('ports')
const version = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    const health = await healthCheck()
    version.value = health.version
  } catch {
    version.value = 'unknown'
  }
  loading.value = false
})

function switchTab(tab: 'ports' | 'hidden') {
  activeTab.value = tab
}
</script>

<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-icon">⚡</div>
        <span>PortView</span>
      </div>

      <nav class="sidebar-nav">
        <button
          class="nav-item"
          :class="{ active: activeTab === 'ports' }"
          @click="switchTab('ports')"
        >
          <span class="nav-icon">📡</span>
          <span>端口监控</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'hidden' }"
          @click="switchTab('hidden')"
        >
          <span class="nav-icon">🙈</span>
          <span>隐藏端口</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div>PortView v{{ version }}</div>
        <div style="margin-top: 4px">端口监控与可视化</div>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <PortsView v-if="activeTab === 'ports'" />
      <HiddenPortsView v-else />
    </main>
  </div>
</template>
