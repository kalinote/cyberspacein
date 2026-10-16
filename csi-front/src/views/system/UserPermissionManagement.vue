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
      <div v-if="isMobile" class="mobile-config-toolbar">
        <el-input v-model="activeSearchKeyword" :placeholder="activeTab === 'dictionary' ? searchPlaceholder : `搜索本页${activeTab === 'users' ? '用户' : '权限组'}`" clearable><template #prefix><Icon icon="mdi:magnify" /></template></el-input>
        <el-select v-if="activeTab === 'dictionary'" v-model="dictFilterCategory" clearable placeholder="全部分类"><el-option v-for="item in dictCategoryOptions" :key="item" :label="item" :value="item" /></el-select>
        <el-button v-if="canViewCurrentAdd" type="primary" :disabled="!canUseCurrentAdd" @click="handleAdd">{{ addButtonLabel }}</el-button>
      </div>
      <div v-else class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
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

    <el-alert v-if="currentListError" :title="currentListError" type="error" :closable="false" show-icon><el-button link @click="loadActiveTabData()">重新加载</el-button></el-alert>
    <el-skeleton v-else-if="currentListLoading" :rows="6" animated />
    <div v-else-if="isMobile" class="mobile-management-list">
      <template v-if="activeTab === 'users' && canViewUserList">
        <article v-for="user in mobileUsers" :key="user.uuid" class="mobile-management-card">
          <header><div><h2>{{ user.display_name }}</h2><p>@{{ user.username }}</p></div><el-tag :type="user.enabled ? 'success' : 'info'">{{ user.enabled ? '已启用' : '已禁用' }}</el-tag></header>
          <div class="mobile-management-tags"><el-tag v-if="user.temporary_account" type="warning">临时账号</el-tag><el-tag v-for="id in user.groups" :key="id" size="small">{{ groupNameByUuid[id] || id }}</el-tag></div>
          <p v-if="user.remark">{{ user.remark }}</p>
          <details><summary>账号资料</summary><dl><dt>邮箱</dt><dd>{{ user.email || '未设置' }}</dd><dt>最近登录</dt><dd>{{ formatDateTime(user.login_date) }} · {{ user.login_ip || '暂无 IP' }}</dd><dt>到期时间</dt><dd>{{ formatExpired(user.expired_at) }}</dd><dt>创建记录</dt><dd>{{ formatDateTime(user.create_at) }} · {{ user.create_by }}</dd><dt>修改记录</dt><dd>{{ formatDateTime(user.update_at) }} · {{ user.update_by }}</dd><dt>唯一标识</dt><dd>{{ user.uuid }}</dd></dl></details>
          <footer><el-button v-if="hasPerm(PERM_USERS.detailRead)" @click="handleViewUser(user)">查看</el-button><el-button v-if="hasPerm(PERM_USERS.groupUpdate) && !user.is_system" type="primary" plain @click="handleEditUser(user)">编辑</el-button><el-button v-if="hasPerm(PERM_USERS.delete) && !user.is_system" type="danger" plain :loading="deletingUserId === user.uuid" :disabled="Boolean(deletingUserId)" @click="handleDeleteUser(user)">删除</el-button></footer>
        </article>
        <el-empty v-if="!mobileUsers.length" description="本页没有匹配的用户" />
        <el-pagination layout="prev, pager, next" :pager-count="5" :total="userTotal" :page-size="10" v-model:current-page="userPage" @current-change="fetchUsers" />
      </template>
      <template v-else-if="activeTab === 'groups' && canViewGroupList">
        <article v-for="group in mobileGroups" :key="group.uuid" class="mobile-management-card">
          <header><div><h2>{{ group.display_name }}</h2><p>@{{ group.group_name }}</p></div><el-tag :type="group.enabled ? 'success' : 'info'">{{ group.enabled ? '已启用' : '已禁用' }}</el-tag></header>
          <p v-if="group.remark">{{ group.remark }}</p>
          <details><summary>权限与资料 · {{ group.permissions?.includes('*') ? '全部权限' : `${group.permissions?.length || 0} 项权限` }}</summary><dl><dt>创建记录</dt><dd>{{ formatDateTime(group.create_at) }} · {{ group.create_by }}</dd><dt>修改记录</dt><dd>{{ formatDateTime(group.update_at) }} · {{ group.update_by || '-' }}</dd><dt>唯一标识</dt><dd>{{ group.uuid }}</dd></dl><p v-for="code in group.permissions" :key="code" class="mobile-permission-code">{{ code === '*' ? '全部权限' : code }}</p></details>
          <footer><el-button v-if="hasPerm(PERM_GROUPS.update) && !group.is_system" type="primary" plain @click="handleEditGroup(group)">编辑权限组</el-button><el-button v-if="hasPerm(PERM_GROUPS.delete) && !group.is_system" type="danger" plain :loading="deletingGroupId === group.uuid" :disabled="Boolean(deletingGroupId)" @click="handleDeleteGroup(group)">删除</el-button></footer>
        </article>
        <el-empty v-if="!mobileGroups.length" description="本页没有匹配的权限组" />
        <el-pagination layout="prev, pager, next" :pager-count="5" :total="groupTotal" :page-size="10" v-model:current-page="groupPage" @current-change="fetchGroups" />
      </template>
      <template v-else-if="activeTab === 'dictionary' && canViewDictList">
        <article v-for="perm in filteredDictRows" :key="perm.permKey" class="mobile-management-card">
          <header><h2>{{ perm.name }}</h2><el-tag :type="perm.enabled ? 'success' : 'info'">{{ perm.enabled ? '已启用' : '已禁用' }}</el-tag></header><p class="mobile-permission-code">{{ perm.permKey }}</p>
          <div class="mobile-management-tags"><el-tag v-if="perm.category" size="small">{{ perm.category }}</el-tag><el-tag v-for="tag in perm.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag></div><p v-if="perm.desc">{{ perm.desc }}</p>
          <footer><el-button v-if="hasPerm(PERM_DICT.update) && !perm.systemReserved" type="primary" plain @click="openEditDict(perm)">编辑</el-button><el-button v-if="hasPerm(PERM_DICT.delete) && perm.source === 'placeholder'" type="danger" plain @click="handleDeleteDict(perm)">删除</el-button></footer>
        </article>
        <el-empty v-if="!filteredDictRows.length" :description="dictEmptyText" />
      </template>
      <el-empty v-else description="暂无此模块的查看权限" />
    </div>
    <div v-else-if="activeTab === 'users' && canViewUserList" class="space-y-4">
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
              v-if="hasPerm(PERM_USERS.detailRead)"
              type="primary"
              link
              :disabled="!hasPerm(PERM_USERS.detailRead)"
              @click="handleViewUser(user)"
            >
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button
              v-if="hasPerm(PERM_USERS.groupUpdate) && !user.is_system"
              type="primary"
              link
              :disabled="!hasPerm(PERM_USERS.groupUpdate)"
              @click="handleEditUser(user)"
            >
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
            <el-button
              v-if="hasPerm(PERM_USERS.delete) && !user.is_system"
              type="danger"
              link
              :loading="deletingUserId === user.uuid"
              :disabled="Boolean(deletingUserId)"
              @click="handleDeleteUser(user)"
            >
              <template #icon>
                <Icon icon="mdi:delete-outline" />
              </template>
              删除
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
            <el-button v-if="hasPerm(PERM_GROUPS.read)" type="primary" link>
              <template #icon>
                <Icon icon="mdi:eye" />
              </template>
              查看
            </el-button>
            <el-button v-if="hasPerm(PERM_GROUPS.update) && !group.is_system" type="primary" link @click="handleEditGroup(group)">
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
            <el-button
              v-if="hasPerm(PERM_GROUPS.delete) && !group.is_system"
              type="danger"
              link
              :loading="deletingGroupId === group.uuid"
              :disabled="Boolean(deletingGroupId)"
              @click="handleDeleteGroup(group)"
            >
              <template #icon>
                <Icon icon="mdi:delete-outline" />
              </template>
              删除
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
            <el-button v-if="hasPerm(PERM_DICT.update) && !perm.systemReserved" type="primary" link @click="openEditDict(perm)">
              <template #icon>
                <Icon icon="mdi:pencil" />
              </template>
              编辑
            </el-button>
            <el-button v-if="hasPerm(PERM_DICT.delete) && perm.source === 'placeholder'" type="danger" link @click="handleDeleteDict(perm)">
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
    class="mobile-config-dialog"
    v-model="dictDialogVisible"
    :title="dictDialogTitle"
    :width="dictDialogWidth"
    :top="dictDialogTop"
    :fullscreen="dictDialogFullscreen"
  >
    <el-tabs v-if="dictMode === 'create'" v-model="dictCreateTab" class="-mt-2 mb-4">
      <el-tab-pane label="单条新增" name="single" :disabled="dictSaving" />
      <el-tab-pane label="批量新增" name="batch" :disabled="dictSaving" />
    </el-tabs>

    <el-form v-if="dictMode === 'edit' || dictCreateTab === 'single'" ref="dictFormRef" :disabled="dictSaving" :model="dictForm" :rules="dictRules" label-width="90px">
      <el-form-item label="权限码" prop="permKey">
        <el-input v-model="dictForm.permKey" :disabled="dictMode === 'edit'" placeholder="例如：operation:custom:resource:read" />
      </el-form-item>
      <el-form-item label="名称" prop="name">
        <el-input v-model="dictForm.name" :disabled="dictMode === 'edit' && dictForm.source === 'standard'" placeholder="例如：新增用户" />
      </el-form-item>
      <el-form-item label="分类" prop="category">
        <el-select
          v-model="dictForm.category"
          filterable
          allow-create
          default-first-option
          :disabled="dictMode === 'edit' && dictForm.source === 'standard'"
          placeholder="例如：系统配置/用户管理"
          class="w-full!"
        >
          <el-option v-for="c in dictCategoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述" prop="desc">
        <el-input v-model="dictForm.desc" :disabled="dictMode === 'edit' && dictForm.source === 'standard'" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
      </el-form-item>
      <el-form-item label="标签">
        <el-select v-model="dictForm.tags" :disabled="dictMode === 'edit' && dictForm.source === 'standard'" multiple filterable allow-create default-first-option placeholder="例如：可见、可用" class="w-full!">
          <el-option v-for="t in dictTagOptions" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="dictForm.enabled" />
      </el-form-item>
    </el-form>

    <div v-else class="space-y-3">
      <div class="flex items-center justify-between" :class="{ 'mobile-batch-toolbar': isMobile }">
        <div class="text-xs text-gray-500">{{ isMobile ? '逐项填写权限，标记必填的字段不能为空' : '每行一条权限码，带 * 的列为必填' }}</div>
        <div class="flex items-center gap-2">
          <el-button v-if="hasPerm(PERM_DICT.create)" @click="handleResetBatchRows">清空全部</el-button>
          <el-button v-if="hasPerm(PERM_DICT.create)" type="primary" plain @click="handleAddBatchRow">新增一行</el-button>
        </div>
      </div>
      <div v-if="isMobile" class="mobile-management-list">
        <details v-for="(row, index) in dictBatchRows" :key="row.rowId" class="mobile-management-card" :open="index === dictBatchRows.length - 1 || Boolean(row.errorFields.permKey || row.errorFields.name || row.errorFields.category)">
          <summary>第 {{ index + 1 }} 项 · {{ row.name || '待填写权限' }}</summary>
          <el-form label-position="top" :disabled="dictSaving"><el-form-item label="权限码（必填）" :error="row.errorFields.permKey ? '请填写有效权限码' : ''"><el-input v-model="row.permKey" /></el-form-item><el-form-item label="名称（必填）" :error="row.errorFields.name ? '请填写名称' : ''"><el-input v-model="row.name" /></el-form-item><el-form-item label="分类（必填）" :error="row.errorFields.category ? '请填写分类' : ''"><el-select v-model="row.category" filterable allow-create default-first-option><el-option v-for="item in dictCategoryOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="描述"><el-input v-model="row.desc" type="textarea" :rows="2" /></el-form-item><el-form-item label="标签"><el-select v-model="row.tags" multiple filterable allow-create default-first-option><el-option v-for="item in dictTagOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="启用"><el-switch v-model="row.enabled" /></el-form-item></el-form>
          <el-button v-if="hasPerm(PERM_DICT.create)" type="danger" plain @click="handleRemoveBatchRow(index)">移除此项</el-button>
        </details>
      </div>
      <div v-else class="max-h-105 overflow-auto border border-gray-200 rounded-lg">
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
                <el-input v-model="row.permKey" :class="{ 'is-error': row.errorFields.permKey }" placeholder="operation:custom:resource:read" />
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
                <el-button v-if="hasPerm(PERM_DICT.create)" type="danger" link @click="handleRemoveBatchRow(index)">删除</el-button>
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
        v-if="dictMode === 'edit' ? hasPerm(PERM_DICT.update) : hasPerm(PERM_DICT.create)"
        type="primary"
        :loading="dictSaving"
        :disabled="dictMode === 'edit' ? !hasPerm(PERM_DICT.update) : !hasPerm(PERM_DICT.create)"
        @click="handleSaveDict"
      >保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editUserDialogVisible" :title="userDialogTitle" width="520px" class="mobile-config-dialog">
    <div v-if="editingUser" class="space-y-4">
      <div class="text-sm text-gray-600">
        用户：{{ editingUser.display_name }}（@{{ editingUser.username }}）
      </div>

      <el-form label-width="80px">
        <el-form-item label="用户组">
          <el-select
            v-model="editUserGroupUuids"
            multiple
            :disabled="savingEditUser || !canUseEditUser || userDialogMode === 'detail'"
            placeholder="请选择用户组"
            class="w-full!"
          >
            <el-option
              v-for="group in groupChoices"
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

  <el-dialog v-model="createUserDialogVisible" title="新增用户" width="560px" class="mobile-config-dialog">
    <el-form ref="createUserFormRef" :disabled="creatingUser" :model="createUserForm" :rules="createUserRules" label-width="100px">
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
            v-for="group in groupChoices"
            :key="group.uuid"
            :label="group.display_name || group.group_name"
            :value="group.uuid"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="createUserDialogVisible = false">取消</el-button>
      <el-button v-if="hasPerm(PERM_USERS.create)" type="primary" :loading="creatingUser" @click="handleSubmitCreateUser">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createGroupDialogVisible" title="新增权限组" width="1200px" top="2vh" class="group-permission-dialog mobile-config-dialog">
    <nav v-if="isMobile" class="mobile-group-steps"><button :class="{ active: groupSection === 'profile' }" @click="groupSection = 'profile'">1 基本信息</button><button :class="{ active: groupSection === 'permissions' }" @click="groupSection = 'permissions'">2 分配权限</button></nav>
    <el-form ref="createGroupFormRef" :disabled="creatingGroup" :model="createGroupForm" :rules="createGroupRules" label-width="100px">
      <div v-show="!isMobile || groupSection === 'profile'">
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
      </div>
      <el-form-item v-show="!isMobile || groupSection === 'permissions'" label="权限码" prop="permissions">
        <div v-loading="permCodeCatalogLoading" class="w-full"><el-alert v-if="permCodeCatalogError" :title="permCodeCatalogError" type="error" :closable="false"><el-button link @click="fetchPermCodeCatalog">重新加载</el-button></el-alert>
          <GroupPermissionPicker
            v-model="createGroupForm.permissions"
            :perm-codes="enabledCatalogPermCodes"
            :disabled="creatingGroup || permCodeCatalogLoading || Boolean(permCodeCatalogError) || !hasPerm(PERM_GROUPS.create)"
            class="w-full"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="createGroupDialogVisible = false">取消</el-button>
      <el-button v-if="hasPerm(PERM_GROUPS.create)" type="primary" :loading="creatingGroup" :disabled="permCodeCatalogLoading || Boolean(permCodeCatalogError)" @click="handleSubmitCreateGroup">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editGroupDialogVisible" title="编辑权限组" width="1200px" top="2vh" class="group-permission-dialog mobile-config-dialog">
    <nav v-if="isMobile" class="mobile-group-steps"><button :class="{ active: groupSection === 'profile' }" @click="groupSection = 'profile'">1 基本信息</button><button :class="{ active: groupSection === 'permissions' }" @click="groupSection = 'permissions'">2 分配权限</button></nav>
    <div v-if="editingGroup" class="mb-3 text-sm text-gray-600">
      权限组：{{ editingGroup.display_name }}（@{{ editingGroup.group_name }}）
    </div>
    <el-form ref="editGroupFormRef" :disabled="savingEditGroup" :model="editGroupForm" :rules="editGroupRules" label-width="100px">
      <div v-show="!isMobile || groupSection === 'profile'">
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
      </div>
      <el-form-item v-show="!isMobile || groupSection === 'permissions'" label="权限码" prop="permissions">
        <div v-loading="permCodeCatalogLoading" class="w-full"><el-alert v-if="permCodeCatalogError" :title="permCodeCatalogError" type="error" :closable="false"><el-button link @click="fetchPermCodeCatalog">重新加载</el-button></el-alert>
          <GroupPermissionPicker
            v-model="editGroupForm.permissions"
            :perm-codes="enabledCatalogPermCodes"
            :disabled="savingEditGroup || permCodeCatalogLoading || Boolean(permCodeCatalogError) || !hasPerm(PERM_GROUPS.update)"
            class="w-full"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="editGroupDialogVisible = false">取消</el-button>
      <el-button v-if="hasPerm(PERM_GROUPS.update)" type="primary" :loading="savingEditGroup" :disabled="permCodeCatalogLoading || Boolean(permCodeCatalogError)" @click="handleSaveEditGroup">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, onDeactivated, reactive, watch, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import { formatDateTime } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { systemApi } from '@/api/system'
