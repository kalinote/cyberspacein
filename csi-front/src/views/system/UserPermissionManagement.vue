<template>
  <ConfigCenterLayout
    title-prefix="用户"
    title-suffix="权限管理"
    subtitle="管理系统用户、权限组与页面级访问配置"
    sidebar-title="功能模块"
    :nav-items="permissionNavItems"
    v-model="activeTab"
    v-model:expanded-keys="expandedTabKeys"
  >
    <template #toolbar>
      <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
          <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <el-input
            v-if="activeTab === 'users' || activeTab === 'groups'"
            v-model="searchKeyword"
            placeholder="搜索"
            clearable
            class="w-64"
          >
            <template #prefix>
              <Icon icon="mdi:magnify" class="text-gray-400" />
            </template>
          </el-input>
          <el-button type="primary" @click="handleAdd">
            <template #icon>
              <Icon icon="mdi:plus" />
            </template>
            {{ addButtonLabel }}
          </el-button>
        </div>
      </div>
    </template>

    <div v-if="activeTab === 'users'" class="space-y-4">
      <div
        v-for="user in mockUserList"
        :key="user.uuid"
        class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4 flex-1 min-w-0">
            <div
              class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-linear-to-br from-blue-100 to-cyan-100"
            >
              <Icon icon="mdi:account" class="text-2xl text-blue-600" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="mb-2">
                <div class="flex flex-wrap items-baseline gap-2">
                  <h3 class="text-lg font-bold text-gray-900">{{ user.display_name }}</h3>
                  <span class="text-sm text-gray-500 font-mono">@{{ user.username }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2 mt-2">
                  <el-tag
                    size="small"
                    :type="user.enabled ? 'success' : 'info'"
                    effect="light"
                    class="border-0"
                  >
                    {{ user.enabled ? '已启用' : '已禁用' }}
                  </el-tag>
                  <el-tag
                    v-if="user.temporary_account"
                    size="small"
                    type="warning"
                    effect="light"
                    class="border-0"
                  >
                    临时账号
                  </el-tag>
                  <el-tag
                    v-for="role in user.groups"
                    :key="role"
                    size="small"
                    type="primary"
                    effect="plain"
                  >
                    {{ role }}
                  </el-tag>
                </div>
              </div>
              <p v-if="user.remark" class="text-sm text-gray-600 mb-3">{{ user.remark }}</p>
              <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <div class="flex items-center gap-2 min-w-0">
                  <Icon icon="mdi:email-outline" class="text-blue-500 shrink-0" />
                  <span class="text-gray-600 shrink-0">邮箱</span>
                  <span class="font-medium text-gray-900 truncate">{{ user.email }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:ip-network" class="text-green-500 shrink-0" />
                  <span class="text-gray-600">最近登录 IP</span>
                  <span class="font-mono text-xs text-gray-900">{{ user.login_ip || '-' }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:clock-outline" class="text-purple-500 shrink-0" />
                  <span class="text-gray-600">最近登录</span>
                  <span class="font-medium text-gray-900">{{ formatDateTime(user.login_date) }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:calendar-end" class="text-amber-500 shrink-0" />
                  <span class="text-gray-600">到期时间</span>
                  <span class="font-medium text-gray-900">{{ formatExpired(user.expired_at) }}</span>
                </div>
              </div>
              <div class="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
                <span>于 {{ formatDateTime(user.create_at) }} 由 {{ user.create_by }} 创建</span>
                <span>于 {{ formatDateTime(user.update_at) }} 由 {{ user.update_by }} 更新</span>
                <span class="font-mono text-gray-400 truncate max-w-full" :title="user.uuid">UUID {{ user.uuid }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <el-button type="primary" link>
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button type="primary" link>
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
          </div>
        </div>
      </div>
      <div
        v-if="mockUserList.length === 0"
        class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80"
      >
        <Icon icon="mdi:account-search-outline" class="text-6xl text-gray-300 mb-4" />
        <p class="text-gray-500">暂无匹配的用户</p>
      </div>
    </div>
    <div v-else-if="activeTab === 'groups'" class="space-y-4">
      <div
        v-for="group in mockGroupList"
        :key="group.uuid"
        class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4 flex-1 min-w-0">
            <div
              class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-linear-to-br from-indigo-100 to-blue-100"
            >
              <Icon icon="mdi:shield-account" class="text-2xl text-indigo-600" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="mb-2">
                <div class="flex flex-wrap items-baseline gap-2">
                  <h3 class="text-lg font-bold text-gray-900">{{ group.display_name }}</h3>
                  <span class="text-sm text-gray-500 font-mono">@{{ group.group_name }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2 mt-2">
                  <el-tag
                    size="small"
                    :type="group.enabled ? 'success' : 'info'"
                    effect="light"
                    class="border-0"
                  >
                    {{ group.enabled ? '已启用' : '已禁用' }}
                  </el-tag>
                </div>
              </div>
              <p v-if="group.remark" class="text-sm text-gray-600 mb-3">{{ group.remark }}</p>
              <div class="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
                <span>于 {{ formatDateTime(group.create_at) }} 由 {{ group.create_by }} 创建</span>
                <span>于 {{ formatDateTime(group.update_at) }} 由 {{ group.update_by || '-' }} 更新</span>
                <span class="font-mono text-gray-400 truncate max-w-full" :title="group.uuid">UUID {{ group.uuid }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <el-button type="primary" link>
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button type="primary" link>
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
          </div>
        </div>
      </div>
      <div
        v-if="mockGroupList.length === 0"
        class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80"
      >
        <Icon icon="mdi:shield-search-outline" class="text-6xl text-gray-300 mb-4" />
        <p class="text-gray-500">暂无匹配的权限组</p>
      </div>
    </div>
    <div v-else-if="activeTab === 'abilities'" class="rounded-xl border border-dashed border-gray-200 bg-gray-50/80 p-12 text-center">
      <Icon icon="mdi:key-outline" class="text-5xl text-gray-300 mx-auto mb-4" />
      <p class="text-gray-600 font-medium">功能权限管理</p>
      <p class="text-sm text-gray-500 mt-2">功能开发中，敬请期待。</p>
    </div>
  </ConfigCenterLayout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import { formatDateTime } from '@/utils/action'

defineOptions({ name: 'UserPermissionManagement' })

const activeTab = ref('users')
const expandedTabKeys = ref([])
const searchKeyword = ref('')

const mockUserList = [
  {
    uuid: '0cc175b9c0f1b6a831c399e269772661',
    create_by: 'system',
    create_at: '2026-03-09T21:00:41.998000',
    update_by: 'system',
    update_at: '2026-03-09T21:00:41.998000',
    remark: '管理员',
    username: 'admin',
    display_name: '管理员',
    email: 'admin@example.com',
    login_ip: '127.0.0.1',
    login_date: '2026-03-09T21:00:41.998000',
    enabled: true,
    temporary_account: false,
    expired_at: null,
    groups: ['d7afde3e7059cd0a0fe09eec4b0008cd']
  },
  {
    uuid: 'd7afde3e7059cd0a0fe09eec4b0008cd',
    create_by: 'admin',
    create_at: '2026-03-09T21:00:41.998000',
    update_by: 'admin',
    update_at: '2026-03-09T21:00:41.998000',
    remark: '游客',
    username: 'guest',
    display_name: '游客',
    email: 'guest@example.com',
    login_ip: '127.0.0.1',
    login_date: '2026-03-09T21:00:41.998000',
    enabled: true,
    temporary_account: true,
    expired_date: '2026-05-24T21:00:41.998000',
    roles: ['af060936763625676867426784642642']
  }
]

const mockGroupList = [
  {
    uuid: 'd7afde3e7059cd0a0fe09eec4b0008cd',
    create_by: 'system',
    create_at: '2026-03-09T21:00:41.998000',
    update_by: null,
    update_at: null,
    remark: '最高权限组',
    group_name: 'admin',
    display_name: '最高权限组',
    enabled: true
  },
  {
    uuid: 'af060936763625676867426784642642',
    create_by: 'admin',
    create_at: '2026-03-09T21:00:41.998000',
    update_by: null,
    update_at: null,
    remark: '临时使用，会过期',
    group_name: 'temporary',
    display_name: '临时权限组',
    enabled: true
  }
]

function formatExpired(dateStr) {
  if (!dateStr) return '永久有效'
  return formatDateTime(dateStr)
}

const permissionNavItems = [
  { key: 'users', label: '用户管理', icon: 'mdi:account-multiple' },
  { key: 'groups', label: '权限组管理', icon: 'mdi:shield-account' },
  { key: 'abilities', label: '功能权限管理', icon: 'mdi:key-outline' }
]

const currentTabMeta = computed(() => findNavItemByKey(permissionNavItems, activeTab.value))
const currentTabIcon = computed(() => currentTabMeta.value?.icon || 'mdi:help')
const currentTabLabel = computed(() => currentTabMeta.value?.label || '')

const addButtonLabel = computed(() => {
  const map = {
    users: '新增用户',
    groups: '新增权限组',
    abilities: '新增功能权限'
  }
  return map[activeTab.value] || '新增'
})

function handleAdd() {
  ElMessage.info(`${addButtonLabel.value}功能开发中`)
}
</script>
