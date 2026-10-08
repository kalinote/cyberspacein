<template>
  <section class="mobile-blueprint-editor" aria-label="手机蓝图编辑器">
    <div class="editor-summary">
      <div><strong>{{ title || '未命名蓝图' }}</strong><small>{{ dirty ? '有未保存修改' : '草稿已保存' }} · {{ nodes.length }} 个节点 · {{ edges.length }} 条数据连接</small></div>
      <el-button :disabled="loading || saving" @click="settingsVisible = true">设置</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="$emit('retry')">重新加载</el-button></el-alert>
    <el-alert v-else-if="!editable" title="当前权限仅可查看，无法修改或保存蓝图" type="warning" :closable="false" />
    <div class="editor-tabs"><button :aria-pressed="view === 'list'" @click="view = 'list'">流程目录</button><button :aria-pressed="view === 'canvas'" @click="view = 'canvas'; $emit('fit')">画布</button><button @click="interfacesVisible = true">公开 IO</button></div>
    <div class="editor-modes" aria-label="画布操作模式">
      <button v-for="item in modes" :key="item.value" :disabled="!editable && item.value !== 'browse' || saving" :aria-pressed="mode === item.value" @click="changeMode(item.value)">{{ item.label }}</button>
    </div>
    <p class="mode-help">{{ mode === 'connect' ? '选择起点的输出端口，再选择兼容输入。公开 IO 绑定在独立向导中操作。' : mode === 'move' ? '拖动节点或在节点菜单中调整坐标，应用后才计入草稿。' : mode === 'select' ? `点选节点，可批量移除。已选 ${selectedIds.length} 个。` : '点选节点查看参数及上游、下游。目录顺序不代表执行顺序。' }}</p>
    <div v-show="view === 'canvas'" class="editor-canvas"><slot name="canvas" /><div class="fit-buttons"><el-button @click="$emit('fit')">聚焦节点</el-button><el-button @click="$emit('fit-all')">显示全图</el-button></div></div>
    <div v-if="view === 'list'" class="editor-directory">
      <el-input v-model="query" placeholder="查找节点名称、类型或 ID" clearable aria-label="查找蓝图节点" />
      <el-empty v-if="!nodes.length && !loading && !error" description="从添加节点开始创建蓝图" :image-size="64" />
      <button v-for="node in filteredNodes" :key="node.id" class="node-row" :class="{ active: selectedIds.includes(node.id) || selectedId === node.id }" @click="selectNode(node.id)">
        <span class="node-kind">{{ node.data.config?.type }}</span><strong>{{ node.data.config?.name || node.id }}</strong><small>{{ node.id }} · {{ edges.filter(edge => edge.target === node.id).length }} 上游 / {{ edges.filter(edge => edge.source === node.id).length }} 下游</small>
        <span v-if="node.data.boundaryBinding" class="binding-note">公开 IO 已绑定</span><span v-if="mode === 'select'">{{ selectedIds.includes(node.id) ? '已选择' : '点按选择' }}</span>
      </button>
      <p v-if="nodes.length && !filteredNodes.length">没有匹配的节点</p>
      <button v-if="edges.length" class="secondary-row" @click="connectionsVisible = true">查看全部 {{ edges.length }} 条数据连接</button>
    </div>
    <div v-if="mode === 'move'" class="layout-actions"><el-button @click="$emit('cancel-layout'); mode = 'browse'; $emit('mode', 'browse')">取消移动</el-button><el-button type="primary" :disabled="!editable" @click="$emit('apply-layout'); mode = 'browse'; $emit('mode', 'browse')">应用布局</el-button></div>
    <div v-else-if="mode === 'select' && selectedIds.length" class="layout-actions"><span>已选 {{ selectedIds.length }} 个节点</span><el-button :disabled="!editable || saving" @click="groupMoveVisible = true; groupX = 0; groupY = 0">批量移动</el-button><el-button type="danger" plain :disabled="!editable || saving" @click="$emit('remove', { nodeIds: [...selectedIds] })">移除所选</el-button></div>
    <div class="editor-bottom">
      <div class="history-actions"><el-button :disabled="!editable || !canUndo || saving || mode === 'move'" @click="$emit('undo')">撤销</el-button><el-button :disabled="!editable || !canRedo || saving || mode === 'move'" @click="$emit('redo')">重做</el-button><el-button :disabled="loading" @click="issuesVisible = true">校验{{ issues.length ? ` (${issues.length})` : '' }}</el-button></div>
      <div class="save-actions"><el-button :disabled="!editable || saving || loading || mode === 'move'" @click="addVisible = true">添加节点</el-button><el-button type="primary" :loading="saving" :disabled="!editable || loading || Boolean(error) || mode === 'move'" @click="$emit('save')">保存草稿</el-button></div>
    </div>

    <MobileSheet v-model="nodeVisible" :title="selectedNode?.data.config?.name || '节点详情'">
      <template v-if="selectedNode">
        <p class="muted">{{ selectedNode.data.config?.description || '暂无节点说明' }}</p><p class="muted">{{ selectedNode.id }} · 版本 {{ selectedNode.data.config?.version || selectedNode.data.config?.definition_version || '—' }}</p>
        <div class="node-actions"><el-button :disabled="!editable || saving" @click="nodeVisible = false; fieldsVisible = true">编辑参数</el-button><el-button :disabled="!editable || saving" @click="beginConnection(selectedNode.id)">连接端口</el-button><el-button :disabled="!editable || saving" @click="nodeVisible = false; moveNodeVisible = true; moveX = selectedNode.position.x; moveY = selectedNode.position.y">调整位置</el-button></div>
        <div v-if="isBoundaryConfig(selectedNode.data.config)" class="io-explanation"><p>{{ getBoundaryDirection(selectedNode) === 'input' ? '蓝图输入可替代起始节点的输出端口。' : '蓝图输出可替代结束节点的输入端口。' }}</p><el-button :disabled="!editable || saving" @click="nodeVisible = false; bindingVisible = true">{{ selectedNode.data.boundaryBinding ? '修改 IO 绑定' : '建立 IO 绑定' }}</el-button><el-button v-if="selectedNode.data.boundaryBinding" :disabled="!editable || saving" @click="$emit('unbind', selectedNode.id)">解除绑定</el-button></div>
        <slot name="upgrade" />
        <h3>数据连接</h3><p v-if="!selectedEdges.length" class="muted">该节点暂无数据连接</p>
        <button v-for="edge in selectedEdges" :key="edge.id" class="connection-row" @click="openEdge(edge)">{{ edgeLabel(edge) }}<small>查看连接</small></button>
        <el-button type="danger" plain :disabled="!editable || saving" @click="$emit('remove', { nodeIds: [selectedNode.id] })">移除此节点</el-button>
      </template>
    </MobileSheet>
    <MobileSheet v-model="fieldsVisible" :destroy-on-close="true" :title="`${selectedNode?.data.config?.name || '节点'} · 参数`"><slot v-if="selectedNode && fieldsVisible" name="fields" :node="selectedNode" /><template #footer><el-button type="primary" @click="fieldsVisible = false">完成参数编辑</el-button></template></MobileSheet>
    <MobileSheet v-model="settingsVisible" title="蓝图设置"><slot name="settings" /><div class="node-actions"><el-button @click="settingsVisible = false; templateVisible = true">模板参数</el-button><el-button @click="settingsVisible = false; resourceVisible = true">资源配置</el-button></div><slot name="publish" /></MobileSheet>
    <MobileSheet v-model="templateVisible" :destroy-on-close="true" title="模板参数与绑定"><slot v-if="templateVisible" name="template" /></MobileSheet>
    <MobileSheet v-model="resourceVisible" title="资源配置"><slot name="resource" /></MobileSheet>
    <MobileSheet v-model="interfacesVisible" title="公开输入与输出"><p class="muted">公开接口、普通数据连接和 IO 替换绑定各自保留原有语义。</p><slot name="interfaces" /><button v-for="node in boundaryNodes" :key="node.id" class="node-row" @click="interfacesVisible = false; selectNode(node.id)">{{ node.data.config?.name }} · {{ node.id }}<small>{{ node.data.boundaryBinding ? '查看或修改绑定' : '配置公开接口' }}</small></button></MobileSheet>
    <MobileSheet v-model="addVisible" title="添加节点"><el-input v-model="addQuery" placeholder="搜索节点名称或类型" clearable /><button v-for="config in availableConfigs" :key="config.id" class="node-row" :disabled="!editable || saving" @click="addVisible = false; $emit('add-node', config.id)"><span class="node-kind">{{ config.type }} · v{{ config.version || config.definition_version }}</span><strong>{{ config.name }}</strong><small>{{ config.description || '添加后编辑参数与连接' }}</small></button></MobileSheet>
    <MobileSheet v-model="connectionVisible" :title="`连接端口 · ${connectionStep}/3`">
      <p class="muted">{{ connectionStep === 1 ? '选择起点节点的输出端口' : connectionStep === 2 ? '选择兼容的目标输入端口' : '确认数据流向与两端接口' }}</p>
      <template v-if="connectionStep === 1"><label>起点节点</label><el-select v-model="connection.source" filterable class="full-width"><el-option v-for="node in nodes.filter(item => !item.data.boundaryBinding)" :key="node.id" :label="`${node.data.config?.name} · ${node.id}`" :value="node.id" /></el-select><button v-for="handle in sourceHandles" :key="handle.id" class="node-row" @click="connection.sourceHandle = handle.id; connectionStep = 2"><strong>{{ handle.relabel || handle.label || handle.name || handle.id }}</strong><small>{{ handle.data_type || 'value' }} · {{ handle.interface_type_id || handle.id }}</small></button><p v-if="!sourceHandles.length" class="muted">该节点没有可用输出端口。</p></template>
      <template v-else-if="connectionStep === 2"><p class="connection-summary">从 {{ nodeName(connection.source) }} / {{ handleName(connection.source, connection.sourceHandle) }}</p><button v-for="option in compatibleTargets" :key="`${option.node.id}:${option.handle.id}`" class="node-row" @click="connection.target = option.node.id; connection.targetHandle = option.handle.id; connectionStep = 3"><strong>{{ option.node.data.config?.name }} / {{ option.handle.relabel || option.handle.label || option.handle.name || option.handle.id }}</strong><small>{{ option.node.id }} · {{ option.handle.data_type || 'value' }} · {{ option.handle.interface_type_id || option.handle.id }}</small></button><p v-if="!compatibleTargets.length" class="muted">暂无兼容输入。请检查传输类型、业务接口与输入端口占用，或先添加节点。</p></template>
      <template v-else><div class="connection-summary"><strong>{{ nodeName(connection.source) }}</strong><small>{{ connection.source }}</small><span>{{ handleName(connection.source, connection.sourceHandle) }} · {{ connection.sourceHandle }}</span><p>↓</p><strong>{{ nodeName(connection.target) }}</strong><small>{{ connection.target }}</small><span>{{ handleName(connection.target, connection.targetHandle) }} · {{ connection.targetHandle }}</span></div><el-alert v-if="connectionIssue" :title="connectionIssue" type="error" :closable="false" /><p v-else>将新增一条数据连接，不改变其它分支或端口连接。</p></template>
      <template #footer><el-button v-if="connectionStep > 1" @click="connectionStep--">上一步</el-button><el-button v-if="connectionStep === 3" type="primary" :disabled="!editable || saving || Boolean(connectionIssue)" @click="$emit('connect', { ...connection }); connectionVisible = false">确认连接</el-button><el-button v-else @click="connectionVisible = false">取消</el-button></template>
    </MobileSheet>
    <MobileSheet v-model="bindingVisible" title="公开 IO 绑定 · 选择目标"><p class="muted">{{ selectedNode && getBoundaryDirection(selectedNode) === 'input' ? '选择已有输出数据连接的起始节点，再映射需要替代的输出端口。' : '选择已有输入数据连接的结束节点，再映射需要替代的输入端口。' }}</p><button v-for="candidate in bindingCandidates" :key="candidate.node.id" class="node-row" :disabled="!candidate.valid || !editable || saving" @click="bindingVisible = false; $emit('bind', { boundaryId: selectedId, targetId: candidate.node.id })"><strong>{{ candidate.node.data.config?.name }} · {{ candidate.node.id }}</strong><small>{{ candidate.valid ? '下一步：选择端口与接口名称' : candidate.reason }}</small></button></MobileSheet>
    <MobileSheet v-model="connectionsVisible" title="全部数据连接"><button v-for="edge in edges" :key="edge.id" class="connection-row" @click="connectionsVisible = false; openEdge(edge)">{{ edgeLabel(edge) }}</button></MobileSheet>
    <MobileSheet v-model="edgeVisible" title="数据连接详情"><template v-if="selectedEdge"><p class="connection-summary">{{ edgeLabel(selectedEdge) }}</p><el-button @click="edgeVisible = false; selectNode(selectedEdge.source)">查看起点</el-button><el-button @click="edgeVisible = false; selectNode(selectedEdge.target)">查看终点</el-button><el-button type="danger" plain :disabled="!editable || saving" @click="$emit('remove', { edgeIds: [selectedEdge.id] })">移除连接</el-button></template></MobileSheet>
    <MobileSheet v-model="moveNodeVisible" title="调整节点位置"><p class="muted">坐标只影响布局，数据连接保持不变。</p><label>X 坐标</label><el-input-number v-model="moveX" :controls="false" /><label>Y 坐标</label><el-input-number v-model="moveY" :controls="false" /><template #footer><el-button @click="moveNodeVisible = false">取消</el-button><el-button type="primary" :disabled="!editable || saving || !Number.isFinite(moveX) || !Number.isFinite(moveY)" @click="$emit('position', { nodeId: selectedId, x: moveX, y: moveY }); moveNodeVisible = false">应用坐标</el-button></template></MobileSheet>
    <MobileSheet v-model="groupMoveVisible" title="批量移动所选节点"><p class="muted">统一移动 {{ selectedIds.length }} 个节点，保留它们的相对位置和所有连接。正数向右或向下，负数向左或向上。</p><label>水平偏移</label><el-input-number v-model="groupX" :step="40" /><label>垂直偏移</label><el-input-number v-model="groupY" :step="40" /><template #footer><el-button @click="groupMoveVisible = false">取消</el-button><el-button type="primary" :disabled="!editable || saving || !Number.isFinite(groupX) || !Number.isFinite(groupY)" @click="$emit('move-group', { nodeIds: [...selectedIds], x: groupX, y: groupY }); groupMoveVisible = false">应用批量布局</el-button></template></MobileSheet>
    <MobileSheet v-model="issuesVisible" title="草稿校验"><el-empty v-if="!issues.length" description="本地校验通过，保存时服务器继续校验" :image-size="64" /><button v-for="(issue, index) in issues" :key="index" class="connection-row" @click="issuesVisible = false; issue.nodeId ? selectNode(issue.nodeId) : settingsVisible = true">{{ issue.message }}<small>{{ issue.nodeId ? '定位节点' : '查看蓝图设置' }}</small></button></MobileSheet>
  </section>
