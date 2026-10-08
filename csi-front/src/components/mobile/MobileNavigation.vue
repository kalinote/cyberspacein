<template>
  <header class="mobile-header">
    <button class="mobile-icon-button" aria-label="返回上一页" @click="goBack">
      <Icon icon="mdi:arrow-left" />
    </button>
    <div class="mobile-header-title"><span>CyberSpaceIN</span><strong>{{ pageTitle }}</strong></div>
    <button class="mobile-icon-button" aria-label="全部功能" @click="panel = 'all'">
      <Icon icon="mdi:view-grid-outline" />
    </button>
  </header>

  <nav v-show="!keyboardOpen" class="mobile-navigation" aria-label="移动主导航">
    <button v-if="hasPerm(PERM.pages.overview.visible)" :disabled="!hasPerm(PERM.pages.overview.access)" :class="{ active: route.path === '/' }" :aria-current="route.path === '/' ? 'page' : undefined" @click="router.push('/')">
      <Icon icon="mdi:view-dashboard-outline" /><span>工作台</span>
    </button>
    <button v-if="knowledgeEntries.length" :disabled="!intelligenceTarget" :class="{ active: intelligenceActive }" :aria-current="intelligenceActive ? 'page' : undefined" @click="intelligenceTarget && router.push(intelligenceTarget)">
      <Icon icon="mdi:text-search" /><span>情报</span>
    </button>
    <button v-if="taskEntries.length" :class="{ active: taskActive || panel === 'tasks' }" :aria-expanded="panel === 'tasks'" @click="panel = 'tasks'">
      <Icon icon="mdi:clipboard-pulse-outline" /><span>任务</span>
    </button>
    <button :class="{ active: panel === 'account' || route.path.startsWith('/system') }" :aria-expanded="panel === 'account'" @click="panel = 'account'">
      <Icon icon="mdi:account-circle-outline" /><span>我的</span>
    </button>
  </nav>

  <MobileSheet :model-value="Boolean(panel)" :title="panel === 'tasks' ? '任务与分析' : panel === 'account' ? '我的与设置' : '全部功能'" @update:model-value="value => { if (!value) panel = '' }">
    <div v-if="panel === 'account'" class="mobile-account">
      <Icon icon="mdi:account-circle" /><div><strong>{{ displayUsername }}</strong><p>按当前账号权限显示可用功能</p></div>
    </div>
    <section v-for="group in visibleGroups" :key="group.title" class="mobile-menu-group">
      <h2>{{ group.title }}</h2>
      <div class="mobile-menu-grid">
        <button v-for="entry in group.items" :key="entry.path" :disabled="!hasPerm(entry.permission.access)" @click="router.push(entry.path); panel = ''">
          <Icon :icon="entry.icon" /><span>{{ entry.label }}</span><Icon v-if="!hasPerm(entry.permission.access)" icon="mdi:lock-outline" class="mobile-menu-lock" />
        </button>
      </div>
    </section>
    <button v-if="panel === 'account'" class="mobile-logout" :disabled="loggingOut" @click="logout">{{ loggingOut ? '正在退出…' : '退出登录' }}</button>
  </MobileSheet>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { authApi } from '@/api/auth'
import { clearAuth, getAuthState } from '@/stores/auth'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { KNOWLEDGE_DESTINATIONS } from '@/utils/knowledgeNavigation'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileSheet from './MobileSheet.vue'

const router = useRouter()
const route = useRoute()
const { keyboardOpen } = useMobileViewport()
const panel = ref('')
const loggingOut = ref(false)
const groups = [
  { title: '情报与资料', kind: 'intelligence', items: [
    { label: '工作台', path: '/', icon: 'mdi:view-dashboard-outline', permission: PERM.pages.overview },
    { label: '信息检索', path: '/search', icon: 'mdi:text-search', permission: PERM.pages.search },
    { label: '平台来源', path: '/platforms', icon: 'mdi:web', permission: PERM.pages.search },
    { label: '资料库', path: '/target', icon: 'mdi:bookshelf', permission: PERM.pages.target },
    { label: '重点实体', path: '/target/highlights', icon: 'mdi:star-outline', permission: PERM.pages.target.highlights },
    { label: '专题 Wiki', path: '/target/wiki', icon: 'mdi:book-open-page-variant-outline', permission: PERM.pages.target.wiki },
    { label: '证据链', path: '/evidence', icon: 'mdi:graph-outline', permission: PERM.pages.evidence },
  ] },
  { title: '任务与分析', kind: 'tasks', items: [
    { label: '行动部署', path: '/action', icon: 'mdi:rocket-launch-outline', permission: PERM.pages.action },
    { label: '历史行动', path: '/action/history', icon: 'mdi:history', permission: PERM.pages.action.history },
    { label: '行动蓝图', path: '/action/blueprints', icon: 'mdi:file-tree-outline', permission: PERM.pages.action.blueprints },
    { label: '周期调度', path: '/action/tasks', icon: 'mdi:calendar-clock', permission: PERM.pages.action.tasks },
    { label: '分析引擎', path: '/agent', icon: 'mdi:brain', permission: PERM.pages.agent },
    { label: '分析会话', path: '/agent/sessions', icon: 'mdi:chat-processing-outline', permission: PERM.pages.agent.sessions },
    { label: '告警信息', path: '/alert', icon: 'mdi:bell-outline', permission: PERM.pages.system.alert },
  ] },
  { title: '配置与管理', kind: 'settings', items: [
    { label: '系统配置', path: '/system', icon: 'mdi:cog-outline', permission: PERM.pages.system.config },
    { label: '用户权限', path: '/system/permissions', icon: 'mdi:account-key-outline', permission: PERM.pages.system.permissions },
    { label: '行动资源', path: '/action/resource-config', icon: 'mdi:database-cog-outline', permission: PERM.pages.action.resource },
    { label: '引擎配置', path: '/agent/engine-config', icon: 'mdi:tune-variant', permission: PERM.pages.agent.config },
  ] },
]
const allowedGroups = computed(() => groups.map(group => ({ ...group, items: group.items.filter(entry => hasPerm(entry.permission.visible)) })).filter(group => group.items.length))
const taskEntries = computed(() => allowedGroups.value.find(group => group.kind === 'tasks')?.items ?? [])
const knowledgeEntries = computed(() => KNOWLEDGE_DESTINATIONS.filter(entry => hasPerm(entry.permission.visible)))
const intelligenceTarget = computed(() => knowledgeEntries.value.find(entry => hasPerm(entry.permission.access))?.path)
const visibleGroups = computed(() => allowedGroups.value.filter(group => panel.value !== 'tasks' || group.kind === 'tasks'))
const intelligenceActive = computed(() => /^\/(search|details|target|platforms|evidence)(\/|$)/.test(route.path))
const taskActive = computed(() => /^\/(action|agent|alert)(\/|$)/.test(route.path))
const displayUsername = computed(() => getAuthState().user?.display_name || getAuthState().user?.username || '当前用户')
const pageTitle = computed(() => {
  const entry = groups.flatMap(group => group.items).find(item => item.path === route.path)
  if (entry) return entry.label
  return {
    'article-detail': '文章阅读', 'forum-detail': '论坛阅读', 'platform': '平台详情',
    'wiki-detail': '专题详情', 'wiki-editor': '编辑专题', 'wiki-create': '新建专题', 'evidence-list': '证据链列表', 'evidence-editor': '证据链详情',
    'new-action-blueprint': '新建行动蓝图', 'edit-action-blueprint': '编辑行动蓝图',
    'action-detail': '行动详情', 'component-task-management': '组件任务', 'agent-analysis-detail': '分析详情', '403': '访问受限',
  }[route.name] || 'CyberSpaceIN'
})

