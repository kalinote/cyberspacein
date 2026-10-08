<template>
  <main class="mobile-blueprint-list">
    <header class="blueprint-heading"><div><h1>行动蓝图</h1><p>查看执行方案，运行并管理版本</p></div><el-button :disabled="!hasAll([PERM.operations.action.blueprint.create, PERM.pages.action.create.access])" @click="$emit('create')"><Icon icon="mdi:plus" />新建</el-button></header>
    <div class="blueprint-search"><el-input v-model="keyword" placeholder="搜索本页名称、目标或描述" aria-label="搜索本页蓝图" clearable /><el-button aria-label="筛选蓝图" @click="draftPinned = pinned; filterVisible = true"><Icon icon="mdi:filter-variant" /></el-button></div>
    <p class="blueprint-summary">共 {{ pagination.total }} 个 · {{ pinned === '' ? '全部蓝图' : pinned === 'true' ? '主页已置顶' : '未置顶' }}<span v-if="keyword"> · 本页匹配 {{ filteredBlueprints.length }} 个</span></p>
    <p v-if="preparing" class="blueprint-preparing" role="status"><Icon icon="mdi:loading" class="animate-spin" />正在校验蓝图并读取封装接口…</p>
    <div v-if="!hasPerm(PERM.operations.action.blueprint.read)" class="blueprint-state">暂无蓝图读取权限</div>
    <div v-else-if="error" class="blueprint-state" role="alert"><p>{{ error }}</p><el-button @click="$emit('retry')">重新加载</el-button></div>
    <div v-else v-loading="loading" class="blueprint-results"><el-empty v-if="!loading && !filteredBlueprints.length" :description="keyword ? '本页没有匹配的蓝图' : '暂无蓝图'" :image-size="64" />
      <article v-for="blueprint in filteredBlueprints" :key="blueprint.id" class="blueprint-card"><button class="blueprint-card-link" @click="openDetail(blueprint)"><div class="blueprint-card-title"><h2>{{ blueprint.title || '未命名蓝图' }}</h2><Icon v-if="blueprint.isPinned" icon="mdi:pin" aria-label="主页已置顶" /><Icon icon="mdi:chevron-right" /></div><div class="blueprint-tags"><el-tag v-if="blueprint.isTemplate" type="warning" size="small">参数模板</el-tag><el-tag type="info" size="small">{{ blueprint.defaultSchedulingMode === 'streaming' ? '异步执行' : '同步执行' }}</el-tag><el-tag v-if="blueprint.latestRevisionNumber" size="small" type="success">已发布 R{{ blueprint.latestRevisionNumber }}</el-tag><span v-else>尚未发布</span></div><p class="blueprint-goal">{{ blueprint.taskGoal || blueprint.description || '暂无目标说明' }}</p><div class="blueprint-card-meta"><span>{{ blueprint.stepCount }} 步骤 · {{ blueprint.branchCount }} 分支</span><span>{{ blueprint.executionDeadline === '未设置' ? '不限执行期限' : `期限 ${blueprint.executionDeadline}` }}</span></div></button></article>
    </div>
    <div v-if="!error && pagination.total > pagination.pageSize" class="blueprint-pagination"><el-pagination :current-page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" :pager-count="5" layout="prev, pager, next" @current-change="$emit('page-change', $event)" /></div>
    <MobileSheet v-model="filterVisible" title="筛选蓝图"><el-form label-position="top"><el-form-item label="主页置顶状态"><el-radio-group v-model="draftPinned" class="blueprint-filter-options"><el-radio value="">全部蓝图</el-radio><el-radio value="true">已置顶到主页</el-radio><el-radio value="false">未置顶</el-radio></el-radio-group></el-form-item></el-form><template #footer><div class="blueprint-footer"><el-button @click="draftPinned = ''">重置</el-button><el-button type="primary" @click="$emit('filter', draftPinned); filterVisible = false">应用筛选</el-button></div></template></MobileSheet>
    <MobileSheet v-model="detailVisible" :title="selected?.title || '蓝图详情'">
      <div v-if="detailLoading" class="blueprint-state">正在加载蓝图详情…</div><div v-else-if="detailError" class="blueprint-state" role="alert"><p>{{ detailError }}</p><el-button @click="openDetail(selected)">重新加载</el-button></div>
      <div v-else-if="detail" class="blueprint-detail">
        <div class="blueprint-tags"><el-tag v-if="detail.is_template" type="warning">参数模板</el-tag><el-tag type="info">版本 {{ detail.version || '—' }}</el-tag></div><h3>行动目标</h3><p>{{ detail.target || '暂无目标说明' }}</p><h3>蓝图说明</h3><p>{{ detail.description || '暂无说明' }}</p>
        <dl><dt>默认模式</dt><dd>{{ detail.default_scheduling_mode === 'streaming' ? '异步执行' : '同步执行' }}</dd><dt>执行期限</dt><dd>{{ selected.executionDeadline === '未设置' ? '不限制' : selected.executionDeadline }}</dd><dt>流程规模</dt><dd>{{ detail.graph?.nodes?.length || 0 }} 个节点 · {{ detail.graph?.edges?.length || 0 }} 条连线</dd><dt>更新时间</dt><dd>{{ formatDateTime(detail.updated_at) }}</dd><dt>创建时间</dt><dd>{{ formatDateTime(detail.created_at) }}</dd></dl>
        <details v-if="detail.is_template" class="blueprint-expand"><summary>运行参数（{{ detail.template?.params?.length || 0 }}）</summary><article v-for="param in detail.template?.params || []" :key="param.id || param.name" class="blueprint-param"><strong>{{ param.label || param.name }}</strong><el-tag v-if="param.required" size="small" type="danger">必填</el-tag><p>{{ param.description || param.name }}</p><span>类型：{{ param.type }}</span></article><p v-if="!detail.template?.params?.length">此模板没有运行参数</p></details>
        <details class="blueprint-expand"><summary>公开输入与输出（{{ interfaces.length }}）</summary><article v-for="(port, index) in interfaces" :key="`${port.direction}-${port.port_id || index}`" class="blueprint-param"><strong>{{ port.name || port.port_id }}</strong><p>{{ port.direction === 'input' ? '输入' : '输出' }} · {{ port.interface_type_id || '未设置类型' }}</p><p v-if="port.description">{{ port.description }}</p></article><p v-if="!interfaces.length">暂无公开接口</p></details>
        <div class="blueprint-management"><BlueprintPinButton :blueprint="selected" @change="selected.isPinned = $event; $emit('pin-change', selected.id, $event)" /><el-button :disabled="!hasPerm(PERM.operations.action.blueprint.read)" @click="dispatch('history')"><Icon icon="mdi:history" />发布历史</el-button><el-button :disabled="!hasPerm(PERM.operations.action.blueprint.publish)" @click="dispatch('publish')"><Icon icon="mdi:publish" />发布版本</el-button><el-button :disabled="!canEncapsulate || preparing" :loading="preparing" @click="dispatch('encapsulate')"><Icon icon="mdi:package-variant" />封装为节点</el-button><el-button @click="dispatch('view')"><Icon icon="mdi:graph-outline" />查看流程图</el-button><el-button :disabled="!hasAll([PERM.operations.action.blueprint.update, PERM.pages.action.create.access])" @click="dispatch('edit')"><Icon icon="mdi:pencil-outline" />打开图形编辑器</el-button><el-button type="danger" plain :disabled="!hasPerm(PERM.operations.action.blueprint.delete)" @click="dispatch('delete')"><Icon icon="mdi:trash-can-outline" />删除蓝图</el-button></div>
      </div>
      <template #footer><div class="blueprint-footer"><el-button @click="detailVisible = false">返回列表</el-button><el-button type="primary" :disabled="detailLoading || !!detailError || !detail || !canExecute || starting" @click="runMode = detail.default_scheduling_mode === 'streaming' ? 'streaming' : 'barrier'; runDebug = false; detailVisible = false; runVisible = true">运行设置</el-button></div></template>
    </MobileSheet>
    <MobileSheet v-model="runVisible" title="运行蓝图" :close-on-click-modal="!starting" :close-on-press-escape="!starting" :show-close="!starting"><div class="blueprint-detail"><h3>{{ selected?.title }}</h3><p>{{ selected?.isTemplate ? '确认执行方式后填写模板参数' : '确认执行方式后将创建一次新的行动' }}</p><el-form label-position="top"><el-form-item label="执行方式"><el-radio-group v-model="runMode"><el-radio-button value="barrier">同步</el-radio-button><el-radio-button value="streaming">异步</el-radio-button></el-radio-group></el-form-item><el-form-item label="调试运行"><el-switch v-model="runDebug" /></el-form-item></el-form><p v-if="runDebug">调试运行会启用调试输出节点，并把接收到的数据写入行动日志。</p></div><template #footer><div class="blueprint-footer"><el-button :disabled="starting" @click="runVisible = false; detailVisible = true">上一步</el-button><el-button type="primary" :disabled="!canExecute" :loading="starting" @click="runVisible = false; $emit('run', selected, runDebug, runMode)">{{ selected?.isTemplate ? '填写参数' : '确认运行' }}</el-button></div></template></MobileSheet>
  </main>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import BlueprintPinButton from '@/components/action/BlueprintPinButton.vue'
