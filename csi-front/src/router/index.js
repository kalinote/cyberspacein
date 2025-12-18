import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Search from '../views/Search.vue'
import ActionMonitor from '../views/action/ActionMonitor.vue'
import Alert from '../views/Alert.vue'
import Platform from '../views/details/PlatformDetail.vue'
import VideoEditor from '../views/VideoEditor.vue'
import NewAction from '../views/action/NewAction.vue'
import ActionResourceConfig from '../views/action/ActionResourceConfig.vue'
import AgentMonitor from '../views/agent/AgentMonitor.vue'

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
      // 新建行动
      path: '/action/new',
      name: 'new-action',
      component: NewAction
    },
    {
      // 行动资源配置
      path: '/action/resource-config',
      name: 'action-resource-config',
      component: ActionResourceConfig
    },
    {
      // 告警信息
      path: '/alert',
      name: 'alert',
      component: Alert
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
      path: '/platform/:id',
      name: 'platform',
      component: Platform
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

