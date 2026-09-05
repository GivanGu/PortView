<template>
  <div class="service-config">
    <div class="service-config-header">
      <button class="btn btn--primary" @click="addMapping">
        <Plus class="w-4 h-4" /> 添加映射
      </button>
      <button class="btn" @click="save">
        <Save class="w-4 h-4" /> 保存
      </button>
    </div>

    <div v-if="mappings.length === 0" class="service-empty">
      <Network class="w-12 h-12 text-muted" />
      <p class="service-empty-text">暂无服务映射</p>
    </div>

    <div v-else class="service-table-wrapper">
      <table class="service-table">
        <thead>
          <tr>
            <th>服务名称</th>
            <th>容器/主机</th>
            <th>端口</th>
            <th>协议</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(m, i) in mappings" :key="i">
            <td>
              <input
                v-model="m.name"
                class="form-input table-input"
                placeholder="Nginx-Web"
              />
            </td>
            <td>
              <select v-model="m.target_type" class="form-select table-input">
                <option value="docker">Docker</option>
                <option value="host">Host</option>
              </select>
            </td>
            <td>
              <input
                v-model.number="m.port"
                type="number"
                class="form-input table-input"
                min="1"
                max="65535"
              />
            </td>
            <td>
              <select v-model="m.protocol" class="form-select table-input">
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
              </select>
            </td>
            <td>
              <button
                class="btn btn--icon btn--danger"
                @click="removeMapping(i)"
                title="删除"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Plus, Save, Trash2, Network } from '@/icons'

const props = defineProps<{
  config: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'save'): void
}>()

const mappings = ref<any[]>([])

watch(
  () => props.config,
  (val) => {
    mappings.value = [...(val.mappings || [])]
  },
  { immediate: true, deep: true },
)

function addMapping() {
  mappings.value.push({
    name: '',
    target_type: 'docker',
    port: 0,
    protocol: 'tcp',
  })
}

function removeMapping(index: number) {
  mappings.value.splice(index, 1)
}

function save() {
  props.config.mappings = mappings.value
  emit('save')
}
</script>

<style scoped>
.service-config {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.service-config-header {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.service-empty {
  text-align: center;
  padding: 2rem 0;
  color: var(--text-muted);
}

.service-empty-text {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.service-table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.service-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.service-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}

.service-table td {
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--border);
}

.table-input {
  width: 100%;
  font-size: 0.8rem;
}

.btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.4rem 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-primary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn:hover {
  background: var(--bg-hover);
}

.btn--primary {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
}

.btn--primary:hover {
  background: var(--brand-hover);
}

.btn--icon {
  padding: 0.25rem 0.4rem;
}

.btn--danger:hover {
  background: var(--red-soft);
  color: var(--red);
}

.form-select {
  padding: 0.3rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-base);
  color: var(--text-primary);
  font-size: 0.8rem;
}
</style>
