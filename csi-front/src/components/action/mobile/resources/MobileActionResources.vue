<template>
  <div class="mobile-action-resources">
    <el-select v-if="activeTab === 'accounts'" v-model="platformFilter" clearable filterable placeholder="全部平台" aria-label="筛选采集平台" class="resource-platform-filter" @change="page = 1; load()"><el-option v-for="platform in platforms" :key="platform.id" :label="platform.name" :value="platform.id" /></el-select>
    <div class="resource-list-meta"><span>{{ activeTab === 'nodes' ? `${filteredItems.length} 个节点` : `${total} 项资源` }}</span><span v-if="['baseComponents', 'nodeHandles', 'accounts'].includes(activeTab)">关键词筛选本页</span></div>
    <div v-if="!config" class="resource-state"><Icon icon="mdi:wrench-outline" /><h3>{{ label }}功能开发中</h3><p>此模块暂未提供可用的管理功能。</p></div>
    <div v-else-if="!canRead" class="resource-state" role="status">暂无读取此类资源的权限。</div>
    <el-alert v-else-if="listError" :title="listError" type="error" :closable="false" show-icon><el-button link @click="load">重新加载</el-button></el-alert>
    <el-skeleton v-else-if="loading && !items.length" :rows="6" animated />
    <div v-else-if="!loading && !filteredItems.length" class="resource-state"><Icon icon="mdi:inbox-outline" /><p>{{ keyword ? '没有匹配的资源' : '暂无资源' }}</p></div>
    <div v-else class="resource-card-list" :aria-busy="loading">
      <article v-for="item in filteredItems" :key="item.id || item.node_family_id" class="resource-card">
        <button type="button" class="resource-card-main" :disabled="activeTab === 'accounts' && !hasPerm(config.detail)" @click="openDetail(item)">
          <div class="resource-card-heading"><h3>{{ item.name || item.label || item.account_name || item.handle_name || '未命名资源' }}</h3><Icon icon="mdi:chevron-right" /></div>
          <div class="resource-card-tags"><span v-if="activeTab === 'nodes'">{{ item.definition_origin === 'backend_builtin' ? '系统内置' : '自定义' }}</span><span v-if="activeTab === 'nodes'" :class="item.enabled ? 'success' : 'muted'">{{ item.enabled ? '已启用' : '已禁用' }}</span><span v-if="item.version">v{{ item.version }}</span><span v-if="item.status">{{ statusLabels[item.status] || item.status }}</span><span v-if="activeTab === 'encapsulatedNodes'">最新 v{{ item.latest_definition_version }} · {{ item.active_version_count }} 个有效版本</span><span v-if="activeTab === 'nodeHandles'">{{ item.type === 'reference' ? '引用类型' : '值类型' }}</span></div>
          <p v-if="item.description">{{ item.description }}</p>
          <p v-if="activeTab === 'encapsulatedNodes'">源蓝图：{{ item.source_blueprint?.name || item.source_blueprint?.id || '不可用' }}</p>
          <small v-if="activeTab === 'accounts'">{{ platforms.find(platform => platform.id === item.platform_id)?.name || item.platform_id }} · {{ formatDateTime(item.updated_at) }}</small>
          <small v-else-if="activeTab === 'nodes'">{{ item.handles?.length || 0 }} 个接口 · {{ item.inputs?.length || 0 }} 个输入项</small>
          <small v-else-if="activeTab === 'baseComponents'">{{ item.total_runs || 0 }} 次运行 · 平均 {{ item.average_runtime ?? '—' }} 秒</small>
          <small v-else-if="activeTab === 'nodeHandles'">{{ item.handle_name }}</small>
        </button>
        <div v-if="activeTab === 'accounts' && !hasPerm(config.detail)" class="resource-card-note">暂无账号详情读取权限</div>
      </article>
    </div>
    <nav v-if="totalPages > 1 && canRead" class="resource-pagination" aria-label="资源分页"><el-button :disabled="page <= 1 || loading" @click="page--; load()">上一页</el-button><span>{{ page }} / {{ totalPages }}</span><el-button :disabled="page >= totalPages || loading" @click="page++; load()">下一页</el-button></nav>

    <el-dialog v-model="detailVisible" :title="detailMode === 'family' ? '封装节点版本' : '资源详情'" class="mobile-config-dialog resource-detail-dialog" append-to-body destroy-on-close>
      <el-skeleton v-if="detailLoading" :rows="7" animated />
      <el-alert v-else-if="detailError" :title="detailError" type="error" :closable="false"><el-button link @click="openDetail(selectedItem, detailMode === 'version')">重新加载</el-button></el-alert>
      <template v-else-if="detail">
        <template v-if="detailMode === 'family'">
          <h2 class="resource-detail-title">{{ detail.name }}</h2><p class="resource-detail-subtitle">源蓝图：{{ detail.source_blueprint?.name || detail.source_blueprint?.id || '不可用' }}</p>
          <el-alert v-if="detail.source_blueprint?.is_deleted" title="源蓝图已删除" type="warning" :closable="false" />
          <p class="resource-detail-subtitle">下次封装 v{{ detail.next_definition_version }} · 历史最高 v{{ detail.max_history_version }}</p>
          <article v-for="version in detail.versions || []" :key="version.id" class="resource-version"><button type="button" @click="openDetail(version, true)"><strong>v{{ version.definition_version }} · {{ version.name }}</strong><span v-if="version.is_latest">最新版本</span><p>{{ version.description || '暂无说明' }}</p><small>{{ version.draft_reference_count || 0 }} 个蓝图引用 · {{ formatDateTime(version.created_at) }}</small><Icon icon="mdi:chevron-right" /></button></article>
        </template>
        <template v-else>
          <el-button v-if="detailMode === 'version'" link @click="detail = selectedFamily; detailMode = 'family'">返回版本列表</el-button>
          <h2 class="resource-detail-title">{{ currentResource.name || currentResource.account_name || currentResource.label || currentResource.handle_name }}</h2>
          <MobileResourceFields :fields="detailFields" />
          <template v-if="['nodes', 'encapsulatedNodes'].includes(activeTab)">
            <section class="resource-detail-section"><h3>接口 · {{ currentResource.handles?.length || 0 }}</h3><article v-for="(handle, index) in currentResource.handles || []" :key="index" class="resource-detail-item"><h4>{{ handle.relabel || handle.label || `接口 ${index + 1}` }}</h4><MobileResourceFields :fields="[{ label: '接口 ID', value: handle.id || handle.interface_type_id }, { label: '方向', value: handle.type === 'target' ? '输入' : '输出' }, { label: '位置', value: handle.position }, { label: '稳定端口', value: handle.port_id }, { label: '样式', value: handle.custom_style }]" /></article><p v-if="!currentResource.handles?.length">暂无接口</p></section>
            <section class="resource-detail-section"><h3>输入项 · {{ currentResource.inputs?.length || 0 }}</h3><article v-for="(input, index) in currentResource.inputs || []" :key="index" class="resource-detail-item"><h4>{{ input.label || input.name }}</h4><MobileResourceFields :fields="[{ label: '字段与类型', value: `${input.name} · ${input.type}` }, { label: '描述', value: input.description }, { label: '必填', value: input.required }, { label: '默认值', value: input.default }, { label: '选项', value: input.options }, { label: '自定义属性', value: input.custom_props }, { label: '自定义样式', value: input.custom_style }]" /></article><p v-if="!currentResource.inputs?.length">暂无输入项</p></section>
          </template>
          <section v-if="detailMode === 'version'" class="resource-detail-section"><h3>可编辑蓝图引用</h3><article v-for="reference in detail.references || []" :key="reference.blueprint_id" class="resource-detail-item"><h4>{{ reference.blueprint_name }}</h4><MobileResourceFields :fields="[{ label: '蓝图版本', value: reference.blueprint_version }, { label: '节点实例数', value: reference.instance_count }, { label: '实例 ID', value: reference.instance_ids }]" /></article><p v-if="!detail.references?.length">没有可编辑蓝图引用</p></section>
        </template>
      </template>
      <template #footer><el-button @click="detailVisible = false">返回列表</el-button><template v-if="detail && !detailLoading && !detailError && detailMode !== 'family'"><el-button v-if="canEditDetail" type="primary" @click="openEditor(currentResource)">编辑</el-button><el-button v-if="activeTab === 'nodes' && currentResource.definition_origin === 'backend_builtin' && hasPerm(PERM.operations.action.node.nativeStatusUpdate)" :type="currentResource.enabled ? 'warning' : 'success'" @click="askMutation('toggle', currentResource)">{{ currentResource.enabled ? '禁用' : '启用' }}</el-button><el-button v-if="canDeleteDetail" type="danger" plain :disabled="detailMode === 'version' && Boolean(currentResource.draft_reference_count || detail.references?.length)" @click="askMutation('delete', currentResource)">删除</el-button></template></template>
    </el-dialog>

    <el-dialog v-model="formVisible" :title="`${editingId ? '编辑' : '新增'}${label}`" class="mobile-config-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <el-alert v-if="formError" :title="formError" type="error" :closable="false" class="resource-form-error"><el-button v-if="optionsError" link @click="loadOptions">重新加载选项</el-button></el-alert>
      <el-skeleton v-if="formLoading" :rows="7" animated />
      <MobileResourceForm v-else v-model="draft" v-model:step="formStep" :kind="activeTab" :options="options" :invalid-index="invalidIndex" :disabled="saving" @save="save" />
      <template #footer><el-button :disabled="saving" @click="formStep > 0 ? formStep-- : formVisible = false">{{ formStep > 0 ? '上一组' : '取消' }}</el-button><el-button v-if="formStep < formStepCount - 1" type="primary" :disabled="formLoading || saving" @click="formStep++">下一组</el-button><el-button v-else type="primary" :loading="saving" :disabled="formLoading || optionsError || !canSave" @click="save">保存配置</el-button></template>
    </el-dialog>

    <MobileSheet v-model="confirmVisible" :title="confirmation?.title || '确认操作'" :close-on-click-modal="!mutating" :close-on-press-escape="!mutating" :show-close="!mutating"><p class="resource-confirm-text">{{ confirmation?.message }}</p><el-alert v-if="mutationError" :title="mutationError" type="error" :closable="false" /><template #footer><el-button :disabled="mutating" @click="confirmVisible = false">取消</el-button><el-button :type="confirmation?.action === 'toggle' && !confirmation?.item.enabled ? 'success' : 'danger'" :loading="mutating" @click="performMutation">{{ confirmation?.confirmLabel || '确定' }}</el-button></template></MobileSheet>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { actionApi } from '@/api/action'
