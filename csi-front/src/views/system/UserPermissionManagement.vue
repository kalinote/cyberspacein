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
          <el-input v-model="activeSearchKeyword" :placeholder="searchPlaceholder" clearable class="w-60!">
            <template #prefix>
              <Icon icon="mdi:magnify" class="text-gray-400" />
            </template>
          </el-input>
          <el-select
            v-if="activeTab === 'dictionary'"
            v-model="dictFilterCategory"
            clearable
            placeholder="按分类筛选"
            class="w-60!"
          >
            <el-option label="全部分类" value="" />
            <el-option v-for="c in dictCategoryOptions" :key="c" :label="c" :value="c" />
          </el-select>
          <el-button v-if="canViewCurrentAdd" type="primary" :disabled="!canUseCurrentAdd" @click="handleAdd">
            <template #icon>
              <Icon icon="mdi:plus" />
            </template>
            {{ addButtonLabel }}
          </el-button>
        </div>
      </div>
    </template>

    <div v-if="activeTab === 'users' && canViewUserList" class="space-y-4">
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
            <el-button
              v-if="hasPerm(PERM_USERS.detailView)"
              type="primary"
              link
              :disabled="!hasAny([PERM_USERS.detailUse, PERM_PAGE_USERS?.detailUse])"
              @click="handleViewUser(user)"
            >
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button
              v-if="hasPerm(PERM_USERS.editView)"
              type="primary"
              link
              :disabled="!hasAny([PERM_USERS.editUse, PERM_PAGE_USERS?.editUse])"
              @click="handleEditUser(user)"
            >
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
    <div v-else-if="activeTab === 'groups' && canViewGroupList" class="space-y-4">
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
            <el-button v-if="hasPerm(PERM_GROUPS.detailView)" type="primary" link :disabled="!hasPerm(PERM_GROUPS.detailUse)">
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button v-if="hasPerm(PERM_GROUPS.editView)" type="primary" link :disabled="!hasPerm(PERM_GROUPS.editUse)" @click="handleEditGroup(group)">
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
    <div v-else-if="activeTab === 'dictionary' && canViewDictList" class="space-y-4">
      <div
        v-for="perm in filteredDictRows"
        :key="perm.permKey"
        class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow px-5 py-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 class="text-base font-bold text-gray-900">{{ perm.name }}</h3>
              <span class="text-[11px] text-gray-400 font-mono break-all">{{ perm.permKey }}</span>
            </div>
            <div class="flex flex-wrap items-center gap-2 mt-2">
              <el-tag
                size="small"
                :type="perm.enabled ? 'success' : 'info'"
                effect="light"
                class="border-0"
              >
                {{ perm.enabled ? '已启用' : '已禁用' }}
              </el-tag>
              <el-tag v-if="perm.category" size="small" type="primary" effect="plain">
                {{ perm.category }}
              </el-tag>
              <el-tag v-for="t in perm.tags || []" :key="t" size="small" type="info" effect="light" class="border-0">
                {{ t }}
              </el-tag>
            </div>
            <p v-if="perm.desc" class="text-xs text-gray-600 mt-2">{{ perm.desc }}</p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <el-button v-if="hasPerm(PERM_DICT.editView)" type="primary" link :disabled="!hasPerm(PERM_DICT.editUse)" @click="openEditDict(perm)">
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
            <el-button v-if="hasPerm(PERM_DICT.deleteView)" type="danger" link :disabled="!hasPerm(PERM_DICT.deleteUse)" @click="handleDeleteDict(perm)">
              <template #icon>
                <Icon icon="mdi:delete-outline" />
              </template>
              删除
            </el-button>
          </div>
        </div>
      </div>

      <div
        v-if="filteredDictRows.length === 0"
        class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80"
      >
        <Icon icon="mdi:key-variant" class="text-6xl text-gray-300 mb-4" />
        <p class="text-gray-500">{{ dictEmptyText }}</p>
      </div>
    </div>
  </ConfigCenterLayout>

  <el-dialog
    v-model="dictDialogVisible"
    :title="dictDialogTitle"
    :width="dictDialogWidth"
    :top="dictDialogTop"
    :fullscreen="dictDialogFullscreen"
  >
    <el-tabs v-if="dictMode === 'create'" v-model="dictCreateTab" class="-mt-2 mb-4">
      <el-tab-pane label="单条新增" name="single" />
      <el-tab-pane label="批量新增" name="batch" />
    </el-tabs>

    <el-form v-if="dictMode === 'edit' || dictCreateTab === 'single'" ref="dictFormRef" :model="dictForm" :rules="dictRules" label-width="90px">
      <el-form-item label="权限码" prop="permKey">
        <el-input v-model="dictForm.permKey" :disabled="dictMode === 'edit'" placeholder="例如：system:user:create" />
      </el-form-item>
      <el-form-item label="名称" prop="name">
        <el-input v-model="dictForm.name" placeholder="例如：新增用户" />
      </el-form-item>
      <el-form-item label="分类" prop="category">
        <el-select
          v-model="dictForm.category"
          filterable
          allow-create
          default-first-option
          placeholder="例如：系统配置/用户管理"
          class="w-full!"
        >
          <el-option v-for="c in dictCategoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述" prop="desc">
        <el-input v-model="dictForm.desc" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
      </el-form-item>
      <el-form-item label="标签">
        <el-select v-model="dictForm.tags" multiple filterable allow-create default-first-option placeholder="例如：可见、可用" class="w-full!">
          <el-option v-for="t in dictTagOptions" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="dictForm.enabled" />
      </el-form-item>
    </el-form>

    <div v-else class="space-y-3">
      <div class="flex items-center justify-between">
        <div class="text-xs text-gray-500">每行一条权限码，带 * 的列为必填</div>
        <div class="flex items-center gap-2">
          <el-button v-if="hasPerm(PERM_DICT.batchAddView)" :disabled="!hasPerm(PERM_DICT.batchAddUse)" @click="handleResetBatchRows">清空全部</el-button>
          <el-button v-if="hasPerm(PERM_DICT.batchAddView)" type="primary" plain :disabled="!hasPerm(PERM_DICT.batchAddUse)" @click="handleAddBatchRow">新增一行</el-button>
        </div>
      </div>
      <div class="max-h-105 overflow-auto border border-gray-200 rounded-lg">
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left w-16">行号</th>
              <th class="px-3 py-2 text-left min-w-52">权限码 *</th>
              <th class="px-3 py-2 text-left min-w-36">名称 *</th>
              <th class="px-3 py-2 text-left min-w-36">分类 *</th>
              <th class="px-3 py-2 text-left min-w-40">描述</th>
              <th class="px-3 py-2 text-left min-w-44">标签</th>
              <th class="px-3 py-2 text-center w-20">启用</th>
              <th class="px-3 py-2 text-center w-20">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in dictBatchRows" :key="row.rowId" class="border-t border-gray-100 align-top">
              <td class="px-3 py-2 text-gray-500">{{ index + 1 }}</td>
              <td class="px-3 py-2">
                <el-input v-model="row.permKey" :class="{ 'is-error': row.errorFields.permKey }" placeholder="system:user:view" />
              </td>
              <td class="px-3 py-2">
                <el-input v-model="row.name" :class="{ 'is-error': row.errorFields.name }" placeholder="查看用户" />
              </td>
              <td class="px-3 py-2">
                <el-select
                  v-model="row.category"
                  :class="{ 'is-error': row.errorFields.category }"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="系统配置/用户管理"
                  class="w-full!"
                >
                  <el-option v-for="c in dictCategoryOptions" :key="c" :label="c" :value="c" />
                </el-select>
              </td>
              <td class="px-3 py-2">
                <el-input v-model="row.desc" placeholder="可选" />
              </td>
              <td class="px-3 py-2">
                <el-select v-model="row.tags" multiple filterable allow-create default-first-option placeholder="可选" class="w-full!">
                  <el-option v-for="t in dictTagOptions" :key="t" :label="t" :value="t" />
                </el-select>
              </td>
              <td class="px-3 py-2 text-center">
                <el-switch v-model="row.enabled" />
              </td>
              <td class="px-3 py-2 text-center">
                <el-button v-if="hasPerm(PERM_DICT.batchAddView)" type="danger" link :disabled="!hasPerm(PERM_DICT.batchAddUse)" @click="handleRemoveBatchRow(index)">删除</el-button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="dictBatchErrorSummary" class="text-xs text-red-600">{{ dictBatchErrorSummary }}</div>
    </div>

    <template #footer>
      <el-button @click="dictDialogVisible = false">取消</el-button>
      <el-button
        v-if="dictCreateTab === 'batch' ? hasPerm(PERM_DICT.batchAddView) : (dictMode === 'edit' ? hasPerm(PERM_DICT.editView) : hasPerm(PERM_DICT.addView))"
        type="primary"
        :loading="dictSaving"
        :disabled="dictCreateTab === 'batch' ? !hasPerm(PERM_DICT.batchAddUse) : (dictMode === 'edit' ? !hasPerm(PERM_DICT.editUse) : !hasPerm(PERM_DICT.addUse))"
        @click="handleSaveDict"
      >保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editUserDialogVisible" :title="userDialogTitle" width="520px">
    <div v-if="editingUser" class="space-y-4">
      <div class="text-sm text-gray-600">
        用户：{{ editingUser.display_name }}（@{{ editingUser.username }}）
      </div>

      <el-form label-width="80px">
        <el-form-item label="用户组">
          <el-select
            v-model="editUserGroupUuids"
            multiple
            :disabled="!canUseEditUser"
            placeholder="请选择用户组"
            class="w-full!"
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
      <el-button
        v-if="canViewEditUserSave"
        type="primary"
        :loading="savingEditUser"
        :disabled="!canUseEditUser"
        @click="handleSaveEditUser"
      >
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
          class="w-full!"
          value-format="YYYY-MM-DDTHH:mm:ss.SSSZ"
        />
      </el-form-item>
      <el-form-item label="用户组" prop="groups">
        <el-select v-model="createUserForm.groups" multiple placeholder="请选择用户组（可选）" class="w-full!">
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
      <el-button v-if="hasPerm(PERM_USERS.addView)" type="primary" :loading="creatingUser" :disabled="!hasPerm(PERM_USERS.addUse)" @click="handleSubmitCreateUser">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createGroupDialogVisible" title="新增权限组" width="1200px" top="2vh" class="group-permission-dialog">
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
        <div v-loading="permCodeCatalogLoading" class="w-full">
          <GroupPermissionPicker
            v-model="createGroupForm.permissions"
            :perm-codes="enabledCatalogPermCodes"
            :disabled="permCodeCatalogLoading || !hasPerm(PERM_GROUPS.addUse)"
            class="w-full"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="createGroupDialogVisible = false">取消</el-button>
      <el-button v-if="hasPerm(PERM_GROUPS.addView)" type="primary" :loading="creatingGroup" :disabled="!hasPerm(PERM_GROUPS.addUse)" @click="handleSubmitCreateGroup">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editGroupDialogVisible" title="编辑权限组" width="1200px" top="2vh" class="group-permission-dialog">
    <div v-if="editingGroup" class="mb-3 text-sm text-gray-600">
      权限组：{{ editingGroup.display_name }}（@{{ editingGroup.group_name }}）
    </div>
    <el-form ref="editGroupFormRef" :model="editGroupForm" :rules="editGroupRules" label-width="100px">
      <el-form-item label="组标识">
        <el-input v-model="editGroupForm.group_name" disabled />
      </el-form-item>
      <el-form-item label="展示名称" prop="display_name">
        <el-input v-model="editGroupForm.display_name" placeholder="请输入展示名称" />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input v-model="editGroupForm.remark" type="textarea" :rows="2" placeholder="请输入备注（可选）" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="editGroupForm.enabled" />
      </el-form-item>
      <el-form-item label="权限码" prop="permissions">
        <div v-loading="permCodeCatalogLoading" class="w-full">
          <GroupPermissionPicker
            v-model="editGroupForm.permissions"
            :perm-codes="enabledCatalogPermCodes"
            :disabled="permCodeCatalogLoading || !hasPerm(PERM_GROUPS.editUse)"
            class="w-full"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="editGroupDialogVisible = false">取消</el-button>
      <el-button v-if="hasPerm(PERM_GROUPS.editView)" type="primary" :loading="savingEditGroup" :disabled="!hasPerm(PERM_GROUPS.editUse)" @click="handleSaveEditGroup">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import { formatDateTime } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { systemApi } from '@/api/system'
