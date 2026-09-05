<template>
  <div class="hot-ports-table">
    <table>
      <thead>
        <tr>
          <th>端口</th>
          <th>服务</th>
          <th>协议</th>
          <th>来源</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in ports" :key="p.port">
          <td>
            <span class="port-num">{{ p.port }}</span>
          </td>
          <td>{{ p.service_name || '未知' }}</td>
          <td>
            <span
              class="protocol-badge"
              :class="p.protocol?.toLowerCase()"
            >{{ p.protocol }}</span>
          </td>
          <td>
            <span
              class="source-badge"
              :class="p.source"
            >
              {{ sourceLabel(p.source) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  ports: any[]
}>()

function sourceLabel(source: string) {
  const map: Record<string, string> = {
    docker: '容器',
    system: '系统',
    host: '主机',
  }
  return map[source] || ' — '
}
</script>

<style scoped>
.hot-ports-table {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

th {
  text-align: left;
  padding: 0.4rem 0.75rem;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-size: 0.68rem;
  letter-spacing: 0.03em;
}

td {
  padding: 0.3rem 0.75rem;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}

tr:last-child td {
  border-bottom: none;
}

.port-num {
  font-family: monospace;
  font-weight: 600;
}

.protocol-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.3rem;
  border-radius: var(--radius-sm);
  font-weight: 700;
}

.protocol-badge.tcp { color: var(--amber); }
.protocol-badge.udp { color: var(--cyan); }

.source-badge.docker { color: var(--cyan); }
.source-badge.system { color: var(--amber); }
.source-badge.host { color: var(--purple); }
</style>