import { platformApi } from '@/api/platform'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'
import { formatDateTime } from '@/utils/action'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import MobileResourceFields from './MobileResourceFields.vue'
import MobileResourceForm from './MobileResourceForm.vue'
import { RESOURCE_PERMISSIONS, makeResourceDraft, validateResourceDraft, resourcePayload } from './mobileResourceData'

const props = defineProps({ activeTab: { type: String, required: true }, keyword: { type: String, default: '' }, label: { type: String, default: '资源' } })
const emit = defineEmits(['changed', 'overlayChange'])
const config = computed(() => RESOURCE_PERMISSIONS[props.activeTab])
const canRead = computed(() => Boolean(config.value && hasPerm(config.value.page.visible) && hasPerm(config.value.page.access) && hasPerm(config.value.read)))
const canReadDetail = computed(() => canRead.value && (props.activeTab !== 'accounts' || hasPerm(config.value.detail)))
const items = ref([]), total = ref(0), page = ref(1), loading = ref(false), listError = ref(''), platforms = ref([]), platformFilter = ref('')
const totalPages = computed(() => props.activeTab === 'nodes' ? 1 : Math.max(1, Math.ceil(total.value / 10)))
const filteredItems = computed(() => props.activeTab === 'encapsulatedNodes' ? items.value : items.value.filter(item => [item.name, item.label, item.account_name, item.handle_name, item.description, item.id, item.type].some(value => String(value || '').toLowerCase().includes(props.keyword.trim().toLowerCase()))))
const statusLabels = { ACTIVE: '正常', RISK: '风险', CAPTCHA: '验证码', INVALID_PWD: '密码异常', EXPIRED: '已过期', BANNED: '已封禁', running: '运行中', pending: '待运行', finished: '已完成', failed: '失败', stopped: '已停止', cancelled: '已取消', paused: '已暂停', timeout: '已超时' }
const detailVisible = ref(false), detailLoading = ref(false), detailError = ref(''), detail = ref(null), detailMode = ref('resource'), selectedItem = ref(null), selectedFamily = ref(null)
const currentResource = computed(() => detailMode.value === 'version' ? detail.value?.node || {} : detail.value || {})
const canEditDetail = computed(() => Boolean(config.value?.update && hasPerm(config.value.update) && (props.activeTab !== 'nodes' || currentResource.value.definition_origin === 'user') && (props.activeTab !== 'accounts' || hasPerm(config.value.detail))))
const canDeleteDetail = computed(() => Boolean(config.value?.delete && hasPerm(config.value.delete) && (props.activeTab !== 'nodes' || currentResource.value.definition_origin === 'user')))
const formVisible = ref(false), formLoading = ref(false), formError = ref(''), optionsError = ref(false), saving = ref(false), editingId = ref(''), formStep = ref(0), invalidIndex = ref(-1), draft = ref({})
const options = ref({ platforms: [], types: [], components: [], handles: [] })
const formStepCount = computed(() => props.activeTab === 'nodes' ? 4 : props.activeTab === 'accounts' ? 3 : 2)
const canSave = computed(() => Boolean(canRead.value && config.value?.[editingId.value ? 'update' : 'create'] && hasPerm(config.value[editingId.value ? 'update' : 'create'])))
const confirmation = ref(null), confirmVisible = ref(false), mutating = ref(false), mutationError = ref('')
let active = true, listId = 0, detailId = 0, formId = 0, visitId = 0, searchTimer = null
const detailFields = computed(() => {
  const data = currentResource.value
  if (props.activeTab === 'accounts') return [
    { label: '账号 ID', value: data.id }, { label: '平台', value: platforms.value.find(item => item.id === data.platform_id)?.name || data.platform_id },
    { label: '状态', value: statusLabels[data.status] || data.status }, { label: '状态说明', value: data.status_reason },
    { label: '用户名', value: data.credentials?.username }, { label: '手机号', value: data.credentials?.phone }, { label: '邮箱', value: data.credentials?.email },
    { label: '频率限制', value: data.rate_limit }, { label: '创建时间', value: formatDateTime(data.created_at) }, { label: '更新时间', value: formatDateTime(data.updated_at) },
  ]
  if (props.activeTab === 'baseComponents') return [{ label: '组件 ID', value: data.id }, { label: '说明', value: data.description }, { label: '状态', value: statusLabels[data.status] || data.status }, { label: '总运行次数', value: data.total_runs }, { label: '平均运行秒数', value: data.average_runtime }, { label: '最近运行', value: formatDateTime(data.last_run_at, { defaultValue: '未运行' }) }]
  if (props.activeTab === 'nodeHandles') return [{ label: '接口 ID', value: data.id }, { label: '接口名称', value: data.handle_name }, { label: '类型', value: data.type }, { label: '颜色', value: data.color }, { label: '兼容接口', value: data.other_compatible_interfaces }, { label: '自定义样式', value: data.custom_style }]
  return [{ label: '节点 ID', value: data.id }, { label: '说明', value: data.description }, { label: '类型', value: data.type || data.node_kind }, { label: '定义来源', value: data.definition_origin === 'backend_builtin' ? '系统内置' : data.definition_origin }, { label: '版本', value: data.definition_version || data.version },
    ...(detailMode.value === 'version' ? [{ label: '资源族 ID', value: data.node_family_id }, { label: '源蓝图', value: detail.value.source_blueprint?.name || data.source_blueprint_id }, { label: '源 Revision', value: data.source_revision_id }] : []),
    { label: '运行命令', value: data.command }, { label: '运行参数', value: data.command_args }, { label: '关联组件', value: data.related_components }, { label: '组件超时', value: data.component_timeouts }, { label: '默认配置', value: data.default_configs }, ...(data.execution ? [{ label: '执行设置', value: data.execution }] : []),
  ]
})

