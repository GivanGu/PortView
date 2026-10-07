import { onBeforeUnmount } from 'vue'

const LONG_PRESS_MS = 450
const MOVE_TOLERANCE = 12
/** 长按弹出菜单后抬手仍会派发一次 click，短暂抑制它，避免顺带触发「打开服务」 */
let suppressUntil = 0

/** 刚发生过长按 → 紧随的 click 应被忽略 */
export function longPressSuppressed(): boolean {
  return Date.now() < suppressUntil
}

/**
 * 触摸端长按唤出菜单（桌面端仍走 contextmenu）。
 * 返回可直接绑到元素上的指针事件处理器；滚动开始会触发 pointercancel 自动取消计时。
 */
export function useLongPress(open: (x: number, y: number) => void) {
  let timer: ReturnType<typeof setTimeout> | null = null
  let startX = 0
  let startY = 0

  function cancel() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function onPointerdown(e: PointerEvent) {
    // 鼠标端不启用：右键已有原生菜单
    if (e.pointerType === 'mouse' || e.button !== 0) return
    startX = e.clientX
    startY = e.clientY
    cancel()
    timer = setTimeout(() => {
      timer = null
      suppressUntil = Date.now() + 800
      navigator.vibrate?.(8)
      open(startX, startY)
    }, LONG_PRESS_MS)
  }

  function onPointermove(e: PointerEvent) {
    if (!timer) return
    if (Math.abs(e.clientX - startX) > MOVE_TOLERANCE || Math.abs(e.clientY - startY) > MOVE_TOLERANCE) cancel()
  }

  // Android 长按会同时派发原生 contextmenu：已走原生路径就撤掉自建计时，避免重复弹出
  function onContextmenu() {
    cancel()
  }

  onBeforeUnmount(cancel)

  return {
    onPointerdown,
    onPointermove,
    onPointerup: cancel,
    onPointercancel: cancel,
    onContextmenu,
  }
}