import GroupPermissionPicker from '@/components/system/GroupPermissionPicker.vue'
import { hasPerm } from '@/utils/permissionKit'
import { useMobileViewport } from '@/composables/useMobileViewport'

defineOptions({ name: 'UserPermissionManagement' })
const { isMobile } = useMobileViewport()
const groupSection = ref('profile')

const PERM_TABS = PERM.pages.system.permissions.tabs
const PERM_USERS = PERM.operations.system.users
const PERM_GROUPS = PERM.operations.system.groups
const PERM_DICT = PERM.operations.system.permissionCodes
let pageActive = true, pageEpoch = 0, dialogEpoch = 0, dictRequest = 0, catalogRequest = 0, optionsRequest = 0
let ownConfirmation = false, confirmationId = 0
const userLoading = ref(false), groupLoading = ref(false), dictLoading = ref(false)
const userError = ref(''), groupError = ref(''), dictError = ref(''), permCodeCatalogError = ref('')

const activeTab = ref('users')
const expandedTabKeys = ref([])
const userSearchKeyword = ref('')
const groupSearchKeyword = ref('')
const dictSearchKeyword = ref('')
const dictFilterCategory = ref('')
const currentListLoading = computed(() => ({ users: userLoading.value, groups: groupLoading.value, dictionary: dictLoading.value })[activeTab.value])
const currentListError = computed(() => ({ users: userError.value, groups: groupError.value, dictionary: dictError.value })[activeTab.value])

