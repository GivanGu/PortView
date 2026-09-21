import { watch, type Ref } from 'vue'
import { useSearch, type Tab } from '@/store/search'

/** 非搜索页（概览/设置/隐藏端口）的「关键词聚焦」动画驱动。
 * 在页面根元素上调用：useSearchFocus(rootRef, 'overview')。
 * 页面内给可定位的卡片/行元素加 data-sfocus 属性，
 * 搜索词命中其文本（标题+提示+当前值）时：滚动到第一个命中元素，
 * 把全部命中元素的视口矩形交给 overlay 播放「四边生长→定格→消失」动画。
 * 无匹配 → 顶栏抖动一次。
 */
export function useSearchFocus(rootRef: Ref<HTMLElement | null>, tab: Tab) {
  const { query, activeTab, setFocusBoxes, shake } = useSearch()
  let timer: ReturnType<typeof setTimeout> | null = null

  watch(
    [query, activeTab],
    () => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      // 仅当前激活页响应（v-show 保活视图，隐藏页不能抢动画）
      if (activeTab.value !== tab) return
      const q = query.value.trim().toLowerCase()
      if (!q) return
      timer = setTimeout(() => {
        timer = null
        const root = rootRef.value
        if (!root) return
        const hits = Array.from(root.querySelectorAll<HTMLElement>('[data-sfocus]')).filter(
          (el) => (el.textContent || '').toLowerCase().includes(q),
        )
        if (hits.length === 0) {
          shake()
          return
        }
        // 先滚动到第一个命中元素，等滚动落定后再取矩形（滚动中 rect 会漂移）
        hits[0].scrollIntoView({ behavior: 'smooth', block: 'center' })
        setTimeout(() => {
          setFocusBoxes(
            hits.map((el, i) => {
              const r = el.getBoundingClientRect()
              return { x: r.left, y: r.top, w: r.width, h: r.height, delay: i * 100 }
            }),
          )
        }, 350)
      }, 300)
    },
    { immediate: true },
  )
}
