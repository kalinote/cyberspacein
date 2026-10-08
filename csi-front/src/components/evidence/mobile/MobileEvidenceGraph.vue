<template>
  <el-drawer v-model="visible" direction="btt" size="100%" append-to-body class="mobile-evidence-workspace" modal-class="mobile-evidence-workspace-overlay" :show-close="false" destroy-on-close @opened="fitLocal">
    <template #header><div class="evidence-graph-heading"><el-button @click="visible = false">阅读</el-button><div><h2>{{ graph.title }}</h2><small>局部图谱 · {{ dirty ? '草稿未保存' : '已保存' }}{{ editable ? '' : ' · 只读' }}</small></div><el-button type="primary" :loading="saving" :disabled="!editable || !dirty" @click="$emit('save')">保存</el-button></div></template>
    <div class="evidence-graph-filter" aria-label="关系筛选"><button v-for="item in filters" :key="item.value" type="button" :aria-pressed="filter === item.value" :class="{ active: filter === item.value }" @click="filter = item.value">{{ item.label }}</button></div>
    <div class="evidence-graph-context"><span>{{ focusedNode?.data.node.label || '暂无节点' }} · {{ depth }} 层</span><el-button @click="directoryVisible = true">节点目录</el-button></div>
    <div class="evidence-graph-context compact"><el-button :disabled="depth >= rendered.nodes.length || !projection.hiddenCount" @click="depth++">展开一层</el-button><el-button :disabled="depth === 1" @click="depth = 1">聚焦一层</el-button><el-button @click="fitLocal">回到焦点</el-button></div>
    <p v-if="saveError" role="alert" class="evidence-graph-error">保存失败，草稿已保留：{{ saveError }}</p>
    <p class="evidence-graph-hint" role="status">{{ modeHint }}</p>
    <div class="evidence-graph-canvas">
      <VueFlow :id="mobileFlowId" :nodes="canvasNodes" :edges="canvasEdges" :node-types="nodeTypes" :nodes-connectable="false" :nodes-draggable="editable && mode === 'move'" :select-nodes-on-drag="false" :delete-key-code="null" :min-zoom="0.12" :max-zoom="2" :fit-view-on-init="false" :pan-on-scroll="false" :zoom-on-double-click="false" :node-drag-threshold="8" :connection-radius="30" @node-click="onNodeTap($event.node.id)" @edge-click="onEdgeTap($event.edge)" @node-drag-start="beginDrag" @node-drag-stop="finishDrag"><Background :gap="24" /><Controls :show-interactive="false" /></VueFlow>
      <div v-if="!rendered.nodes.length" class="evidence-graph-empty">还没有节点<br><el-button :disabled="!editable" @click="$emit('add-node')">添加第一个节点</el-button></div>
      <span v-if="projection.hiddenCount" class="evidence-graph-hidden">另有 {{ projection.hiddenCount }} 个节点 · 从目录切换焦点</span>
    </div>
    <section v-if="selectedRelation && mode === 'browse'" class="evidence-graph-selection"><div><strong>{{ selectedRelation.data.edge.label }} · {{ RELATION_STATUS[selectedRelation.data.edge.status] }}</strong><p>{{ selectedRelation.data.edge.anchors.length }} 项具体版本依据</p></div><el-button @click="$emit('open-selection')">查看依据</el-button></section>
    <section v-else-if="selectedNode && mode === 'browse'" class="evidence-graph-selection"><div><strong>{{ selectedNode.data.node.label }}</strong><p>{{ selectedNode.data.inherited ? '引用内部节点 · 只读' : NODE_KINDS[selectedNode.data.node.kind].label }}</p></div><el-button @click="focusId = selectedNode.id; depth = 1">聚焦</el-button><el-button @click="$emit('open-selection')">详情</el-button></section>
    <section v-if="mode === 'move' || mode === 'multi'" class="evidence-graph-move">
      <div class="evidence-graph-context"><span>{{ mode === 'multi' ? `已选择 ${selectedIds.length} 个本链节点` : selectedNode?.data.inherited ? '引用节点不可移动' : selectedNode?.data.node.label || '先点选本链节点' }}</span><el-button v-if="mode === 'multi'" @click="directoryVisible = true">勾选节点</el-button></div>
      <div class="evidence-nudge" aria-label="移动选中节点"><el-button v-for="direction in directions" :key="direction.label" :disabled="!editable || !moveIds.length || saving" @click="moveBy(moveIds, direction.delta)">{{ direction.label }}</el-button><el-button v-if="mode === 'multi'" type="danger" plain :disabled="!editable || !selectedIds.length || saving" @click="$emit('remove-nodes', [...selectedIds])">移出</el-button></div>
    </section>
    <template #footer><div class="evidence-graph-history"><el-button :disabled="!editable || !canUndo || saving" @click="resetOffsets(); $emit('undo')">撤销</el-button><el-button :disabled="!editable || !canRedo || saving" @click="resetOffsets(); $emit('redo')">重做</el-button><el-button :disabled="!editable" @click="$emit('add-node')">添加节点</el-button></div><nav class="evidence-graph-modes" aria-label="图谱操作模式"><button v-for="item in modes" :key="item.value" type="button" :class="{ active: mode === item.value }" :aria-pressed="mode === item.value" :disabled="item.value !== 'browse' && !editable" @click="mode = item.value"><Icon :icon="item.icon" /><span>{{ item.label }}</span></button></nav></template>
  </el-drawer>
  <MobileSheet v-model="directoryVisible" :title="mode === 'multi' ? '勾选本链节点' : '切换局部图焦点'">
    <el-input v-model="directoryQuery" clearable placeholder="查找节点名称" aria-label="查找图谱节点" />
    <p class="evidence-graph-hint">{{ mode === 'multi' ? '引用内部节点只读。移出会先确认本链关联关系数量。' : mode === 'relation' ? '也可从目录选择起点和终点。' : '切换焦点只调整当前视图，不修改原图位置。' }}</p>
    <div class="evidence-graph-directory"><button v-for="node in directoryNodes" :key="node.id" type="button" :disabled="mode === 'multi' && node.data.inherited" :aria-pressed="mode === 'multi' ? selectedIds.includes(node.id) : focusId === node.id" @click="chooseDirectoryNode(node)"><Icon :icon="mode === 'multi' ? selectedIds.includes(node.id) ? 'mdi:checkbox-marked' : 'mdi:checkbox-blank-outline' : NODE_KINDS[node.data.node.kind].icon" /><span>{{ node.data.node.label }}<small>{{ node.data.inherited ? '引用内部 · 只读' : '本链节点' }}</small></span></button></div>
    <template #footer><el-button class="w-full" @click="directoryVisible = false">{{ mode === 'multi' ? `完成选择（${selectedIds.length}）` : '返回图谱' }}</el-button></template>
  </MobileSheet>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { NODE_KINDS, RELATION_STATUS } from '@/utils/evidence'