/** """读取当前模块的真实数据，切换模块或重复加载时丢弃旧响应。""" */
async function load() {
  const id = ++listId
  if (!active || !canRead.value) { items.value = []; total.value = 0; loading.value = false; return }
  const tab = props.activeTab
  loading.value = true
  listError.value = ''
  try {
    const api = { nodes: actionApi.getNodes, encapsulatedNodes: actionApi.getEncapsulatedNodes, baseComponents: actionApi.getBaseComponents, nodeHandles: actionApi.getNodeHandles, accounts: actionApi.getAccountList }[tab]
    const response = await api({ page: page.value, page_size: 10, ...(tab === 'encapsulatedNodes' ? { keyword: props.keyword.trim() || undefined } : {}), ...(tab === 'accounts' ? { platform_id: platformFilter.value || undefined } : {}) })
    if (id !== listId || !active) return
    if (response?.code != null && response.code !== 0) throw new Error(response.message || '资源加载失败')
    const data = response?.data ?? response
    if (tab === 'nodes') {
      if (!Array.isArray(data)) throw new Error('节点列表格式异常')
      items.value = data.filter(item => item.node_kind !== 'encapsulated')
      total.value = items.value.length
    } else {
      if (!Array.isArray(data?.items)) throw new Error('资源列表格式异常')
      items.value = data.items
      total.value = data.total || 0
    }
  } catch (error) {
    if (id === listId && active) { listError.value = error?.message || '资源加载失败，请重试'; items.value = []; total.value = 0 }
  } finally { if (id === listId) loading.value = false }
}

