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
          <el-button
            v-if="activeTab !== 'abilities'"
            type="primary"
            @click="handleAdd"
          >
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
        v-for="user in userList"
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
                    v-for="groupUuid in user.groups"
                    :key="groupUuid"
                    size="small"
                    type="primary"
                    effect="plain"
                  >
                    {{ groupNameByUuid[groupUuid] || groupUuid }}
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
            <el-button type="primary" link @click="handleEditUser(user)">
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
          </div>
        </div>
      </div>
      <div
        v-if="userList.length === 0"
        class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80"
      >
        <Icon icon="mdi:account-search-outline" class="text-6xl text-gray-300 mb-4" />
        <p class="text-gray-500">暂无匹配的用户</p>
      </div>
    </div>
    <div v-else-if="activeTab === 'groups'" class="space-y-4">
      <div
        v-for="group in groupList"
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
        v-if="groupList.length === 0"
        class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80"
      >
        <Icon icon="mdi:shield-search-outline" class="text-6xl text-gray-300 mb-4" />
        <p class="text-gray-500">暂无匹配的权限组</p>
      </div>
    </div>
    <div v-else-if="activeTab === 'abilities'" class="text-left">
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
            <div class="min-w-0">
              <div class="text-base font-bold text-gray-900">功能权限管理</div>
              <div class="text-xs text-gray-500 mt-1">从权限目录选择权限码，并为权限组分配权限。</div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <el-input
                v-model="abilitySearchKeyword"
                placeholder="搜索权限（名称/权限码）"
                clearable
                class="w-72"
              >
                <template #prefix>
                  <Icon icon="mdi:magnify" class="text-gray-400" />
                </template>
              </el-input>
            </div>
          </div>

          <div class="grid grid-cols-12 gap-0">
            <div class="col-span-5 border-r border-gray-100 p-4">
              <div class="flex items-center justify-between mb-3">
                <div class="text-sm font-medium text-gray-700">权限目录</div>
                <div class="text-xs text-gray-400">共 {{ abilityCatalogStats.totalPerms }} 个权限码</div>
              </div>

              <div class="rounded-lg border border-gray-100 bg-white">
                <el-tree
                  ref="abilityTreeRef"
                  :data="abilityCatalogTree"
                  node-key="key"
                  :props="abilityTreeProps"
                  :default-expand-all="false"
                  :highlight-current="true"
                  :expand-on-click-node="true"
                  :filter-node-method="abilityFilterTreeNode"
                  @current-change="handleAbilityCurrentNodeChange"
                  class="ability-tree"
                >
                  <template #default="{ data }">
                    <div class="min-w-0">
                      <div class="flex items-center gap-2 min-w-0">
                        <Icon :icon="data.icon || 'mdi:key-outline'" class="text-gray-400 shrink-0" />
                        <span class="text-sm text-gray-800 truncate">{{ data.label }}</span>
                      </div>
                      <div v-if="data.permKey" class="text-[11px] text-gray-400 font-mono truncate mt-0.5">
                        {{ data.permKey }}
                      </div>
                    </div>
                  </template>
                </el-tree>
              </div>
              <div v-if="abilitySearchEmptyHint" class="mt-3 text-xs text-gray-500">
                {{ abilitySearchEmptyHint }}
              </div>

              <div v-if="abilityCatalogStats.missingPerms.length > 0" class="mt-3 text-xs text-amber-600">
                检测到 {{ abilityCatalogStats.missingPerms.length }} 个权限码未在目录中定义：{{ abilityCatalogStats.missingPerms.slice(0, 3).join('、') }}<span v-if="abilityCatalogStats.missingPerms.length > 3"> 等</span>
              </div>
            </div>

            <div class="col-span-7 p-4">
              <div class="flex items-start justify-between gap-4 mb-3">
                <div class="min-w-0">
                  <div class="text-sm font-medium text-gray-700">权限分配</div>
                  <div class="text-xs text-gray-500 mt-1">
                    当前权限组：<span class="font-medium text-gray-800">{{ currentAbilityGroupLabel }}</span>
                  </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <el-button :disabled="!abilityCanEdit" @click="handleAbilityReset">重置</el-button>
                  <el-button type="primary" :disabled="!abilityCanEdit" :loading="abilitySaving" @click="handleAbilitySave">保存</el-button>
                </div>
              </div>

              <div class="bg-gray-50/70 rounded-lg border border-gray-100 p-4 mb-4">
                <div class="flex flex-wrap items-center gap-3">
                  <el-select
                    v-model="abilitySelectedGroupUuid"
                    filterable
                    placeholder="请选择权限组"
                    class="w-72"
                  >
                    <el-option
                      v-for="g in abilityGroupsForSelect"
                      :key="g.uuid"
                      :label="g.display_name || g.group_name || g.uuid"
                      :value="g.uuid"
                    />
                  </el-select>
                  <div class="text-xs text-gray-500">
                    已选权限：<span class="font-medium text-gray-800">{{ abilitySelectedPermSetSize }}</span>
                    <span v-if="abilityLastSavedAt" class="ml-3 text-gray-400">上次保存：{{ formatDateTime(abilityLastSavedAt) }}</span>
                  </div>
                </div>
                <div v-if="abilityGroupsForSelect.length === 0" class="mt-3 text-xs text-gray-500">
                  暂无可用权限组，请先在“权限组管理”中创建权限组。
                </div>
                <div v-if="abilityGroupHasWildcard" class="mt-3 text-xs text-blue-600">
                  当前权限组包含 <span class="font-mono">*</span>，视为拥有全部权限；此页暂不支持编辑该组的权限明细。
                </div>
              </div>

              <div v-if="!abilitySelectedGroupUuid" class="rounded-lg border border-dashed border-gray-200 bg-white p-10 text-center">
                <Icon icon="mdi:account-cog-outline" class="text-5xl text-gray-300 mx-auto mb-4" />
                <div class="text-sm font-medium text-gray-700">请先选择一个权限组</div>
                <div class="text-xs text-gray-500 mt-2">选择后即可在右侧为该组勾选权限码。</div>
              </div>
              <div v-else-if="abilityPermsInCurrentNode.length === 0" class="rounded-lg border border-dashed border-gray-200 bg-white p-10 text-center">
                <Icon icon="mdi:key-remove-outline" class="text-5xl text-gray-300 mx-auto mb-4" />
                <div class="text-sm font-medium text-gray-700">未选择权限节点</div>
                <div class="text-xs text-gray-500 mt-2">请在左侧权限目录中选择一个模块或具体权限码。</div>
              </div>
              <div v-else class="bg-white rounded-xl border border-gray-200 shadow-sm">
                <div class="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
                  <div class="min-w-0">
                    <div class="text-sm font-bold text-gray-900 truncate">{{ abilityCurrentNodeTitle }}</div>
                    <div class="text-xs text-gray-500 mt-1 truncate">{{ abilityCurrentNodeSubTitle }}</div>
                  </div>
                  <div class="text-xs text-gray-400 shrink-0">
                    共 {{ abilityPermsInCurrentNode.length }} 项
                  </div>
                </div>
                <div class="p-4">
                  <div class="space-y-2">
                    <div
                      v-for="perm in abilityPermsInCurrentNode"
                      :key="perm.permKey"
                      class="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:border-blue-100 hover:bg-blue-50/30 transition-colors"
                    >
                      <el-checkbox
                        :model-value="abilityIsPermChecked(perm.permKey)"
                        :disabled="!abilityCanEdit || abilityGroupHasWildcard"
                        @change="(val) => abilityTogglePerm(perm.permKey, val)"
                      />
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                          <div class="text-sm font-medium text-gray-900">{{ perm.name }}</div>
                          <el-tag v-for="t in perm.tags || []" :key="t" size="small" type="info" effect="light" class="border-0">
                            {{ t }}
                          </el-tag>
                        </div>
                        <div class="text-xs text-gray-500 mt-1">
                          <span class="font-mono text-gray-400">{{ perm.permKey }}</span>
                          <span v-if="perm.desc" class="ml-2">{{ perm.desc }}</span>
                        </div>
                      </div>
                      <el-button
                        v-if="perm.docs"
                        type="primary"
                        link
                        :disabled="!perm.docs"
                        @click="handleAbilityOpenDocs(perm.docs)"
                      >
                        <template #icon>
                          <Icon icon="mdi:open-in-new" />
                        </template>
                        说明
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
      </div>
    </div>
  </ConfigCenterLayout>

  <el-dialog v-model="editUserDialogVisible" title="编辑用户" width="520px">
    <div v-if="editingUser" class="space-y-4">
      <div class="text-sm text-gray-600">
        用户：{{ editingUser.display_name }}（@{{ editingUser.username }}）
      </div>

      <el-form label-width="80px">
        <el-form-item label="用户组">
          <el-select
            v-model="editUserGroupUuids"
            multiple
            placeholder="请选择用户组"
            class="w-full"
          >
            <el-option
              v-for="group in groupList"
              :key="group.uuid"
              :label="group.display_name || group.group_name"
              :value="group.uuid"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="editUserDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="savingEditUser" @click="handleSaveEditUser">
        保存
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createUserDialogVisible" title="新增用户" width="560px">
    <el-form ref="createUserFormRef" :model="createUserForm" :rules="createUserRules" label-width="100px">
      <el-form-item label="用户名" prop="username">
        <el-input v-model="createUserForm.username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="createUserForm.password" type="password" show-password placeholder="请输入密码" />
      </el-form-item>
      <el-form-item label="显示名称" prop="display_name">
        <el-input v-model="createUserForm.display_name" placeholder="请输入显示名称" />
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="createUserForm.email" placeholder="请输入邮箱（可选）" />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input v-model="createUserForm.remark" type="textarea" :rows="2" placeholder="请输入备注（可选）" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="createUserForm.enabled" />
      </el-form-item>
      <el-form-item label="临时账号">
        <el-switch v-model="createUserForm.temporary_account" />
      </el-form-item>
      <el-form-item label="到期时间" prop="expired_at">
        <el-date-picker
          v-model="createUserForm.expired_at"
          type="datetime"
          placeholder="请选择到期时间（可选）"
          class="w-full"
          value-format="YYYY-MM-DDTHH:mm:ss.SSSZ"
        />
      </el-form-item>
      <el-form-item label="用户组" prop="groups">
        <el-select v-model="createUserForm.groups" multiple placeholder="请选择用户组（可选）" class="w-full">
          <el-option
            v-for="group in groupList"
            :key="group.uuid"
            :label="group.display_name || group.group_name"
            :value="group.uuid"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="createUserDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="creatingUser" @click="handleSubmitCreateUser">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createGroupDialogVisible" title="新增权限组" width="560px">
    <el-form ref="createGroupFormRef" :model="createGroupForm" :rules="createGroupRules" label-width="100px">
      <el-form-item label="组标识" prop="group_name">
        <el-input v-model="createGroupForm.group_name" placeholder="例如：admin、analyst（唯一）" />
      </el-form-item>
      <el-form-item label="展示名称" prop="display_name">
        <el-input v-model="createGroupForm.display_name" placeholder="请输入展示名称" />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input v-model="createGroupForm.remark" type="textarea" :rows="2" placeholder="请输入备注（可选）" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="createGroupForm.enabled" />
      </el-form-item>
      <el-form-item label="权限码" prop="permissions">
        <el-select
          v-model="createGroupForm.permissions"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="输入权限码后回车添加（可选）"
          class="w-full"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="createGroupDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="creatingGroup" @click="handleSubmitCreateGroup">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import { formatDateTime } from '@/utils/action'