import { projectMobileEvidenceGraph } from './mobileEvidenceGraph'

const props = defineProps({ graph: { type: Object, required: true }, rendered: { type: Object, required: true }, selection: Object, editable: Boolean, dirty: Boolean, saving: Boolean, saveError: String, canUndo: Boolean, canRedo: Boolean, flowId: String, nodeTypes: Object })
const visible = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['save', 'undo', 'redo', 'select-node', 'select-edge', 'open-selection', 'relation', 'move-nodes', 'remove-nodes', 'add-node'])
const mobileFlowId = `${props.flowId || 'evidence-editor'}-mobile`
const { setCenter, updateNodeInternals } = useVueFlow(mobileFlowId)
const mode = ref('browse'), filter = ref('all'), focusId = ref(''), depth = ref(1), sourceId = ref('')
const directoryVisible = ref(false), directoryQuery = ref(''), selectedIds = ref([]), offsets = ref({})
let dragStart = null, active = true
const filters = [{ value: 'all', label: '全部' }, { value: 'support', label: '支持' }, { value: 'refute', label: '反驳' }, { value: 'pending', label: '待核实' }]
const modes = [{ value: 'browse', label: '浏览', icon: 'mdi:cursor-default-outline' }, { value: 'relation', label: '关系', icon: 'mdi:vector-line' }, { value: 'move', label: '移动', icon: 'mdi:cursor-move' }, { value: 'multi', label: '多选', icon: 'mdi:checkbox-multiple-marked-outline' }]
const directions = [{ label: '←', delta: { x: -40, y: 0 } }, { label: '↑', delta: { x: 0, y: -40 } }, { label: '↓', delta: { x: 0, y: 40 } }, { label: '→', delta: { x: 40, y: 0 } }]
const projection = computed(() => projectMobileEvidenceGraph(props.rendered, { focusId: focusId.value, depth: depth.value, filter: filter.value }))
const focusedNode = computed(() => props.rendered.nodes.find(node => node.id === projection.value.focusId))
const selectedNode = computed(() => props.selection?.type === 'node' ? props.rendered.nodes.find(node => node.id === props.selection.id) : null)
const selectedRelation = computed(() => props.selection?.type === 'edge' ? props.rendered.edges.find(edge => edge.id === props.selection.id && edge.data?.edge) : null)
const moveIds = computed(() => mode.value === 'multi' ? selectedIds.value : selectedNode.value && !selectedNode.value.data.inherited ? [selectedNode.value.id] : [])
const canvasNodes = computed(() => projection.value.nodes.map(node => ({ ...node, position: { x: node.position.x + (offsets.value[node.id]?.x || 0), y: node.position.y + (offsets.value[node.id]?.y || 0) }, draggable: props.editable && !props.saving && mode.value === 'move' && !node.data.inherited, selected: mode.value === 'multi' ? selectedIds.value.includes(node.id) : sourceId.value === node.id || props.selection?.type === 'node' && props.selection.id === node.id })))
const canvasEdges = computed(() => projection.value.edges.map(edge => ({ ...edge, selected: props.selection?.type === 'edge' && props.selection.id === edge.id, interactionWidth: 32 })))
const directoryNodes = computed(() => props.rendered.nodes.filter(node => node.data.node.label.toLowerCase().includes(directoryQuery.value.trim().toLowerCase())))
const modeHint = computed(() => mode.value === 'relation' ? sourceId.value ? `已选起点：${props.rendered.nodes.find(node => node.id === sourceId.value)?.data.node.label || ''}，再点选终点` : '依次点选起点和终点，再填写关系与原始依据' : mode.value === 'move' ? '拖动本链节点，或用方向按钮微调；引用内部只读' : mode.value === 'multi' ? '在目录勾选节点，统一微调或移出本链' : '拖动画布、双指缩放；点选节点或关系查看依据')

