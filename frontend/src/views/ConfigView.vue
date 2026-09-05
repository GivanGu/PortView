<template>
  <div class="config-page">
    <Tabs v-model:active-tab="activeTab">
      <TabPane key="services" label="服务映射">
        <ServiceConfig :config="serviceConfig" @save="saveServiceConfig" />
      </TabPane>
      <TabPane key="hidden" label="隐藏端口">
        <HiddenConfig
          :hidden-ports="hiddenPorts"
          @reload="reloadHidden"
          @add="addHiddenPort"
          @remove="removeHiddenPort"
        />
      </TabPane>
      <TabPane key="ranges" label="🎯 自定义区间">
        <RangeManager
          :ranges="customRanges"
          @add="addRange"
          @edit="editRange"
          @delete="deleteRange"
        />
      </TabPane>
    </Tabs>

    <Toast ref="toastRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'
import {
  fetchConfig, saveConfig, fetchHiddenPorts, hidePort,
  unhidePort, fetchCustomRanges,
  createCustomRange, updateCustomRange, deleteCustomRange,
} from '@/api'
import { usePortsStore } from '@/stores/ports'

const Tabs = defineAsyncComponent(() => import('@/components/config/Tabs.vue'))
const TabPane = defineAsyncComponent(() => import('@/components/config/TabPane.vue'))
const ServiceConfig = defineAsyncComponent(() => import('@/components/config/ServiceConfig.vue'))
const HiddenConfig = defineAsyncComponent(() => import('@/components/config/HiddenConfig.vue'))
const RangeManager = defineAsyncComponent(() => import('@/components/config/RangeManager.vue'))
const Toast = defineAsyncComponent(() => import('@/components/common/Toast.vue'))

const activeTab = ref('services')
const serviceConfig = ref<Record<string, any>>({})
const hiddenPorts = ref<number[]>([])
const toastRef = ref<any>(null)
const ports = usePortsStore()

const customRanges = computed(() => ports.customRanges)

async function loadAll() {
  const c = await fetchConfig()
  if (c.success) serviceConfig.value = c.data
  const h = await fetchHiddenPorts()
  if (h.success) hiddenPorts.value = h.data
  const r = await fetchCustomRanges()
  if (r.success) ports.customRanges = r.data
}

function saveServiceConfig() {
  saveConfig(serviceConfig.value)
  toastRef.value?.show('保存成功', 'success')
}

function reloadHidden() {
  fetchHiddenPorts().then(r => {
    if (r.success) hiddenPorts.value = r.data
  })
}

function addHiddenPort(port: number) {
  hidePort(port)
  hiddenPorts.value.push(port)
}

function removeHiddenPort(port: number) {
  unhidePort(port)
  hiddenPorts.value = hiddenPorts.value.filter(p => p !== port)
}

async function addRange(range: { name: string; start_port: number; end_port: number; color: string }) {
  const res = await createCustomRange(range)
  if (res.success) {
    ports.customRanges = res.data
    toastRef.value?.show('区间添加成功', 'success')
  } else {
    toastRef.value?.show(res.error || '添加失败', 'error')
  }
}

async function editRange(id: string, range: any) {
  const res = await updateCustomRange(id, range)
  if (res.success) {
    ports.customRanges = res.data
    toastRef.value?.show('区间修改成功', 'success')
  }
}

async function deleteRange(id: string) {
  const res = await deleteCustomRange(id)
  if (res.success) {
    ports.customRanges = res.data
    if (ports.activeRangeId === id) ports.setActiveRange(null)
    toastRef.value?.show('区间已删除', 'info')
  }
}

onMounted(() => loadAll())
</script>

<style scoped>
.config-page {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
