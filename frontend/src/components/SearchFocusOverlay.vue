<script setup lang="ts">
// 关键词聚焦动画层：在命中卡片四周播放「四边生长 → 定格 → 淡出」。
// 纯展示层，pointer-events: none，不拦截任何交互。
import { useSearch } from '@/store/search'

const { boxes, focusNonce } = useSearch()
</script>

<template>
  <Teleport to="body">
    <div v-if="boxes.length" class="sf-overlay">
      <!-- key 随 focusNonce 变化重挂载，确保每次搜索都重新播放动画 -->
      <div :key="focusNonce">
        <div
          v-for="(b, i) in boxes"
          :key="i"
          class="sf-box"
          :style="{ left: b.x + 'px', top: b.y + 'px', width: b.w + 'px', height: b.h + 'px', '--sf-delay': b.delay + 'ms' }"
        >
          <i class="sf-e sf-top"></i>
          <i class="sf-e sf-bottom"></i>
          <i class="sf-e sf-left"></i>
          <i class="sf-e sf-right"></i>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style>
.sf-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
}

.sf-box {
  position: absolute;
}

.sf-e {
  position: absolute;
  background: var(--accent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent) 70%, transparent);
}

.sf-top {
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  animation: sf-x 1.05s ease both;
  animation-delay: var(--sf-delay, 0ms);
}

.sf-bottom {
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  animation: sf-x 1.05s ease both;
  animation-delay: var(--sf-delay, 0ms);
}

.sf-left {
  top: 0;
  left: 0;
  bottom: 0;
  width: 2px;
  animation: sf-y 1.05s ease both;
  animation-delay: var(--sf-delay, 0ms);
}

.sf-right {
  top: 0;
  right: 0;
  bottom: 0;
  width: 2px;
  animation: sf-y 1.05s ease both;
  animation-delay: var(--sf-delay, 0ms);
}

@keyframes sf-x {
  0% {
    transform: scaleX(0);
    opacity: 1;
  }
  24% {
    transform: scaleX(1);
  }
  78% {
    opacity: 1;
  }
  100% {
    transform: scaleX(1);
    opacity: 0;
  }
}

@keyframes sf-y {
  0% {
    transform: scaleY(0);
    opacity: 1;
  }
  24% {
    transform: scaleY(1);
  }
  78% {
    opacity: 1;
  }
  100% {
    transform: scaleY(1);
    opacity: 0;
  }
}
</style>