/** """以可读缩放回到焦点，纵向浏览邻居，避免自动缩小为不可读的全图。""" */
async function fitLocal() {
  await nextTick()
  if (!visible.value || !active) return
  updateNodeInternals?.(canvasNodes.value.map(node => node.id))
  const node = canvasNodes.value.find(item => item.id === projection.value.focusId)
  if (visible.value && active && node) setCenter(node.position.x + 104, node.position.y + 60, { zoom: 0.75, duration: 0 })
}
/** """丢弃纯视图位移，撤销或重做由父编辑器恢复原始图定义。""" */
function resetOffsets() { offsets.value = {}; dragStart = null }
/**
 * 按模式解释节点点击，关系点选只产生独立表单草稿。
 * @param {string} id 完整节点路径。
 */
function onNodeTap(id) {
  const node = props.rendered.nodes.find(item => item.id === id)
  if (!node) return
  emit('select-node', id)
  if (!props.editable || props.saving) return
  if (mode.value === 'multi' && !node.data.inherited) selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter(value => value !== id) : [...selectedIds.value, id]
  if (mode.value !== 'relation') return
  if (!sourceId.value) sourceId.value = id
  else if (sourceId.value !== id) { const source = sourceId.value; sourceId.value = ''; emit('relation', { source, target: id }) }
}
/** """只选择真实关系，集合包含线不进入关系编辑。""" */
function onEdgeTap(edge) { if (edge.data?.edge && !edge.data.containment) emit('select-edge', edge) }
/** """目录既可改变焦点，也可在关系和多选模式中选择端点。""" */
function chooseDirectoryNode(node) {
  if (mode.value === 'multi' || mode.value === 'relation') onNodeTap(node.id)
  else { focusId.value = node.id; depth.value = 1; emit('select-node', node.id) }
  if (mode.value !== 'multi') directoryVisible.value = false
}
/** """记录拖动开始的投影坐标，不把自动局部排版当作持久化位置。""" */
function beginDrag({ node }) {
  if (!props.editable || props.saving || mode.value !== 'move' || node.data.inherited) return
  dragStart = { id: node.id, position: { ...node.position }, graph: props.graph }
  emit('select-node', node.id)
}
/** """将拖动位移交给父编辑器，拒绝撤权或切换图之后的迟到事件。""" */
function finishDrag({ node }) {
  const start = dragStart
  dragStart = null
  if (!start || start.id !== node.id || start.graph !== props.graph || mode.value !== 'move') return
  moveBy([node.id], { x: node.position.x - start.position.x, y: node.position.y - start.position.y })
}
/**
 * 用户明确移动时才写入原图位移，同时更新独立的局部显示偏移。
 * @param {Array<string>} ids 本链节点。
 * @param {{x:number,y:number}} delta 移动增量。
 */