/**
 * 检查异步操作是否仍属于当前页面、模块和弹窗，并重新验证授权。
 * @param {object} context 操作开始时的页面、模块、权限及可选弹窗序号。
 * @returns {boolean} 只有当前上下文可以继续更新界面或提交写入。
 */
function isContextCurrent(context) {
  if (!pageActive || context.page !== pageEpoch || context.tab !== activeTab.value) return false
  if (context.dialog !== undefined && context.dialog !== dialogEpoch) return false
  const tab = PERM_TABS[context.tab]
  if (!tab || !hasPerm(tab.visible) || !hasPerm(tab.access)) return false
  return hasPerm(PERM.pages.system.permissions.access) && hasPerm(context.permission)
}

/**
 * 显示本页独占的业务确认，离页或撤权后即使确认迟到也不能执行写入。
 * @param {object} context 当前操作上下文。
 * @param {string} message 原业务确认文案。
 * @param {string} title 确认标题。
 * @param {object} options 原确认按钮选项。
 * @returns {Promise<boolean>} 当前上下文中明确确认才返回真。
 */
async function confirmCurrent(context, message, title, options) {
  if (ownConfirmation || !isContextCurrent(context)) return false
  const id = ++confirmationId
  ownConfirmation = true
  try {
    await ElMessageBox.confirm(message, title, options)
    return isContextCurrent(context)
  } catch { return false }
  finally { if (id === confirmationId) ownConfirmation = false }
}

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
const groupOptions = ref([])
const groupChoices = computed(() => [...new Map([...groupOptions.value, ...groupList.value].map(group => [group.uuid, group])).values()])
const userPage = ref(1)
const groupPage = ref(1)
const userTotal = ref(0)
const groupTotal = ref(0)
const mobileUsers = computed(() => userList.value.filter(item => `${item.display_name} ${item.username} ${item.email || ''}`.toLowerCase().includes(userSearchKeyword.value.trim().toLowerCase())))
const mobileGroups = computed(() => groupList.value.filter(item => `${item.display_name} ${item.group_name} ${item.remark || ''}`.toLowerCase().includes(groupSearchKeyword.value.trim().toLowerCase())))
let userRequest = 0
let groupRequest = 0
const permCodeList = ref([]) // 权限码字典列表（会被字典搜索影响）
const permCodeCatalogList = ref([]) // 权限组弹窗目录专用（与字典解耦）
const permCodeCatalogLoading = ref(false)
const deletingUserId = ref('')
const deletingGroupId = ref('')
const deletingDictId = ref('')

