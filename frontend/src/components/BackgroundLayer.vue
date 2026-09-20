<script setup lang="ts">
// v1.6.6：毛玻璃背景层。模糊/压暗做在图层上（一次），上层表面只半透明，
// 不用 backdrop-filter（省性能）。
// 默认 absolute 铺满父容器（父容器需 position:relative）；fixed=true 时铺满视口。
defineProps<{ src: string; fixed?: boolean }>()
</script>

<template>
  <img class="bg-layer" :class="{ 'bg-layer-fixed': fixed }" :src="src" alt="" draggable="false" />
</template>

<style scoped>
.bg-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: blur(10px) brightness(0.75);
  transform: scale(1.05); /* 抵消 blur 边缘透明 */
  pointer-events: none;
  z-index: 0;
}

.bg-layer-fixed {
  position: fixed;
}
</style>