/** """按资源类型读取详情，账号详情独立检查敏感资料读取权限。""" */
async function openDetail(item, version = false) {
  if (!active || !canReadDetail.value) return
  const id = ++detailId
  selectedItem.value = item
  detailVisible.value = true
  detailError.value = ''
  detail.value = null
  detailMode.value = version ? 'version' : props.activeTab === 'encapsulatedNodes' ? 'family' : 'resource'
  if (detailMode.value === 'family') { selectedFamily.value = item; detail.value = item; detailLoading.value = false; return }
  const api = version ? actionApi.getEncapsulatedNodeDetail : props.activeTab === 'nodes' ? actionApi.getNodeDetail : props.activeTab === 'accounts' ? actionApi.getAccountDetail : null
  if (!api) { detail.value = item; detailLoading.value = false; return }
  detailLoading.value = true
  try {
    const response = await api(item.id)
    if (id !== detailId || !active || !detailVisible.value || !canReadDetail.value) return
    if (response?.code !== 0 || !response.data) throw new Error(response?.message || '详情加载失败')
    detail.value = response.data
  } catch (error) { if (id === detailId && active) detailError.value = error?.message || '详情加载失败，请重试' }
  finally { if (id === detailId) detailLoading.value = false }
}

/** """打开独立分组表单，仅复制已授权的详情或创建默认草稿。""" */
async function openEditor(item = null) {
  const permission = config.value?.[item ? 'update' : 'create']
  if (!active || !canRead.value || !permission || !hasPerm(permission) || (item && !canEditDetail.value)) return
  editingId.value = item?.id || ''
  draft.value = makeResourceDraft(props.activeTab, item || {})
  formStep.value = 0
  invalidIndex.value = -1
  formError.value = ''
  detailVisible.value = false
  formVisible.value = true
  await loadOptions()
}

