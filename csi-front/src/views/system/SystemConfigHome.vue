<template>
  <div class="min-h-screen bg-gray-50 pb-28">
    <Header />
    <FunctionalPageHeader
      title-prefix="系统"
      title-suffix="配置"
      subtitle="集中管理后端运行参数。更改会根据配置类型实时生效或在服务自动重启后生效。"
    />

    <main class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-7" v-loading="loading">
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

      <el-alert v-if="configData?.history_sync_status === 'conflict'" class="mb-5" title="配置文件与 MongoDB 历史存在冲突，已暂停保存、取消和还原操作，请先完成存储协调。" type="error" :closable="false" show-icon />
      <el-alert v-else-if="configData?.history_sync_status === 'pending'" class="mb-5" title="配置已保存，MongoDB 历史正在等待同步。" type="info" :closable="false" show-icon />
      <div v-if="configData?.restart_required" class="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-amber-800">
        <div class="flex gap-3"><Icon icon="mdi:restart-alert" class="text-2xl shrink-0" /><div><p class="font-semibold">{{ configData.pending_status === 'baseline_conflict' ? '部署环境已变化，待重启配置未应用' : '配置已保存，需要重启服务' }}</p><p class="text-sm mt-1">{{ configData.pending_status === 'baseline_conflict' ? '请取消当前待重启配置，并基于最新环境重新编辑和保存。' : `版本 v${configData.pending_version} 的 ${configData.pending_fields?.length || 0} 项配置将在下次服务重启后生效。` }}</p></div></div>
        <div class="flex gap-2 self-end sm:self-auto"><el-button type="warning" plain @click="showPendingFields">查看字段</el-button><el-button type="danger" plain :loading="cancelLoading" :disabled="historyConflict" @click="cancelPending">取消待重启变更</el-button></div>
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
                <el-switch v-else-if="field.value_type === 'boolean'" v-model="form[field.key]" :disabled="!field.editable" inline-prompt active-text="启用" inactive-text="停用" />
                <el-input-number v-else-if="field.value_type === 'integer' || field.value_type === 'number'" v-model="form[field.key]" :disabled="!field.editable" :min="field.constraints?.min" :max="field.constraints?.max" :precision="field.value_type === 'integer' ? 0 : 1" controls-position="right" class="w-full!" />
                <el-input v-else v-model="form[field.key]" :disabled="!field.editable" :type="field.sensitive ? 'password' : 'text'" :show-password="field.sensitive && field.editable" :placeholder="field.sensitive && field.configured ? '已配置，留空表示保持原值' : '请输入配置值'" clearable />
                <p v-if="field.pending_change" class="mt-2 text-xs text-amber-600"><Icon icon="mdi:clock-outline" class="inline text-sm mr-1" />当前运行值：{{ field.sensitive ? (field.active_configured ? '已配置（内容已隐藏）' : '未配置') : formatDisplayValue(field.active_value) }}</p>
              </div>
            </div>
          </section>
        </div>
        <div v-else class="py-20 flex flex-col items-center justify-center text-center text-gray-500"><Icon icon="mdi:file-search-outline" class="text-4xl text-gray-300 mb-2" /><p>没有匹配的配置项</p></div>
      </section>
    </main>

    <div v-if="activeMode !== 'readonly' && activeDirtyCount" class="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur border-t border-gray-200 shadow-[0_-8px_30px_rgba(15,23,42,0.08)]">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between gap-4">
        <p class="text-sm text-gray-600"><span class="font-bold text-blue-600">{{ activeDirtyCount }}</span> 项{{ modeLabel(activeMode) }}配置尚未保存</p>
        <div class="flex gap-3"><el-button @click="resetChanges(activeMode)">放弃本组更改</el-button><el-button :type="activeMode === 'restart' ? 'warning' : 'primary'" :loading="previewLoading" :disabled="historyConflict" @click="openPreview(activeMode)">{{ activeMode === 'runtime' ? '保存实时配置' : '保存待重启配置' }}</el-button></div>
      </div>
    </div>

    <el-dialog v-model="previewVisible" :title="previewMode === 'runtime' ? '实时配置变更预览' : '重启配置变更预览'" width="min(640px, 92vw)" destroy-on-close>
      <div v-if="previewData" class="space-y-5">
        <div v-if="previewData.runtime_fields?.length"><h3 class="font-semibold text-gray-900 mb-2 flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-emerald-500" />实时生效</h3><div class="flex flex-wrap gap-2"><el-tag v-for="key in previewData.runtime_fields" :key="key" type="success">{{ fieldLabel(key) }}</el-tag></div></div>
        <div v-if="previewData.restart_fields?.length"><h3 class="font-semibold text-gray-900 mb-2 flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-amber-500" />重启后生效</h3><div class="flex flex-wrap gap-2"><el-tag v-for="key in previewData.restart_fields" :key="key" type="warning">{{ fieldLabel(key) }}</el-tag></div></div>
        <el-alert v-for="warning in previewData.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon />
      </div>
      <template #footer><el-button @click="previewVisible = false">取消</el-button><el-button :type="previewMode === 'restart' ? 'warning' : 'primary'" :loading="applyLoading" @click="applyChanges">{{ previewMode === 'restart' ? '确认保存待重启配置' : '确认保存' }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="historyVisible" title="配置历史" size="min(760px, 94vw)" destroy-on-close>
      <div v-loading="historyLoading" class="h-full flex flex-col">
        <el-table :data="historyItems" class="flex-1" empty-text="暂无配置历史">
          <el-table-column prop="version" label="版本" width="76"><template #default="scope">v{{ scope.row.version }}</template></el-table-column>
          <el-table-column label="操作" min-width="120"><template #default="scope">{{ operationLabel(scope.row.operation) }}</template></el-table-column>
          <el-table-column label="状态" width="112"><template #default="scope"><el-tag :type="historyStatusType(scope.row.status)" size="small">{{ historyStatusLabel(scope.row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="change_count" label="变更" width="72" />
          <el-table-column prop="created_by" label="操作人" min-width="100" />
          <el-table-column label="时间" min-width="160"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column>
          <el-table-column label="操作" width="80" fixed="right"><template #default="scope"><el-button link type="primary" @click="openHistoryDetail(scope.row.version)">详情</el-button></template></el-table-column>
        </el-table>
        <el-pagination class="mt-4 justify-end" background layout="total, prev, pager, next" :total="historyTotal" :page-size="historyPageSize" v-model:current-page="historyPage" @current-change="loadHistory" />
      </div>
    </el-drawer>

    <el-dialog v-model="historyDetailVisible" :title="`配置版本 v${historyDetail?.version || ''}`" width="min(720px, 94vw)" destroy-on-close>
      <div v-loading="historyDetailLoading">
        <div v-if="historyDetail" class="space-y-4">
          <div class="flex flex-wrap gap-2 text-sm text-gray-500"><el-tag :type="historyStatusType(historyDetail.status)">{{ historyStatusLabel(historyDetail.status) }}</el-tag><span>{{ operationLabel(historyDetail.operation) }}</span><span>{{ historyDetail.created_by }}</span><span>{{ formatDate(historyDetail.created_at) }}</span></div>
          <div v-if="historyDetail.changes?.length" class="space-y-2 max-h-96 overflow-y-auto">
            <div v-for="change in historyDetail.changes" :key="change.key" class="border border-gray-200 rounded-lg p-3"><div class="flex items-center justify-between gap-3"><div><p class="font-medium text-gray-900">{{ change.label }}</p><p class="text-xs text-gray-400 font-mono">{{ change.key }}</p></div><el-tag :type="modeTagType(change.apply_mode)" size="small">{{ modeLabel(change.apply_mode) }}</el-tag></div><div class="mt-2 text-sm grid grid-cols-[1fr_auto_1fr] gap-2 items-center"><span class="truncate text-gray-500">{{ historyValue(change, 'before') }}</span><Icon icon="mdi:arrow-right" class="text-gray-400" /><span class="truncate text-gray-900">{{ historyValue(change, 'after') }}</span></div></div>
          </div>
          <p v-else class="text-center text-gray-500 py-8">该版本为历史基线，没有字段变更记录。</p>
          <div v-if="historyDetail.restore_runtime_fields?.length || historyDetail.restore_restart_fields?.length" class="rounded-lg bg-blue-50 border border-blue-100 p-3 space-y-3"><p class="font-medium text-blue-900">还原影响</p><div v-if="historyDetail.restore_runtime_fields?.length"><p class="text-xs text-gray-500 mb-1">立即恢复</p><div class="flex flex-wrap gap-1"><el-tag v-for="key in historyDetail.restore_runtime_fields" :key="key" type="success" size="small">{{ fieldLabel(key) }}</el-tag></div></div><div v-if="historyDetail.restore_restart_fields?.length"><p class="text-xs text-gray-500 mb-1">重启后恢复</p><div class="flex flex-wrap gap-1"><el-tag v-for="key in historyDetail.restore_restart_fields" :key="key" type="warning" size="small">{{ fieldLabel(key) }}</el-tag></div></div></div>
        </div>
      </div>
      <template #footer><el-button @click="historyDetailVisible = false">关闭</el-button><el-button type="primary" :loading="restoreLoading" :disabled="historyConflict || !(historyDetail?.restore_runtime_fields?.length || historyDetail?.restore_restart_fields?.length)" @click="restoreHistory">还原到此版本</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { systemApi } from '@/api/system'
