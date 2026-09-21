import { reactive, readonly, type DeepReadonly } from 'vue'

/** 收藏页状态栏计数器的共享状态。
 * FavoritesView 在数据/视图变化时写入；App.vue 状态栏右下角读取。
 * active 由 FavoritesView 按「当前页签是收藏页」守卫后写入，离开收藏页置 false。
 */
export interface FavStatus {
  /** 收藏页是否处于前台（状态栏是否显示计数器） */
  active: boolean
  /** 当前视图名称（分组名 / 全部 / 在线 / 离线） */
  group: string
  /** 当前视图条目总数 */
  total: number
  /** 当前视图离线数 */
  offline: number
  /** 当前视图在线数（含外部 URL） */
  online: number
}

const status: FavStatus = reactive({
  active: false,
  group: '',
  total: 0,
  offline: 0,
  online: 0,
})

function setFavStatus(partial: Partial<FavStatus>) {
  Object.assign(status, partial)
}

export function useFavStatus(): { status: DeepReadonly<FavStatus>; setFavStatus: typeof setFavStatus } {
  return { status: readonly(status), setFavStatus }
}

export default useFavStatus