/** """加载表单选项，失败保留草稿并允许重试。""" */
async function loadOptions() {
  const id = ++formId, tab = props.activeTab
  formLoading.value = true
  optionsError.value = false
  formError.value = ''
  try {
    const next = { platforms: [], types: [], components: [], handles: [] }
    if (tab === 'accounts') {
      const response = await platformApi.getPlatformFilterPlatforms()
      if (response?.code !== 0 || !Array.isArray(response.data)) throw new Error('平台选项加载失败')
      next.platforms = response.data
    } else {
      const handles = await actionApi.getAllNodeHandles()
      if (handles?.code !== 0 || !Array.isArray(handles.data)) throw new Error('接口选项加载失败')
      next.handles = handles.data
      if (tab === 'nodes') {
        const [types, components] = await Promise.all([actionApi.getNodeTypeFilter(), actionApi.getBaseComponents({ page: 1, page_size: 20 })])
        const componentData = components?.data ?? components
        if (types?.code !== 0 || !Array.isArray(types.data) || !Array.isArray(componentData?.items)) throw new Error('节点类型或组件选项加载失败')
        next.types = types.data.flatMap(item => Object.entries(item).map(([label, value]) => ({ label, value })))
        next.components = componentData.items
      }
    }
    if (id === formId && active && formVisible.value) options.value = next
  } catch (error) { if (id === formId && active) { formError.value = error?.message || '选项加载失败'; optionsError.value = true } }
  finally { if (id === formId) formLoading.value = false }
}

