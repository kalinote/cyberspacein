import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Search from '../views/Search.vue'
import ActionMonitor from '../views/action/ActionMonitor.vue'
import Alert from '../views/Alert.vue'
import Platform from '../views/details/PlatformDetail.vue'
import NewActionBlueprint from '../views/action/NewActionBlueprint.vue'
import ActionResourceConfig from '../views/action/ActionResourceConfig.vue'
import ActionHistory from '../views/action/ActionHistory.vue'
import ActionDetail from '../views/action/ActionDetail.vue'
import ActionBlueprintList from '../views/action/ActionBlueprintList.vue'
import TaskManagement from '../views/action/TaskManagement.vue'
import TaskConfigManagement from '../views/action/TaskConfigManagement.vue'
import ComponentTaskManagement from '../views/action/ComponentTaskManagement.vue'
import AgentMonitor from '../views/agent/AgentMonitor.vue'
import AgentConfig from '../views/agent/AgentConfig.vue'
import AnalysisDetail from '../views/agent/AnalysisDetail.vue'
import AgentSessionList from '../views/agent/AgentSessionList.vue'
import TargetManagement from '../views/target/TargetManagement.vue'
import HighlightTargetList from '../views/target/HighlightTargetList.vue'
import WikiPageList from '../views/wiki/WikiPageList.vue'
import ArticleDetail from '../views/details/ArticleDetail.vue'
import ForumDetail from '../views/details/ForumDetail.vue'
import WikiDetail from '../views/details/WikiDetail.vue'
import PlatformList from '../views/platform/PlatformList.vue'
import SystemConfigHome from '../views/system/SystemConfigHome.vue'
import UserPermissionManagement from '../views/system/UserPermissionManagement.vue'
import Login from '../views/Login.vue'
import Forbidden from '../views/403.vue'
import { clearAuth, ensureMeInitialized, getAuthState } from '@/stores/auth'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'
import { refreshAuthContext } from '@/services/authContext'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login
    },
    {
      path: '/403',
      name: '403',
      component: Forbidden
    },
    {
      path: '/',
      name: 'home',
      component: Home,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.overview.access }
    },
    {
      path: '/search',
      name: 'search',
      component: Search,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.search.access }
    },
    {
      // 行动部署中心
      path: '/action',
      name: 'action-monitor',
      component: ActionMonitor,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.action.access }
    },
    {
      // 新建行动蓝图
      path: '/action/new',
      name: 'new-action-blueprint',
      component: NewActionBlueprint,
      meta: { requiresAuth: true, pagePermission: PERM.pages.action.create.access }
    },
    {
      // 行动资源配置
      path: '/action/resource-config',
      name: 'action-resource-config',
      component: ActionResourceConfig,
      meta: { requiresAuth: true, pagePermission: PERM.pages.action.resource.access }
    },
    {
      // 历史行动
      path: '/action/history',
      name: 'action-history',
      component: ActionHistory,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.action.history.access }
    },
    {
      // 行动蓝图列表
      path: '/action/blueprints',
      name: 'action-blueprint-list',
      component: ActionBlueprintList,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.action.blueprints.access }
    },
    {
      // 任务管理
      path: '/action/tasks',
      name: 'task-management',
      component: TaskManagement,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.action.tasks.access }
    },
    {
      // 基础组件任务配置管理
      path: '/action/task-configs',
      name: 'task-config-management',
      component: TaskConfigManagement,
      meta: { requiresAuth: true, pagePermission: PERM.pages.action.tasks.access }
    },
    {
      // 组件任务管理
      path: '/action/component-tasks',
      name: 'component-task-management',
      component: ComponentTaskManagement,
      meta: { requiresAuth: true, pagePermission: PERM.pages.action.tasks.access }
    },
    {
      // 行动详情
      path: '/action/:id',
      name: 'action-detail',
      component: ActionDetail,
      meta: { requiresAuth: true, pagePermission: PERM.pages.action.detail.access }
    },
    {
      path: '/system',
      name: 'system-config-home',
      component: SystemConfigHome,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.system.access }
    },
    {
      path: '/system/permissions',
      name: 'system-permissions',
      component: UserPermissionManagement,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.system.permissions.access }
    },
    {
      // 告警信息
      path: '/alert',
      name: 'alert',
      component: Alert,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.system.alert.access }
    },
    {
      // 目标管理
      path: '/target',
      name: 'target-management',
      component: TargetManagement,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.target.access }
    },
    {
      // 重点实体库
      path: '/target/highlights',
      name: 'highlight-target-list',
      component: HighlightTargetList,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.target.highlights.access }
    },
    {
      path: '/target/wiki',
      name: 'wiki-page-list',
      component: WikiPageList,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.target.wiki.access }
    },
    {
      // 分析引擎
      path: '/agent',
      name: 'agent-monitor',
      component: AgentMonitor,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.agent.access }
    },
    {
      // 配置分析引擎
      path: '/agent/engine-config',
      name: 'agent-engine-config',
      component: AgentConfig,
      meta: { requiresAuth: true, pagePermission: PERM.pages.agent.config.access }
    },
    {
      path: '/agent/sessions',
      name: 'agent-session-list',
      component: AgentSessionList,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.agent.sessions.access }
    },
    {
      // 分析详情
      path: '/agent/analysis/:sessionId',
      name: 'agent-analysis-detail',
      component: AnalysisDetail,
      meta: { requiresAuth: true, pagePermission: PERM.pages.agent.analysis.access }
    },
    {
      // 平台详情页
      path: '/details/platform/:id',
      name: 'platform',
      component: Platform,
      meta: { requiresAuth: true, pagePermission: PERM.pages.search.access }
    },
    {
      // 文章详情页
      path: '/details/article/:uuid',
      name: 'article-detail',
      component: ArticleDetail,
      meta: { requiresAuth: true, pagePermission: PERM.pages.search.access }
    },
    {
      // 论坛详情页
      path: '/details/forum/:uuid',
      name: 'forum-detail',
      component: ForumDetail,
      meta: { requiresAuth: true, pagePermission: PERM.pages.search.access }
    },
    {
      path: '/details/wiki/:id',
      name: 'wiki-detail',
      component: WikiDetail,
      meta: { requiresAuth: true, pagePermission: PERM.pages.target.wiki.access }
    },
    {
      // 平台列表页
      path: '/platforms',
      name: 'platform-list',
      component: PlatformList,
      meta: { keepAlive: true, requiresAuth: true, pagePermission: PERM.pages.search.access }
    },

  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

router.beforeEach(async (to) => {
  const requiresAuth = Boolean(to.meta?.requiresAuth)
  if (!requiresAuth) return true

  if (to.path === '/login' || to.path === '/403') return true

  const token = getAuthState().accessToken
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  try {
    await ensureMeInitialized(refreshAuthContext)
  } catch (e) {
    clearAuth()
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const pagePermission = to.meta?.pagePermission
  if (typeof pagePermission !== 'string' || !hasPerm(pagePermission)) {
    return { path: '/403' }
  }

  return true
})

window.addEventListener('csi:auth-refreshed', () => {
  const current = router.currentRoute.value
  const pagePermission = current.meta?.pagePermission
  if (current.meta?.requiresAuth && (!pagePermission || !hasPerm(pagePermission))) {
    router.replace('/403').catch(() => {})
  }
})

export default router