watch(() => route.fullPath, () => { panel.value = '' })

/** """优先返回原页面，直接打开链接时退回有权限的入口。""" */
function goBack() {
  const back = window.history.state?.back
  if (typeof back === 'string' && back.startsWith('/')) {
    const previous = router.resolve(back)
    if (previous.matched.length && !['login', '403'].includes(previous.name)
      && (!previous.meta.requiresAuth || hasPerm(previous.meta.pagePermission))) {
      router.back()
      return
    }
  }
  const entries = groups.flatMap(group => group.items)
  const preferredPath = intelligenceActive.value ? '/search' : route.path.startsWith('/agent') ? '/agent/sessions' : '/'
  const fallback = [...entries.filter(entry => entry.path === preferredPath), ...entries]
    .find(entry => entry.path !== route.path && hasPerm(entry.permission.visible) && hasPerm(entry.permission.access))
  if (fallback) router.replace(fallback.path)
  else panel.value = 'all'
}

/** """退出账号并清理本地登录状态。""" */
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await authApi.logout()
  } catch {
    // 与桌面入口一致，服务不可用时仍清理本地会话。
  } finally {
    clearAuth()
    loggingOut.value = false
    router.push('/login')
  }
}
</script>

<style scoped>
.mobile-header { position: sticky; top: 0; z-index: 100; display: flex; align-items: center; justify-content: space-between; height: var(--mobile-header-height); padding: env(safe-area-inset-top) max(8px, env(safe-area-inset-right)) 0 max(8px, env(safe-area-inset-left)); background: #fff; border-bottom: 1px solid #e2e8f0; }
.mobile-icon-button { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 12px; color: #334155; font-size: 24px; }
.mobile-header-title { min-width: 0; text-align: center; display: flex; flex-direction: column; }
.mobile-header-title span { font-size: 10px; color: #64748b; letter-spacing: .08em; }
.mobile-header-title strong { font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mobile-navigation { position: fixed; z-index: 100; left: 0; right: 0; bottom: 0; height: var(--mobile-nav-height); display: flex; align-items: stretch; padding: 4px env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); background: rgb(255 255 255 / 98%); border-top: 1px solid #e2e8f0; }
.mobile-navigation button { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; color: #64748b; font-size: 11px; }
.mobile-navigation button svg { font-size: 23px; }
.mobile-navigation button.active { color: #2563eb; background: #eff6ff; border-radius: 12px; }
button:disabled { opacity: .45; cursor: not-allowed; }
button:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
.mobile-menu-group + .mobile-menu-group { margin-top: 24px; }
.mobile-menu-group h2 { margin: 0 0 10px; font-size: 13px; color: #64748b; }
.mobile-menu-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.mobile-menu-grid button { min-height: 52px; display: flex; align-items: center; gap: 9px; padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; font-size: 14px; text-align: left; }
.mobile-menu-grid svg { flex-shrink: 0; color: #2563eb; font-size: 20px; }
.mobile-menu-grid .mobile-menu-lock { font-size: 14px; color: #94a3b8; margin-left: auto; }
.mobile-account { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
.mobile-account > svg { font-size: 44px; color: #2563eb; }
.mobile-account strong { overflow-wrap: anywhere; }
.mobile-account p { margin: 4px 0 0; font-size: 12px; color: #64748b; }
.mobile-logout { display: block; width: 100%; min-height: 48px; margin-top: 24px; color: #dc2626; border: 1px solid #fecaca; border-radius: 12px; }
</style>