</template>

<script setup>
import { computed, ref, watch, inject, onBeforeUnmount, onDeactivated } from 'vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { isBoundaryConfig, getBoundaryDirection, validateBindingCandidate } from '@/utils/action/boundaryBinding'
import { blueprintConnectionIssue } from '@/utils/action/mobileGraph'

const props = defineProps({ elements: { type: Array, default: () => [] }, configs: { type: Array, default: () => [] }, selectedId: String, title: String, editable: Boolean, dirty: Boolean, loading: Boolean, saving: Boolean, error: String, canUndo: Boolean, canRedo: Boolean, issues: { type: Array, default: () => [] } })
const emit = defineEmits(['select', 'selection', 'mode', 'fit', 'fit-all', 'save', 'retry', 'undo', 'redo', 'add-node', 'connect', 'bind', 'unbind', 'remove', 'position', 'move-group', 'apply-layout', 'cancel-layout'])
const localDrafts = inject('blueprintLocalDrafts', null), localDraftKey = Symbol('蓝图交互面板草稿')
const view = ref('list'), mode = ref('browse'), query = ref(''), addQuery = ref(''), selectedIds = ref([])
const modes = [{ value: 'browse', label: '浏览' }, { value: 'connect', label: '连线' }, { value: 'move', label: '移动' }, { value: 'select', label: '多选' }]
const nodeVisible = ref(false), fieldsVisible = ref(false), settingsVisible = ref(false), templateVisible = ref(false), resourceVisible = ref(false), interfacesVisible = ref(false), addVisible = ref(false), connectionVisible = ref(false), bindingVisible = ref(false), connectionsVisible = ref(false), edgeVisible = ref(false), moveNodeVisible = ref(false), issuesVisible = ref(false)
const moveX = ref(0), moveY = ref(0), groupX = ref(0), groupY = ref(0), groupMoveVisible = ref(false), selectedEdgeId = ref(null), connectionStep = ref(1)
const connection = ref({ source: '', sourceHandle: '', target: '', targetHandle: '' })
const nodes = computed(() => props.elements.filter(item => !item.source))
const edges = computed(() => props.elements.filter(item => item.source && item.data?.relationKind !== 'boundary-binding'))
const selectedNode = computed(() => nodes.value.find(node => node.id === props.selectedId))
const selectedEdge = computed(() => edges.value.find(edge => edge.id === selectedEdgeId.value))
const selectedEdges = computed(() => edges.value.filter(edge => edge.source === props.selectedId || edge.target === props.selectedId))
const boundaryNodes = computed(() => nodes.value.filter(node => isBoundaryConfig(node.data.config)))
const filteredNodes = computed(() => nodes.value.filter(node => `${node.data.config?.name} ${node.data.config?.type} ${node.id}`.toLowerCase().includes(query.value.toLowerCase())))
const availableConfigs = computed(() => props.configs.filter(config => config.enabled && config.is_latest && !config.rendererUnsupported && `${config.name} ${config.type}`.toLowerCase().includes(addQuery.value.toLowerCase())))
const sourceHandles = computed(() => (nodes.value.find(node => node.id === connection.value.source)?.data.config?.handles || []).filter(handle => handle.type === 'source'))
const compatibleTargets = computed(() => nodes.value.flatMap(node => (node.data.config?.handles || []).filter(handle => handle.type === 'target' && !blueprintConnectionIssue(nodes.value, edges.value, { ...connection.value, target: node.id, targetHandle: handle.id })).map(handle => ({ node, handle }))))
const connectionIssue = computed(() => blueprintConnectionIssue(nodes.value, edges.value, connection.value))
const bindingCandidates = computed(() => selectedNode.value ? nodes.value.filter(node => !isBoundaryConfig(node.data.config)).map(node => { const result = validateBindingCandidate(selectedNode.value, node, nodes.value, edges.value); return { node, valid: result.valid, reason: result.issues[0]?.message || '该节点不能绑定' } }) : [])
watch(() => JSON.stringify({
  connection: connectionVisible.value && connectionStep.value > 1 ? connection.value : null,
  position: moveNodeVisible.value && selectedNode.value && (moveX.value !== selectedNode.value.position.x || moveY.value !== selectedNode.value.position.y) ? [moveX.value, moveY.value] : null,
  group: groupMoveVisible.value && (groupX.value || groupY.value) ? [groupX.value, groupY.value] : null,
}), signature => {
  if (signature === '{"connection":null,"position":null,"group":null}') localDrafts?.delete(localDraftKey)
  else localDrafts?.set(localDraftKey, signature)
}, { flush: 'sync' })

