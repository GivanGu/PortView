/** 设备形态探测：与 style.css 的断点保持一致，供 JS 侧决定交互形态。 */

/** 窄屏断点（与 style.css 移动端段一致） */
export const NARROW_QUERY = '(max-width: 768px)'

/** 触摸端（无悬停能力）：悬停才显隐的操作必须改为常驻 */
export function isCoarsePointer(): boolean {
  return window.matchMedia('(hover: none), (pointer: coarse)').matches
}

export function isNarrow(): boolean {
  return window.matchMedia(NARROW_QUERY).matches
}