const editUserDialogVisible = ref(false)
const editingUser = ref(null)
const editUserGroupUuids = ref([])
const savingEditUser = ref(false)
const userDialogMode = ref('edit')

const canViewEditUserSave = computed(() => userDialogMode.value === 'edit' && hasPerm(PERM_USERS.groupUpdate))
const canUseEditUser = computed(() => hasPerm(PERM_USERS.groupUpdate))
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
watch([createGroupDialogVisible, editGroupDialogVisible], () => { groupSection.value = 'profile' })
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
  const requestId = ++userRequest
  const context = { page: pageEpoch, tab: activeTab.value, permission: PERM_USERS.listRead }
  if (!isContextCurrent(context)) return
  userLoading.value = true
  userError.value = ''
  try {
    const res = await systemApi.getUsers({ page: userPage.value, page_size: 10 })
    if (requestId !== userRequest || !isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !Array.isArray(res?.data?.items)) throw new Error(res?.message || '用户列表加载失败')
    userTotal.value = res.data.total || 0
    userList.value = res.data.items.map(user => ({ ...user, groups: Array.isArray(user.groups) ? user.groups : [] }))
  } catch (error) { if (requestId === userRequest && isContextCurrent(context)) userError.value = error?.message || '用户列表加载失败，请重试' }
  finally { if (requestId === userRequest) userLoading.value = false }
}

async function fetchGroups() {
  const requestId = ++groupRequest
  const context = { page: pageEpoch, tab: activeTab.value, permission: PERM_GROUPS.read }
  if (!isContextCurrent(context)) return
  groupLoading.value = true
  groupError.value = ''
  try {
    const res = await systemApi.getGroups({ page: groupPage.value, page_size: 10 })
    if (requestId !== groupRequest || !isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !Array.isArray(res?.data?.items)) throw new Error(res?.message || '权限组列表加载失败')
    groupTotal.value = res.data.total || 0
    groupList.value = res.data.items
  } catch (error) { if (requestId === groupRequest && isContextCurrent(context)) groupError.value = error?.message || '权限组列表加载失败，请重试' }
  finally { if (requestId === groupRequest) groupLoading.value = false }
}

function normalizePermCode(row) {
  return {
    uuid: row?.uuid || '',
    permKey: row?.perm_key || '',
    name: row?.name || '',
    category: row?.category || '',
    desc: row?.desc || '',
    tags: Array.isArray(row?.tags) ? row.tags : [],
    enabled: Boolean(row?.enabled),
    source: row?.source || 'placeholder',
    backendEnforced: Boolean(row?.backend_enforced),
    systemReserved: Boolean(row?.system_reserved)
  }
}