import { actionApi } from '@/api/action'
import { PERM } from '@/utils/permissions'
import { hasAll, hasPerm } from '@/utils/permissionKit'
import { formatDateTime } from '@/utils/action'

const props = defineProps({ blueprints: { type: Array, default: () => [] }, pagination: { type: Object, required: true }, pinned: { type: String, default: '' }, loading: Boolean, error: String, starting: Boolean, preparing: Boolean, canEncapsulate: Boolean })
const emit = defineEmits(['retry', 'create', 'page-change', 'filter', 'pin-change', 'view', 'edit', 'history', 'publish', 'encapsulate', 'delete', 'run'])
const keyword = ref('')
const filterVisible = ref(false)
const draftPinned = ref('')
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detail = ref(null)
const selected = ref(null)
const runVisible = ref(false)
const runMode = ref('barrier')
const runDebug = ref(false)
let detailGeneration = 0
let pageActive = true
const canExecute = computed(() => hasAll([PERM.operations.action.blueprint.read, PERM.operations.action.instance.execute]))
const filteredBlueprints = computed(() => {
  const search = keyword.value.trim().toLocaleLowerCase()
  return props.blueprints.filter(item => !search || [item.title, item.taskGoal, item.description].some(value => String(value || '').toLocaleLowerCase().includes(search)))
})
const interfaces = computed(() => [...(detail.value?.interface?.inputs || []).map(item => ({ ...item, direction: 'input' })), ...(detail.value?.interface?.outputs || []).map(item => ({ ...item, direction: 'output' }))])

