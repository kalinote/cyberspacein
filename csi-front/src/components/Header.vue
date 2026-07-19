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
            <router-link
              v-if="canViewOverview"
              :to="canAccessOverview ? '/' : route.fullPath"
              class="text-gray-600 hover:text-blue-600 font-medium px-4 py-2 rounded-md hover:bg-blue-50 transition-colors"
              :class="!canAccessOverview ? 'text-gray-400 bg-gray-50 cursor-not-allowed' : ''"
              active-class="!text-blue-600 !bg-blue-50"
              @click="guardNav(canAccessOverview, $event)"
            >概览</router-link>
            <router-link
              v-if="canViewSearch"
              :to="canAccessSearch ? '/search' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/search' ? 'text-blue-600! bg-blue-50!' : '',
                canAccessSearch
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="guardNav(canAccessSearch, $event)"
            >
              检索
            </router-link>
            <div
              v-if="canViewAction"
              class="relative"
              @mouseenter="showActionDropdown = true"
              @mouseleave="showActionDropdown = false"
            >
              <router-link
                :to="canAccessAction ? '/action' : route.fullPath"
                class="font-medium px-4 py-2 rounded-md transition-colors flex items-center space-x-1"
                :class="[
                  route.path.startsWith('/action') ? 'text-blue-600! bg-blue-50!' : '',
                  canAccessAction
                    ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                    : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                ]"
                @click="guardNav(canAccessAction, $event)"
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
                    v-if="canViewActionTask"
                    :to="canAccessActionTask ? '/action/tasks' : route.fullPath"
                    class="block px-4 py-2 transition-colors"
                    :class="[
                      route.path === '/action/tasks' ? 'text-blue-600 bg-blue-50' : '',
                      canAccessActionTask
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click="canAccessActionTask ? (showActionDropdown = false) : null"
                    @click.capture="guardNav(canAccessActionTask, $event)"
                  >
                    基础组件任务
                  </router-link>
                </div>
              </transition>
            </div>
            <router-link
              v-if="canViewTarget"
              :to="canAccessTarget ? '/target' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/target' ? 'text-blue-600! bg-blue-50!' : '',
                canAccessTarget
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="guardNav(canAccessTarget, $event)"
            >
              目标管理
            </router-link>
            <router-link
              v-if="canViewAgent"
              :to="canAccessAgent ? '/agent' : route.fullPath"
              class="font-medium px-4 py-2 rounded-md transition-colors"
              :class="[
                route.path === '/agent' ? 'text-blue-600! bg-blue-50!' : '',
                canAccessAgent
                  ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
                  : 'text-gray-400 bg-gray-50 cursor-not-allowed'
              ]"
              @click="guardNav(canAccessAgent, $event)"
            >
              分析引擎
            </router-link>
            <div
              v-if="canViewSystemMenu"
              class="relative"
              @mouseenter="showSystemDropdown = true"
              @mouseleave="showSystemDropdown = false"
            >
              <router-link
                :to="canAccessSystemMenu ? '/system' : route.fullPath"
                class="text-gray-600 hover:text-blue-600 font-medium px-4 py-2 rounded-md hover:bg-blue-50 transition-colors flex items-center space-x-1"
                :class="isSystemNavActive ? 'text-blue-600! bg-blue-50!' : ''"
                @click="guardNav(canAccessSystemMenu, $event)"
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
                    v-if="canViewAlert"
                    :to="canAccessAlert ? '/alert' : route.fullPath"
                    class="block px-4 py-2 transition-colors whitespace-nowrap"
                    :class="[
                      route.path === '/alert' ? 'text-blue-600 bg-blue-50' : '',
                      canAccessAlert
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click="canAccessAlert ? (showSystemDropdown = false) : null"
                    @click.capture="guardNav(canAccessAlert, $event)"
                  >
                    告警信息
                  </router-link>
                  <router-link
                    v-if="canViewSystemPermissions"
                    :to="canAccessSystemPermissions ? '/system/permissions' : route.fullPath"
                    class="block px-4 py-2 transition-colors whitespace-nowrap"
                    :class="[
                      route.path === '/system/permissions' ? 'text-blue-600 bg-blue-50' : '',
                      canAccessSystemPermissions
                        ? 'text-gray-600 hover:text-blue-600 hover:bg-blue-50 cursor-pointer'
                        : 'text-gray-400 bg-gray-50 cursor-not-allowed'
                    ]"
                    @click="canAccessSystemPermissions ? (showSystemDropdown = false) : null"
                    @click.capture="guardNav(canAccessSystemPermissions, $event)"
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
              v-if="canViewSearch"
              v-model="quickSearchQuery"
              placeholder="快速检索..."
              :prefix-icon="'Search'"
              :disabled="!canQuickSearch"
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
import { noPerm, hasPerm } from '@/utils/permissionKit'

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

const canViewOverview = computed(() => hasPerm(PERM.pages.overview.visible))
const canAccessOverview = computed(() => hasPerm(PERM.pages.overview.access))
const canViewSearch = computed(() => hasPerm(PERM.pages.search.visible))
const canAccessSearch = computed(() => hasPerm(PERM.pages.search.access))
const canQuickSearch = computed(() => (
  canAccessSearch.value && hasPerm(PERM.operations.search.entity.execute)
))
const canViewActionTask = computed(() => hasPerm(PERM.pages.action.tasks.visible))
const canViewAction = computed(() => hasPerm(PERM.pages.action.visible) || canViewActionTask.value)
const canAccessAction = computed(() => hasPerm(PERM.pages.action.access))
const canAccessActionTask = computed(() => hasPerm(PERM.pages.action.tasks.access))
const canViewTarget = computed(() => hasPerm(PERM.pages.target.visible))
const canAccessTarget = computed(() => hasPerm(PERM.pages.target.access))
const canViewAgent = computed(() => hasPerm(PERM.pages.agent.visible))
const canAccessAgent = computed(() => hasPerm(PERM.pages.agent.access))
const canViewSystemConfig = computed(() => hasPerm(PERM.pages.system.config.visible))
const canAccessSystemConfig = computed(() => hasPerm(PERM.pages.system.config.access))
const canViewAlert = computed(() => hasPerm(PERM.pages.system.alert.visible))
const canAccessAlert = computed(() => hasPerm(PERM.pages.system.alert.access))
const canViewSystemPermissions = computed(() => hasPerm(PERM.pages.system.permissions.visible))
const canAccessSystemPermissions = computed(() => hasPerm(PERM.pages.system.permissions.access))
const canViewSystemMenu = computed(() => (
  hasPerm(PERM.pages.system.visible) || canViewSystemConfig.value || canViewAlert.value || canViewSystemPermissions.value
))
const canAccessSystemMenu = computed(() => canAccessSystemConfig.value)

const displayUsername = computed(() => {
  const user = getAuthState().user
  return user?.display_name || user?.username || '未登录'
})

function handleQuickSearch() {
  if (!canQuickSearch.value) {
    noPerm()
    return
  }
  if (!quickSearchQuery.value || !quickSearchQuery.value.trim()) {
    return
  }
  router.push({
    path: '/search',
    query: { q: quickSearchQuery.value.trim() }
  })
  quickSearchQuery.value = ''
}

function guardNav(canAccess, e) {
  if (canAccess) return true
  try {
    e?.preventDefault?.()
    e?.stopPropagation?.()
  } catch {
  }
  noPerm()
  return false
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