import { systemApi } from '@/api/system'

defineOptions({ name: 'UserPermissionManagement' })

const activeTab = ref('users')
const expandedTabKeys = ref([])
const searchKeyword = ref('')

const userList = ref([])
const groupList = ref([])

const editUserDialogVisible = ref(false)
const editingUser = ref(null)
const editUserGroupUuids = ref([])
const savingEditUser = ref(false)

const createUserDialogVisible = ref(false)
const creatingUser = ref(false)
const createUserFormRef = ref(null)
const createUserForm = reactive({
  username: '',
  password: '',
  display_name: '',
  email: '',
  remark: '',
  enabled: true,
  temporary_account: false,
  expired_at: '',
  groups: []
})
const createUserRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }]
}

const createGroupDialogVisible = ref(false)
const creatingGroup = ref(false)
const createGroupFormRef = ref(null)
const createGroupForm = reactive({
  group_name: '',
  display_name: '',
  remark: '',
  enabled: true,
  permissions: []
})
const createGroupRules = {
  group_name: [{ required: true, message: '请输入组标识', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入展示名称', trigger: 'blur' }]
}

const groupNameByUuid = computed(() => {
  const map = {}
  for (const group of groupList.value) {
    map[group.uuid] = group.display_name || group.group_name || group.uuid
  }
  return map
})

const ABILITY_STORAGE_KEY = 'csi_ability_group_permissions_v1'

const abilitySaving = ref(false)
const abilitySearchKeyword = ref('')
const abilityTreeRef = ref(null)
const abilitySelectedGroupUuid = ref('')
const abilityLastSavedAt = ref('')

const abilityGroupPermissionDraftMap = ref({})

const abilityCatalogTree = [
  {
    key: 'module:system',
    label: '系统配置',
    icon: 'mdi:cog-outline',
    children: [
      {
        key: 'page:system:permissions',
        label: '用户与权限管理页',
        icon: 'mdi:account-key-outline',
        permKey: 'page:system:permissions',
        perm: {
          permKey: 'page:system:permissions',
          name: '进入“用户权限管理”页面',
          desc: '控制是否可进入系统配置中的用户权限管理页面',
          tags: ['可见']
        }
      },
      {
        key: 'module:system:user',
        label: '用户管理',
        icon: 'mdi:account-multiple-outline',
        children: [
          {
            key: 'system:user:view',
            label: '查看用户',
            permKey: 'system:user:view',
            perm: { permKey: 'system:user:view', name: '查看用户', desc: '访问用户列表与查看用户信息', tags: ['可见'] }
          },
          {
            key: 'system:user:create',
            label: '新增用户',
            permKey: 'system:user:create',
            perm: { permKey: 'system:user:create', name: '新增用户', desc: '创建系统用户', tags: ['可用'] }
          },
          {
            key: 'system:user:edit',
            label: '编辑用户',
            permKey: 'system:user:edit',
            perm: { permKey: 'system:user:edit', name: '编辑用户', desc: '修改用户信息与用户组', tags: ['可用'] }
          },
          {
            key: 'system:user:disable',
            label: '禁用用户',
            permKey: 'system:user:disable',
            perm: { permKey: 'system:user:disable', name: '禁用用户', desc: '启用/禁用系统用户', tags: ['可用'] }
          }
        ]
      },
      {
        key: 'module:system:group',
        label: '权限组管理',
        icon: 'mdi:shield-account-outline',
        children: [
          {
            key: 'system:group:view',
            label: '查看权限组',
            permKey: 'system:group:view',
            perm: { permKey: 'system:group:view', name: '查看权限组', desc: '访问权限组列表与详情', tags: ['可见'] }
          },
          {
            key: 'system:group:create',
            label: '新增权限组',
            permKey: 'system:group:create',
            perm: { permKey: 'system:group:create', name: '新增权限组', desc: '创建权限组', tags: ['可用'] }
          },
          {
            key: 'system:group:edit',
            label: '编辑权限组',
            permKey: 'system:group:edit',
            perm: { permKey: 'system:group:edit', name: '编辑权限组', desc: '修改权限组信息与权限码', tags: ['可用'] }
          }
        ]
      }
    ]
  },
  {
    key: 'module:agent',
    label: '分析引擎',
    icon: 'mdi:robot-outline',
    children: [
      {
        key: 'module:agent:config',
        label: '引擎配置',
        icon: 'mdi:tune-vertical-variant',
        children: [
          {
            key: 'agent:config:view',
            label: '查看引擎配置',
            permKey: 'agent:config:view',
            perm: { permKey: 'agent:config:view', name: '查看引擎配置', desc: '访问引擎配置页面及读取配置', tags: ['可见'] }
          },
          {
            key: 'agent:config:create',
            label: '新增引擎配置',
            permKey: 'agent:config:create',
            perm: { permKey: 'agent:config:create', name: '新增引擎配置', desc: '创建新的引擎配置项', tags: ['可用'] }
          },
          {
            key: 'agent:config:edit',
            label: '编辑引擎配置',
            permKey: 'agent:config:edit',
            perm: { permKey: 'agent:config:edit', name: '编辑引擎配置', desc: '修改引擎配置项', tags: ['可用'] }
          },
          {
            key: 'agent:config:delete',
            label: '删除引擎配置',
            permKey: 'agent:config:delete',
            perm: { permKey: 'agent:config:delete', name: '删除引擎配置', desc: '删除引擎配置项', tags: ['可用'] }
          }
        ]
      }
    ]
  }
]

const abilityTreeProps = {
  label: 'label',
  children: 'children'
}

function abilityFlattenPermsFromTree(nodes) {
  const list = []
  const stack = Array.isArray(nodes) ? [...nodes] : []
  while (stack.length > 0) {
    const node = stack.shift()
    if (!node) continue
    if (node.perm && node.perm.permKey) {
      list.push(node.perm)
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      stack.push(...node.children)
    }
  }
  return list
}

const abilityAllPerms = computed(() => abilityFlattenPermsFromTree(abilityCatalogTree))
const abilityPermMetaByKey = computed(() => {
  const map = {}
  for (const p of abilityAllPerms.value) {
    map[p.permKey] = p
  }
  return map
})

const abilityCatalogStats = computed(() => {
  const totalPerms = abilityAllPerms.value.length
  const set = new Set(abilityAllPerms.value.map(p => p.permKey))
  const missing = []
  for (const g of groupList.value || []) {
    for (const code of g.permissions || []) {
      if (code === '*') continue
      if (!set.has(code)) missing.push(code)
    }
  }
  return {
    totalPerms,
    missingPerms: Array.from(new Set(missing)).sort()
  }
})

function abilityFilterTreeNode(keyword, data) {
  if (!keyword) return true
  const k = String(keyword).trim().toLowerCase()
  if (!k) return true
  const label = String(data?.label || '').toLowerCase()
  const permKey = String(data?.permKey || data?.perm?.permKey || '').toLowerCase()
  return label.includes(k) || permKey.includes(k)
}

watch(abilitySearchKeyword, (val) => {
  abilityTreeRef.value?.filter?.(val)
})

const abilitySearchEmptyHint = computed(() => {
  const k = String(abilitySearchKeyword.value || '').trim()
  if (!k) return ''
  return `未找到与“${k}”匹配的权限节点`
})

const abilityCurrentNode = ref(null)

function handleAbilityCurrentNodeChange(node) {
  abilityCurrentNode.value = node || null
}

const abilityGroupsForSelect = computed(() => {
  if (Array.isArray(groupList.value) && groupList.value.length > 0) return groupList.value
  return [
    { uuid: 'mock-system', group_name: 'system', display_name: '系统组（本地）', permissions: ['*'] },
    { uuid: 'mock-analyst', group_name: 'analyst', display_name: '分析员（本地）', permissions: [] }
  ]
})

const currentAbilityGroup = computed(() => {
  const id = abilitySelectedGroupUuid.value
  if (!id) return null
  return abilityGroupsForSelect.value.find(g => g.uuid === id) || null
})

const currentAbilityGroupLabel = computed(() => {
  const g = currentAbilityGroup.value
  if (!g) return '未选择'
  return g.display_name || g.group_name || g.uuid
})

const abilityCanEdit = computed(() => Boolean(abilitySelectedGroupUuid.value))

const abilityGroupHasWildcard = computed(() => {
  const id = abilitySelectedGroupUuid.value
  if (!id) return false
  const stored = abilityGroupPermissionDraftMap.value?.[id]
  if (Array.isArray(stored) && stored.includes('*')) return true
  const g = currentAbilityGroup.value
  return Array.isArray(g?.permissions) && g.permissions.includes('*')
})

function abilityLoadFromStorage() {
  try {
    const raw = localStorage.getItem(ABILITY_STORAGE_KEY)
    if (!raw) {
      abilityGroupPermissionDraftMap.value = {}
      return
    }
    const parsed = JSON.parse(raw)
    abilityGroupPermissionDraftMap.value = parsed?.map && typeof parsed.map === 'object' ? parsed.map : {}
    abilityLastSavedAt.value = parsed?.updated_at || ''
  } catch {
    abilityGroupPermissionDraftMap.value = {}
    abilityLastSavedAt.value = ''
  }
}

function abilitySaveToStorage() {
  const payload = {
    updated_at: new Date().toISOString(),
    map: abilityGroupPermissionDraftMap.value || {}
  }
  localStorage.setItem(ABILITY_STORAGE_KEY, JSON.stringify(payload))
  abilityLastSavedAt.value = payload.updated_at
}

abilityLoadFromStorage()

const abilitySelectedPermSet = computed(() => {
  const id = abilitySelectedGroupUuid.value
  if (!id) return new Set()
  const stored = abilityGroupPermissionDraftMap.value?.[id]
  const base = Array.isArray(stored)
    ? stored
    : (Array.isArray(currentAbilityGroup.value?.permissions) ? currentAbilityGroup.value.permissions : [])
  return new Set(base.filter(Boolean))
})

const abilitySelectedPermSetSize = computed(() => abilitySelectedPermSet.value.size)

function abilityIsPermChecked(permKey) {
  return abilitySelectedPermSet.value.has(permKey) || abilitySelectedPermSet.value.has('*')
}

function abilityTogglePerm(permKey, checked) {
  const id = abilitySelectedGroupUuid.value
  if (!id) return
  if (!abilityPermMetaByKey.value[permKey]) {
    ElMessage.warning(`权限码未在目录中定义：${permKey}`)
    return
  }
  const current = new Set(Array.from(abilitySelectedPermSet.value))
  current.delete('*')
  if (checked) current.add(permKey)
  else current.delete(permKey)
  abilityGroupPermissionDraftMap.value = {
    ...(abilityGroupPermissionDraftMap.value || {}),
    [id]: Array.from(current).sort()
  }
}

function abilityFindNodeByKey(nodes, key) {
  const stack = Array.isArray(nodes) ? [...nodes] : []
  while (stack.length > 0) {
    const node = stack.shift()
    if (!node) continue
    if (node.key === key) return node
    if (Array.isArray(node.children) && node.children.length > 0) {
      stack.push(...node.children)
    }
  }
  return null
}

const abilityPermsInCurrentNode = computed(() => {
  const node = abilityCurrentNode.value
  if (!node) return []
  if (node.perm && node.perm.permKey) return [node.perm]
  const perms = abilityFlattenPermsFromTree(node.children || [])
  const uniq = new Map()
  for (const p of perms) {
    if (!p?.permKey) continue
    uniq.set(p.permKey, p)
  }
  return Array.from(uniq.values()).sort((a, b) => String(a.permKey).localeCompare(String(b.permKey)))
})

const abilityCurrentNodeTitle = computed(() => {
  const node = abilityCurrentNode.value
  if (!node) return '未选择'
  return node.label || '未命名节点'
})

const abilityCurrentNodeSubTitle = computed(() => {
  const node = abilityCurrentNode.value
  if (!node) return '请在左侧选择一个模块或权限码'
  if (node.permKey) return node.permKey
  return '该模块下的权限码列表'
})

function handleAbilityOpenDocs(docs) {
  if (!docs) return
  ElMessage.info('说明功能暂未接入外部链接')
}

async function handleAbilitySave() {
  if (!abilitySelectedGroupUuid.value) return
  if (abilityGroupHasWildcard.value) return
  if (abilitySaving.value) return
  abilitySaving.value = true
  try {
    abilitySaveToStorage()
    ElMessage.success('保存成功（本地模拟）')
  } finally {
    abilitySaving.value = false
  }
}

function handleAbilityReset() {
  if (!abilitySelectedGroupUuid.value) return
  const id = abilitySelectedGroupUuid.value
  const g = currentAbilityGroup.value
  const base = Array.isArray(g?.permissions) ? g.permissions : []
  const next = base.includes('*') ? ['*'] : base.filter(Boolean)
  const map = { ...(abilityGroupPermissionDraftMap.value || {}) }
  if (next.length > 0) map[id] = Array.from(new Set(next)).sort()
  else delete map[id]
  abilityGroupPermissionDraftMap.value = map
  ElMessage.success('已重置为当前组的默认权限（本地模拟）')
}

watch(groupList, () => {
  if (abilitySelectedGroupUuid.value) return
  const first = abilityGroupsForSelect.value?.[0]?.uuid
  if (first) abilitySelectedGroupUuid.value = first
})

async function fetchUsers() {
  const res = await systemApi.getUsers({ page: 1, page_size: 10 })
  userList.value =
    (res?.data?.items || []).map(user => ({
      ...user,
      groups: Array.isArray(user.groups) ? user.groups : []
    }))
}

async function fetchGroups() {
  const res = await systemApi.getGroups({ page: 1, page_size: 10 })
  groupList.value = res?.data?.items || []
}

onMounted(async () => {
  try {
    await Promise.all([fetchGroups(), fetchUsers()])
  } catch {
  }
})

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
    groups: '新增权限组'
  }
  return map[activeTab.value] || '新增'
})

