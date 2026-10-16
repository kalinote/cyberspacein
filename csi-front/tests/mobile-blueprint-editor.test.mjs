import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { useVueFlow as useRealVueFlow } from '@vue-flow/core'
import { parse, compileScript, compileTemplate, babelParse } from 'vue/compiler-sfc'
import * as mobileGraph from '../src/utils/action/mobileGraph.js'
import * as boundaryBinding from '../src/utils/action/boundaryBinding.js'
import * as handles from '../src/utils/action/handleConnection.js'
import { PERM } from '../src/utils/permissions.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'
import { INPUT_TYPE_DEFAULTS } from '../src/utils/action/constants.js'

const nodeSource = readFileSync(new URL('../src/utils/action/node.js', import.meta.url), 'utf8').replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '')
const nodeUtils = new Function('INPUT_TYPE_DEFAULTS', `${nodeSource}\nreturn { getDefaultData, normalizeDefaultValue }`)(INPUT_TYPE_DEFAULTS)
const configs = [
  { id: 'source-definition', name: '读取', type: 'reader', enabled: true, is_latest: true, version: '1', handles: [{ id: 'out', port_id: 'stable-out', type: 'source', interface_type_id: 'text', data_type: 'value' }], inputs: [{ id: 'value', name: 'value', type: 'input', default: '原值' }] },
  { id: 'target-definition', name: '接收', type: 'writer', enabled: true, is_latest: true, version: '2', handles: [{ id: 'in', port_id: 'stable-in', type: 'target', interface_type_id: 'text', data_type: 'value' }], inputs: [] },
]
const nodes = configs.map((config, i) => ({ id: i ? 'b' : 'a', type: config.id, position: { x: i * 400, y: 60 }, data: { config, value: '原值' } }))
const edge = { id: 'a-b', source: 'a', sourceHandle: 'out', target: 'b', targetHandle: 'in' }
const blueprint = { id: 'existing', name: '测试蓝图', version: '1.2', target: '检查', resource: { reserved: true }, is_template: true, template: { params: [{ name: 'query', type: 'string' }], bindings: { a: { value: 'query' } } }, graph: { nodes: nodes.map(node => ({ id: node.id, type: node.data.config.type, position: node.position, data: { definition_id: node.type, form_data: { value: '原值' } } })), edges: [{ ...edge, source_port_id: 'stable-out', target_port_id: 'stable-in' }], viewport: { x: -1200, y: 600, zoom: .75 } } }

/** """等待组件异步步骤和响应式回填。""" */
async function settle() { await Vue.nextTick(); await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
/** """为保存、加载和确认构造可控异步结果。""" */
function deferred() { let resolve, reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail }); return { promise, resolve, reject } }

/**
 * 执行真实主控 setup，模拟 Vue Flow 的业务数据操作与接口。
 * @param {object} t 测试上下文。
 * @param {object} options 权限、路由和延迟接口。
 * @returns {object} 真实状态、生命周期、接口记录与路由。
 */