/** """加载当前选中蓝图，关闭或切换后丢弃旧详情响应。""" */
async function openDetail(blueprint) {
  if (!blueprint?.id || !hasPerm(PERM.operations.action.blueprint.read)) return
  const generation = ++detailGeneration
  selected.value = blueprint
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const response = await actionApi.getBlueprint(blueprint.id)
    if (!pageActive || generation !== detailGeneration || !detailVisible.value || !hasPerm(PERM.operations.action.blueprint.read)) return
    if (response.code !== 0 || !response.data) throw new Error(response.message || '蓝图详情不存在')
    detail.value = response.data
    // 运行依赖最新的模板标记和调度模式，避免列表数据陈旧。
    selected.value = { ...blueprint, isTemplate: response.data.is_template, defaultSchedulingMode: response.data.default_scheduling_mode, isPinned: response.data.is_pinned }
  } catch {
    if (pageActive && generation === detailGeneration) detailError.value = '蓝图详情加载失败，请重试'
  } finally {
    if (generation === detailGeneration) detailLoading.value = false
  }
}
/** """收起详情后交由页面处理既有蓝图操作。""" */
function dispatch(operation) {
  detailVisible.value = false
  emit(operation, selected.value)
}
watch(detailVisible, visible => { if (!visible) detailGeneration++ })
watch(() => hasPerm(PERM.operations.action.blueprint.read), allowed => {
  if (!allowed) { detailGeneration++; detailVisible.value = false; runVisible.value = false; detail.value = null; selected.value = null }
})
onActivated(() => { pageActive = true })
onDeactivated(() => { pageActive = false; detailGeneration++; detailVisible.value = false; runVisible.value = false; filterVisible.value = false })
onBeforeUnmount(() => { pageActive = false; detailGeneration++ })
</script>

