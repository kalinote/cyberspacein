<template>
  <div class="min-h-screen bg-gray-50 pb-28">
    <Header v-if="!isMobile" />
    <FunctionalPageHeader
      v-if="!isMobile"
      title-prefix="系统"
      title-suffix="配置"
      subtitle="集中管理后端运行参数。更改会根据配置类型实时生效或在服务自动重启后生效。"
    />

    <el-alert v-if="!canRead" title="暂无系统配置读取权限" type="warning" :closable="false" class="m-4" />
    <main v-else-if="isMobile" v-loading="loading" class="mobile-system-config">
      <header><h1>系统配置</h1><p>按生效方式与类别管理运行参数</p></header>
      <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" />
      <section class="mobile-system-status">
        <strong>{{ configData ? (configData.ready ? '服务运行正常' : '服务启动中') : '等待加载配置' }}</strong><span>v{{ configData?.version ?? '—' }}</span>
        <details><summary>运行与修改记录</summary><p>启动：{{ formatDate(configData?.started_at) }}</p><p>最近修改：{{ configData?.updated_by || '环境变量基线' }} · {{ formatDate(configData?.updated_at) }}</p></details>
        <div><el-button @click="openHistory">配置历史</el-button><el-button :disabled="Boolean(Object.keys(allChanges).length)" @click="loadConfig">刷新</el-button></div>
      </section>
      <section v-if="historyConflict" class="mobile-system-notice"><strong>配置历史存在冲突</strong><p>请完成存储协调后再保存、取消或还原配置。</p><el-button type="danger" :loading="coordinationLoading" :disabled="!canExecute" @click="openCoordination">查看差异并协调</el-button></section>
      <el-alert v-else-if="configData?.history_sync_status === 'pending'" title="配置已保存，历史正在等待同步" type="info" :closable="false" />
      <section v-if="configData?.restart_required" class="mobile-system-notice"><strong>{{ configData.pending_status === 'baseline_conflict' ? '部署环境已变化，待重启配置未应用' : `v${configData.pending_version} 等待重启生效` }}</strong><p>{{ configData.pending_status === 'baseline_conflict' ? '请取消待重启配置，基于最新环境重新编辑。' : `${configData.pending_fields?.length || 0} 项字段将在服务重启后生效。` }}</p><div><el-button @click="showPendingFields">查看字段</el-button><el-button type="danger" plain :disabled="historyConflict || !canExecute" :loading="cancelLoading" @click="cancelPending">取消待重启变更</el-button></div></section>
      <nav class="mobile-system-modes" aria-label="配置生效方式"><button v-for="item in modeSummary" :key="item.mode" :class="{ active: activeMode === item.mode }" @click="switchMode(item.mode); mobileConfigList = false"><Icon :icon="item.icon" /><span>{{ item.label }}</span><small>{{ item.count }} 项<span v-if="item.dirtyCount"> · {{ item.dirtyCount }} 项修改</span></small></button></nav>
      <p class="mobile-system-mode-help">{{ activeModeInfo.description }}</p>
      <el-input v-model="searchQuery" clearable placeholder="搜索当前生效方式下的配置" @input="mobileConfigList = true; activeGroup = 'all'"><template #prefix><Icon icon="mdi:magnify" /></template></el-input>
      <nav v-if="!mobileConfigList && !searchQuery" class="mobile-system-categories" aria-label="配置类别">
        <button v-for="group in mobileConfigGroups" :key="group.key" @click="activeGroup = group.key; mobileConfigList = true"><strong>{{ group.label }}</strong><span>{{ group.count }} 项</span><Icon icon="mdi:chevron-right" /></button>
        <p v-if="!mobileConfigGroups.length">当前类型没有配置项</p>
      </nav>
      <section v-else class="mobile-system-fields">
        <button class="mobile-system-back" @click="mobileConfigList = false; searchQuery = ''; activeGroup = 'all'"><Icon icon="mdi:chevron-left" />返回类别</button>
        <section v-for="group in visibleGroups" :key="group.key"><h2>{{ group.label }}</h2><button v-for="field in group.fields" :key="field.key" class="mobile-system-field" @click="mobileFieldKey = field.key"><span><strong>{{ field.label }}</strong><small>{{ field.sensitive ? (form[field.key] ? '已填写新值，待保存' : field.configured ? '已配置，内容已隐藏' : '未配置') : formatDisplayValue(form[field.key]) }}</small></span><el-tag v-if="isDirty(field.key)" size="small">已修改</el-tag><Icon :icon="field.editable ? 'mdi:chevron-right' : 'mdi:lock-outline'" /></button></section>
        <el-empty v-if="!visibleGroups.length" description="没有匹配的配置项" />
      </section>
      <MobileActionBar v-if="activeDirtyCount" aria-label="保存系统配置"><el-button @click="resetChanges(activeMode)">放弃本组</el-button><el-button :type="activeMode === 'restart' ? 'warning' : 'primary'" :loading="previewLoading" :disabled="historyConflict || !canUpdate" @click="openPreview(activeMode)">预览 {{ activeDirtyCount }} 项修改</el-button></MobileActionBar>
      <MobileSheet :model-value="Boolean(mobileField)" :title="mobileField?.label || '配置详情'" @update:model-value="value => { if (!value) mobileFieldKey = '' }">
        <div v-if="mobileField" class="mobile-system-field-editor">
          <el-tag :type="modeTagType(mobileField.apply_mode)">{{ modeLabel(mobileField.apply_mode) }}</el-tag><p>{{ mobileField.description }}</p><code>{{ mobileField.key }}</code>
          <p v-if="!mobileField.editable || !canUpdate" class="break-all">{{ mobileField.sensitive ? (mobileField.configured ? '已配置（内容已隐藏）' : '未配置') : formatDisplayValue(form[mobileField.key]) }}</p>
          <el-switch v-else-if="mobileField.value_type === 'boolean'" v-model="form[mobileField.key]" :disabled="!mobileField.editable || !canUpdate" inline-prompt active-text="启用" inactive-text="停用" />
          <el-input-number v-else-if="mobileField.value_type === 'integer' || mobileField.value_type === 'number'" v-model="form[mobileField.key]" :disabled="!mobileField.editable || !canUpdate" :min="mobileField.constraints?.min" :max="mobileField.constraints?.max" :precision="mobileField.value_type === 'integer' ? 0 : 1" controls-position="right" />
          <el-input v-else v-model="form[mobileField.key]" :disabled="!mobileField.editable || !canUpdate" :type="mobileField.sensitive ? 'password' : 'text'" :show-password="mobileField.sensitive && mobileField.editable" :placeholder="mobileField.sensitive && mobileField.configured ? '留空保持原值' : '请输入配置值'" clearable />
          <p v-if="mobileField.pending_change">当前运行值：{{ mobileField.sensitive ? (mobileField.active_configured ? '已配置（内容已隐藏）' : '未配置') : formatDisplayValue(mobileField.active_value) }}</p>
          <small v-if="mobileField.editable && canUpdate">修改先保留在当前页面，返回后通过底部按钮预览并保存。</small>
        </div>
        <template #footer><el-button type="primary" class="w-full" @click="mobileFieldKey = ''">完成</el-button></template>
      </MobileSheet>
    </main>
    <main v-else class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-7" v-loading="loading">
      <section class="grid grid-cols-1 xl:grid-cols-[1fr_auto] gap-4 mb-5">
        <div class="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div class="flex flex-wrap items-center gap-x-8 gap-y-3">
            <div>
              <p class="text-xs text-gray-500 mb-1">服务状态</p>
              <div class="flex items-center gap-2 font-semibold text-gray-900">
                <span class="w-2.5 h-2.5 rounded-full" :class="configData?.ready ? 'bg-emerald-500' : 'bg-amber-500'" />
                {{ configData?.ready ? '运行正常' : '启动中' }}
              </div>
            </div>
            <div><p class="text-xs text-gray-500 mb-1">配置版本</p><p class="font-semibold text-gray-900">v{{ configData?.version ?? 0 }}</p></div>
            <div><p class="text-xs text-gray-500 mb-1">启动时间</p><p class="text-sm font-medium text-gray-800">{{ formatDate(configData?.started_at) }}</p></div>
            <div>
              <p class="text-xs text-gray-500 mb-1">最近修改</p>
              <p class="text-sm font-medium text-gray-800">{{ configData?.updated_by || '环境变量基线' }} · {{ formatDate(configData?.updated_at) }}</p>
            </div>
            <div>
              <p class="text-xs text-gray-500 mb-1">配置状态</p>
              <p class="text-sm font-semibold" :class="configData?.restart_required ? 'text-amber-600' : 'text-emerald-600'">{{ configData?.restart_required ? `v${configData.pending_version} 等待重启` : '全部已生效' }}</p>
            </div>
          </div>
        </div>
        <div class="grid grid-cols-2 xl:grid-cols-1 gap-3">
          <button class="bg-white border border-gray-200 rounded-2xl px-5 py-3 shadow-sm flex items-center justify-center gap-3 hover:border-blue-300 transition-colors" @click="openHistory"><Icon icon="mdi:history" class="text-xl text-blue-500" /><span class="font-medium text-gray-700">配置历史</span></button>
          <button class="bg-white border border-gray-200 rounded-2xl px-5 py-3 shadow-sm flex items-center justify-center gap-3 hover:border-blue-300 transition-colors" @click="loadConfig"><Icon icon="mdi:refresh" class="text-xl text-blue-500" /><span class="font-medium text-gray-700">刷新配置</span></button>
        </div>
      </section>

      <div v-if="configData?.history_sync_status === 'conflict'" class="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-4 shadow-sm sm:px-5">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-100 text-red-600">
              <Icon icon="mdi:alert-circle-outline" class="text-2xl" />
            </div>
            <div>
              <p class="font-semibold text-red-900">配置文件与 MongoDB 历史存在冲突</p>
              <p class="mt-1 text-sm leading-6 text-red-700">为避免覆盖历史记录，保存、取消和还原操作已暂停，请先完成存储协调。</p>
            </div>
          </div>
          <el-button type="danger" class="shrink-0 self-end sm:self-auto" :loading="coordinationLoading" :disabled="!canExecute" @click.stop="openCoordination">强制同步</el-button>
        </div>
      </div>
      <el-alert v-else-if="configData?.history_sync_status === 'pending'" class="mb-5" title="配置已保存，MongoDB 历史正在等待同步。" type="info" :closable="false" show-icon />
      <div v-if="configData?.restart_required" class="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-amber-800">
        <div class="flex gap-3"><Icon icon="mdi:restart-alert" class="text-2xl shrink-0" /><div><p class="font-semibold">{{ configData.pending_status === 'baseline_conflict' ? '部署环境已变化，待重启配置未应用' : '配置已保存，需要重启服务' }}</p><p class="text-sm mt-1">{{ configData.pending_status === 'baseline_conflict' ? '请取消当前待重启配置，并基于最新环境重新编辑和保存。' : `版本 v${configData.pending_version} 的 ${configData.pending_fields?.length || 0} 项配置将在下次服务重启后生效。` }}</p></div></div>
        <div class="flex gap-2 self-end sm:self-auto"><el-button type="warning" plain @click="showPendingFields">查看字段</el-button><el-button type="danger" plain :loading="cancelLoading" :disabled="historyConflict || !canExecute" @click="cancelPending">取消待重启变更</el-button></div>
      </div>

      <section class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
        <button v-for="item in modeSummary" :key="item.mode" type="button" class="bg-white border rounded-xl p-4 flex items-center gap-3 text-left transition-all" :class="activeMode === item.mode ? item.activeClass : 'border-gray-200 hover:border-gray-300'" @click="switchMode(item.mode)">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center" :class="item.iconBg"><Icon :icon="item.icon" class="text-xl" :class="item.iconColor" /></div>
          <div class="min-w-0 flex-1"><p class="text-sm text-gray-500">{{ item.label }}</p><div class="flex items-center gap-2"><p class="text-xl font-bold text-gray-900">{{ item.count }}</p><el-tag v-if="item.dirtyCount" size="small" :type="item.mode === 'restart' ? 'warning' : 'primary'">{{ item.dirtyCount }} 项未保存</el-tag></div></div>
          <Icon icon="mdi:chevron-right" class="text-gray-400" />
        </button>
      </section>

      <section class="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
        <div class="mx-4 mt-4 sm:mx-5 sm:mt-5 rounded-xl border p-4 flex gap-3" :class="activeModeInfo.bannerClass">
          <Icon :icon="activeModeInfo.icon" class="text-xl shrink-0 mt-0.5" />
          <div><h2 class="font-semibold">{{ activeModeInfo.title }}</h2><p class="text-sm mt-1 opacity-80">{{ activeModeInfo.description }}</p></div>
        </div>
        <div class="p-4 sm:p-5 border-b border-gray-100 flex flex-col lg:flex-row gap-4 lg:items-center lg:justify-between">
          <div class="flex gap-2 overflow-x-auto pb-1 lg:pb-0">
            <button v-for="group in navGroups" :key="group.key" class="shrink-0 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors" :class="activeGroup === group.key ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'" @click="activeGroup = group.key">
              {{ group.label }}
            </button>
          </div>
          <el-input v-model="searchQuery" clearable placeholder="搜索配置名称或键名" class="lg:max-w-80"><template #prefix><Icon icon="mdi:magnify" /></template></el-input>
        </div>

        <div v-if="visibleGroups.length" class="divide-y divide-gray-100">
          <section v-for="group in visibleGroups" :key="group.key" class="p-5 sm:p-6">
            <div class="mb-4"><h2 class="text-lg font-bold text-gray-900">{{ group.label }}</h2><p class="text-sm text-gray-500 mt-1">{{ group.fields.length }} 项配置</p></div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div v-for="field in group.fields" :key="field.key" class="rounded-xl border p-4 transition-colors" :class="isDirty(field.key) ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200 bg-white'">
                <div class="flex items-start justify-between gap-3 mb-3">
                  <div class="min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <label class="font-semibold text-gray-900">{{ field.label }}</label>
                      <el-tag :type="modeTagType(field.apply_mode)" size="small" effect="light">{{ modeLabel(field.apply_mode) }}</el-tag>
                      <span v-if="field.sensitive" class="text-xs text-amber-600 flex items-center gap-1"><Icon icon="mdi:shield-key-outline" /> 敏感</span>
                    </div>
                    <p class="text-xs text-gray-400 font-mono mt-1 break-all">{{ field.key }}</p>
                    <p v-if="field.description" class="text-sm text-gray-500 mt-2">{{ field.description }}</p>
                  </div>
                  <Icon v-if="field.apply_mode === 'readonly'" icon="mdi:lock-outline" class="text-gray-400 text-lg shrink-0" />
                </div>
                <div v-if="field.apply_mode === 'readonly' && field.sensitive" class="h-9 flex items-center">
                  <el-tag :type="field.configured ? 'success' : 'info'" effect="plain">{{ field.configured ? '已配置（内容已隐藏）' : '未配置' }}</el-tag>
                </div>
                <el-switch v-else-if="field.value_type === 'boolean'" v-model="form[field.key]" :disabled="!field.editable || !canUpdate" inline-prompt active-text="启用" inactive-text="停用" />
                <el-input-number v-else-if="field.value_type === 'integer' || field.value_type === 'number'" v-model="form[field.key]" :disabled="!field.editable || !canUpdate" :min="field.constraints?.min" :max="field.constraints?.max" :precision="field.value_type === 'integer' ? 0 : 1" controls-position="right" class="w-full!" />
                <el-input v-else v-model="form[field.key]" :disabled="!field.editable || !canUpdate" :type="field.sensitive ? 'password' : 'text'" :show-password="field.sensitive && field.editable" :placeholder="field.sensitive && field.configured ? '已配置，留空表示保持原值' : '请输入配置值'" clearable />
                <p v-if="field.pending_change" class="mt-2 text-xs text-amber-600"><Icon icon="mdi:clock-outline" class="inline text-sm mr-1" />当前运行值：{{ field.sensitive ? (field.active_configured ? '已配置（内容已隐藏）' : '未配置') : formatDisplayValue(field.active_value) }}</p>
              </div>
            </div>
          </section>
        </div>
        <div v-else class="py-20 flex flex-col items-center justify-center text-center text-gray-500"><Icon icon="mdi:file-search-outline" class="text-4xl text-gray-300 mb-2" /><p>没有匹配的配置项</p></div>
      </section>
    </main>

    <div v-if="canRead && !isMobile && activeMode !== 'readonly' && activeDirtyCount" class="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur border-t border-gray-200 shadow-[0_-8px_30px_rgba(15,23,42,0.08)]">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between gap-4">
        <p class="text-sm text-gray-600"><span class="font-bold text-blue-600">{{ activeDirtyCount }}</span> 项{{ modeLabel(activeMode) }}配置尚未保存</p>
        <div class="flex gap-3"><el-button @click="resetChanges(activeMode)">放弃本组更改</el-button><el-button :type="activeMode === 'restart' ? 'warning' : 'primary'" :loading="previewLoading" :disabled="historyConflict || !canUpdate" @click="openPreview(activeMode)">{{ activeMode === 'runtime' ? '保存实时配置' : '保存待重启配置' }}</el-button></div>
      </div>
    </div>

    <el-dialog v-model="previewVisible" class="mobile-config-dialog" :title="previewMode === 'runtime' ? '实时配置变更预览' : '重启配置变更预览'" width="min(640px, 92vw)" destroy-on-close>
      <div v-if="previewData" class="space-y-5">
        <div v-if="previewData.runtime_fields?.length"><h3 class="font-semibold text-gray-900 mb-2 flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-emerald-500" />实时生效</h3><div class="flex flex-wrap gap-2"><el-tag v-for="key in previewData.runtime_fields" :key="key" type="success">{{ fieldLabel(key) }}</el-tag></div></div>
        <div v-if="previewData.restart_fields?.length"><h3 class="font-semibold text-gray-900 mb-2 flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-amber-500" />重启后生效</h3><div class="flex flex-wrap gap-2"><el-tag v-for="key in previewData.restart_fields" :key="key" type="warning">{{ fieldLabel(key) }}</el-tag></div></div>
        <el-alert v-for="warning in previewData.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon />
      </div>
      <template #footer><el-button @click="previewVisible = false">取消</el-button><el-button :type="previewMode === 'restart' ? 'warning' : 'primary'" :loading="applyLoading" :disabled="!canUpdate || historyConflict" @click="applyChanges">{{ previewMode === 'restart' ? '确认保存待重启配置' : '确认保存' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="coordinationVisible" class="mobile-config-dialog mobile-system-coordination" title="系统配置存储协调" width="min(1180px, 96vw)" top="3vh" destroy-on-close :close-on-click-modal="false">
      <div v-loading="coordinationLoading" class="min-h-56">
        <div v-if="coordinationData" class="space-y-5">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div class="rounded-xl border border-purple-200 bg-purple-50 p-4"><p class="text-xs text-purple-600">MongoDB 最新历史</p><p class="text-xl font-bold text-purple-900 mt-1">v{{ coordinationData.database.version }}</p><p class="text-xs text-purple-700 mt-1">{{ operationLabel(coordinationData.database.operation) }} · {{ historyStatusLabel(coordinationData.database.status) }}</p></div>
            <div class="rounded-xl border border-blue-200 bg-blue-50 p-4"><p class="text-xs text-blue-600">data 配置文件</p><p class="text-xl font-bold text-blue-900 mt-1">v{{ coordinationData.file.version }}</p><p class="text-xs text-blue-700 mt-1">{{ coordinationData.file.outbox_count }} 条待处理 outbox</p></div>
            <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p class="text-xs text-emerald-600">拟生成协调版本</p><p class="text-xl font-bold text-emerald-900 mt-1">v{{ coordinationData.proposed_version }}</p><p class="text-xs text-emerald-700 mt-1">{{ coordinationImpactData.runtime.length }} 项立即生效 · {{ coordinationImpactData.restart.length }} 项等待重启</p></div>
          </div>

          <el-alert v-for="warning in coordinationData.warnings || []" :key="warning" :title="warning" type="warning" :closable="false" show-icon />

          <section v-if="!isMobile">
            <div class="grid grid-cols-2 gap-4 mb-2 text-sm font-semibold text-gray-700"><span>MongoDB 最新 v{{ coordinationData.database.version }}</span><span class="text-right">data/system-config.json v{{ coordinationData.file.version }}</span></div>
            <MonacoDiffEditor
              :key="coordinationData.coordination_token"
              :original="coordinationDatabaseJson"
              :modified="coordinationFileJson"
              language="json"
              :min-height="360"
            />
          </section>

          <section class="rounded-xl border border-gray-200 overflow-hidden">
            <div class="p-4 bg-gray-50 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div><h3 class="font-semibold text-gray-900">选择差异字段来源</h3><p class="text-sm text-gray-500 mt-1">还需选择 {{ unresolvedCoordinationCount }} 项；数据库缺失字段会自动保留文件侧值。</p></div>
              <div class="flex flex-wrap gap-2"><el-button size="small" @click="selectAllCoordination('database')">全部采用数据库</el-button><el-button size="small" @click="selectAllCoordination('file')">全部采用文件</el-button><el-button size="small" @click="clearCoordinationResolutions">清空</el-button></div>
            </div>
            <div v-if="coordinationData.differences?.length" class="divide-y divide-gray-100 max-h-80 overflow-y-auto">
              <div v-for="item in coordinationData.differences" :key="item.key" class="p-4 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto] gap-4 lg:items-center">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap"><span class="font-medium text-gray-900">{{ item.label }}</span><el-tag :type="modeTagType(item.apply_mode)" size="small">{{ modeLabel(item.apply_mode) }}</el-tag><el-tag v-if="item.sensitive" type="warning" size="small">敏感值已隐藏</el-tag><el-tag v-if="!item.database_available" type="danger" size="small">数据库缺失</el-tag></div>
                  <p class="text-xs text-gray-400 font-mono mt-1">{{ item.key }}</p>
                  <div class="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    <p class="rounded bg-purple-50 px-2 py-1.5 text-purple-800">数据库：{{ coordinationValue(item, 'database') }}</p>
                    <p class="rounded bg-blue-50 px-2 py-1.5 text-blue-800">文件：{{ coordinationValue(item, 'file') }}</p>
                  </div>
                </div>
                <el-radio-group v-model="coordinationResolutions[item.key]" size="small">
                  <el-radio-button value="database" :disabled="!item.database_available">采用数据库</el-radio-button>
                  <el-radio-button value="file">采用文件</el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div v-else class="p-8 text-center text-gray-500">配置值一致，仅版本历史需要协调。</div>
          </section>
        </div>
      </div>
      <template #footer>
        <el-button @click="coordinationVisible = false">取消</el-button>
        <el-button type="danger" :loading="coordinationCommitLoading" :disabled="!canExecute || !coordinationData || unresolvedCoordinationCount > 0" @click="commitCoordination">确认生成协调版本</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="historyVisible" title="配置历史" :size="isMobile ? '100%' : 'min(760px, 94vw)'" :direction="isMobile ? 'btt' : 'rtl'" class="mobile-system-history" destroy-on-close>
      <div v-loading="historyLoading" class="h-full flex flex-col">
        <div v-if="isMobile" class="mobile-system-history-list"><button v-for="item in historyItems" :key="item.version" @click="openHistoryDetail(item.version)"><strong>v{{ item.version }} · {{ operationLabel(item.operation) }}</strong><el-tag :type="historyStatusType(item.status)" size="small">{{ historyStatusLabel(item.status) }}</el-tag><p>{{ item.change_count }} 项变更 · {{ item.created_by }}</p><small>{{ formatDate(item.created_at) }}</small></button><el-empty v-if="!historyItems.length" description="暂无配置历史" /></div>
        <el-table v-else :data="historyItems" class="flex-1" empty-text="暂无配置历史">
          <el-table-column prop="version" label="版本" width="76"><template #default="scope">v{{ scope.row.version }}</template></el-table-column>
          <el-table-column label="操作" min-width="120"><template #default="scope">{{ operationLabel(scope.row.operation) }}</template></el-table-column>
          <el-table-column label="状态" width="112"><template #default="scope"><el-tag :type="historyStatusType(scope.row.status)" size="small">{{ historyStatusLabel(scope.row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="change_count" label="变更" width="72" />
          <el-table-column prop="created_by" label="操作人" min-width="100" />
          <el-table-column label="时间" min-width="160"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column>
          <el-table-column label="操作" width="80" fixed="right"><template #default="scope"><el-button link type="primary" @click="openHistoryDetail(scope.row.version)">详情</el-button></template></el-table-column>
        </el-table>
        <el-pagination class="mt-4 justify-end" background :layout="isMobile ? 'prev, pager, next' : 'total, prev, pager, next'" :pager-count="isMobile ? 5 : 7" :total="historyTotal" :page-size="historyPageSize" v-model:current-page="historyPage" @current-change="loadHistory" />
      </div>
    </el-drawer>

    <el-dialog v-model="historyDetailVisible" class="mobile-config-dialog mobile-system-history-detail" :title="`配置版本 v${historyDetail?.version || ''}`" width="min(720px, 94vw)" destroy-on-close>
      <div v-loading="historyDetailLoading">
        <div v-if="historyDetail" class="space-y-4">
          <div class="flex flex-wrap gap-2 text-sm text-gray-500"><el-tag :type="historyStatusType(historyDetail.status)">{{ historyStatusLabel(historyDetail.status) }}</el-tag><span>{{ operationLabel(historyDetail.operation) }}</span><span>{{ historyDetail.created_by }}</span><span>{{ formatDate(historyDetail.created_at) }}</span></div>
          <div v-if="historyDetail.changes?.length" class="space-y-2 max-h-96 overflow-y-auto">
            <div v-for="change in historyDetail.changes" :key="change.key" class="border border-gray-200 rounded-lg p-3"><div class="flex items-center justify-between gap-3"><div><p class="font-medium text-gray-900">{{ change.label }}</p><p class="text-xs text-gray-400 font-mono">{{ change.key }}</p></div><el-tag :type="modeTagType(change.apply_mode)" size="small">{{ modeLabel(change.apply_mode) }}</el-tag></div><div class="mt-2 text-sm grid grid-cols-[1fr_auto_1fr] gap-2 items-center"><span class="truncate text-gray-500">{{ historyValue(change, 'before') }}</span><Icon icon="mdi:arrow-right" class="text-gray-400" /><span class="truncate text-gray-900">{{ historyValue(change, 'after') }}</span></div></div>
          </div>
          <p v-else class="text-center text-gray-500 py-8">该版本为历史基线，没有字段变更记录。</p>
          <div v-if="historyDetail.coordination" class="rounded-lg bg-purple-50 border border-purple-100 p-3 space-y-2 text-sm">
            <p class="font-medium text-purple-900">存储协调来源</p>
            <p class="text-purple-800">data 文件 v{{ historyDetail.coordination.file_version }} · MongoDB v{{ historyDetail.coordination.database_version }}</p>
            <p class="text-purple-700">采用文件 {{ historyDetail.coordination.file_fields?.length || 0 }} 项，采用数据库 {{ historyDetail.coordination.database_fields?.length || 0 }} 项，取代 outbox {{ historyDetail.coordination.discarded_outbox_ids?.length || 0 }} 条。</p>
          </div>
          <div v-if="historyDetail.restore_runtime_fields?.length || historyDetail.restore_restart_fields?.length" class="rounded-lg bg-blue-50 border border-blue-100 p-3 space-y-3"><p class="font-medium text-blue-900">还原影响</p><div v-if="historyDetail.restore_runtime_fields?.length"><p class="text-xs text-gray-500 mb-1">立即恢复</p><div class="flex flex-wrap gap-1"><el-tag v-for="key in historyDetail.restore_runtime_fields" :key="key" type="success" size="small">{{ fieldLabel(key) }}</el-tag></div></div><div v-if="historyDetail.restore_restart_fields?.length"><p class="text-xs text-gray-500 mb-1">重启后恢复</p><div class="flex flex-wrap gap-1"><el-tag v-for="key in historyDetail.restore_restart_fields" :key="key" type="warning" size="small">{{ fieldLabel(key) }}</el-tag></div></div></div>
        </div>
      </div>
      <template #footer><el-button @click="historyDetailVisible = false">关闭</el-button><el-button type="primary" :loading="restoreLoading" :disabled="!canExecute || historyConflict || !(historyDetail?.restore_runtime_fields?.length || historyDetail?.restore_restart_fields?.length)" @click="restoreHistory">还原到此版本</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import MonacoDiffEditor from '@/components/MonacoDiffEditor.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import MobileActionBar from '@/components/mobile/MobileActionBar.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import '@/components/layout/mobileConfig.css'