function harness(t, options = {}) {
  const filename = 'src/views/action/NewActionBlueprint.vue'
  const { descriptor } = parse(readFileSync(new URL(`../${filename}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: filename })
  const template = compileTemplate({ source: descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  const route = Vue.reactive({ params: { blueprintId: options.create ? undefined : 'existing' } })
  const auth = Vue.reactive({ permissions: options.permissions || ['*'] })
  const isMobile = Vue.ref(options.mobile !== false)
  const hooks = { mounted: [], beforeUnmount: [], activated: [], deactivated: [], leave: [], update: [] }
  const calls = { saves: [], creates: [], load: [], nodes: 0, navigate: [], fit: [], viewport: [], errors: [], issues: 0, desktopHydration: [] }
  const windowEvents = new Map()
  let state
  const imports = {
    vue: { ...Vue, provide() {}, onMounted: fn => hooks.mounted.push(fn), onBeforeUnmount: fn => hooks.beforeUnmount.push(fn), onActivated: fn => hooks.activated.push(fn), onDeactivated: fn => hooks.deactivated.push(fn) },
    'vue-router': { useRoute: () => route, useRouter: () => ({ push: path => calls.navigate.push(path) }), onBeforeRouteLeave: fn => hooks.leave.push(fn), onBeforeRouteUpdate: fn => hooks.update.push(fn) },
    'element-plus': { ElMessage: { error: message => calls.errors.push(message), success() {}, warning() {} }, ElNotification() {}, ElMessageBox: { confirm: options.confirm || (async () => {}), close() {} } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile }) },
    '@/utils/action': { ...nodeUtils, getNodeColor: () => '#333' },
    '@/utils/action/boundaryBinding': boundaryBinding, '@/utils/action/mobileGraph': mobileGraph, '@/utils/action/handleConnection': handles,
    '@/utils/action/useSidebarResize': { useSidebarResize: () => ({ sidebarWidth: Vue.ref(400), isResizing: Vue.ref(false), startResize() {} }) },
    '@/components/action/nodes/nativeNodeRendererRegistry': { resolveNativeNodeRenderer: () => ({}) },
    '@/utils/permissions': { PERM }, '@/utils/permissionKit': { hasPerm: code => hasAllForPermissions(auth.permissions, [code]), hasAll: codes => hasAllForPermissions(auth.permissions, codes) },
    '@/api/action': { actionApi: {
      getNodes: () => { calls.nodes++; return options.getNodes?.() || Promise.resolve({ code: 0, data: structuredClone(configs) }) },
      getBlueprint: id => { calls.load.push(id); return options.load?.(id) || Promise.resolve({ code: 0, data: structuredClone(blueprint) }) },
      updateActionBlueprint: (id, payload) => { calls.saves.push({ id, payload }); return options.save?.(id, payload) || Promise.resolve({ code: 0, data: { id } }) },
      createActionBlueprint: payload => { calls.creates.push(payload); return options.createApi?.(payload) || Promise.resolve({ code: 0, data: { id: 'created-id' } }) },
    } },
    '@vue-flow/core': { VueFlow: {}, useVueFlow: () => ({
      addEdges: edges => { state.elements.value = [...state.elements.value, ...(Array.isArray(edges) ? edges : [edges])] },
      addNodes: node => { state.elements.value = [...state.elements.value, node] },
      onConnect() {}, screenToFlowCoordinate: point => point, onNodesInitialized: () => ({ off() {} }), updateNodeInternals() {}, onNodeDrag() {}, onNodeDragStop() {},
      updateNode: (id, patch) => { const node = state.elements.value.find(item => item.id === id); if (node) Object.assign(node, patch) },
      updateNodeData: (id, patch) => { const node = state.elements.value.find(item => item.id === id); if (node) Object.assign(node.data, patch) },
      getNodes: Vue.computed(() => state?.elements.value.filter(item => !item.source) || []), getEdges: Vue.computed(() => state?.elements.value.filter(item => item.source) || []), isValidConnection: Vue.ref(() => true),
      getViewport: () => ({ x: 99, y: 88, zoom: 1.4 }), setViewport: value => calls.viewport.push(value), fitView: value => calls.fit.push(value),
      setElements: value => calls.desktopHydration.push(JSON.parse(JSON.stringify(value))),
    }) },
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    imports[node.source.value] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', {}]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(node.source.value)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const window = { addEventListener: (event, fn) => windowEvents.set(event, fn), removeEventListener: event => windowEvents.delete(event) }
  const component = new Function('imports', 'window', 'console', code.replace('export default', 'return'))(imports, window, { error() {} })
  const scope = Vue.effectScope()
  state = scope.run(() => component.setup({}, { expose() {} }))
  state.mobileEditorRef.value = { closeSheets() {}, showFields() {}, showIssues: () => calls.issues++ }
  t.after(() => { hooks.beforeUnmount.forEach(fn => fn()); scope.stop() })
  return { state, calls, hooks, route, auth, isMobile, windowEvents }
}

test('端口向导同时检查传输类型、业务接口、输入占用与多输入契约', () => {
  assert.equal(mobileGraph.blueprintConnectionIssue(nodes, [], edge), '')
  const reference = structuredClone(nodes); reference[0].data.config.handles[0].data_type = 'reference'; reference[0].data.config.handles[0].compatible_interface_type_ids = ['*']
  assert.match(mobileGraph.blueprintConnectionIssue(reference, [], edge), /传输类型/)
  const incompatible = structuredClone(nodes); incompatible[1].data.config.handles[0].interface_type_id = 'number'
  assert.match(mobileGraph.blueprintConnectionIssue(incompatible, [], edge), /业务接口/)
  assert.match(mobileGraph.blueprintConnectionIssue(nodes, [{ ...edge, id: 'old', source: 'other' }], edge), /已有上游/)
  const multiple = structuredClone(nodes); multiple[1].data.config.handles[0].allow_multiple_inputs = true
  assert.equal(mobileGraph.blueprintConnectionIssue(multiple, [{ ...edge, id: 'old', source: 'other' }], edge), '')
  assert.match(mobileGraph.blueprintConnectionIssue(nodes, [edge], { ...edge, id: undefined }), /已经连接/)
  const bound = structuredClone(nodes); bound[0].data.boundaryBinding = { bound_node_id: 'b' }
  assert.match(mobileGraph.blueprintConnectionIssue(bound, [], edge), /IO/)
})

test('草稿历史排除测量与派生边，撤销重做保留分支和字段类型', () => {
  const snapshot = mobileGraph.captureBlueprintDraft({ elements: [...nodes, edge, { id: 'derived', source: 'a', target: 'b', data: { relationKind: 'boundary-binding' } }], form: { target: '目标' }, params: [], bindings: {}, resource: {} })
  assert.equal(snapshot.elements.length, 3)
  const history = mobileGraph.createBlueprintHistory(3); history.reset(snapshot)
  const changed = structuredClone(snapshot); changed.elements[0].data.value = false; history.commit(changed)
  assert.equal(history.undo().elements[0].data.value, '原值')
  assert.equal(history.redo().elements[0].data.value, false)
  history.undo(); history.commit({ ...snapshot, form: { target: '新分支' } }); assert.equal(history.canRedo, false)
})

test('手机保存沿用 PC viewport、真实节点类型、稳定端口与模板资源载荷', async t => {
  const { state, calls } = harness(t)
  await state.initializeEditor(); await settle()
  assert.equal(state.historyReady.value, true)
  assert.equal(state.draftDirty.value, false)
  assert.deepEqual(calls.viewport, [])
  state.updateMobileField('a', { inputId: 'value', value: '手机值' }); await settle()
  assert.equal(state.draftDirty.value, true)
  assert.equal(await state.handleSaveAction(), true)
  assert.equal(calls.saves.length, 1)
  const payload = calls.saves[0].payload
  assert.deepEqual(payload.graph.viewport, blueprint.graph.viewport)
  assert.equal(payload.graph.nodes[0].type, 'reader')
  assert.equal(payload.graph.nodes[0].data.form_data.value, '手机值')
  assert.equal(payload.graph.edges[0].source_port_id, 'stable-out')
  assert.equal(payload.graph.edges[0].target_port_id, 'stable-in')
  assert.deepEqual(payload.template.bindings, blueprint.template.bindings)
  assert.deepEqual(payload.resource, blueprint.resource)
  assert.equal(state.draftDirty.value, false)
  assert.deepEqual(calls.navigate, [])
})

test('手机保存失败保留草稿且可重试，保存中变化不会被误标为已保存', async t => {
  const pending = deferred(); let attempt = 0
  const { state, calls } = harness(t, { save: () => ++attempt === 1 ? Promise.reject(new Error('网络错误')) : pending.promise })
  await state.initializeEditor(); state.actionForm.value.title = '第一次修改'
  assert.equal(await state.handleSaveAction(), false); assert.equal(state.draftDirty.value, true)
  const saving = state.handleSaveAction(); assert.equal(await state.handleSaveAction(), false)
  state.actionForm.value.title = '保存期间的新修改'; pending.resolve({ code: 0, data: { id: 'existing' } }); await saving
  assert.equal(calls.saves.length, 2); assert.equal(calls.saves[1].payload.name, '第一次修改'); assert.equal(state.draftDirty.value, true)
})

test('新增蓝图保存后使用返回 ID 更新，连续添加不重复节点 ID', async t => {
  const { state, calls } = harness(t, { create: true })
  await state.initializeEditor(); state.actionForm.value.title = '新蓝图'; state.actionForm.value.target = '新目标'
  await state.addMobileNode('source-definition'); await state.addMobileNode('source-definition')
  assert.equal(new Set(state.elements.value.map(node => node.id)).size, 2)
  assert.equal(await state.handleSaveAction(), true); assert.equal(calls.creates.length, 1)
  state.actionForm.value.title = '已创建后的编辑'; await state.handleSaveAction()
  assert.equal(calls.creates.length, 1); assert.equal(calls.saves[0].id, 'created-id')
})

test('撤销重做包含节点参数、连接和明确应用的坐标，取消移动不变更草稿', async t => {
  const { state } = harness(t); await state.initializeEditor()
  state.updateMobileField('a', { inputId: 'value', value: '新值' }); await settle(); state.recordHistory()
  await state.restoreHistory('undo'); assert.equal(state.elements.value[0].data.value, '原值')
  await state.restoreHistory('redo'); assert.equal(state.elements.value[0].data.value, '新值')
  const signature = state.draftSignature.value
  state.setMobileMode('move'); state.recordMobileDrag({ node: { id: 'a', position: { x: 999, y: 0 } } }); state.cancelMobileLayout(); await settle()
  assert.equal(state.draftSignature.value, signature)
  await state.moveMobileGroup({ nodeIds: ['a', 'b'], x: 40, y: -20 }); assert.equal(state.elements.value[1].position.x, 440)
  await state.restoreHistory('undo'); assert.equal(state.elements.value[1].position.x, 400)
})

test('节点删除清理关联边、IO 绑定和模板引用，撤销可完整恢复', async t => {
  const { state } = harness(t); await state.initializeEditor()
  state.elements.value.push({ id: 'io', type: 'io', position: { x: 0, y: 0 }, data: { config: { id: 'io', type: 'io', node_kind: 'backend_native', builtin_key: 'blueprint.input', inputs: [], handles: [] }, interfacePortId: 'stable-io', boundaryBinding: { bound_node_id: 'a', port_mappings: [] } } })
  state.recordHistory(); await state.removeMobileElements({ nodeIds: ['a'] }); await settle()
  assert.equal(state.elements.value.some(node => node.id === 'a' || node.id === 'a-b'), false)
  assert.equal(state.elements.value.find(node => node.id === 'io').data.boundaryBinding, null)
  assert.equal(state.templateBindings.value.a, undefined)
  await state.restoreHistory('undo'); assert.equal(state.elements.value.some(node => node.id === 'a-b'), true); assert.equal(state.templateBindings.value.a.value, 'query')
})

test('失活、权限撤销和同路由换 ID 拒绝迟到响应，确认期间撤权不删除', async t => {
  const old = deferred(), confirm = deferred()
  const h = harness(t, { load: id => id === 'existing' ? old.promise : Promise.resolve({ code: 0, data: { ...structuredClone(blueprint), name: '新蓝图' } }), confirm: () => confirm.promise })
  const loading = h.state.initializeEditor(); await settle(); h.route.params.blueprintId = 'new'; await settle(); old.resolve({ code: 0, data: structuredClone(blueprint) }); await loading; await settle()
  assert.equal(h.state.actionForm.value.title, '新蓝图')
  const removal = h.state.removeMobileElements({ nodeIds: ['a'] }); h.auth.permissions = [PERM.operations.action.blueprint.read, PERM.operations.action.node.read]; confirm.resolve(); await removal
  assert.equal(h.state.elements.value.some(node => node.id === 'a'), true)
  assert.equal(await h.state.handleSaveAction(), false)
  const pending = deferred(); const inactive = harness(t, { load: () => pending.promise }); const task = inactive.state.initializeEditor(); await settle(); inactive.hooks.deactivated.forEach(fn => fn()); pending.resolve({ code: 0, data: structuredClone(blueprint) }); await task
  assert.equal(inactive.state.elements.value.length, 0)
})

test('离页保护拒绝取消、保存中跳转和确认期间新修改；表单缺失不提交', async t => {
  const confirm = deferred(); const { state, hooks, calls } = harness(t, { confirm: () => confirm.promise })
  await state.initializeEditor(); state.actionForm.value.title = ''
  assert.equal(await state.handleSaveAction(), false); assert.equal(calls.saves.length, 0); assert.equal(calls.issues, 1)
  const leave = hooks.leave[0](); state.actionForm.value.title = '确认期间继续编辑'; confirm.resolve(); assert.equal(await leave, false)
  state.saving.value = true; assert.equal(await hooks.leave[0](), false)
})

test('桌面继续以原表单异步验证，重复点击只发送一次保存且导航列表', async t => {
  const validation = deferred(); const { state, calls } = harness(t, { mobile: false }); await state.initializeEditor()
  state.actionFormRef.value = { validate: () => validation.promise }; state.actionForm.value.title = '桌面修改'
  const saving = state.handleSaveAction(); assert.equal(await state.handleSaveAction(), false); validation.resolve(); assert.equal(await saving, true)
  assert.equal(calls.saves.length, 1); assert.deepEqual(calls.saves[0].payload.graph.viewport, { x: 99, y: 88, zoom: 1.4 }); assert.deepEqual(calls.navigate, ['/action/blueprints'])
})

test('手机投影压缩稀疏坐标并保留分支、环路、端点和原参数', () => {
  const original = structuredClone([...nodes, { ...nodes[1], id: 'c', position: { x: 10000, y: -5000 } }, edge, { ...edge, id: 'a-c', target: 'c' }, { ...edge, id: 'b-a', source: 'b', target: 'a' }])
  const before = JSON.stringify(original)
  const projected = mobileGraph.projectMobileBlueprint(original)
  assert.deepEqual(projected.filter(item => item.source), original.filter(item => item.source))
  assert.equal(projected.filter(item => !item.source).every(node => Math.abs(node.position.x) < 500 && Math.abs(node.position.y) < 500), true)
  projected[0].data.value = '显示数据变化'; projected[0].position.x = 99
  assert.equal(JSON.stringify(original), before)
})

test('手机浏览不会修改草稿，拖动增量只有应用后进入原布局，撤销重做同步投影', async t => {
  const { state, calls } = harness(t); await state.initializeEditor()
  const initial = state.draftSignature.value
  const display = { ...state.mobileCanvasNodes.value.find(node => node.id === 'b').position }
  await state.fitMobileGraph(); assert.deepEqual(calls.fit.at(-1).nodes, ['a']); assert.equal(calls.fit.at(-1).minZoom, .8)
  await state.fitMobileGraph(true); assert.equal(calls.fit.at(-1).nodes, undefined)
  assert.equal(state.draftSignature.value, initial)
  state.setMobileMode('move'); state.recordMobileDrag({ node: { id: 'b', position: { x: display.x + 40, y: display.y - 20 } } })
  assert.equal(state.draftSignature.value, initial)
  assert.equal(await state.handleSaveAction(), false)
  await state.applyMobileLayout(); assert.deepEqual(state.elements.value.find(node => node.id === 'b').position, { x: 440, y: 40 })
  await state.restoreHistory('undo'); assert.deepEqual(state.mobileCanvasNodes.value.find(node => node.id === 'b').position, display)
  await state.restoreHistory('redo'); assert.deepEqual(state.mobileCanvasNodes.value.find(node => node.id === 'b').position, { x: display.x + 40, y: display.y - 20 })
  assert.equal(await state.handleSaveAction(), true)
  assert.deepEqual(calls.saves[0].payload.graph.nodes.find(node => node.id === 'b').position, { x: 440, y: 40 })
  assert.deepEqual(calls.saves[0].payload.graph.viewport, blueprint.graph.viewport)
})

test('未应用面板草稿阻止保存与无提示离页，确认期间继续输入使离页确认失效', async t => {
  const confirmation = deferred(); const { state, calls, hooks, windowEvents } = harness(t, { confirm: () => confirmation.promise })
  await state.initializeEditor()
  const key = Symbol('字段草稿'); state.blueprintLocalDrafts.set(key, '初始修改')
  assert.equal(state.draftDirty.value, false); assert.equal(await state.handleSaveAction(), false); assert.equal(calls.saves.length, 0)
  const event = { prevented: false, preventDefault() { this.prevented = true } }
  state.handleDraftBeforeUnload(event); assert.equal(event.prevented, true)
  const leaving = hooks.leave[0](); state.blueprintLocalDrafts.set(key, '继续输入'); confirmation.resolve(); assert.equal(await leaving, false)
  state.blueprintLocalDrafts.delete(key); assert.equal(await hooks.leave[0](), true)
})

test('跨断点先水合当前完整图，拒绝卸载和重挂画布的旧模型回写', async t => {
  const { state, isMobile, calls } = harness(t); await state.initializeEditor()
  const original = state.draftSignature.value
  isMobile.value = false
  state.acceptDesktopElements([nodes[0]])
  assert.equal(state.draftSignature.value, original)
  await settle()
  assert.equal(calls.desktopHydration.length, 2)
  assert.equal(calls.desktopHydration.every(frame => frame.some(item => item.id === edge.id)), true)
  assert.equal(state.isValidConnection.value(edge), true)
  assert.equal(state.isValidConnection.value({ ...edge, id: undefined }), false)
  isMobile.value = true
  state.acceptDesktopElements([nodes[0]])
  await settle()
  assert.equal(state.draftSignature.value, original)
  assert.equal(state.draftDirty.value, false)
})

test('真实 Vue Flow store 重复水合已有分支不会按新连接规则丢边', async t => {
  const { state } = harness(t); await state.initializeEditor()
  state.elements.value.push({ ...structuredClone(nodes[1]), id: 'c' }, { ...edge, id: 'a-c', target: 'c' })
  let flow
  const renderer = Vue.createRenderer({ createComment: text => ({ text }), insert() {}, remove() {}, parentNode() {}, nextSibling() {} })
  const app = renderer.createApp({ setup() { flow = useRealVueFlow('blueprint-hydration-regression'); return () => null } })
  app.mount({})
  const errors = []
  flow.onError(error => errors.push(error))
  flow.isValidConnection.value = state.isValidConnection.value
  t.after(() => app.unmount())
  for (let turn = 0; turn < 3; turn++) {
    flow.setElements(state.elements.value)
    assert.deepEqual(flow.getEdges.value.map(item => item.id).sort(), ['a-b', 'a-c'])
    state.elements.value = [...flow.getNodes.value, ...flow.getEdges.value]
    state.updateMobileField('a', { inputId: 'value', value: `第 ${turn + 1} 次手机修改` })
    await settle()
  }
  assert.deepEqual(errors, [])
  assert.equal(flow.getNodes.value.find(node => node.id === 'a').data.value, '第 3 次手机修改')
})
