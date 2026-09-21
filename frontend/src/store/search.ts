import { ref, readonly, type Ref } from 'vue'

/** 导航页签（与 App.vue 的 navItems 一一对应）。 */
export type Tab = 'overview' | 'favorites' | 'ports' | 'notes' | 'hidden' | 'settings'

/** 顶栏全局搜索的共享状态。
 * query 由顶栏输入框写入；各视图 watch 它后按当前页激活状态执行过滤。
 * activeTab 由 App.vue 切页时写入，作为各视图的守卫（v-show 保活视图防止隐藏页响应搜索）。
 * shakeNonce 自增 → 顶栏播放一次抖动（当前页无匹配）。
 * boxes + focusNonce：非搜索页（概览/设置/隐藏）的聚焦动画目标矩形（视口坐标）。
 */
const query: Ref<string> = ref('')
const activeTab: Ref<Tab> = ref('overview')
const shakeNonce = ref(0)

export interface FocusBox {
  x: number
  y: number
  w: number
  h: number
  /** 多个命中时依次错开出现（ms） */
  delay: number
}
const boxes: Ref<FocusBox[]> = ref([])
const focusNonce = ref(0)

function setQuery(v: string) {
  query.value = v
}

function clear() {
  query.value = ''
}

function setActiveTab(tab: Tab) {
  activeTab.value = tab
}

function shake() {
  shakeNonce.value++
}

function setFocusBoxes(list: FocusBox[]) {
  boxes.value = list
  focusNonce.value++
}

export function useSearch() {
  return {
    query: readonly(query),
    activeTab: readonly(activeTab),
    shakeNonce: readonly(shakeNonce),
    boxes: readonly(boxes),
    focusNonce: readonly(focusNonce),
    setQuery,
    clear,
    setActiveTab,
    shake,
    setFocusBoxes,
  }
}

export default useSearch