/** """完整校验每个分组后使用原有资源接口保存，迟到响应不能覆盖新草稿。""" */
async function save() {
  if (!active || !formVisible.value || saving.value || formLoading.value || optionsError.value || !canSave.value) return
  const validation = validateResourceDraft(props.activeTab, draft.value)
  if (validation) { formError.value = validation.message; formStep.value = validation.step; invalidIndex.value = validation.index ?? -1; return }
  const id = ++formId, tab = props.activeTab, resourceId = editingId.value
  saving.value = true
  formError.value = ''
  try {
    const payload = JSON.parse(JSON.stringify(resourcePayload(tab, draft.value)))
    const response = tab === 'nodes' ? await (resourceId ? actionApi.updateNode(resourceId, payload) : actionApi.createNode(payload)) : tab === 'accounts' ? await (resourceId ? actionApi.updateAccount(resourceId, payload) : actionApi.createAccount(payload)) : await actionApi.createNodeHandle(payload)
    if (id !== formId || !active || !formVisible.value) return
    if (response?.code !== 0) throw new Error(response?.message || '保存失败')
    ElMessage.success(resourceId ? '资源已更新' : '资源已创建')
    formVisible.value = false
    emit('changed')
    await load()
  } catch (error) { if (id === formId && active) formError.value = error?.message || '保存失败，请重试' }
  finally { if (id === formId) saving.value = false }
}