function handleAdd() {
  if (activeTab.value === 'users') {
    openCreateUserDialog()
    return
  }
  if (activeTab.value === 'groups') {
    openCreateGroupDialog()
    return
  }
}

function handleEditUser(user) {
  editingUser.value = user
  editUserGroupUuids.value = Array.isArray(user.groups) ? [...user.groups] : []
  editUserDialogVisible.value = true
}

function openCreateUserDialog() {
  createUserForm.username = ''
  createUserForm.password = ''
  createUserForm.display_name = ''
  createUserForm.email = ''
  createUserForm.remark = ''
  createUserForm.enabled = true
  createUserForm.temporary_account = false
  createUserForm.expired_at = ''
  createUserForm.groups = []
  createUserDialogVisible.value = true
}

function openCreateGroupDialog() {
  createGroupForm.group_name = ''
  createGroupForm.display_name = ''
  createGroupForm.remark = ''
  createGroupForm.enabled = true
  createGroupForm.permissions = []
  createGroupDialogVisible.value = true
}

async function handleSaveEditUser() {
  if (!editingUser.value) return
  savingEditUser.value = true
  try {
    await systemApi.updateUser(editingUser.value.uuid, {
      groups: editUserGroupUuids.value
    })
    ElMessage.success('保存成功')
    editUserDialogVisible.value = false
    await fetchUsers()
  } catch {
  } finally {
    savingEditUser.value = false
  }
}

