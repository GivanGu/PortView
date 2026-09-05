<template>
  <div v-show="isActive" class="tab-pane">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  key: string
  label: string
  activeTab?: string
}>(), {
  activeTab: '',
})

const isActive = computed(() => props.activeTab === props.key)
</script>

<style scoped>
.tab-pane {
  height: 100%;
}
</style>