import { systemApi } from '@/api/system'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'
import { buildConfigChanges, countConfigModes, selectConfigChangesByMode } from '@/utils/systemConfigPolicy'
import {
  buildCoordinationResolutions,
  coordinationImpact,
  formatCoordinationSnapshot,
  unresolvedCoordinationKeys
} from '@/utils/systemConfigCoordination'

defineOptions({ name: 'SystemConfigHome' })
const { isMobile } = useMobileViewport()
const canRead = computed(() => hasPerm(PERM.operations.system.config.read))
const canUpdate = computed(() => canRead.value && hasPerm(PERM.operations.system.config.update))
const canExecute = computed(() => canRead.value && hasPerm(PERM.operations.system.config.execute))
const mobileConfigList = ref(false)
const mobileFieldKey = ref('')
let pageActive = true
let pageEpoch = 0
let configRequest = 0
let historyRequest = 0
let historyDetailRequest = 0
const pendingConfirmations = new Set()

const loading = ref(false)
const loadError = ref('')
const previewLoading = ref(false)
const applyLoading = ref(false)
const cancelLoading = ref(false)
const historyLoading = ref(false)
const historyDetailLoading = ref(false)
const restoreLoading = ref(false)
const coordinationLoading = ref(false)
const coordinationCommitLoading = ref(false)
const configData = ref(null)
const form = reactive({})
const original = reactive({})
const searchQuery = ref('')
const activeGroup = ref('all')
const activeMode = ref('runtime')
const previewVisible = ref(false)
const previewData = ref(null)
const previewChanges = ref({})
const previewVersion = ref(null)
const previewMode = ref(null)
const historyVisible = ref(false)
const historyItems = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 20
const historyDetailVisible = ref(false)
const historyDetail = ref(null)
const coordinationVisible = ref(false)
const coordinationData = ref(null)
const coordinationResolutions = reactive({})