async function fetchPermCodes(params = {}) {
  const requestId = ++dictRequest
  const context = { page: pageEpoch, tab: 'dictionary', permission: PERM_DICT.read }
  if (!isContextCurrent(context)) return
  dictLoading.value = true
  dictError.value = ''
  try {
    const res = await systemApi.getPermCodes(params)
    if (requestId !== dictRequest || !isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !Array.isArray(res?.data)) throw new Error(res?.message || '权限码加载失败')
    permCodeList.value = res.data.map(normalizePermCode)
  } catch (error) { if (requestId === dictRequest && isContextCurrent(context)) dictError.value = error?.message || '权限码加载失败，请重试' }
  finally { if (requestId === dictRequest) dictLoading.value = false }
}

async function fetchPermCodeCatalog() {
  const requestId = ++catalogRequest
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'groups', permission: createGroupDialogVisible.value ? PERM_GROUPS.create : PERM_GROUPS.update }
  if (!isContextCurrent(context)) return
  permCodeCatalogLoading.value = true
  permCodeCatalogError.value = ''
  try {
    const res = await systemApi.getPermCodes({})
    if (requestId !== catalogRequest || !isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !Array.isArray(res?.data)) throw new Error(res?.message || '权限目录加载失败')
    permCodeCatalogList.value = res.data.map(normalizePermCode)
  } catch (error) {
    if (requestId === catalogRequest && isContextCurrent(context)) permCodeCatalogError.value = error?.message || '权限目录加载失败，请重试'
  } finally {
    if (requestId === catalogRequest) permCodeCatalogLoading.value = false
  }
}