/** """按当前模式选择节点，不将浏览手势当成拖拽或连线。""" */
function selectNode(id) {
  if (!nodes.value.some(node => node.id === id)) return
  emit('select', id)
  if (mode.value === 'select') { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter(value => value !== id) : [...selectedIds.value, id]; return }
  if (mode.value === 'connect' && props.editable) { beginConnection(id); return }
  if (mode.value === 'move') { const node = nodes.value.find(item => item.id === id); moveX.value = node.position.x; moveY.value = node.position.y; moveNodeVisible.value = true }
  else nodeVisible.value = true
}
/** """切换交互模式时撤回尚未应用的位置变更。""" */
function changeMode(value) {
  if (mode.value === 'move' && value !== 'move') emit('cancel-layout')
  if (value === 'move' && mode.value !== 'move') { view.value = 'canvas'; emit('fit') }
  mode.value = value
  selectedIds.value = []
  emit('mode', value)
}
/** """重新开始三步端口连接，清除上次目标。""" */
function beginConnection(id) {
  if (!props.editable || props.saving) return
  connection.value = { source: id || '', sourceHandle: '', target: '', targetHandle: '' }
  connectionStep.value = 1
  nodeVisible.value = false
  connectionVisible.value = true
}
/** """显示真实边，不改变其端口和方向。""" */
function openEdge(edge) { selectedEdgeId.value = edge.id; nodeVisible.value = false; edgeVisible.value = true }
/** """查找节点显示名，找不到时保留可追溯的 ID。""" */
function nodeName(id) { return nodes.value.find(node => node.id === id)?.data.config?.name || id }
/** """查找端口显示名，保留未解析端口。""" */
function handleName(nodeId, handleId) {
  const handle = nodes.value.find(node => node.id === nodeId)?.data.config?.handles?.find(item => item.id === handleId)
  return handle?.relabel || handle?.label || handle?.name || handleId
}
/** """用完整两端标识展示连接，避免同名节点混淆。""" */
function edgeLabel(edge) { return `${nodeName(edge.source)} (${edge.source}) / ${handleName(edge.source, edge.sourceHandle)} → ${nodeName(edge.target)} (${edge.target}) / ${handleName(edge.target, edge.targetHandle)}` }
/** """离页或撤权关闭传送到 body 的所有编辑面板。""" */
function closeSheets() {
  for (const sheet of [nodeVisible, fieldsVisible, settingsVisible, templateVisible, resourceVisible, interfacesVisible, addVisible, connectionVisible, bindingVisible, connectionsVisible, edgeVisible, moveNodeVisible, groupMoveVisible, issuesVisible]) sheet.value = false
}
watch(() => props.editable, editable => { if (!editable) { closeSheets(); changeMode('browse') } })
watch(() => props.selectedId, id => { if (!id) { nodeVisible.value = false; fieldsVisible.value = false; bindingVisible.value = false } })
watch(selectedIds, ids => emit('selection', [...ids]))
watch(() => props.elements, () => { selectedIds.value = selectedIds.value.filter(id => nodes.value.some(node => node.id === id)); if (!selectedEdge.value) edgeVisible.value = false }, { deep: true })
onDeactivated(closeSheets)
onBeforeUnmount(() => { closeSheets(); localDrafts?.delete(localDraftKey) })
defineExpose({ selectNode, openEdge, closeSheets, showFields: () => { fieldsVisible.value = true }, showIssues: () => { issuesVisible.value = true } })
</script>

