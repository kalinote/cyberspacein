<template>
  <header class="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-blue-100 transition-all duration-300">
    <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center">
          <div class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-linear-to-br from-blue-500 to-cyan-400 rounded-lg flex items-center justify-center">
              <Icon icon="mdi:database-search" class="text-white text-lg" />
            </div>
            <span class="text-xl font-bold text-gray-800">CyberSpace<span class="text-blue-500">IN</span></span>
          </div>

          <nav class="hidden md:flex ml-10 space-x-8">
            <router-link to="/" class="text-gray-600 hover:text-blue-600 font-medium px-4 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">概览</router-link>
            <router-link
              v-if="navSearch.canView"
              :to="navSearch.canUse ? '/search' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/search' ? 'text-blue-600! bg-blue-50!' : '',
                navSearch.canUse
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="navSearch.guardNav"
            >
              检索
            </router-link>
            <div
              v-if="navAction.canView"
              class="relative"
              @mouseenter="showActionDropdown = true"
              @mouseleave="showActionDropdown = false"
            >
              <router-link
                :to="navAction.canUse ? '/action' : route.fullPath"
                class="font-medium px-4 py-2 rounded-md transition-colors flex items-center space-x-1"
                :class="[
                  route.path.startsWith('/action') ? 'text-blue-600! bg-blue-50!' : '',
                  navAction.canUse
                    ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                    : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                ]"
                @click="navAction.guardNav"
              >
                <span>行动部署</span>
                <Icon icon="mdi:chevron-down" class="text-sm transition-transform" :class="showActionDropdown ? 'rotate-180' : ''" />
              </router-link>
              <transition
                enter-active-class="transition-all duration-200 ease-out"
                enter-from-class="opacity-0 -translate-y-2"
                enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition-all duration-150 ease-in"
                leave-from-class="opacity-100 translate-y-0"
                leave-to-class="opacity-0 -translate-y-2"
              >
                <div 
                  v-show="showActionDropdown"
                  class="absolute top-full left-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-blue-100 py-2 z-50"
                >
                  <router-link
                    v-if="navActionTask.canView"
                    :to="navActionTask.canUse ? '/action/tasks' : route.fullPath"
                    class="block px-4 py-2 transition-colors"
                    :class="[
                      route.path === '/action/tasks' ? 'text-blue-600 bg-blue-50' : '',
                      navActionTask.canUse
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click="navActionTask.canUse ? (showActionDropdown = false) : null"
                    @click.capture="navActionTask.guardNav"
                  >
                    基础组件任务
                  </router-link>
                </div>
              </transition>
            </div>
            <router-link
              v-if="navTarget.canView"
              :to="navTarget.canUse ? '/target' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/target' ? 'text-blue-600! bg-blue-50!' : '',
                navTarget.canUse
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="navTarget.guardNav"
            >
              目标管理
            </router-link>
            <router-link
              v-if="navAgent.canView"
              :to="navAgent.canUse ? '/agent' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/agent' ? 'text-blue-600! bg-blue-50!' : '',
                navAgent.canUse
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="navAgent.guardNav"
            >
              分析引擎
            </router-link>
            <a href="#" class="text-gray-600 hover:text-blue-600 font-medium px-4 py-2 rounded-md hover:bg-blue-50 transition-colors">报告</a>
            <div
              v-if="navSystemMenu.canView"
              class="relative"
              @mouseenter="showSystemDropdown = true"
              @mouseleave="showSystemDropdown = false"
            >
              <router-link
                to="/system"
                class="text-gray-600 hover:text-blue-600 font-medium px-4 py-2 rounded-md hover:bg-blue-50 transition-colors flex items-center space-x-1"
                :class="isSystemNavActive ? 'text-blue-600! bg-blue-50!' : ''"
              >
                <span>系统配置</span>
                <Icon icon="mdi:chevron-down" class="text-sm transition-transform" :class="showSystemDropdown ? 'rotate-180' : ''" />
              </router-link>
              <transition
                enter-active-class="transition-all duration-200 ease-out"
                enter-from-class="opacity-0 -translate-y-2"
                enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition-all duration-150 ease-in"
                leave-from-class="opacity-100 translate-y-0"
                leave-to-class="opacity-0 -translate-y-2"
              >
                <div
                  v-show="showSystemDropdown"
                  class="absolute top-full left-0 mt-1 min-w-48 bg-white rounded-lg shadow-lg border border-blue-100 py-2 z-50"
                >
                  <router-link
                    v-if="navAlert.canView"
                    :to="navAlert.canUse ? '/alert' : route.fullPath"
                    class="block px-4 py-2 transition-colors whitespace-nowrap"
                    :class="[
                      route.path === '/alert' ? 'text-blue-600 bg-blue-50' : '',
                      navAlert.canUse
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click="navAlert.canUse ? (showSystemDropdown = false) : null"
                    @click.capture="navAlert.guardNav"
                  >
                    告警信息
                  </router-link>
                  <router-link
                    v-if="navSystemPermissions.canView"
                    to="/system/permissions"
                    class="block px-4 py-2 transition-colors whitespace-nowrap"
                    :class="[
                      route.path === '/system/permissions' ? 'text-blue-600 bg-blue-50' : '',
                      navSystemPermissions.canUse
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click.prevent="navSystemPermissions.canUse ? (showSystemDropdown = false) : null"
                    @click.capture="navSystemPermissions.guardNav"
                  >
                    用户权限管理
                  </router-link>
                </div>
              </transition>
            </div>
          </nav>
        </div>

        <div class="flex items-center space-x-10">
          <div class="hidden md:block">
            <el-input
              v-model="quickSearchQuery"
              placeholder="快速检索..."
              :prefix-icon="'Search'"
              style="width: 200px"
              clearable
              @keyup.enter="handleQuickSearch"
            />
          </div>

          <el-dropdown trigger="click" @command="handleUserCommand" @visible-change="handleUserDropdownVisibleChange">
            <div class="flex items-center gap-3 cursor-pointer select-none">
              <div class="w-8 h-8 bg-linear-to-br from-blue-100 to-cyan-100 rounded-full flex items-center justify-center">
                <Icon icon="mdi:account" class="text-blue-600" />
              </div>
              <span class="hidden sm:inline text-sm font-medium text-gray-700 max-w-40 truncate">
                {{ displayUsername }}
              </span>
              <Icon
                icon="mdi:chevron-down"
                class="hidden sm:inline text-gray-500 transition-transform duration-200"
                :class="userDropdownVisible ? 'rotate-180' : ''"
              />
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { authApi } from '@/api/auth'
import { clearAuth, getAuthState } from '@/stores/auth'
import { PERM } from '@/utils/permissions'
import { makeViewUse } from '@/utils/permissionKit'