/** """显示当前资源操作的既有确认语义，封装版本引用阻止删除。""" */
function askMutation(action, item) {
  const permission = action === 'toggle' ? PERM.operations.action.node.nativeStatusUpdate : config.value?.delete
  if (!canRead.value || !permission || !hasPerm(permission) || (action === 'delete' && !canDeleteDetail.value)) return
  if (action === 'toggle' && (props.activeTab !== 'nodes' || item.definition_origin !== 'backend_builtin')) return
  if (props.activeTab === 'encapsulatedNodes' && (item.draft_reference_count || detail.value?.references?.length)) return
  let message = `确定要删除${props.activeTab === 'accounts' ? '采集账号' : '节点'}「${item.account_name || item.name}」吗？`
  if (action === 'toggle') message = item.enabled ? `禁用“${item.name}”后将从节点面板隐藏，且不能启动新的相关行动；在途行动不受影响。` : `启用“${item.name}”后可在新蓝图中使用。`
  if (props.activeTab === 'encapsulatedNodes') {
    const remaining = (selectedFamily.value?.versions || []).filter(version => version.id !== item.id).sort((a, b) => b.definition_version - a.definition_version)
    message = `确定删除“${item.name}”v${item.definition_version} 吗？${item.is_latest && remaining.length ? `删除后 v${remaining[0].definition_version} 将成为最新版。` : ''}${remaining.length ? '资源族仍有有效版本，历史版本号不会被复用。' : '这是最后一个有效版本，删除后将清理整个资源族及其旧式专属接口；再次封装会从 v1 开始。'}`
  }
  confirmation.value = { action, item: { ...item }, message, title: action === 'toggle' ? (item.enabled ? '确认禁用' : '确认启用') : '确认删除', confirmLabel: action === 'toggle' ? (item.enabled ? '禁用' : '启用') : '确定删除', permission }
  mutationError.value = ''
  confirmVisible.value = true
}

/** """确认后再检查权限和当前页面，失败保留原资料与确认信息。""" */
async function performMutation() {
  const change = confirmation.value, visit = visitId, tab = props.activeTab
  if (!active || !confirmVisible.value || mutating.value || !canRead.value || !change || !hasPerm(change.permission)) return
  mutating.value = true
  mutationError.value = ''
  try {
    const response = change.action === 'toggle' ? await actionApi.setNativeNodeEnabled(change.item.id, !change.item.enabled) : tab === 'accounts' ? await actionApi.deleteAccount(change.item.id) : tab === 'encapsulatedNodes' ? await actionApi.deleteEncapsulatedNode(change.item.id, { silent: true }) : await actionApi.deleteNode(change.item.id)
    if (visit !== visitId || !active) return
    if (response?.code != null && response.code !== 0) throw new Error(response.message || '操作失败')
    confirmVisible.value = false
    detailVisible.value = false
    ElMessage.success(change.action === 'toggle' ? '节点状态已更新' : '资源已删除')
    emit('changed')
    if (items.value.length === 1 && page.value > 1) page.value--
    await load()
  } catch (error) {
    if (visit !== visitId || !active) return
    mutationError.value = error?.code === 240423 ? '该版本仍被可编辑蓝图引用，暂时无法删除；请重新加载详情查看引用。' : error?.message || '操作失败，请重试'
  } finally { if (visit === visitId) mutating.value = false }
}

watch(() => props.activeTab, async () => {
  visitId++; listId++; detailId++; formId++
  if (searchTimer) clearTimeout(searchTimer)
  items.value = []; total.value = 0; page.value = 1; platformFilter.value = ''
  detailVisible.value = false; formVisible.value = false; confirmVisible.value = false
  detail.value = null; selectedFamily.value = null; selectedItem.value = null; saving.value = false; mutating.value = false
  const visit = visitId
  if (props.activeTab === 'accounts' && canRead.value) {
    try { const response = await platformApi.getPlatformFilterPlatforms(); if (visit === visitId && active) platforms.value = response?.data || [] } catch { if (visit === visitId) platforms.value = [] }
  }
  if (visit === visitId && active) await load()
}, { immediate: true })
watch(() => props.keyword, () => {
  if (props.activeTab !== 'encapsulatedNodes') return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; load() }, 250)
})
watch(canRead, value => { if (!value) { visitId++; listId++; detailId++; formId++; items.value = []; total.value = 0; loading.value = false; mutating.value = false; detailVisible.value = false; formVisible.value = false; confirmVisible.value = false } else load() })
watch(canReadDetail, value => { if (!value) { detailId++; detail.value = null; detailVisible.value = false; if (editingId.value) formVisible.value = false } })
watch(detailVisible, value => { if (!value) { detailId++; detailLoading.value = false } })
watch(formVisible, value => { if (!value) { formId++; formLoading.value = false; saving.value = false } })
watch([detailVisible, formVisible, confirmVisible], values => emit('overlayChange', values.some(Boolean)), { flush: 'sync' })
onBeforeUnmount(() => { active = false; visitId++; listId++; detailId++; formId++; detailVisible.value = false; formVisible.value = false; confirmVisible.value = false; if (searchTimer) clearTimeout(searchTimer) })
defineExpose({ openEditor, load })
</script>

