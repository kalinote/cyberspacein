<template>
  <main v-if="isMobile" class="mobile-forbidden">
    <Icon icon="mdi:shield-lock-outline" /><h1>暂无访问权限</h1><p>当前账号无法打开此页面。你可以进入已有权限的模块，或联系管理员调整权限。</p>
    <nav v-if="availableEntries.length" aria-label="可访问的页面"><router-link v-for="entry in availableEntries" :key="entry.path" :to="entry.path">{{ entry.label }}<Icon icon="mdi:chevron-right" /></router-link></nav>
    <router-link v-if="!getAuthState().accessToken" class="mobile-login-link" to="/login">返回登录</router-link>
  </main>
  <div v-else class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <el-card class="w-full max-w-md">
      <div class="flex flex-col items-center text-center">
        <div class="text-6xl font-bold text-red-500 leading-none mb-4">403</div>
        <h2 class="text-xl font-bold text-gray-900 mb-2">无权限访问</h2>
        <p class="text-gray-600 mb-6">当前账号没有访问该页面的权限。</p>
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { getAuthState } from '@/stores/auth'
import { PERM } from '@/utils/permissions'

defineOptions({ name: '403' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const availableEntries = computed(() => [
  { label: '工作台', path: '/', permission: PERM.pages.overview },
  { label: '信息检索', path: '/search', permission: PERM.pages.search },
  { label: '专题 Wiki', path: '/target/wiki', permission: PERM.pages.target.wiki },
  { label: '证据链', path: '/evidence', permission: PERM.pages.evidence },
  { label: '分析会话', path: '/agent/sessions', permission: PERM.pages.agent.sessions },
].filter(entry => getAuthState().accessToken && hasPerm(entry.permission.visible) && hasPerm(entry.permission.access)))
</script>

<style scoped>
.mobile-forbidden { padding: 40px 24px; min-height: calc(100dvh - 130px); background: #f8fafc; }
.mobile-forbidden > svg { font-size: 56px; color: #64748b; margin-bottom: 24px; }
.mobile-forbidden h1 { font-size: 24px; font-weight: 750; color: #0f172a; }
.mobile-forbidden p { color: #64748b; font-size: 14px; line-height: 1.8; margin-top: 16px; }
.mobile-forbidden nav { display: grid; gap: 10px; margin-top: 28px; }
.mobile-forbidden nav a { display: flex; align-items: center; justify-content: space-between; min-height: 54px; padding: 14px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; color: #2563eb; }
.mobile-login-link { display: block; margin-top: 24px; padding-block: 14px; color: #2563eb; }
</style>