const fields = computed(() => configData.value?.fields || [])
const fieldMap = computed(() => Object.fromEntries(fields.value.map(item => [item.key, item])))
const mobileField = computed(() => fieldMap.value[mobileFieldKey.value])
const mobileConfigGroups = computed(() => (configData.value?.groups || []).map(group => ({ ...group, count: fields.value.filter(field => field.group === group.key && field.apply_mode === activeMode.value).length })).filter(group => group.count))
const navGroups = computed(() => [{ key: 'all', label: '全部配置' }, ...(configData.value?.groups || [])])
const visibleGroups = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return (configData.value?.groups || []).map(group => ({
    ...group,
    fields: fields.value.filter(field => field.group === group.key && field.apply_mode === activeMode.value && (activeGroup.value === 'all' || field.group === activeGroup.value) && (!query || field.label.toLowerCase().includes(query) || field.key.toLowerCase().includes(query) || (field.description || '').toLowerCase().includes(query)))
  })).filter(group => group.fields.length)
})
const allChanges = computed(() => buildConfigChanges(fields.value, form, original))
const runtimeChanges = computed(() => selectConfigChangesByMode(fields.value, allChanges.value, 'runtime'))
const restartChanges = computed(() => selectConfigChangesByMode(fields.value, allChanges.value, 'restart'))
const runtimeDirtyCount = computed(() => Object.keys(runtimeChanges.value).length)
const restartDirtyCount = computed(() => Object.keys(restartChanges.value).length)
const activeDirtyCount = computed(() => activeMode.value === 'runtime' ? runtimeDirtyCount.value : activeMode.value === 'restart' ? restartDirtyCount.value : 0)
const historyConflict = computed(() => configData.value?.history_sync_status === 'conflict')
const coordinationDatabaseJson = computed(() => formatCoordinationSnapshot(coordinationData.value?.database?.display_snapshot))
const coordinationFileJson = computed(() => formatCoordinationSnapshot(coordinationData.value?.file?.display_snapshot))
const unresolvedCoordinationCount = computed(() => unresolvedCoordinationKeys(coordinationData.value?.differences, coordinationResolutions).length)
const coordinationImpactData = computed(() => coordinationImpact(coordinationData.value?.differences, coordinationResolutions, coordinationData.value?.fixed_impact))
const modeSummary = computed(() => {
  const counts = countConfigModes(fields.value)
  return [
    { mode: 'runtime', label: '实时生效', count: counts.runtime, dirtyCount: runtimeDirtyCount.value, icon: 'mdi:flash-outline', iconBg: 'bg-emerald-50', iconColor: 'text-emerald-500', activeClass: 'border-emerald-400 ring-2 ring-emerald-100' },
    { mode: 'restart', label: '重启后生效', count: counts.restart, dirtyCount: restartDirtyCount.value, icon: 'mdi:restart', iconBg: 'bg-amber-50', iconColor: 'text-amber-500', activeClass: 'border-amber-400 ring-2 ring-amber-100' },
    { mode: 'readonly', label: '只读配置', count: counts.readonly, dirtyCount: 0, icon: 'mdi:lock-outline', iconBg: 'bg-slate-100', iconColor: 'text-slate-500', activeClass: 'border-slate-400 ring-2 ring-slate-100' }
  ]
})
const activeModeInfo = computed(() => ({
  runtime: { title: '实时生效配置', description: '本组配置独立保存，验证通过后立即应用。', icon: 'mdi:flash-outline', bannerClass: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  restart: { title: '重启后生效配置', description: '本组配置保存后进入待重启状态，将在下次人工或运维重启服务时生效。', icon: 'mdi:restart', bannerClass: 'border-amber-200 bg-amber-50 text-amber-800' },
  readonly: { title: '只读配置', description: '这些核心基础设施与安全配置仅供查看，需要通过部署环境变量修改。', icon: 'mdi:lock-outline', bannerClass: 'border-slate-200 bg-slate-50 text-slate-700' }
}[activeMode.value]))
function initializeForm(data) {
  for (const key of Object.keys(form)) delete form[key]
  for (const key of Object.keys(original)) delete original[key]
  for (const field of data.fields || []) {
    const value = field.sensitive ? '' : (field.value ?? (field.value_type === 'boolean' ? false : ''))
    form[field.key] = value
    original[field.key] = value
  }
}
async function loadConfig(options = {}) {
  if (!pageActive || !canRead.value) return
  const requestId = ++configRequest
  const epoch = pageEpoch
  loading.value = true
  loadError.value = ''
  try {
    const response = await systemApi.getSystemConfig()
    if (!pageActive || !canRead.value || epoch !== pageEpoch || requestId !== configRequest) return
    const drafts = options.preserveDraft ? { ...allChanges.value } : {}
    configData.value = response.data
    initializeForm(response.data)
    for (const [key, value] of Object.entries(drafts)) {
      if (fieldMap.value[key]?.editable) form[key] = value
    }
  } catch { if (pageActive && epoch === pageEpoch && requestId === configRequest) loadError.value = '配置加载失败，请点击刷新重试' }
  finally { if (requestId === configRequest) loading.value = false }
}
function switchMode(mode) { activeMode.value = mode; activeGroup.value = 'all' }
function resetChanges(mode) {
  for (const field of fields.value.filter(item => item.apply_mode === mode)) form[field.key] = original[field.key]
}
function isDirty(key) { return Object.prototype.hasOwnProperty.call(allChanges.value, key) }
function fieldLabel(key) { return fieldMap.value[key]?.label || key }
function modeLabel(mode) { return ({ runtime: '实时生效', restart: '重启生效', readonly: '只读' }[mode] || mode) }
function modeTagType(mode) { return ({ runtime: 'success', restart: 'warning', readonly: 'info' }[mode] || 'info') }
function formatDate(value) {
  if (!value) return '暂无记录'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
function formatDisplayValue(value) {
  if (value === null || value === undefined || value === '') return '未配置'
  if (typeof value === 'boolean') return value ? '启用' : '停用'
  return String(value)
}
function changesForMode(mode) { return mode === 'runtime' ? runtimeChanges.value : restartChanges.value }
async function openPreview(mode) {
  if (previewLoading.value || !pageActive || !canUpdate.value || historyConflict.value || !configData.value || !['runtime', 'restart'].includes(mode)) return
  const selectedChanges = { ...changesForMode(mode) }
  const version = configData.value.version
  const epoch = pageEpoch
  if (!Object.keys(selectedChanges).length) return
  if (mode === 'restart' && runtimeDirtyCount.value) {
    ElMessage.warning('请先保存或放弃实时生效配置的更改，再保存重启配置')
    return
  }
  previewLoading.value = true
  try {
    const response = await systemApi.previewSystemConfig({ expected_version: version, changes: selectedChanges })
    if (!pageActive || !canUpdate.value || epoch !== pageEpoch) return
    if (JSON.stringify(selectedChanges) !== JSON.stringify(changesForMode(mode)) || configData.value.version !== version) {
      ElMessage.warning('配置已继续修改，请重新预览后保存')
      return
    }
    previewChanges.value = selectedChanges
    previewVersion.value = version
    previewMode.value = mode
    previewData.value = response.data
    previewVisible.value = true
  } finally { if (epoch === pageEpoch) previewLoading.value = false }
}
function commitSavedChanges(savedChanges, responseData) {
  for (const key of Object.keys(savedChanges)) {
    const field = fieldMap.value[key]
    if (field?.sensitive) {
      if (form[key] === savedChanges[key]) form[key] = ''
      original[key] = ''
      field.configured = true
    } else {
      original[key] = savedChanges[key]
    }
  }
  configData.value.version = responseData.version
  configData.value.updated_at = responseData.updated_at
  configData.value.updated_by = responseData.updated_by
  configData.value.restart_required = responseData.restart_required
  configData.value.pending_version = responseData.pending_version
  configData.value.pending_fields = responseData.pending_fields
  configData.value.history_sync_status = responseData.history_sync_status
}
async function applyChanges() {
  if (!previewData.value || !previewMode.value || applyLoading.value || !pageActive || !canUpdate.value || historyConflict.value || !configData.value) return
  const mode = previewMode.value
  const selectedChanges = { ...previewChanges.value }
  const epoch = pageEpoch
  if (JSON.stringify(selectedChanges) !== JSON.stringify(changesForMode(mode)) || configData.value.version !== previewVersion.value) {
    previewVisible.value = false
    ElMessage.warning('配置已变化，请重新预览后保存')
    return
  }
  applyLoading.value = true
  try {
    const payload = { expected_version: previewVersion.value, changes: selectedChanges }
    if (mode === 'runtime') {
      const response = await systemApi.applyRuntimeSystemConfig(payload)
      if (!pageActive || !canUpdate.value || epoch !== pageEpoch) return
      commitSavedChanges(selectedChanges, response.data)
      ElMessage.success('实时配置已保存并生效')
      previewVisible.value = false
      return
    }
    const response = await systemApi.stagePendingSystemConfig(payload)
    if (!pageActive || !canUpdate.value || epoch !== pageEpoch) return
    commitSavedChanges(selectedChanges, response.data)
    previewVisible.value = false
    ElMessage.warning('配置已保存，将在下次服务重启后生效')
    await loadConfig({ preserveDraft: true })
  } finally { if (epoch === pageEpoch) applyLoading.value = false }
}

function showPendingFields() {
  mobileConfigList.value = true
  activeMode.value = 'restart'
  activeGroup.value = 'all'
  searchQuery.value = ''
  window.scrollTo({ top: 260, behavior: 'smooth' })
}
async function cancelPending() {
  if (!pageActive || !canExecute.value || historyConflict.value || cancelLoading.value || !configData.value) return
  const epoch = pageEpoch
  const version = configData.value.version
  cancelLoading.value = true
  try {
    const confirmation = Symbol()
    pendingConfirmations.add(confirmation)
    try { await ElMessageBox.confirm('将撤销全部待重启字段，已生效的实时配置不会受到影响。', '取消待重启变更', { confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning' }) }
    catch { return }
    finally { pendingConfirmations.delete(confirmation) }
    if (!pageActive || !canExecute.value || epoch !== pageEpoch || configData.value?.version !== version || historyConflict.value) return
    await systemApi.cancelPendingSystemConfig({ expected_version: version, confirmed: true })
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    ElMessage.success('待重启配置已取消')
    await loadConfig({ preserveDraft: true })
    if (historyVisible.value) await loadHistory()
  } finally { if (epoch === pageEpoch) cancelLoading.value = false }
}
function replaceCoordinationResolutions(values) {
  for (const key of Object.keys(coordinationResolutions)) delete coordinationResolutions[key]
  Object.assign(coordinationResolutions, values)
}
async function openCoordination() {
  if (!pageActive || !canExecute.value || coordinationLoading.value) return
  const epoch = pageEpoch
  coordinationLoading.value = true
  try {
    const response = await systemApi.previewSystemConfigCoordination({ silent: true })
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    coordinationData.value = response.data
    replaceCoordinationResolutions({})
    coordinationVisible.value = true
  } catch (error) {
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    ElMessage.error(error?.message || '存储协调预览加载失败')
    await loadConfig({ preserveDraft: true })
  } finally { if (epoch === pageEpoch) coordinationLoading.value = false }
}
function selectAllCoordination(source) {
  replaceCoordinationResolutions(buildCoordinationResolutions(coordinationData.value?.differences, source))
}
function clearCoordinationResolutions() {
  replaceCoordinationResolutions({})
}
function coordinationValue(item, side) {
  if (side === 'database' && !item.database_available) return '缺失'
  if (item.sensitive) return item[`${side}_configured`] ? '已配置（内容已隐藏）' : '未配置'
  return formatDisplayValue(item[`${side}_value`])
}
async function commitCoordination() {
  if (!pageActive || !canExecute.value || !coordinationData.value || unresolvedCoordinationCount.value || coordinationCommitLoading.value) return
  const epoch = pageEpoch
  const token = coordinationData.value.coordination_token
  const resolutions = { ...coordinationResolutions }
  const proposedVersion = coordinationData.value.proposed_version
  const impact = coordinationImpactData.value
  coordinationCommitLoading.value = true
  try {
    const confirmation = Symbol()
    pendingConfirmations.add(confirmation)
    try {
      await ElMessageBox.confirm(`将生成配置版本 v${proposedVersion}：${impact.runtime.length} 项实时配置立即生效，${impact.restart.length} 项配置等待重启。`, '确认强制同步', { confirmButtonText: '确认生成协调版本', cancelButtonText: '返回检查', type: 'error' })
    } catch { return }
    finally { pendingConfirmations.delete(confirmation) }
    if (!pageActive || !canExecute.value || epoch !== pageEpoch || coordinationData.value?.coordination_token !== token || JSON.stringify(resolutions) !== JSON.stringify(coordinationResolutions)) return
    const response = await systemApi.commitSystemConfigCoordination({
      coordination_token: token,
      resolutions,
      confirmed: true
    }, { silent: true })
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    coordinationVisible.value = false
    const syncPending = response.data.history_sync_status === 'pending'
    ElMessage[syncPending ? 'warning' : 'success'](
      syncPending ? '协调版本已写入，MongoDB 历史等待同步' : '系统配置存储协调完成'
    )
    await loadConfig({ preserveDraft: true })
    if (historyVisible.value) await loadHistory()
  } catch (error) {
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    ElMessage.error(error?.message || '存储协调提交失败，请重新加载对比')
  } finally { if (epoch === pageEpoch) coordinationCommitLoading.value = false }
}
async function openHistory() {
  if (!pageActive || !canRead.value) return
  historyVisible.value = true
  historyPage.value = 1
  await loadHistory()
}
async function loadHistory() {
  if (!pageActive || !canRead.value) return
  const requestId = ++historyRequest
  const epoch = pageEpoch
  historyLoading.value = true
  try {
    const response = await systemApi.getSystemConfigHistory({ page: historyPage.value, page_size: historyPageSize })
    if (!pageActive || !canRead.value || epoch !== pageEpoch || requestId !== historyRequest) return
    historyItems.value = response.data.items || []
    historyTotal.value = response.data.total || 0
  } finally { if (requestId === historyRequest) historyLoading.value = false }
}
async function openHistoryDetail(version) {
  if (!pageActive || !canRead.value) return
  const requestId = ++historyDetailRequest
  const epoch = pageEpoch
  historyDetailVisible.value = true
  historyDetailLoading.value = true
  historyDetail.value = null
  try {
    const response = await systemApi.getSystemConfigHistoryDetail(version)
    if (!pageActive || !canRead.value || epoch !== pageEpoch || requestId !== historyDetailRequest) return
    historyDetail.value = response.data
  } finally { if (requestId === historyDetailRequest) historyDetailLoading.value = false }
}
async function restoreHistory() {
  if (!pageActive || !canExecute.value || historyConflict.value || !historyDetail.value || !configData.value || restoreLoading.value) return
  const epoch = pageEpoch
  const version = configData.value.version
  const targetVersion = historyDetail.value.version
  const runtimeCount = historyDetail.value.restore_runtime_fields?.length || 0
  const restartCount = historyDetail.value.restore_restart_fields?.length || 0
  if (!runtimeCount && !restartCount) return
  restoreLoading.value = true
  try {
    const confirmation = Symbol()
    pendingConfirmations.add(confirmation)
    try { await ElMessageBox.confirm(`还原会创建一个新版本：${runtimeCount} 项实时配置将立即恢复，${restartCount} 项配置将在重启后生效。`, `还原到 v${targetVersion}`, { confirmButtonText: '确认还原', cancelButtonText: '取消', type: 'warning' }) }
    catch { return }
    finally { pendingConfirmations.delete(confirmation) }
    if (!pageActive || !canExecute.value || epoch !== pageEpoch || configData.value?.version !== version || historyDetail.value?.version !== targetVersion || historyConflict.value) return
    const response = await systemApi.restoreSystemConfigHistory(targetVersion, { expected_version: version, confirmed: true })
    if (!pageActive || !canExecute.value || epoch !== pageEpoch) return
    historyDetailVisible.value = false
    ElMessage.success(response.data.restart_required ? '配置已还原，部分配置等待重启生效' : '配置已还原并生效')
    await loadConfig({ preserveDraft: true })
    await loadHistory()
  } finally { if (epoch === pageEpoch) restoreLoading.value = false }
}
function operationLabel(value) { return ({ runtime_update: '实时修改', restart_update: '待重启修改', restore: '版本还原', cancel_pending: '取消待重启', environment_rebase: '环境基线变化', migration_baseline: '历史基线', storage_reconcile: '存储协调' }[value] || value) }
function historyStatusLabel(value) { return ({ applied: '已生效', pending_restart: '待重启', superseded: '已取代', rolled_back: '已回滚', baseline_conflict: '基线冲突', applying: '应用中' }[value] || value) }
function historyStatusType(value) { return ({ applied: 'success', pending_restart: 'warning', superseded: 'info', rolled_back: 'danger', baseline_conflict: 'danger', applying: 'primary' }[value] || 'info') }
function historyValue(change, side) {
  if (change.sensitive) return change[`${side}_configured`] ? '已配置（内容已隐藏）' : '未配置'
  return formatDisplayValue(change[side])
}

/** """手机端仍有草稿时，阻止刷新页面直接丢失修改。""" */
function protectMobileDraft(event) {
  if (!pageActive || !isMobile.value || !Object.keys(allChanges.value).length) return
  event.preventDefault()
  event.returnValue = ''
}
onBeforeRouteLeave(async () => {
  if (!pageActive || !isMobile.value || !Object.keys(allChanges.value).length) return true
  const epoch = pageEpoch
  const confirmation = Symbol()
  pendingConfirmations.add(confirmation)
  try {
    await ElMessageBox.confirm('当前配置修改尚未保存，离开后将丢失。', '离开系统配置', { confirmButtonText: '放弃并离开', cancelButtonText: '继续编辑', type: 'warning' })
    if (!pageActive || epoch !== pageEpoch) return false
    resetChanges('runtime')
    resetChanges('restart')
    return true
  } catch { return false }
  finally { pendingConfirmations.delete(confirmation) }
})
onMounted(() => { loadConfig(); window.addEventListener('beforeunload', protectMobileDraft) })
onBeforeUnmount(() => { deactivatePage(); window.removeEventListener('beforeunload', protectMobileDraft) })
onActivated(() => {
  const returning = !pageActive
  pageActive = true
  // 桌面缓存仍保留尚未保存的草稿，避免重新激活时静默覆盖。
  if (returning && !Object.keys(allChanges.value).length) loadConfig()
})
/** """使离页或撤权前的请求失效，并收起本页面的临时弹层。""" */
function invalidateRequests() {
  pageEpoch += 1
  configRequest += 1
  historyRequest += 1
  historyDetailRequest += 1
  mobileFieldKey.value = ''
  for (const state of [previewVisible, coordinationVisible, historyVisible, historyDetailVisible, loading, previewLoading, applyLoading, historyLoading, historyDetailLoading, coordinationLoading, cancelLoading, restoreLoading, coordinationCommitLoading]) state.value = false
  previewData.value = null
  previewChanges.value = {}
  previewVersion.value = null
  previewMode.value = null
  coordinationData.value = null
  replaceCoordinationResolutions({})
  if (pendingConfirmations.size) {
    ElMessageBox.close()
    pendingConfirmations.clear()
  }
}
/** """停用缓存页面一次，卸载时复用同一清理过程。""" */
function deactivatePage() {
  if (!pageActive) return
  pageActive = false
  invalidateRequests()
}
onDeactivated(deactivatePage)
watch([canRead, canUpdate, canExecute], ([read, update, execute], [oldRead, oldUpdate, oldExecute]) => {
  if ((!read && oldRead) || (!update && oldUpdate) || (!execute && oldExecute)) invalidateRequests()
  if (!read) {
    configData.value = null
    initializeForm({ fields: [] })
    historyItems.value = []
    historyDetail.value = null
    historyTotal.value = 0
  } else if (!oldRead && pageActive) loadConfig()
}, { flush: 'sync' })
</script>

<style scoped>
.mobile-system-config { padding: 20px 16px; display: grid; gap: 16px; }
.mobile-system-config h1 { font-size: 23px; font-weight: 750; color: #0f172a; }
.mobile-system-config header > p, .mobile-system-mode-help { font-size: 13px; color: #64748b; line-height: 1.7; margin-top: 6px; }
.mobile-system-status, .mobile-system-notice { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; overflow-wrap: anywhere; }
.mobile-system-status > span { float: right; color: #64748b; font-size: 13px; }
.mobile-system-status summary { padding-block: 12px; min-height: 44px; color: #64748b; font-size: 13px; }
.mobile-system-status p, .mobile-system-notice p { font-size: 13px; line-height: 1.7; color: #64748b; margin-bottom: 10px; }
.mobile-system-status > div, .mobile-system-notice > div { display: flex; flex-wrap: wrap; gap: 8px; }
.mobile-system-status .el-button, .mobile-system-notice .el-button { flex: 1; min-height: 44px; margin: 0; }
.mobile-system-notice { border-color: #fcd34d; background: #fffbeb; }
.mobile-system-modes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.mobile-system-modes button { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 4px; border-radius: 12px; background: #e2e8f0; color: #475569; font-size: 12px; }
.mobile-system-modes button.active { background: #dbeafe; color: #1d4ed8; box-shadow: inset 0 0 0 1px #93c5fd; }
.mobile-system-modes svg { font-size: 23px; }
.mobile-system-modes small { font-size: 10px; }
.mobile-system-categories { display: grid; gap: 10px; }
.mobile-system-categories button { display: flex; align-items: center; gap: 12px; text-align: left; padding: 18px 14px; border: 1px solid #e2e8f0; border-radius: 14px; background: white; }
.mobile-system-categories strong { flex: 1; }
.mobile-system-categories span { color: #64748b; font-size: 12px; }
.mobile-system-back { display: flex; gap: 4px; align-items: center; min-height: 44px; color: #2563eb; font-size: 14px; }
.mobile-system-fields h2 { font-weight: 700; padding: 12px 0; }
.mobile-system-field { display: flex; width: 100%; text-align: left; align-items: center; gap: 10px; border-bottom: 1px solid #e2e8f0; padding: 16px 12px; background: white; }
.mobile-system-field > span { flex: 1; min-width: 0; }
.mobile-system-field strong, .mobile-system-field small { display: block; overflow-wrap: anywhere; }
.mobile-system-field strong { font-size: 14px; }
.mobile-system-field small { color: #64748b; font-size: 12px; margin-top: 6px; max-height: 3em; overflow: hidden; }
.mobile-system-field-editor { display: grid; gap: 16px; font-size: 14px; line-height: 1.7; }
.mobile-system-field-editor code { overflow-wrap: anywhere; font-size: 12px; color: #64748b; }
.mobile-system-field-editor .el-input-number { width: 100%; }
.mobile-system-field-editor small { color: #64748b; }
.mobile-system-config :deep(.el-input__wrapper), .mobile-system-field-editor :deep(.el-input__wrapper) { min-height: 44px; }
</style>
<style>
@media (max-width: 767px) {
  .mobile-system-history.el-drawer { height: var(--mobile-viewport-height, 100dvh) !important; top: var(--mobile-viewport-top, 0px); bottom: auto; }
  .mobile-system-history .el-drawer__header { margin-bottom: 0; }
  .mobile-system-history .el-drawer__close-btn { min-height: 44px; min-width: 44px; }
  .mobile-system-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
  .mobile-system-history-list button { padding: 16px; border: 1px solid #e2e8f0; border-radius: 14px; text-align: left; }
  .mobile-system-history-list strong { display: block; margin-bottom: 8px; }
  .mobile-system-history-list p, .mobile-system-history-list small { display: block; margin-top: 8px; color: #64748b; }
  .mobile-system-history-detail .grid { grid-template-columns: minmax(0, 1fr); }
  .mobile-system-history-detail .truncate { white-space: normal; overflow-wrap: anywhere; }
  .mobile-system-history-detail .font-mono, .mobile-system-coordination .font-mono { overflow-wrap: anywhere; }
  .mobile-system-coordination .el-radio-button__inner { min-height: 44px; display: flex; align-items: center; }
  .mobile-system-coordination .max-h-80, .mobile-system-history-detail .max-h-96 { max-height: none; }
  .mobile-system-coordination .el-button { min-height: 44px; }
}
</style>