<style scoped>
.mobile-action-resources { min-width: 0; }
.resource-platform-filter { width: 100%; margin-bottom: 12px; }
.resource-list-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; font-size: 12px; color: #64748b; margin: 4px 0 14px; }
.resource-card-list { display: grid; gap: 12px; }
.resource-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; }
.resource-card-main { display: block; width: 100%; padding: 16px; text-align: left; }
.resource-card-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.resource-card-heading h3 { color: #0f172a; font-size: 16px; font-weight: 650; overflow-wrap: anywhere; line-height: 1.6; }
.resource-card-heading svg { flex-shrink: 0; color: #94a3b8; margin-top: 5px; }
.resource-card-tags { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.resource-card-tags span { padding: 2px 6px; background: #eff6ff; border-radius: 5px; color: #2563eb; font-size: 11px; }
.resource-card-tags .success { color: #15803d; background: #f0fdf4; }
.resource-card-tags .muted { color: #64748b; background: #f1f5f9; }
.resource-card-main p { color: #64748b; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; margin: 8px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.resource-card small, .resource-card-note { color: #94a3b8; font-size: 11px; overflow-wrap: anywhere; }
.resource-card-note { padding: 0 16px 14px; }
.resource-pagination { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 18px; font-size: 13px; color: #64748b; }
.resource-pagination .el-button { min-height: 44px; }
.resource-state { padding: 32px 12px; text-align: center; color: #64748b; font-size: 13px; line-height: 1.8; }
.resource-state svg { font-size: 36px; margin: 0 auto 12px; color: #94a3b8; }
.resource-detail-title { font-size: 21px; font-weight: 700; color: #0f172a; line-height: 1.5; overflow-wrap: anywhere; margin: 0 0 12px; }
.resource-detail-subtitle { font-size: 13px; line-height: 1.7; color: #64748b; margin-bottom: 16px; overflow-wrap: anywhere; }
.resource-detail-section { margin-top: 24px; }
.resource-detail-section > h3 { font-size: 15px; color: #334155; font-weight: 650; margin-bottom: 12px; }
.resource-detail-section > p { color: #94a3b8; font-size: 13px; }
.resource-detail-item { border: 1px solid #e2e8f0; padding: 12px; border-radius: 12px; margin-top: 10px; }
.resource-detail-item h4 { font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.resource-version { border: 1px solid #e2e8f0; border-radius: 12px; margin: 12px 0; }
.resource-version button { display: block; width: 100%; position: relative; text-align: left; padding: 14px 28px 14px 14px; }
.resource-version strong { display: block; overflow-wrap: anywhere; }
.resource-version span { color: #15803d; font-size: 11px; }
.resource-version p { color: #64748b; font-size: 13px; margin: 8px 0; overflow-wrap: anywhere; }
.resource-version small { font-size: 11px; color: #94a3b8; }
.resource-version svg { position: absolute; right: 8px; top: 20px; }
.resource-confirm-text { color: #475569; line-height: 1.8; font-size: 14px; overflow-wrap: anywhere; margin-bottom: 16px; }
.resource-form-error { margin-bottom: 16px; }
.resource-card-list[aria-busy=true] { opacity: .6; }
button:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
</style>
