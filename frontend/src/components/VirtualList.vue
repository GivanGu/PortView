<template>
  <div class="virtual-list" ref="parent">
    <div
      :style="{ height: `${virtualPadding}px`, width: '100%' }"
      class="virtual-list-phantom"
    />
    <div
      ref="scrollbarRef"
      class="virtual-list-content"
      :style="{ transform: `translateY(${virtualOffset}px)` }"
    >
      <div
        v-for="item in virtualItems"
        :key="item.key"
        :data-index="item.index"
        class="virtual-list-item"
        :style="{ height: `${item.size}px` }"
      >
        <slot :item="items[item.index]" :index="item.index" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 通用虚拟滚动列表 — 基于 @tanstack/vue-virtual
 *
 * Props:
 * - items: any[]        完整数据列表
 * - item-height: number  单项固定高度（默认 80px）
 * - key-field: string    用于 key 的字段名（默认 'id')
 * - overscan: number     预渲染项数（默认 5）
 * - class: string        额外类名
 */
import { ref, watch, onMounted, nextTick } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'

interface Props {
  items: any[]
  itemHeight?: number
  keyField?: string
  overscan?: number
}

const props = withDefaults(defineProps<Props>(), {
  itemHeight: 80,
  keyField: 'id',
  overscan: 5,
})

const parent = ref<HTMLElement | null>(null)
const scrollbarRef = ref<HTMLElement | null>(null)

const rowVirtualizer = useVirtualizer({
  count: props.items.length,
  getScrollElement: () => parent.value,
  estimateSize: () => props.itemHeight,
  overscan: props.overscan,
  getItemKey: (index) => {
    const item = props.items[index]
    return item?.[props.keyField] ?? index
  },
})

const virtualItems = rowVirtualizer.getVirtualItems(props.items.length)
const virtualOffset = virtualItems.length > 0 ? virtualItems[0].start : 0
const virtualPadding = props.items.length > 0
  ? rowVirtualizer.getTotalSize()
  : 0

// 监听 items 变化，触发重排
watch(
  () => props.items.length,
  () => {
    nextTick(() => rowVirtualizer.measure())
  },
)

onMounted(() => rowVirtualizer.measure())

defineExpose({
  scrollTo: rowVirtualizer.scrollToIndex,
  scrollToOffset: rowVirtualizer.scrollToOffset,
})
</script>

<style scoped>
.virtual-list {
  height: 100%;
  overflow: auto;
  position: relative;
}

.virtual-list-phantom {
  width: 100%;
  position: relative;
}

.virtual-list-content {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
}

.virtual-list-item {
  position: relative;
}
</style>
