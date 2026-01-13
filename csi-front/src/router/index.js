import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Search from '../views/Search.vue'
import ActionMonitor from '../views/action/ActionMonitor.vue'
import Alert from '../views/Alert.vue'
import Platform from '../views/details/PlatformDetail.vue'
import VideoEditor from '../views/VideoEditor.vue'
import NewActionBlueprint from '../views/action/NewActionBlueprint.vue'
import ActionResourceConfig from '../views/action/ActionResourceConfig.vue'
import ActionHistory from '../views/action/ActionHistory.vue'
import ActionDetail from '../views/action/ActionDetail.vue'
import AgentMonitor from '../views/agent/AgentMonitor.vue'
import TargetManagement from '../views/target/TargetManagement.vue'
import ArticleDetail from '../views/details/ArticleDetail.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home
    },
    {
      path: '/search',
      name: 'search',
      component: Search
    },
    {
      // 行动部署中心
      path: '/action',
      name: 'action-monitor',
      component: ActionMonitor
    },
    {
      // 新建行动蓝图
      path: '/action/new',
      name: 'new-action-blueprint',
      component: NewActionBlueprint
    },
    {
      // 行动资源配置
      path: '/action/resource-config',
      name: 'action-resource-config',
      component: ActionResourceConfig
    },
    {
      // 历史行动
      path: '/action/history',
      name: 'action-history',
      component: ActionHistory
    },
    {
      // 行动详情
      path: '/action/:id',
      name: 'action-detail',
      component: ActionDetail
    },
    {
      // 告警信息
      path: '/alert',
      name: 'alert',
      component: Alert
    },
    {
      // 目标管理
      path: '/target',
      name: 'target-management',
      component: TargetManagement
    },
    {
      // 智能体
      path: '/agent',
      name: 'agent-monitor',
      component: AgentMonitor
    },
    {
      // 视频编辑器
      path: '/video-editor',
      name: 'video-editor',
      component: VideoEditor
    },
    {
      // 平台详情页
      path: '/details/platform/:id',
      name: 'platform',
      component: Platform
    },
    {
      // 文章详情页
      path: '/details/article/:uuid',
      name: 'article-detail',
      component: ArticleDetail
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

export default router