defineOptions({ name: 'Header' })

const router = useRouter()
const route = useRoute()
const showActionDropdown = ref(false)
const showSystemDropdown = ref(false)
const isSystemNavActive = computed(
  () => route.path.startsWith('/system') || route.path === '/alert'
)
const quickSearchQuery = ref('')
const userDropdownVisible = ref(false)

const navSearch = makeViewUse(PERM.pages.search.view, PERM.pages.search.use)
const navAction = makeViewUse(PERM.pages.action.view, PERM.pages.action.use)
const navActionTask = makeViewUse(PERM.pages.action.task.view, PERM.pages.action.task.use)
const navTarget = makeViewUse(PERM.pages.target.view, PERM.pages.target.use)
const navAgent = makeViewUse(PERM.pages.agent.view, PERM.pages.agent.use)
const navSystemMenu = makeViewUse(PERM.pages.system.view, PERM.pages.system.view)
const navAlert = makeViewUse(PERM.pages.system.alert.view, PERM.pages.system.alert.use)
const navSystemPermissions = makeViewUse(PERM.pages.system.permissions.view, PERM.pages.system.permissions.use)

const displayUsername = computed(() => {
  const user = getAuthState().user
  return user?.display_name || user?.username || '未登录'
})

function handleQuickSearch() {
  if (!quickSearchQuery.value || !quickSearchQuery.value.trim()) {
    return
  }
  router.push({
    path: '/search',
    query: { q: quickSearchQuery.value.trim() }
  })
  quickSearchQuery.value = ''
}

function handleUserDropdownVisibleChange(visible) {
  userDropdownVisible.value = visible
}

async function handleUserCommand(command) {
  if (command !== 'logout') return
  try {
    await authApi.logout()
  } catch {
  } finally {
    clearAuth()
    router.push('/login').catch(() => {})
  }
}
</script>