import GroupPermissionPicker from '@/components/system/GroupPermissionPicker.vue'
import { hasPerm, hasAny } from '@/utils/permissionKit'

defineOptions({ name: 'UserPermissionManagement' })

const PERM_TABS = PERM.pages.system.permissions.tabs
const PERM_USERS = PERM.operations.system.permissions.users
const PERM_GROUPS = PERM.operations.system.permissions.groups
const PERM_DICT = PERM.operations.system.permissions.dict
const PERM_PAGE_USERS = PERM.pages.system.permissions.userManagement?.users

const activeTab = ref('users')
const expandedTabKeys = ref([])
const userSearchKeyword = ref('')
const groupSearchKeyword = ref('')
const dictSearchKeyword = ref('')
const dictFilterCategory = ref('')

const activeSearchKeyword = computed({
  get() {
    if (activeTab.value === 'users') return userSearchKeyword.value
    if (activeTab.value === 'groups') return groupSearchKeyword.value
    if (activeTab.value === 'dictionary') return dictSearchKeyword.value
    return ''
  },
  set(val) {
    if (activeTab.value === 'users') userSearchKeyword.value = val
    else if (activeTab.value === 'groups') groupSearchKeyword.value = val
    else if (activeTab.value === 'dictionary') dictSearchKeyword.value = val
  }
})