async function loadActiveTabData(tab = activeTab.value) {
  try {
    if (tab === 'users' && hasPerm(PERM_USERS.listRead)) await fetchUsers()
    else if (tab === 'groups' && hasPerm(PERM_GROUPS.read)) await fetchGroups()
    else if (tab === 'dictionary' && hasPerm(PERM_DICT.read)) await fetchPermCodes({ keyword: dictSearchKeyword.value.trim() || undefined })
  } catch {
  }
}

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
    .filter(item => hasPerm(PERM_TABS[item.key]?.visible))
    .map(item => ({
      ...item,
      disabled: !hasPerm(PERM_TABS[item.key]?.access)
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

const canViewUserList = computed(() => hasPerm(PERM_TABS.users.visible) && hasPerm(PERM_TABS.users.access) && hasPerm(PERM_USERS.listRead))
const canViewGroupList = computed(() => hasPerm(PERM_TABS.groups.visible) && hasPerm(PERM_TABS.groups.access) && hasPerm(PERM_GROUPS.read))
const canViewDictList = computed(() => hasPerm(PERM_TABS.dictionary.visible) && hasPerm(PERM_TABS.dictionary.access) && hasPerm(PERM_DICT.read))

const canViewCurrentAdd = computed(() => {
  if (activeTab.value === 'users') return hasPerm(PERM_USERS.create)
  if (activeTab.value === 'groups') return hasPerm(PERM_GROUPS.create)
  if (activeTab.value === 'dictionary') return hasPerm(PERM_DICT.create)
  return false
})

const canUseCurrentAdd = computed(() => {
  if (activeTab.value === 'users') return hasPerm(PERM_USERS.create)
  if (activeTab.value === 'groups') return hasPerm(PERM_GROUPS.create)
  if (activeTab.value === 'dictionary') return hasPerm(PERM_DICT.create)
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
  enabled: true,
  originalEnabled: true,
  source: 'placeholder'
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
  if (!hasPerm(PERM_DICT.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value.push(createBatchRow())
}

function handleRemoveBatchRow(index) {
  if (!hasPerm(PERM_DICT.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value.splice(index, 1)
  if (dictBatchRows.value.length === 0) {
    dictBatchRows.value.push(createBatchRow())
  }
}

function handleResetBatchRows() {
  if (!hasPerm(PERM_DICT.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  dictBatchRows.value = [createBatchRow()]
  resetBatchRowErrors()
}

function openCreateDict() {
  if (!hasPerm(PERM_DICT.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'dictionary') return
  dialogEpoch++
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
  dictForm.originalEnabled = true
  dictForm.source = 'placeholder'
  dictDialogVisible.value = true
}

function openEditDict(row) {
  if (!hasPerm(PERM_DICT.update)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'dictionary' || row.systemReserved) return
  dialogEpoch++
  dictMode.value = 'edit'
  dictForm.uuid = row.uuid || ''
  dictForm.permKey = row.permKey
  dictForm.name = row.name || ''
  dictForm.category = row.category || ''
  dictForm.desc = row.desc || ''
  dictForm.tags = Array.isArray(row.tags) ? [...row.tags] : []
  dictForm.enabled = Boolean(row.enabled)
  dictForm.originalEnabled = Boolean(row.enabled)
  dictForm.source = row.source || 'placeholder'
  dictDialogVisible.value = true
}

async function handleDeleteDict(row) {
  if (!hasPerm(PERM_DICT.delete)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!row.uuid || row.source !== 'placeholder' || deletingDictId.value) return
  const context = { page: pageEpoch, tab: 'dictionary', permission: PERM_DICT.delete }
  if (!await confirmCurrent(context, `确认删除权限码：${row.permKey}？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })) return
  deletingDictId.value = row.uuid
  try {
    await systemApi.deletePermCode(row.uuid)
    if (!isContextCurrent(context)) return
    ElMessage.success('删除成功')
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '删除失败，请重试')
  } finally {
    if (context.page === pageEpoch) deletingDictId.value = ''
  }
}

async function handleSaveDict() {
  const permission = dictMode.value === 'edit' ? PERM_DICT.update : PERM_DICT.create
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'dictionary', permission }
  if (!isContextCurrent(context) || !dictDialogVisible.value || dictSaving.value) return
  if (dictMode.value === 'create' && dictCreateTab.value === 'batch') {
    await handleSaveDictBatch()
    return
  }
  dictSaving.value = true
  try {
    const ok = await dictFormRef.value?.validate?.().catch(() => false)
    if (!ok || !isContextCurrent(context)) return
    const snapshot = { ...dictForm, tags: [...dictForm.tags] }
    const mode = dictMode.value
    const name = String(snapshot.name || '').trim()
    const category = String(snapshot.category || '').trim()
    const desc = String(snapshot.desc || '').trim()
    const tags = snapshot.tags.map(tag => String(tag).trim()).filter(Boolean)
    if (mode === 'create') {
      await systemApi.createPermCode({ perm_key: String(snapshot.permKey || '').trim(), name, category, desc: desc || undefined, tags, enabled: Boolean(snapshot.enabled) })
      if (!isContextCurrent(context)) return
      ElMessage.success('新增成功')
    } else {
      let impactAcknowledged = false
      if (snapshot.originalEnabled && !snapshot.enabled) {
        const impactRes = await systemApi.getPermCodeImpact(snapshot.uuid)
        if (!isContextCurrent(context)) return
        if (impactRes?.code != null && impactRes.code !== 0) throw new Error(impactRes.message || '权限影响范围加载失败')
        const impact = impactRes?.data || {}
        const message = '禁用后将影响 ' + (impact.group_count || 0) + ' 个权限组、' + (impact.user_count || 0) + ' 个用户，是否继续？'
        if (!await confirmCurrent(context, message, '禁用权限确认', { type: 'warning' })) return
        impactAcknowledged = true
      }
      const payload = snapshot.source === 'standard'
        ? { enabled: Boolean(snapshot.enabled), impact_acknowledged: impactAcknowledged }
        : { name, category, desc: desc || undefined, tags, enabled: Boolean(snapshot.enabled), impact_acknowledged: impactAcknowledged }
      if (!isContextCurrent(context)) return
      await systemApi.updatePermCode(snapshot.uuid, payload)
      if (!isContextCurrent(context)) return
      ElMessage.success('保存成功')
    }
    dictDialogVisible.value = false
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '保存失败，请重试')
  } finally {
    if (context.dialog === dialogEpoch) dictSaving.value = false
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
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'dictionary', permission: PERM_DICT.create }
  if (dictSaving.value || !dictDialogVisible.value || !isContextCurrent(context)) return
  const normalizedRows = validateBatchRows()
  if (normalizedRows.length === 0) return

  dictSaving.value = true
  try {
    await systemApi.createPermCodesBatch({
      items: normalizedRows.map(row => row.item)
    })
    if (!isContextCurrent(context)) return
    ElMessage.success('批量新增成功')
    dictDialogVisible.value = false
    handleResetBatchRows()
    await fetchPermCodes({ keyword: String(dictSearchKeyword.value || '').trim() || undefined })
  } catch (error) {
    if (!isContextCurrent(context)) return
    const message = getRequestErrorMessage(error)
    applyBatchErrorFeedback(message)
  } finally {
    if (context.dialog === dialogEpoch) dictSaving.value = false
  }
}

let dictSearchTimer = null
watch(
  () => [activeTab.value, dictSearchKeyword.value],
  ([tab, keyword]) => {
    if (dictSearchTimer) clearTimeout(dictSearchTimer)
    dictSearchTimer = null
    dictRequest++
    if (!pageActive || tab !== 'dictionary') return
    dictSearchTimer = setTimeout(() => {
      fetchPermCodes({ keyword: String(keyword || '').trim() || undefined }).catch(() => {})
    }, 300)
  }
)

async function handleEditUser(user) {
  if (!hasPerm(PERM_USERS.groupUpdate)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'users' || user?.is_system) return
  const context = { page: pageEpoch, dialog: ++dialogEpoch, tab: 'users', permission: PERM_USERS.groupUpdate }
  try {
    const res = await systemApi.getUser(user.uuid)
    if (!isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !res?.data) throw new Error(res?.message || '用户详情加载失败')
    const detail = res?.data || user
    if (isMobile.value) await loadMobileGroupOptions()
    if (!isContextCurrent(context)) return
    userDialogMode.value = 'edit'
    editingUser.value = detail
    editUserGroupUuids.value = Array.isArray(detail.groups) ? [...detail.groups] : []
    editUserDialogVisible.value = true
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '用户详情加载失败，请重试')
  }
}

async function handleViewUser(user) {
  if (!hasPerm(PERM_USERS.detailRead)) {
    ElMessage.warning('暂无查看权限')
    return
  }
  if (!pageActive || activeTab.value !== 'users') return
  const context = { page: pageEpoch, dialog: ++dialogEpoch, tab: 'users', permission: PERM_USERS.detailRead }
  try {
    const res = await systemApi.getUser(user.uuid)
    if (!isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !res?.data) throw new Error(res?.message || '用户详情加载失败')
    const detail = res?.data || user
    userDialogMode.value = 'detail'
    editingUser.value = detail
    editUserGroupUuids.value = Array.isArray(detail.groups) ? [...detail.groups] : []
    editUserDialogVisible.value = true
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '用户详情加载失败，请重试')
  }
}

async function handleDeleteUser(user) {
  if (!hasPerm(PERM_USERS.delete)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (user?.is_system) {
    ElMessage.warning('系统内置账号不可删除')
    return
  }
  if (!user?.uuid || deletingUserId.value) return
  const context = { page: pageEpoch, tab: 'users', permission: PERM_USERS.delete }
  const userLabel = user.display_name || user.username || user.uuid
  if (!await confirmCurrent(context,
      `确认删除用户“${userLabel}”？删除后账号将被停用，所有活动会话将终止。`,
      '删除用户',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      }
    )) return

  deletingUserId.value = user.uuid
  try {
    await systemApi.deleteUser(user.uuid)
    if (!isContextCurrent(context)) return
    ElMessage.success('用户删除成功')
    await fetchUsers()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '删除失败，请重试')
  } finally {
    if (context.page === pageEpoch) deletingUserId.value = ''
  }
}

function handleEditGroup(group) {
  if (!hasPerm(PERM_GROUPS.update)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'groups' || group?.is_system) return
  dialogEpoch++
  editingGroup.value = group
  editGroupForm.group_name = group?.group_name || ''
  editGroupForm.display_name = group?.display_name || ''
  editGroupForm.remark = group?.remark || ''
  editGroupForm.enabled = Boolean(group?.enabled)
  editGroupForm.permissions = Array.isArray(group?.permissions) ? [...group.permissions] : []
  editGroupDialogVisible.value = true
  fetchPermCodeCatalog()
}

async function handleDeleteGroup(group) {
  if (!hasPerm(PERM_GROUPS.delete)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (group?.is_system) {
    ElMessage.warning('系统内置权限组不可删除')
    return
  }
  if (!group?.uuid || deletingGroupId.value) return
  const context = { page: pageEpoch, tab: 'groups', permission: PERM_GROUPS.delete }
  const groupLabel = group.display_name || group.group_name || group.uuid
  if (!await confirmCurrent(context,
      `确认删除权限组“${groupLabel}”？仅未被用户引用的权限组可以删除。`,
      '删除权限组',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      }
    )) return

  deletingGroupId.value = group.uuid
  try {
    await systemApi.deleteGroup(group.uuid)
    if (!isContextCurrent(context)) return
    ElMessage.success('权限组删除成功')
    await fetchGroups()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '删除失败，请重试')
  } finally {
    if (context.page === pageEpoch) deletingGroupId.value = ''
  }
}

async function openCreateUserDialog() {
  if (!hasPerm(PERM_USERS.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'users') return
  const context = { page: pageEpoch, dialog: ++dialogEpoch, tab: 'users', permission: PERM_USERS.create }
  createUserForm.username = ''
  createUserForm.password = ''
  createUserForm.display_name = ''
  createUserForm.email = ''
  createUserForm.remark = ''
  createUserForm.enabled = true
  createUserForm.temporary_account = false
  createUserForm.expired_at = ''
  createUserForm.groups = []
  try {
    if (isMobile.value) await loadMobileGroupOptions()
    else if (hasPerm(PERM_GROUPS.read)) await fetchGroups()
    if (isContextCurrent(context)) createUserDialogVisible.value = true
  } catch (error) { if (isContextCurrent(context)) ElMessage.error(error?.message || '权限组选项加载失败，请重试') }
}

/** """手机用户表单读取完整可选权限组，不受列表当前页限制。""" */
async function loadMobileGroupOptions() {
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'users', permission: PERM_GROUPS.read }
  const requestId = ++optionsRequest
  if (!isContextCurrent(context)) { groupOptions.value = []; return }
  const groups = []
  let page = 1
  let total = 0
  do {
    const res = await systemApi.getGroups({ page, page_size: 100 })
    if (requestId !== optionsRequest || !isContextCurrent(context)) return
    if ((res?.code != null && res.code !== 0) || !Array.isArray(res?.data?.items)) throw new Error(res?.message || '权限组选项加载失败')
    const items = res.data.items
    groups.push(...items)
    total = res?.data?.total || 0
    if (!items.length) break
    page += 1
  } while (groups.length < total)
  if (requestId === optionsRequest && isContextCurrent(context)) groupOptions.value = groups
}

function openCreateGroupDialog() {
  if (!hasPerm(PERM_GROUPS.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!pageActive || activeTab.value !== 'groups') return
  dialogEpoch++
  createGroupForm.group_name = ''
  createGroupForm.display_name = ''
  createGroupForm.remark = ''
  createGroupForm.enabled = true
  createGroupForm.permissions = []
  createGroupDialogVisible.value = true
  fetchPermCodeCatalog()
}

async function handleSaveEditUser() {
  if (!hasPerm(PERM_USERS.groupUpdate)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!editingUser.value || !editUserDialogVisible.value || savingEditUser.value || userDialogMode.value !== 'edit') return
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'users', permission: PERM_USERS.groupUpdate }
  if (!isContextCurrent(context)) return
  savingEditUser.value = true
  try {
    await systemApi.updateUserGroups(editingUser.value.uuid, {
      groups: [...editUserGroupUuids.value]
    })
    if (!isContextCurrent(context)) return
    ElMessage.success('保存成功')
    editUserDialogVisible.value = false
    await fetchUsers()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '保存失败，请重试')
  } finally {
    if (context.dialog === dialogEpoch) savingEditUser.value = false
  }
}

async function handleSubmitCreateUser() {
  if (!hasPerm(PERM_USERS.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (creatingUser.value || !createUserDialogVisible.value) return
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'users', permission: PERM_USERS.create }
  if (!isContextCurrent(context)) return
  creatingUser.value = true
  try {
    const ok = await createUserFormRef.value?.validate?.().catch(() => false)
    if (!ok || !isContextCurrent(context)) return
    const payload = {
      username: createUserForm.username.trim(),
      password: createUserForm.password,
      display_name: createUserForm.display_name.trim(),
      email: createUserForm.email?.trim() || undefined,
      remark: createUserForm.remark?.trim() || undefined,
      enabled: Boolean(createUserForm.enabled),
      temporary_account: Boolean(createUserForm.temporary_account),
      expired_at: createUserForm.expired_at || undefined,
      groups: Array.isArray(createUserForm.groups) ? [...createUserForm.groups] : []
    }
    await systemApi.createUser(payload)
    if (!isContextCurrent(context)) return
    ElMessage.success('创建成功')
    createUserDialogVisible.value = false
    await fetchUsers()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '创建失败，请重试')
  } finally {
    if (context.dialog === dialogEpoch) creatingUser.value = false
  }
}

async function handleSubmitCreateGroup() {
  if (!hasPerm(PERM_GROUPS.create)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (creatingGroup.value || !createGroupDialogVisible.value || permCodeCatalogLoading.value || permCodeCatalogError.value) return
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'groups', permission: PERM_GROUPS.create }
  if (!isContextCurrent(context)) return
  creatingGroup.value = true
  try {
    const ok = await createGroupFormRef.value?.validate?.().catch(() => false)
    if (!isContextCurrent(context)) return
    if (!ok) { groupSection.value = 'profile'; return }
    const payload = {
      group_name: createGroupForm.group_name.trim(),
      display_name: createGroupForm.display_name.trim(),
      remark: createGroupForm.remark?.trim() || undefined,
      enabled: Boolean(createGroupForm.enabled),
      permissions: Array.isArray(createGroupForm.permissions) ? [...createGroupForm.permissions] : []
    }
    await systemApi.createGroup(payload)
    if (!isContextCurrent(context)) return
    ElMessage.success('创建成功')
    createGroupDialogVisible.value = false
    await fetchGroups()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '创建失败，请重试')
  } finally {
    if (context.dialog === dialogEpoch) creatingGroup.value = false
  }
}

async function handleSaveEditGroup() {
  if (!hasPerm(PERM_GROUPS.update)) {
    ElMessage.warning('暂无操作权限')
    return
  }
  if (!editingGroup.value || !editGroupDialogVisible.value || savingEditGroup.value || permCodeCatalogLoading.value || permCodeCatalogError.value) return
  const context = { page: pageEpoch, dialog: dialogEpoch, tab: 'groups', permission: PERM_GROUPS.update }
  if (!isContextCurrent(context)) return
  savingEditGroup.value = true
  try {
    const ok = await editGroupFormRef.value?.validate?.().catch(() => false)
    if (!isContextCurrent(context)) return
    if (!ok) { groupSection.value = 'profile'; return }
    const payload = {
      display_name: editGroupForm.display_name.trim(),
      remark: editGroupForm.remark?.trim() || undefined,
      enabled: Boolean(editGroupForm.enabled),
      permissions: Array.isArray(editGroupForm.permissions) ? [...editGroupForm.permissions] : []
    }
    await systemApi.updateGroup(editingGroup.value.uuid, payload)
    if (!isContextCurrent(context)) return
    ElMessage.success('保存成功')
    editGroupDialogVisible.value = false
    await fetchGroups()
  } catch (error) {
    if (isContextCurrent(context)) ElMessage.error(error?.message || '保存失败，请重试')
  } finally {
    if (context.dialog === dialogEpoch) savingEditGroup.value = false
  }
}

/**
 * 作废当前页面的异步工作并关闭挂载到 body 的弹窗，保留列表筛选和页码。
 * @returns {void} 页面再次激活时重新读取当前模块。
 */
function invalidatePageWork() {
  pageEpoch++; dialogEpoch++; userRequest++; groupRequest++; dictRequest++; catalogRequest++; optionsRequest++
  if (dictSearchTimer) clearTimeout(dictSearchTimer)
  dictSearchTimer = null
  confirmationId++
  if (ownConfirmation) ElMessageBox.close()
  ownConfirmation = false
  editUserDialogVisible.value = false; createUserDialogVisible.value = false
  editGroupDialogVisible.value = false; createGroupDialogVisible.value = false; dictDialogVisible.value = false
  editingUser.value = null; editingGroup.value = null
  creatingUser.value = false; creatingGroup.value = false; savingEditUser.value = false; savingEditGroup.value = false; dictSaving.value = false
  userLoading.value = false; groupLoading.value = false; dictLoading.value = false; permCodeCatalogLoading.value = false
  userError.value = ''; groupError.value = ''; dictError.value = ''
  deletingUserId.value = ''; deletingGroupId.value = ''; deletingDictId.value = ''
}

watch([editUserDialogVisible, createUserDialogVisible, editGroupDialogVisible, createGroupDialogVisible, dictDialogVisible], (values, previous) => {
  if (!values.some((value, index) => !value && previous[index])) return
  dialogEpoch++; catalogRequest++; optionsRequest++
  creatingUser.value = false; creatingGroup.value = false; savingEditUser.value = false; savingEditGroup.value = false; dictSaving.value = false; permCodeCatalogLoading.value = false
}, { flush: 'sync' })
watch(activeTab, () => { invalidatePageWork(); loadActiveTabData() })
watch(() => [PERM.pages.system.permissions.access, ...Object.values(PERM_TABS).flatMap(tab => [tab.visible, tab.access]), ...Object.values(PERM_USERS), ...Object.values(PERM_GROUPS), ...Object.values(PERM_DICT)].map(code => hasPerm(code)), () => {
  invalidatePageWork()
  if (!canViewUserList.value) userList.value = []
  if (!canViewGroupList.value) groupList.value = []
  if (!canViewDictList.value) permCodeList.value = []
  if (!hasPerm(PERM_GROUPS.read)) groupOptions.value = []
  loadActiveTabData()
})
onMounted(() => loadActiveTabData())
onActivated(() => { if (!pageActive) { pageActive = true; loadActiveTabData() } })
onDeactivated(() => { pageActive = false; invalidatePageWork() })
onBeforeUnmount(() => { pageActive = false; invalidatePageWork() })
</script>

<style scoped>
.mobile-management-list { display: grid; gap: 12px; }
.mobile-management-card { border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; background: white; min-width: 0; overflow-wrap: anywhere; }
.mobile-management-card header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.mobile-management-card header > div { min-width: 0; }
.mobile-management-card h2 { font-weight: 700; font-size: 17px; color: #0f172a; }
.mobile-management-card p { margin-top: 6px; font-size: 13px; color: #64748b; line-height: 1.6; }
.mobile-management-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.mobile-management-tags :deep(.el-tag) { max-width: 100%; height: auto; min-height: 24px; white-space: normal; }
.mobile-management-card summary { min-height: 44px; padding-block: 12px; font-size: 14px; color: #475569; cursor: pointer; }
.mobile-management-card dl { margin: 0; font-size: 13px; line-height: 1.7; }
.mobile-management-card dt { color: #64748b; margin-top: 8px; }
.mobile-management-card dd { margin: 0; color: #0f172a; }
.mobile-management-card footer { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.mobile-management-card footer .el-button { flex: 1; min-height: 44px; margin: 0; }
.mobile-permission-code { font-family: monospace; overflow-wrap: anywhere; }
.mobile-group-steps { display: flex; gap: 8px; margin-bottom: 16px; position: sticky; top: 0; background: white; z-index: 2; padding-bottom: 8px; }
.mobile-group-steps button { flex: 1; min-height: 44px; border-radius: 10px; background: #f1f5f9; color: #475569; }
.mobile-group-steps button.active { background: #dbeafe; color: #1d4ed8; font-weight: 600; }
.mobile-batch-toolbar { flex-direction: column; align-items: stretch; gap: 10px; }
.mobile-batch-toolbar .el-button { flex: 1; min-height: 44px; margin: 0; }
:deep(.group-permission-dialog .el-dialog__body) {
  max-height: calc(100vh - 180px);
  overflow: auto;
}
</style>