function moveBy(ids, delta) {
  if (!active || !visible.value || !props.editable || props.saving || !['move', 'multi'].includes(mode.value) || !Number.isFinite(delta.x) || !Number.isFinite(delta.y)) return
  const own = new Set(props.graph.nodes.map(node => node.id)), accepted = ids.filter(id => own.has(id))
  if (!accepted.length || (!delta.x && !delta.y)) return
  for (const id of accepted) offsets.value[id] = { x: (offsets.value[id]?.x || 0) + delta.x, y: (offsets.value[id]?.y || 0) + delta.y }
  emit('move-nodes', { ids: accepted, delta })
}
watch([focusId, depth, filter], () => { resetOffsets(); fitLocal() })
watch(mode, () => { sourceId.value = ''; dragStart = null })
watch(() => props.editable, value => { if (!value) { mode.value = 'browse'; sourceId.value = ''; selectedIds.value = []; dragStart = null } })
watch(() => props.graph, (value, previous) => { if (value !== previous) resetOffsets() })
watch(() => props.graph.id, () => { visible.value = false; directoryVisible.value = false; focusId.value = ''; depth.value = 1; selectedIds.value = []; sourceId.value = ''; resetOffsets() })
watch(() => props.graph.nodes.map(node => node.id), ids => { selectedIds.value = selectedIds.value.filter(id => ids.includes(id)) })
watch(visible, value => { if (!value) { directoryVisible.value = false; sourceId.value = ''; dragStart = null } else active = true })
onDeactivated(() => { active = false; visible.value = false; directoryVisible.value = false; dragStart = null })
onBeforeUnmount(() => { active = false; directoryVisible.value = false; dragStart = null })
</script>