const userList = ref([])
const groupList = ref([])
const permCodeList = ref([]) // 权限码字典列表（会被字典搜索影响）
const permCodeCatalogList = ref([]) // 权限组弹窗目录专用（与字典解耦）
const permCodeCatalogLoading = ref(false)

const editUserDialogVisible = ref(false)
const editingUser = ref(null)
const editUserGroupUuids = ref([])
const savingEditUser = ref(false)
const userDialogMode = ref('edit')

const canViewEditUserSave = computed(() => userDialogMode.value === 'edit' && hasPerm(PERM_USERS.editView))
const canUseEditUser = computed(() => hasAny([PERM_USERS.editUse, PERM_PAGE_USERS?.editUse]))
const userDialogTitle = computed(() => (userDialogMode.value === 'detail' ? '查看用户' : '编辑用户'))

const editGroupDialogVisible = ref(false)
const editingGroup = ref(null)
const editGroupFormRef = ref(null)
const savingEditGroup = ref(false)
const editGroupForm = reactive({
  group_name: '',
  display_name: '',
  remark: '',
  enabled: true,
  permissions: []
})
const editGroupRules = {
  display_name: [{ required: true, message: '请输入展示名称', trigger: 'blur' }]
}

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

function normalizePermCode(row) {
  return {
    uuid: row?.uuid || '',
    permKey: row?.perm_key || '',
    name: row?.name || '',
    category: row?.category || '',
    desc: row?.desc || '',
    tags: Array.isArray(row?.tags) ? row.tags : [],
    enabled: Boolean(row?.enabled)
  }
}

