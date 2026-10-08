import { computed, ref, watch } from 'vue'
import { getAuthState } from '@/stores/auth'
import { normalizeRecentVisit } from '@/utils/recentVisitPolicy'

const storageKey = 'csi_recent_visits_v1'
const entries = ref([])
const auth = getAuthState()

watch(() => [auth.sessionId, auth.accessToken, auth.user?.id], () => {
  entries.value = []
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
    if (auth.accessToken && auth.sessionId && saved?.sessionId === auth.sessionId && Array.isArray(saved.items)) {
      entries.value = saved.items.slice(0, 8)
    } else {
      sessionStorage.removeItem(storageKey)
    }
  } catch { /* 存储不可用时仅保留当前页面的访问记录。 */ }
}, { immediate: true, flush: 'sync' })

export const recentVisits = computed(() => auth.accessToken
  ? entries.value.map(item => normalizeRecentVisit(item, auth.permissions)).filter(Boolean)
  : [])

/** """按当前登录会话保存最近访问，最多保留八条且同一资源去重。""" */
export function rememberRecentVisit(route, title = '') {
  if (!auth.accessToken) return
  const item = normalizeRecentVisit(route, auth.permissions, title)
  if (!item) return
  const previous = recentVisits.value.find(entry => entry.key === item.key)
  if (!title && previous) item.title = previous.title
  entries.value = [item, ...recentVisits.value.filter(entry => entry.key !== item.key)].slice(0, 8)
  try {
    if (auth.sessionId) sessionStorage.setItem(storageKey, JSON.stringify({ sessionId: auth.sessionId, items: entries.value }))
  } catch { /* 存储不可用不影响页面跳转。 */ }
}

/** """清除当前浏览器标签页的最近访问记录。""" */
export function clearRecentVisits() {
  entries.value = []
  try { sessionStorage.removeItem(storageKey) } catch { /* 内存记录已清理。 */ }
}