<style scoped>
.evidence-graph-heading{display:flex;align-items:center;gap:8px;width:100%;min-width:0}.evidence-graph-heading>div{flex:1;min-width:0}.evidence-graph-heading h2{font-size:16px;font-weight:700;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.evidence-graph-heading small{font-size:11px;color:#64748b}.evidence-graph-filter{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;padding:6px 0}.evidence-graph-filter button{min-height:44px;border-radius:9px;font-size:13px;color:#475569;background:#f1f5f9}.evidence-graph-filter button.active{background:#dbeafe;color:#1d4ed8;font-weight:600}.evidence-graph-context{display:flex;align-items:center;gap:6px;min-width:0}.evidence-graph-context>span{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:12px;color:#475569}.evidence-graph-context.compact{justify-content:space-between}.evidence-graph-context .el-button{margin:0}.evidence-graph-hint{font-size:11px;line-height:1.5;color:#64748b;margin:6px 0;overflow-wrap:anywhere}.evidence-graph-error{font-size:12px;color:#b91c1c;max-height:44px;overflow:auto}.evidence-graph-canvas{flex:1;min-height:140px;position:relative;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;overflow:hidden}.evidence-graph-empty{position:absolute;inset:25% 12%;text-align:center;line-height:2;color:#64748b;font-size:13px}.evidence-graph-hidden{position:absolute;top:6px;left:8px;right:8px;pointer-events:none;font-size:10px;color:#64748b;background:#ffffffd9;padding:4px;border-radius:5px;text-align:center}.evidence-graph-selection{display:flex;align-items:center;gap:6px;padding:10px 0 0;min-width:0}.evidence-graph-selection>div{flex:1;min-width:0;overflow-wrap:anywhere}.evidence-graph-selection strong{font-size:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.evidence-graph-selection p{font-size:11px;color:#64748b;margin-top:4px}.evidence-graph-selection .el-button{margin:0;padding:8px}.evidence-graph-move{padding-top:6px}.evidence-nudge{display:flex;gap:6px;margin-top:4px}.evidence-nudge .el-button{flex:1;margin:0;min-width:0;padding:6px;font-size:19px}.evidence-nudge .el-button:last-child{font-size:14px}.evidence-graph-history{display:flex;gap:8px;margin-bottom:6px}.evidence-graph-history .el-button{flex:1;margin:0;min-width:0}.evidence-graph-modes{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}.evidence-graph-modes button{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:52px;border-radius:10px;gap:3px;color:#64748b;font-size:11px}.evidence-graph-modes button svg{font-size:21px}.evidence-graph-modes button.active{color:#2563eb;background:#eff6ff}.evidence-graph-modes button:disabled{opacity:.4}.evidence-graph-directory{padding-top:10px;max-height:50dvh;overflow:auto}.evidence-graph-directory button{display:flex;gap:10px;align-items:center;width:100%;min-height:56px;padding:10px 4px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:14px}.evidence-graph-directory button>svg{font-size:22px;color:#2563eb;flex-shrink:0}.evidence-graph-directory button>span{min-width:0;overflow-wrap:anywhere}.evidence-graph-directory small{display:block;font-size:11px;color:#64748b;margin-top:4px}.evidence-graph-directory button:disabled{opacity:.5}
</style>
<style>
.mobile-evidence-workspace-overlay{top:var(--mobile-viewport-top,0px);height:var(--mobile-viewport-height,100dvh);bottom:auto}.mobile-evidence-workspace.el-drawer{height:var(--mobile-viewport-height,100dvh)!important;transition-property:transform}.mobile-evidence-workspace .el-drawer__header{padding:max(10px,env(safe-area-inset-top)) 12px 8px;margin:0;flex-shrink:0}.mobile-evidence-workspace .el-drawer__body{display:flex;flex-direction:column;padding:0 12px 8px;min-height:0;overflow:auto}.mobile-evidence-workspace .el-drawer__footer{flex-shrink:0;padding:8px 12px max(8px,env(safe-area-inset-bottom));border-top:1px solid #e2e8f0}.mobile-evidence-workspace .el-button{min-height:44px}.mobile-evidence-workspace .vue-flow__controls-button{width:44px;height:44px}.mobile-evidence-workspace .vue-flow__controls-button svg{width:20px;height:20px;max-width:20px;max-height:20px}.mobile-evidence-workspace .vue-flow__node{touch-action:none}.mobile-evidence-workspace .evidence-node{width:208px;min-height:100px;padding:10px 12px}.mobile-evidence-workspace .node-label{font-size:17px}.mobile-evidence-workspace .node-description{display:none}.mobile-evidence-workspace .node-footer{margin-top:8px}.mobile-evidence-workspace .vue-flow__handle{opacity:0;pointer-events:none}.mobile-evidence-workspace .vue-flow__edge-text{font-size:13px}
</style>