async function fetchPermCodes(params = {}) {
  const res = await systemApi.getPermCodes(params)
  const rows = Array.isArray(res?.data) ? res.data : []
  permCodeList.value = rows.map(normalizePermCode)
}

async function fetchPermCodeCatalog() {
  if (permCodeCatalogLoading.value) return
  permCodeCatalogLoading.value = true
  try {
    const res = await systemApi.getPermCodes({})
    const rows = Array.isArray(res?.data) ? res.data : []
    permCodeCatalogList.value = rows.map(normalizePermCode)
  } finally {
    permCodeCatalogLoading.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([fetchGroups(), fetchUsers(), fetchPermCodes(), fetchPermCodeCatalog()])
  } catch {
  }
})

function formatExpired(dateStr) {
  if (!dateStr) return '永久有效'
  return formatDateTime(dateStr)
}

const basePermissionNavItems = [
  { key: 'users', label: '用户管理', icon: 'mdi:account-multiple' },
  { key: 'groups', label: '权限组管理', icon: 'mdi:shield-account' },
  { key: 'dictionary', label: '权限码字典', icon: 'mdi:book-open-variant' }
]

const permissionNavItems = computed(() =>
  basePermissionNavItems
    .filter(item => hasPerm(PERM_TABS[item.key]?.view))
    .map(item => ({
      ...item,
      disabled: !hasPerm(PERM_TABS[item.key]?.use)
    }))
)