async function handleSubmitCreateUser() {
  if (creatingUser.value) return
  const ok = await createUserFormRef.value?.validate?.().catch(() => false)
  if (!ok) return

  creatingUser.value = true
  try {
    const payload = {
      username: createUserForm.username.trim(),
      password: createUserForm.password,
      display_name: createUserForm.display_name.trim(),
      email: createUserForm.email?.trim() || undefined,
      remark: createUserForm.remark?.trim() || undefined,
      enabled: Boolean(createUserForm.enabled),
      temporary_account: Boolean(createUserForm.temporary_account),
      expired_at: createUserForm.expired_at || undefined,
      groups: Array.isArray(createUserForm.groups) ? createUserForm.groups : []
    }
    await systemApi.createUser(payload)
    ElMessage.success('创建成功')
    createUserDialogVisible.value = false
    await fetchUsers()
  } catch {
  } finally {
    creatingUser.value = false
  }
}

async function handleSubmitCreateGroup() {
  if (creatingGroup.value) return
  const ok = await createGroupFormRef.value?.validate?.().catch(() => false)
  if (!ok) return

  creatingGroup.value = true
  try {
    const payload = {
      group_name: createGroupForm.group_name.trim(),
      display_name: createGroupForm.display_name.trim(),
      remark: createGroupForm.remark?.trim() || undefined,
      enabled: Boolean(createGroupForm.enabled),
      permissions: Array.isArray(createGroupForm.permissions) ? createGroupForm.permissions : []
    }
    await systemApi.createGroup(payload)
    ElMessage.success('创建成功')
    createGroupDialogVisible.value = false
    await fetchGroups()
  } catch {
  } finally {
    creatingGroup.value = false
  }
}
</script>

<style scoped>
.ability-tree {
  padding: 6px 0;
}

.ability-tree :deep(.el-tree-node__content) {
  height: auto;
  align-items: flex-start;
  padding-top: 8px;
  padding-bottom: 8px;
}

.ability-tree :deep(.el-tree-node__content:hover) {
  background-color: rgba(59, 130, 246, 0.06);
}

.ability-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: rgba(59, 130, 246, 0.10);
}

.ability-tree :deep(.el-tree-node__expand-icon) {
  margin-top: 2px;
}

.ability-tree :deep(.el-tree-node__label) {
  width: 100%;
  white-space: normal;
  line-height: 1.25;
}
</style>
