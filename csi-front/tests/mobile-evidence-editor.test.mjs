import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript, babelParse } from 'vue/compiler-sfc'
import * as evidence from '../src/utils/evidence.js'
import * as mobileEvidence from '../src/components/evidence/mobile/mobileEvidence.js'
import * as mobileEvidenceGraph from '../src/components/evidence/mobile/mobileEvidenceGraph.js'
import { PERM } from '../src/utils/permissions.js'

/**
 * 执行真实组件脚本，以依赖替身隔离网络、弹层和生命周期。
 * @param {string} file 源组件路径。
 * @param {object} options 组件属性及可替换接口。
 * @returns {object} 真实状态、事件与作用域清理。
 */
function componentState(file, { props = {}, imports = {}, emit = () => {} } = {}) {
  const events = [], hooks = {}, timers = new Map(), scope = Vue.effectScope()
  let timer = 0
  const dependencies = {
    vue: { ...Vue, useModel: (props, name) => Vue.computed({ get: () => props[name], set: value => { props[name] = value } }), onMounted: callback => { hooks.mounted = callback }, onBeforeUnmount: callback => { hooks.unmount = callback }, onDeactivated: callback => { hooks.deactivate = callback }, onActivated: callback => { hooks.activate = callback } },
    'vue-router': { useRoute: () => ({ params: { id: 'parent' } }), useRouter: () => ({ push() {} }), onBeforeRouteLeave: callback => { hooks.leave = callback }, onBeforeRouteUpdate: callback => { hooks.update = callback } },
    'element-plus': { ElMessage: { success() {}, warning() {}, info() {} }, ElMessageBox: { confirm: async () => {} } },
    '@vue-flow/core': { useVueFlow: () => ({ fitView() {}, setCenter() {} }) },
    '@/utils/evidence': evidence,
    '@/components/evidence/mobile/mobileEvidence': mobileEvidence,
    './mobileEvidence': mobileEvidence,
    './mobileEvidenceGraph': mobileEvidenceGraph,
    '@/components/evidence/mobile/mobileEvidenceGraph': mobileEvidenceGraph,
    '@/utils/permissionKit': { hasPerm: code => typeof code === 'string' },
    '@/utils/permissions': { PERM },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: Vue.ref(true) }) },
    '@/stores/recentVisits': { rememberRecentVisit() {} },
    ...imports
  }
  const { descriptor } = parse(readFileSync(new URL(file, import.meta.url), 'utf8'))
  let code = compileScript(descriptor, { id: 'evidence-behavior' }).content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    dependencies[node.source.value] ||= { default: {} }
    code = code.slice(0, node.start) + node.specifiers.map(item => `const ${item.local.name} = imports[${JSON.stringify(node.source.value)}][${JSON.stringify(item.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', 'setTimeout', 'clearTimeout', 'window', code.replace('export default', 'return'))(dependencies, callback => { timers.set(++timer, callback); return timer }, id => timers.delete(id), { addEventListener() {}, removeEventListener() {} })
  const state = scope.run(() => component.setup(props, { expose() {}, emit: (name, ...args) => { events.push([name, ...args]); emit(name, ...args) } }))
  return { state, events, hooks, close: () => { hooks.unmount?.(); scope.stop() } }
}

/** """提供包含折叠集合成员及多项依据的真实图结构。""" */
function sampleGraph() {
  const graph = { ...evidence.makeEvidenceGraph('blank', '测试判断'), id: 'parent', revision: 7 }
  graph.nodes = [evidence.makeEvidenceNode('note', { id: 'judgment', label: '待验证判断' }), evidence.makeEvidenceNode('collection', { id: 'group', label: '指定材料', members: [{ entity_type: 'article', uuid: 'one' }, { entity_type: 'forum', uuid: 'two' }] })]
  graph.edges = [{ id: 'relation', source: 'group/@article:one', target: 'judgment', label: '支持', directed: true, status: 'pending', description: '', anchors: [{ entity: { entity_type: 'article', uuid: 'one' }, quote: '支持材料原文', locator: '第三段' }] }]
  return graph
}

/** """为移动组件构建响应式图与选择状态。""" */
function mobileProps(graph = sampleGraph()) {
  return Vue.reactive({ graph, rendered: evidence.projectEvidenceGraph(graph), selection: null, editable: true, resolving: new Set(), expanded: new Set(), resolveErrors: {} })
}

test('阅读模型优先判断，列出真实关系并排除集合包含线', () => {
  const graph = sampleGraph()
  const resolved = { group: { items: [{ entity_type: 'article', uuid: 'one', title: '材料一' }], total: 1 } }
  const projected = evidence.projectEvidenceGraph(graph, resolved, new Set(['group']))
  const before = JSON.stringify(graph)
  const reading = mobileEvidence.evidenceReadingSections(projected)
  assert.equal(reading.judgments[0].id, 'judgment')
  assert.equal(reading.materials.length, 2)
  assert.deepEqual(reading.relations.map(entry => entry.id), ['relation'])
  assert.equal(JSON.stringify(graph), before)
})

test('编辑折叠集合关系保持真实内部端点、原始版本与多条依据', () => {
  const graph = sampleGraph()
  const projected = evidence.projectEvidenceGraph(graph)
  assert.equal(projected.edges[0].source, 'group')
  const draft = mobileEvidence.createEvidenceRelationDraft(projected.edges[0], graph)
  draft.label = '反驳'
  draft.anchors.push({ entity: { entity_type: 'forum', uuid: 'two' }, quote: '反证', locator: '二楼' })
  assert.equal(graph.edges[0].label, '支持')
  assert.equal(graph.edges[0].anchors.length, 1)
  assert.equal(mobileEvidence.commitEvidenceRelation(graph, draft, projected.nodes, true), '')
  assert.equal(graph.edges[0].source, 'group/@article:one')
  assert.deepEqual(graph.edges[0].anchors.map(anchor => anchor.entity.uuid), ['one', 'two'])
  assert.equal(graph.edges[0].anchors[0].locator, '第三段')
})

test('继承关系与只读账号不能修改，新增悬空端点不能提交', () => {
  const graph = sampleGraph()
  const projected = evidence.projectEvidenceGraph(graph)
  assert.equal(mobileEvidence.createEvidenceRelationDraft({ data: { inherited: true, edge: graph.edges[0] } }, graph), null)
  const draft = mobileEvidence.createEvidenceRelationDraft(null, graph, 'judgment')
  draft.target = 'gone'
  assert.match(mobileEvidence.commitEvidenceRelation(graph, draft, projected.nodes, true), /端点/)
  draft.target = 'group'
  assert.match(mobileEvidence.commitEvidenceRelation(graph, draft, projected.nodes, false), /权限/)
  assert.equal(graph.edges.length, 1)
})

test('材料依据只接受具体版本、去重集合成员并保留不同实体类型', () => {
  const refs = mobileEvidence.evidenceMaterialRefs([
    { kind: 'versions', version_source: { source_id: 'all' } },
    { kind: 'entity', entity: { entity_type: 'article', uuid: 'same' } },
    { kind: 'collection', members: [{ entity_type: 'article', uuid: 'same' }, { entity_type: 'forum', uuid: 'same' }] }
  ])
  assert.deepEqual(refs, [{ entity_type: 'article', uuid: 'same' }, { entity_type: 'forum', uuid: 'same' }])
})

test('新增材料、取消及确认通过实际移动组件草稿流程，不提前改动图', () => {
  const props = mobileProps()
  const page = componentState('../src/components/evidence/mobile/MobileEvidenceEditor.vue', { props })
  try {
    const before = JSON.stringify(props.graph)
    page.state.startNode()
    page.state.chooseNodeKind('material')
    page.state.acceptMaterials([evidence.makeEvidenceNode('entity', { label: '材料', entity: { entity_type: 'article', uuid: 'new' } })])
    assert.equal(page.state.hasDraft.value, true)
    page.state.sheetVisible.value = false
    assert.equal(JSON.stringify(props.graph), before)
    assert.equal(page.events.length, 0)
    page.state.sheet.value = 'add'
    page.state.confirmNodes()
    assert.equal(page.events[0][0], 'add-nodes')
    assert.equal(page.events[0][1][0].entity.uuid, 'new')
    assert.equal(JSON.stringify(props.graph), before)
  } finally { page.close() }
})

test('实际关系表单通过具体版本多选补充依据，撤权后不提交', () => {
  const props = mobileProps()
  const page = componentState('../src/components/evidence/mobile/MobileEvidenceEditor.vue', { props })
  try {
    page.state.startRelation(props.rendered.edges[0])
    page.state.pickerPurpose.value = 'anchors'
    page.state.acceptMaterials([evidence.makeEvidenceNode('collection', { members: [{ entity_type: 'forum', uuid: 'three' }, { entity_type: 'article', uuid: 'four' }] })])
    assert.equal(page.state.relationDraft.value.anchors.length, 3)
    assert.equal(props.graph.edges[0].anchors.length, 1)
    page.state.confirmRelation()
    assert.equal(page.events[0][0], 'edit-edge')
    assert.equal(page.events[0][1].source, 'group/@article:one')
    props.editable = false
    page.state.confirmRelation()
    assert.equal(page.events.length, 1)
    assert.match(page.state.formError.value, /权限/)
  } finally { page.close() }
})

test('全屏图返回详情保留既有选择，节点编辑取消不修改集合成员', () => {
  const props = mobileProps()
  props.selection = { type: 'node', id: 'group' }
  const page = componentState('../src/components/evidence/mobile/MobileEvidenceEditor.vue', { props })
  try {
    page.state.graphVisible.value = true
    page.state.openGraphSelection()
    assert.equal(page.state.graphVisible.value, false)
    assert.equal(page.state.sheet.value, 'node')
    assert.equal(props.selection.id, 'group')
    page.state.editNode()
    page.state.nodeDraft.value.members.splice(0, 1)
    assert.equal(props.graph.nodes[1].members.length, 2)
    page.state.sheet.value = 'node'
    assert.equal(page.state.hasDraft.value, false)
  } finally { page.close() }
})

/** """装载父编辑器并使真实保存、撤销和权限逻辑可独立验证。""" */
async function editorState(api = {}, imports = {}) {
  const graph = sampleGraph()
  const page = componentState('../src/views/evidence/EvidenceEditor.vue', { imports: { '@/api/evidence': { evidenceApi: { get: async () => ({ data: structuredClone(graph) }), ...api } }, ...imports } })
  await page.state.load()
  return page
}

test('移动关系确认复用父编辑器的撤销/重做，含多依据和折叠端点', async () => {
  const page = await editorState()
  try {
    const draft = structuredClone(sampleGraph().edges[0])
    draft.label = '反驳'
    page.state.commitMobileEdge(draft)
    assert.equal(page.state.dirty.value, true)
    await page.state.undo()
    assert.equal(page.state.graph.value.edges[0].label, '支持')
    assert.equal(page.state.dirty.value, false)
    await page.state.redo()
    assert.equal(page.state.graph.value.edges[0].label, '反驳')
    assert.equal(page.state.graph.value.edges[0].source, 'group/@article:one')
    assert.equal(page.state.graph.value.edges[0].anchors[0].quote, '支持材料原文')
  } finally { page.close() }
})

test('保存传入原始修订号，冲突完整保留编辑与依据', async () => {
  const calls = []
  const page = await editorState({ save: async (id, payload) => { calls.push([id, payload]); throw new Error('修订冲突') } })
  try {
    page.state.graph.value.title = '本地编辑'
    assert.equal(await page.state.save(), false)
    assert.equal(calls[0][1].expected_revision, 7)
    assert.equal(calls[0][1].edges[0].source, 'group/@article:one')
    assert.equal(page.state.graph.value.title, '本地编辑')
    assert.equal(page.state.graph.value.revision, 7)
    assert.equal(page.state.dirty.value, true)
    assert.equal(page.state.saveError.value, '修订冲突')
  } finally { page.close() }
})

test('保存途中继续编辑不会被响应覆盖，重载后旧保存也不回写修订', async () => {
  let resolveSave
  const page = await editorState({ save: () => new Promise(resolve => { resolveSave = resolve }) })
  try {
    page.state.graph.value.title = '首次编辑'
    const saving = page.state.save()
    page.state.graph.value.title = '后续编辑'
    resolveSave({ data: { revision: 8 } })
    assert.equal(await saving, true)
    assert.equal(page.state.graph.value.title, '后续编辑')
    assert.equal(page.state.graph.value.revision, 8)
    assert.equal(page.state.dirty.value, true)
    const outdated = page.state.save()
    await page.state.load()
    resolveSave({ data: { revision: 9 } })
    assert.equal(await outdated, false)
    assert.equal(page.state.graph.value.revision, 7)
    assert.equal(page.state.dirty.value, false)
  } finally { page.close() }
})

test('手机移动写回增量、批量移出与撤销恢复完整关系依据', async () => {
  const confirmations = []
  const page = await editorState({}, { 'element-plus': { ElMessage: { success() {}, warning() {} }, ElMessageBox: { confirm: async message => { confirmations.push(message) } } } })
  try {
    const position = { ...page.state.graph.value.nodes[0].position }
    page.state.commitMobileMove({ ids: ['judgment', 'group/@article:one'], delta: { x: 40, y: -20 } })
    assert.deepEqual(page.state.graph.value.nodes[0].position, { x: position.x + 40, y: position.y - 20 })
    assert.equal(page.state.dirty.value, true)
    await page.state.undo()
    assert.deepEqual(page.state.graph.value.nodes[0].position, position)
    assert.equal(page.state.dirty.value, false)
    await page.state.redo()
    await page.state.removeMobileNodes(['group', 'group/@article:one'])
    assert.match(confirmations[0], /1 个节点.*1 条关系/)
    assert.equal(page.state.graph.value.nodes.length, 1)
    assert.equal(page.state.graph.value.edges.length, 0)
    await page.state.undo()
    assert.equal(page.state.graph.value.edges[0].source, 'group/@article:one')
    assert.equal(page.state.graph.value.edges[0].anchors[0].entity.uuid, 'one')
  } finally { page.close() }
})

test('撤权和离页阻止移动、迟到删除确认与保存响应，保留本地草稿', async () => {
  const permissions = Vue.reactive(new Set([PERM.operations.evidence.chain.read, PERM.operations.evidence.chain.update]))
  let finishDelete, finishSave
  const page = await editorState({ save: () => new Promise(resolve => { finishSave = resolve }) }, { '@/utils/permissionKit': { hasPerm: code => permissions.has(code) }, 'element-plus': { ElMessage: { success() {}, warning() {} }, ElMessageBox: { confirm: () => new Promise(resolve => { finishDelete = resolve }) } } })
  try {
    const deleting = page.state.removeMobileNodes(['group'])
    permissions.delete(PERM.operations.evidence.chain.update)
    finishDelete()
    await deleting
    assert.equal(page.state.graph.value.nodes.length, 2)
    const snapshot = page.state.serialized.value
    page.state.commitMobileMove({ ids: ['group'], delta: { x: 40, y: 0 } })
    assert.equal(page.state.serialized.value, snapshot)
    permissions.add(PERM.operations.evidence.chain.update)
    page.state.graph.value.title = '权限变化时保留的草稿'
    const saving = page.state.save()
    permissions.delete(PERM.operations.evidence.chain.update)
    finishSave({ data: { revision: 8 } })
    assert.equal(await saving, false)
    assert.equal(page.state.graph.value.revision, 7)
    assert.equal(page.state.dirty.value, true)
    assert.match(page.state.saveError.value, /权限已变更/)
    permissions.add(PERM.operations.evidence.chain.update)
    const leaving = page.state.removeMobileNodes(['group'])
    page.hooks.deactivate()
    finishDelete()
    await leaving
    assert.equal(page.state.graph.value.nodes.length, 2)
  } finally { page.close() }
})

test('真实图组件两次点选只创建端点草稿，拖动仅发出增量并拒绝引用内节点', async () => {
  const props = mobileProps()
  props.modelValue = true
  const page = componentState('../src/components/evidence/mobile/MobileEvidenceGraph.vue', { props, emit: (name, id) => { if (name === 'select-node') props.selection = { type: 'node', id } } })
  try {
    const snapshot = JSON.stringify(props.graph)
    page.state.mode.value = 'relation'
    await Vue.nextTick()
    page.state.onNodeTap('judgment')
    page.state.onNodeTap('group')
    assert.deepEqual(page.events.find(event => event[0] === 'relation'), ['relation', { source: 'judgment', target: 'group' }])
    assert.equal(JSON.stringify(props.graph), snapshot)
    page.state.mode.value = 'move'
    await Vue.nextTick()
    const node = page.state.canvasNodes.value.find(node => node.id === 'group')
    page.state.beginDrag({ node })
    page.state.finishDrag({ node: { ...node, position: { x: node.position.x + 35, y: node.position.y - 10 } } })
    assert.deepEqual(page.events.find(event => event[0] === 'move-nodes'), ['move-nodes', { ids: ['group'], delta: { x: 35, y: -10 } }])
    page.state.moveBy(['group/@article:one'], { x: 20, y: 0 })
    assert.equal(page.events.filter(event => event[0] === 'move-nodes').length, 1)
    props.editable = false
    page.state.moveBy(['group'], { x: 20, y: 0 })
    assert.equal(page.events.filter(event => event[0] === 'move-nodes').length, 1)
    page.state.directoryVisible.value = true
    page.hooks.deactivate()
    assert.equal(props.modelValue, false)
    assert.equal(page.state.directoryVisible.value, false)
  } finally { page.close() }
})

test('图谱关系进入既有依据表单，关闭回到图谱，离页关闭全部弹层', async () => {
  const props = mobileProps(), page = componentState('../src/components/evidence/mobile/MobileEvidenceEditor.vue', { props })
  try {
    page.state.graphVisible.value = true
    page.state.startGraphRelation({ source: 'judgment', target: 'group' })
    assert.equal(page.state.graphVisible.value, false)
    assert.equal(page.state.sheet.value, 'relation')
    assert.equal(page.state.relationStep.value, 1)
    assert.equal(page.state.relationDraft.value.target, 'group')
    assert.equal(props.graph.edges.length, 1)
    await Vue.nextTick()
    page.state.sheet.value = ''
    await Vue.nextTick()
    assert.equal(page.state.graphVisible.value, true)
    page.state.entityPicker.value = true
    page.state.chainPicker.value = true
    page.hooks.deactivate()
    await Vue.nextTick()
    assert.equal(page.state.graphVisible.value, false)
    assert.equal(page.state.entityPicker.value, false)
    assert.equal(page.state.chainPicker.value, false)
  } finally { page.close() }
})