watch(permissionNavItems, (items) => {
  if (!Array.isArray(items) || items.length === 0) return
  const exists = items.some(item => item.key === activeTab.value)
  const activeEnabled = items.some(item => item.key === activeTab.value && !item.disabled)
  if (exists && activeEnabled) return
  const firstEnabled = items.find(item => !item.disabled)
  activeTab.value = (firstEnabled || items[0]).key
}, { immediate: true })

const canViewUserList = computed(() => hasAny([PERM_USERS.listView, PERM_PAGE_USERS?.view]))
const canViewGroupList = computed(() => hasPerm(PERM_GROUPS.listView))
const canViewDictList = computed(() => hasPerm(PERM_DICT.listView))

const canViewCurrentAdd = computed(() => {
  if (activeTab.value === 'users') return hasPerm(PERM_USERS.addView)
  if (activeTab.value === 'groups') return hasPerm(PERM_GROUPS.addView)
  if (activeTab.value === 'dictionary') return hasPerm(PERM_DICT.addView)
  return false
})

const canUseCurrentAdd = computed(() => {
  if (activeTab.value === 'users') return hasAny([PERM_USERS.addUse, PERM_PAGE_USERS?.addUse])
  if (activeTab.value === 'groups') return hasPerm(PERM_GROUPS.addUse)
  if (activeTab.value === 'dictionary') return hasPerm(PERM_DICT.addUse)
  return false
})

const currentTabMeta = computed(() => findNavItemByKey(permissionNavItems.value, activeTab.value))
const currentTabIcon = computed(() => currentTabMeta.value?.icon || 'mdi:help')
const currentTabLabel = computed(() => currentTabMeta.value?.label || '')

const addButtonLabel = computed(() => {
  const map = {
    users: '新增用户',
    groups: '新增权限组',
    dictionary: '新增权限码'
  }
  return map[activeTab.value] || '新增'
})

const searchPlaceholder = computed(() => {
  const map = {
    users: '搜索用户',
    groups: '搜索权限组',
    dictionary: '搜索权限码'
  }
  return map[activeTab.value] || '搜索'
})

function handleAdd() {
  if (!canUseCurrentAdd.value) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (activeTab.value === 'users') {
    openCreateUserDialog()
    return
  }
  if (activeTab.value === 'groups') {
    openCreateGroupDialog()
    return
  }
  if (activeTab.value === 'dictionary') {
    openCreateDict()
    return
  }
}

const dictRows = computed(() => permCodeList.value)
const enabledPermCodes = computed(() => permCodeList.value.filter(item => item.enabled))
const enabledCatalogPermCodes = computed(() => permCodeCatalogList.value.filter(item => item.enabled))

const filteredDictRows = computed(() => {
  const selectedCategory = String(dictFilterCategory.value || '').trim()
  if (!selectedCategory) return dictRows.value
  return dictRows.value.filter(item => String(item?.category || '').trim() === selectedCategory)
})