import { buildConfigChanges, countConfigModes, selectConfigChangesByMode } from '@/utils/systemConfigPolicy'

defineOptions({ name: 'SystemConfigHome' })

const loading = ref(false)
const previewLoading = ref(false)
const applyLoading = ref(false)
const cancelLoading = ref(false)
const historyLoading = ref(false)
const historyDetailLoading = ref(false)
const restoreLoading = ref(false)
const configData = ref(null)
const form = reactive({})
const original = reactive({})
const searchQuery = ref('')
const activeGroup = ref('all')
const activeMode = ref('runtime')
const previewVisible = ref(false)
const previewData = ref(null)
const previewMode = ref(null)
const historyVisible = ref(false)
const historyItems = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 20
const historyDetailVisible = ref(false)
const historyDetail = ref(null)

const fields = computed(() => configData.value?.fields || [])
const fieldMap = computed(() => Object.fromEntries(fields.value.map(item => [item.key, item])))
const navGroups = computed(() => [{ key: 'all', label: '全部配置' }, ...(configData.value?.groups || [])])
const visibleGroups = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return (configData.value?.groups || []).map(group => ({
    ...group,
    fields: fields.value.filter(field => field.apply_mode === activeMode.value && (activeGroup.value === 'all' || field.group === activeGroup.value) && (!query || field.label.toLowerCase().includes(query) || field.key.toLowerCase().includes(query) || (field.description || '').toLowerCase().includes(query)))
  })).filter(group => group.fields.length)
})
const allChanges = computed(() => buildConfigChanges(fields.value, form, original))
const runtimeChanges = computed(() => selectConfigChangesByMode(fields.value, allChanges.value, 'runtime'))
const restartChanges = computed(() => selectConfigChangesByMode(fields.value, allChanges.value, 'restart'))
const runtimeDirtyCount = computed(() => Object.keys(runtimeChanges.value).length)
const restartDirtyCount = computed(() => Object.keys(restartChanges.value).length)
const activeDirtyCount = computed(() => activeMode.value === 'runtime' ? runtimeDirtyCount.value : activeMode.value === 'restart' ? restartDirtyCount.value : 0)
const historyConflict = computed(() => configData.value?.history_sync_status === 'conflict')
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
async function loadConfig() {
  loading.value = true
  try {
    const response = await systemApi.getSystemConfig()
    configData.value = response.data
    initializeForm(response.data)
  } finally { loading.value = false }
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
  const selectedChanges = changesForMode(mode)
  if (!Object.keys(selectedChanges).length) return
  if (mode === 'restart' && runtimeDirtyCount.value) {
    ElMessage.warning('请先保存或放弃实时生效配置的更改，再保存重启配置')
    return
  }
  previewLoading.value = true
  try {
    const response = await systemApi.previewSystemConfig({ expected_version: configData.value.version, changes: selectedChanges })
    previewMode.value = mode
    previewData.value = response.data
    previewVisible.value = true
  } finally { previewLoading.value = false }
}
function commitSavedChanges(savedChanges, responseData) {
  for (const key of Object.keys(savedChanges)) {
    const field = fieldMap.value[key]
    if (field?.sensitive) {
      form[key] = ''
      original[key] = ''
      field.configured = true
    } else {
      original[key] = form[key]
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
  if (!previewData.value || !previewMode.value) return
  const mode = previewMode.value
  const selectedChanges = { ...changesForMode(mode) }
  applyLoading.value = true
  try {
    const payload = { expected_version: configData.value.version, changes: selectedChanges }
    if (mode === 'runtime') {
      const response = await systemApi.applyRuntimeSystemConfig(payload)
      commitSavedChanges(selectedChanges, response.data)
      ElMessage.success('实时配置已保存并生效')
      previewVisible.value = false
      return
    }
    await systemApi.stagePendingSystemConfig(payload)
    previewVisible.value = false
    ElMessage.warning('配置已保存，将在下次服务重启后生效')
    await loadConfig()
  } finally { applyLoading.value = false }
}

function showPendingFields() {
  activeMode.value = 'restart'
  activeGroup.value = 'all'
  searchQuery.value = ''
  window.scrollTo({ top: 260, behavior: 'smooth' })
}
async function cancelPending() {
  await ElMessageBox.confirm('将撤销全部待重启字段，已生效的实时配置不会受到影响。', '取消待重启变更', { confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning' })
  cancelLoading.value = true
  try {
    await systemApi.cancelPendingSystemConfig({ expected_version: configData.value.version, confirmed: true })
    ElMessage.success('待重启配置已取消')
    await loadConfig()
    if (historyVisible.value) await loadHistory()
  } finally { cancelLoading.value = false }
}
async function openHistory() {
  historyVisible.value = true
  historyPage.value = 1
  await loadHistory()
}
async function loadHistory() {
  historyLoading.value = true
  try {
    const response = await systemApi.getSystemConfigHistory({ page: historyPage.value, page_size: historyPageSize })
    historyItems.value = response.data.items || []
    historyTotal.value = response.data.total || 0
  } finally { historyLoading.value = false }
}
async function openHistoryDetail(version) {
  historyDetailVisible.value = true
  historyDetailLoading.value = true
  historyDetail.value = null
  try {
    const response = await systemApi.getSystemConfigHistoryDetail(version)
    historyDetail.value = response.data
  } finally { historyDetailLoading.value = false }
}
async function restoreHistory() {
  if (!historyDetail.value) return
  const runtimeCount = historyDetail.value.restore_runtime_fields?.length || 0
  const restartCount = historyDetail.value.restore_restart_fields?.length || 0
  await ElMessageBox.confirm(`还原会创建一个新版本：${runtimeCount} 项实时配置将立即恢复，${restartCount} 项配置将在重启后生效。`, `还原到 v${historyDetail.value.version}`, { confirmButtonText: '确认还原', cancelButtonText: '取消', type: 'warning' })
  restoreLoading.value = true
  try {
    const response = await systemApi.restoreSystemConfigHistory(historyDetail.value.version, { expected_version: configData.value.version, confirmed: true })
    historyDetailVisible.value = false
    ElMessage.success(response.data.restart_required ? '配置已还原，部分配置等待重启生效' : '配置已还原并生效')
    await loadConfig()
    await loadHistory()
  } finally { restoreLoading.value = false }
}
function operationLabel(value) { return ({ runtime_update: '实时修改', restart_update: '待重启修改', restore: '版本还原', cancel_pending: '取消待重启', environment_rebase: '环境基线变化', migration_baseline: '历史基线' }[value] || value) }
function historyStatusLabel(value) { return ({ applied: '已生效', pending_restart: '待重启', superseded: '已取代', rolled_back: '已回滚', baseline_conflict: '基线冲突', applying: '应用中' }[value] || value) }
function historyStatusType(value) { return ({ applied: 'success', pending_restart: 'warning', superseded: 'info', rolled_back: 'danger', baseline_conflict: 'danger', applying: 'primary' }[value] || 'info') }
function historyValue(change, side) {
  if (change.sensitive) return change[`${side}_configured`] ? '已配置（内容已隐藏）' : '未配置'
  return formatDisplayValue(change[side])
}

onMounted(loadConfig)
</script>