<style scoped>
.blueprint-preparing { display: flex; gap: 8px; align-items: center; padding: 12px; background: #eff6ff; color: #1d4ed8; border-radius: 12px; font-size: 13px; margin-bottom: 12px; }
.mobile-blueprint-list { padding: 16px 12px 24px; color: #0f172a; }.blueprint-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }.blueprint-heading h1 { font-size: 23px; font-weight: 750; margin: 0; }.blueprint-heading p { font-size: 12px; color: #64748b; margin: 5px 0 0; }.blueprint-search { display: flex; gap: 8px; margin-top: 18px; }.blueprint-search :deep(.el-input) { min-width: 0; }.blueprint-summary { font-size: 12px; color: #64748b; margin: 12px 0; }.blueprint-results { min-height: 160px; }.blueprint-card { background: white; border: 1px solid #e2e8f0; border-radius: 16px; margin-bottom: 12px; overflow: hidden; }.blueprint-card-link { display: block; width: 100%; text-align: left; padding: 16px; }.blueprint-card-title { display: flex; align-items: center; gap: 8px; }.blueprint-card-title h2 { flex: 1; min-width: 0; margin: 0; font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }.blueprint-card-title svg { flex-shrink: 0; color: #64748b; }.blueprint-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 10px 0; font-size: 12px; color: #64748b; }.blueprint-goal { font-size: 14px; color: #475569; line-height: 1.6; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }.blueprint-card-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 5px; font-size: 12px; color: #64748b; margin-top: 12px; }.blueprint-state { padding: 28px 12px; text-align: center; color: #64748b; font-size: 14px; }.blueprint-state p { margin-bottom: 14px; }.blueprint-pagination { display: flex; justify-content: center; margin-top: 20px; }.blueprint-filter-options { display: grid; gap: 10px; }.blueprint-filter-options .el-radio { margin: 0; min-height: 44px; }.blueprint-footer { display: flex; gap: 8px; }.blueprint-footer .el-button { flex: 1; margin: 0; min-width: 0; }.mobile-blueprint-list :deep(.el-button), .mobile-blueprint-list :deep(.el-input__wrapper), .blueprint-detail :deep(.el-button) { min-height: 44px; }.blueprint-detail { overflow-wrap: anywhere; font-size: 14px; color: #334155; }.blueprint-detail h3 { font-size: 15px; font-weight: 700; color: #0f172a; margin: 18px 0 8px; }.blueprint-detail p { white-space: pre-wrap; line-height: 1.7; }.blueprint-detail dl { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px 10px; font-size: 13px; margin: 18px 0; }.blueprint-detail dt { color: #64748b; }.blueprint-detail dd { margin: 0; }.blueprint-expand { border-top: 1px solid #e2e8f0; }.blueprint-expand summary { padding: 14px 0; cursor: pointer; color: #0f172a; }.blueprint-param { padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 8px; }.blueprint-param > .el-tag { margin-left: 8px; }.blueprint-param p, .blueprint-param > span { font-size: 12px; color: #64748b; }.blueprint-management { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 16px; }.blueprint-management :deep(.el-button) { width: 100%; margin: 0 !important; min-width: 0; padding: 10px 7px; font-size: 12px; }.blueprint-management :deep(.el-button:last-child) { grid-column: 1 / -1; }.blueprint-detail :deep(.el-radio-button__inner) { min-height: 44px; padding: 14px 20px; }
</style>