const dictEmptyText = computed(() => {
  if (dictSearchKeyword.value || dictFilterCategory.value) return '没有匹配的权限码'
  return '暂无权限码'
})
const dictCategoryOptions = computed(() => {
  const set = new Set()
  for (const item of permCodeList.value) {
    const category = String(item?.category || '').trim()
    if (category) set.add(category)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
})
const dictTagOptions = computed(() => {
  const set = new Set()
  for (const item of permCodeList.value) {
    for (const tag of item?.tags || []) {
      const value = String(tag || '').trim()
      if (value) set.add(value)
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
})

const dictDialogVisible = ref(false)
const dictMode = ref('create') // create | edit
const dictCreateTab = ref('single')
const dictSaving = ref(false)
const dictFormRef = ref(null)
const dictBatchErrorSummary = ref('')
const dictForm = reactive({
  uuid: '',
  permKey: '',
  name: '',
  category: '',
  desc: '',
  tags: [],
  enabled: true
})

const dictRules = {
  permKey: [{ required: true, message: '请输入权限码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择或输入分类', trigger: 'change' }]
}

const dictDialogTitle = computed(() => (dictMode.value === 'edit' ? '编辑权限码' : '新增权限码'))
const dictDialogWidth = computed(() => {
  if (dictMode.value === 'create' && dictCreateTab.value === 'batch') return '92vw'
  return '560px'
})
const dictDialogTop = computed(() => {
  if (dictMode.value === 'create' && dictCreateTab.value === 'batch') return '4vh'
  return '15vh'
})
const dictDialogFullscreen = computed(() => false)

function createBatchRow() {
  return {
    rowId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    permKey: '',
    name: '',
    category: '',
    desc: '',
    tags: [],
    enabled: true,
    errorFields: {
      permKey: false,
      name: false,
      category: false
    }
  }
}

const dictBatchRows = ref([createBatchRow()])

function resetBatchRowErrors() {
  dictBatchErrorSummary.value = ''
  for (const row of dictBatchRows.value) {
    row.errorFields.permKey = false
    row.errorFields.name = false
    row.errorFields.category = false
  }
}

function handleAddBatchRow() {
  if (!hasPerm(PERM_DICT.batchAddUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value.push(createBatchRow())
}

function handleRemoveBatchRow(index) {
  if (!hasPerm(PERM_DICT.batchAddUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value.splice(index, 1)
  if (dictBatchRows.value.length === 0) {
    dictBatchRows.value.push(createBatchRow())
  }
}

function handleResetBatchRows() {
  if (!hasPerm(PERM_DICT.batchAddUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value = [createBatchRow()]
  resetBatchRowErrors()
}

function openCreateDict() {
  if (!hasPerm(PERM_DICT.addUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictMode.value = 'create'
  dictCreateTab.value = 'single'
  handleResetBatchRows()
  dictForm.uuid = ''
  dictForm.permKey = ''
  dictForm.name = ''
  dictForm.category = ''
  dictForm.desc = ''
  dictForm.tags = []
  dictForm.enabled = true
  dictDialogVisible.value = true
}

function openEditDict(row) {
  if (!hasPerm(PERM_DICT.editUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictMode.value = 'edit'
  dictForm.uuid = row.uuid || ''
  dictForm.permKey = row.permKey
  dictForm.name = row.name || ''
  dictForm.category = row.category || ''
  dictForm.desc = row.desc || ''
  dictForm.tags = Array.isArray(row.tags) ? [...row.tags] : []
  dictForm.enabled = Boolean(row.enabled)
  dictDialogVisible.value = true
}

async function handleDeleteDict(row) {
  if (!hasPerm(PERM_DICT.deleteUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除权限码：${row.permKey}？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await systemApi.deletePermCode(row.uuid)
    ElMessage.success('删除成功')
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } catch {
  }
}

async function handleSaveDict() {
  if (dictMode.value === 'edit' && !hasPerm(PERM_DICT.editUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (dictMode.value === 'create' && dictCreateTab.value === 'single' && !hasPerm(PERM_DICT.addUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (dictMode.value === 'create' && dictCreateTab.value === 'batch' && !hasPerm(PERM_DICT.batchAddUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (dictMode.value === 'create' && dictCreateTab.value === 'batch') {
    await handleSaveDictBatch()
    return
  }
  if (dictSaving.value) return
  const ok = await dictFormRef.value?.validate?.().catch(() => false)
  if (!ok) return

  const permKey = String(dictForm.permKey || '').trim()
  const name = String(dictForm.name || '').trim()
  const category = String(dictForm.category || '').trim()
  const desc = String(dictForm.desc || '').trim()
  const tags = Array.isArray(dictForm.tags) ? dictForm.tags.map(t => String(t).trim()).filter(Boolean) : []

  dictSaving.value = true
  try {
    if (dictMode.value === 'create') {
      await systemApi.createPermCode({
        perm_key: permKey,
        name,
        category,
        desc: desc || undefined,
        tags,
        enabled: Boolean(dictForm.enabled)
      })
      ElMessage.success('新增成功')
      dictDialogVisible.value = false
      await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
      return
    }

    await systemApi.updatePermCode(dictForm.uuid, {
      name,
      category,
      desc: desc || undefined,
      tags,
      enabled: Boolean(dictForm.enabled)
    })
    ElMessage.success('保存成功')
    dictDialogVisible.value = false
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } finally {
    dictSaving.value = false
  }
}

function getRequestErrorMessage(error) {
  return String(error?.message || '').trim() || '批量新增失败'
}

function parseRowByPermKeyFromMessage(message) {
  for (let i = 0; i < dictBatchRows.value.length; i += 1) {
    const permKey = String(dictBatchRows.value[i].permKey || '').trim()
    if (!permKey) continue
    if (message.includes(permKey)) return i
  }
  return -1
}

function validateBatchRows() {
  resetBatchRowErrors()
  const normalizedRows = []
  const permKeyMap = new Map()
  const duplicateIndexes = []

  for (let i = 0; i < dictBatchRows.value.length; i += 1) {
    const row = dictBatchRows.value[i]
    const permKey = String(row.permKey || '').trim()
    const name = String(row.name || '').trim()
    const category = String(row.category || '').trim()
    const desc = String(row.desc || '').trim()
    const tags = Array.isArray(row.tags) ? row.tags.map(t => String(t).trim()).filter(Boolean) : []
    const isEmpty = !permKey && !name && !category && !desc && tags.length === 0
    if (isEmpty) continue

    if (!permKey) row.errorFields.permKey = true
    if (!name) row.errorFields.name = true
    if (!category) row.errorFields.category = true

    if (permKey) {
      if (!permKeyMap.has(permKey)) permKeyMap.set(permKey, [])
      permKeyMap.get(permKey).push(i)
    }

    normalizedRows.push({
      index: i,
      item: {
        perm_key: permKey,
        name,
        category,
        desc: desc || undefined,
        tags,
        enabled: Boolean(row.enabled)
      }
    })
  }

  for (const indexes of permKeyMap.values()) {
    if (indexes.length <= 1) continue
    duplicateIndexes.push(...indexes)
    for (const idx of indexes) {
      dictBatchRows.value[idx].errorFields.permKey = true
    }
  }

  if (normalizedRows.length === 0) {
    dictBatchErrorSummary.value = '请至少填写一条有效记录'
    return []
  }

  const hasRequiredError = dictBatchRows.value.some(row => row.errorFields.permKey || row.errorFields.name || row.errorFields.category)
  if (hasRequiredError) {
    dictBatchErrorSummary.value = '请补全必填字段（权限码、名称、分类）'
    return []
  }

  if (duplicateIndexes.length > 0) {
    const lineNoText = Array.from(new Set(duplicateIndexes)).map(i => i + 1).join('、')
    dictBatchErrorSummary.value = `权限码存在重复，请检查第 ${lineNoText} 行`
    return []
  }

  return normalizedRows
}

function markRowError(index, field, message) {
  if (index < 0 || index >= dictBatchRows.value.length) return
  if (field && dictBatchRows.value[index].errorFields[field] !== undefined) {
    dictBatchRows.value[index].errorFields[field] = true
  }
  dictBatchErrorSummary.value = message
}

function applyBatchErrorFeedback(message) {
  const matchedIndex = parseRowByPermKeyFromMessage(message)
  if (matchedIndex >= 0) {
    markRowError(matchedIndex, 'permKey', `第 ${matchedIndex + 1} 行失败：${message}`)
    return
  }
  if (message.includes('perm_key') && message.includes('不能为空')) {
    const firstEmptyIndex = dictBatchRows.value.findIndex(row => !String(row.permKey || '').trim())
    if (firstEmptyIndex >= 0) {
      markRowError(firstEmptyIndex, 'permKey', `第 ${firstEmptyIndex + 1} 行失败：权限码不能为空`)
      return
    }
  }
  if (message.includes('重复权限码') || message.includes('权限码已存在')) {
    dictBatchErrorSummary.value = `批量新增失败：${message}`
    return
  }
  dictBatchErrorSummary.value = `批量新增失败：${message}`
}

async function handleSaveDictBatch() {
  if (dictSaving.value) return
  const normalizedRows = validateBatchRows()
  if (normalizedRows.length === 0) return

  dictSaving.value = true
  try {
    await systemApi.createPermCodesBatch({
      items: normalizedRows.map(row => row.item)
    })
    ElMessage.success('批量新增成功')
    dictDialogVisible.value = false
    handleResetBatchRows()
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } catch (error) {
    const message = getRequestErrorMessage(error)
    applyBatchErrorFeedback(message)
  } finally {
    dictSaving.value = false
  }
}

let dictSearchTimer = null
watch(
  () => [activeTab.value, dictSearchKeyword.value],
  ([tab, keyword]) => {
    if (dictSearchTimer) clearTimeout(dictSearchTimer)
    dictSearchTimer = null
    if (tab !== 'dictionary') return
    dictSearchTimer = setTimeout(() => {
      fetchPermCodes({ keyword: String(keyword || '').trim() || undefined }).catch(() => {})
    }, 300)
  }
)

onBeforeUnmount(() => {
  if (dictSearchTimer) clearTimeout(dictSearchTimer)
})

function handleEditUser(user) {
  if (!hasAny([PERM_USERS.editUse, PERM_PAGE_USERS?.editUse])) {
    ElMessage.warning('暂无操作权限')
    return
  }
  userDialogMode.value = 'edit'
  editingUser.value = user
  editUserGroupUuids.value = Array.isArray(user.groups) ? [...user.groups] : []
  editUserDialogVisible.value = true
}

function handleViewUser(user) {
  if (!hasAny([PERM_USERS.detailUse, PERM_PAGE_USERS?.detailUse])) {
    ElMessage.warning('暂无查看权限')
    return
  }
  userDialogMode.value = 'detail'
  editingUser.value = user
  editUserGroupUuids.value = Array.isArray(user.groups) ? [...user.groups] : []
  editUserDialogVisible.value = true
}

function handleEditGroup(group) {
  if (!hasPerm(PERM_GROUPS.editUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  fetchPermCodeCatalog().catch(() => {})
  editingGroup.value = group
  editGroupForm.group_name = group?.group_name || ''
  editGroupForm.display_name = group?.display_name || ''
  editGroupForm.remark = group?.remark || ''
  editGroupForm.enabled = Boolean(group?.enabled)
  editGroupForm.permissions = Array.isArray(group?.permissions) ? [...group.permissions] : []
  editGroupDialogVisible.value = true
}

function openCreateUserDialog() {
  if (!hasAny([PERM_USERS.addUse, PERM_PAGE_USERS?.addUse])) {
    ElMessage.warning('暂无操作权限')
    return
  }
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
  if (!hasPerm(PERM_GROUPS.addUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  fetchPermCodeCatalog().catch(() => {})
  createGroupForm.group_name = ''
  createGroupForm.display_name = ''
  createGroupForm.remark = ''
  createGroupForm.enabled = true
  createGroupForm.permissions = []
  createGroupDialogVisible.value = true
}

async function handleSaveEditUser() {
  if (!hasAny([PERM_USERS.editUse, PERM_PAGE_USERS?.editUse])) {
    ElMessage.warning('暂无操作权限')
    return
  }
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
  if (!hasAny([PERM_USERS.addUse, PERM_PAGE_USERS?.addUse])) {
    ElMessage.warning('暂无操作权限')
    return
  }
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
  if (!hasPerm(PERM_GROUPS.addUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
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

async function handleSaveEditGroup() {
  if (!hasPerm(PERM_GROUPS.editUse)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!editingGroup.value) return
  if (savingEditGroup.value) return
  const ok = await editGroupFormRef.value?.validate?.().catch(() => false)
  if (!ok) return

  savingEditGroup.value = true
  try {
    const payload = {
      display_name: editGroupForm.display_name.trim(),
      remark: editGroupForm.remark?.trim() || undefined,
      enabled: Boolean(editGroupForm.enabled),
      permissions: Array.isArray(editGroupForm.permissions) ? editGroupForm.permissions : []
    }
    await systemApi.updateGroup(editingGroup.value.uuid, payload)
    ElMessage.success('保存成功')
    editGroupDialogVisible.value = false
    await fetchGroups()
  } catch {
  } finally {
    savingEditGroup.value = false
  }
}
</script>

<style scoped>
:deep(.group-permission-dialog .el-dialog__body) {
  max-height: calc(100vh - 180px);
  overflow: auto;
}
</style>