<style scoped>
.mobile-blueprint-editor { display: flex; flex: 1; min-height: 0; min-width: 0; flex-direction: column; overflow: hidden; background: #f8fafc; }
.editor-summary { padding: 12px 14px; display: flex; gap: 8px; justify-content: space-between; align-items: center; background: white; }
.editor-summary>div { min-width: 0; } .editor-summary strong { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; } .editor-summary small { display: block; color: #64748b; font-size: 11px; margin-top: 5px; }
.editor-tabs,.editor-modes { display: flex; gap: 6px; padding: 6px 12px; background: white; } .editor-tabs button,.editor-modes button { flex: 1; min-height: 44px; border-radius: 10px; border: 1px solid #e2e8f0; font-size: 12px; background: white; color: #475569; }
button[aria-pressed="true"] { color: #1d4ed8; border-color: #bfdbfe; background: #eff6ff; font-weight: 700; } button:disabled { opacity: .45; }
.mode-help { font-size: 11px; line-height: 1.6; color: #64748b; padding: 4px 14px 8px; margin: 0; }
.editor-directory { flex: 1; overflow: auto; overscroll-behavior: contain; padding: 0 12px 12px; min-height: 0; }
.node-row,.connection-row,.secondary-row { display: block; width: 100%; margin-top: 9px; padding: 13px; text-align: left; border: 1px solid #e2e8f0; border-radius: 13px; background: white; color: #334155; overflow-wrap: anywhere; min-height: 48px; font-size: 13px; }
.node-row.active { border-color: #60a5fa; background: #eff6ff; } .node-row strong,.node-row small,.connection-row small { display: block; margin-top: 5px; }.node-row small,.connection-row small,.muted { font-size: 12px; color: #64748b; line-height: 1.7; overflow-wrap: anywhere; }.node-kind,.binding-note { font-size: 11px; color: #6366f1; }
.editor-canvas { position: relative; flex: 1; min-height: 120px; overflow: hidden; }.fit-buttons { position: absolute; top: 8px; right: 8px; z-index: 5; display: flex; gap: 6px; }
.editor-bottom { flex-shrink: 0; padding: 8px 12px; border-top: 1px solid #e2e8f0; background: white; }.history-actions,.save-actions,.layout-actions,.node-actions { display: flex; flex-wrap: wrap; gap: 8px; }.history-actions { margin-bottom: 8px; }.save-actions>* { flex: 1; }.el-button+.el-button { margin-left: 0; }.el-button { min-height: 44px; }.history-actions .el-button { flex: 1; }.layout-actions { padding: 8px 12px; align-items: center; background: #eff6ff; }
.node-actions { margin: 16px 0; }.node-actions .el-button { flex: 1; padding-inline: 8px; }.connection-summary { padding: 14px; background: #eff6ff; border-radius: 12px; font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }.io-explanation { padding: 12px; background: #f5f3ff; border-radius: 12px; font-size: 12px; margin: 12px 0; }.full-width { width: 100%; } label { display: block; margin: 12px 0 6px; font-size: 13px; } h3 { font-size: 14px; margin: 16px 0 8px; }
.connection-summary strong,.connection-summary small,.connection-summary span { display: block; }.connection-summary small { color: #64748b; }
:deep(.vue-flow__controls-button) { width: 44px; height: 44px; min-width: 44px; padding: 0; display: flex; align-items: center; justify-content: center; box-sizing: border-box; } :deep(.vue-flow__controls-button svg) { width: 20px; height: 20px; max-width: 20px; max-height: 20px; }
</style>
