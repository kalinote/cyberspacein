import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript, compileTemplate, babelParse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'
import { INPUT_TYPE_DEFAULTS } from '../src/utils/action/constants.js'
import * as boundaryBinding from '../src/utils/action/boundaryBinding.js'

const source = readFileSync(new URL('../src/components/action/BlueprintFlowDialog.vue', import.meta.url), 'utf8')
const nodeSource = readFileSync(new URL('../src/utils/action/node.js', import.meta.url), 'utf8').replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '')
const nodeUtils = new Function('INPUT_TYPE_DEFAULTS', `${nodeSource}\nreturn { getDefaultData, normalizeDefaultValue }`)(INPUT_TYPE_DEFAULTS)
const blueprint = {
  id: 'blueprint-a', name: '测试只读蓝图', is_template: false,
  graph: {
    viewport: { x: -1300, y: 650, zoom: 0.85 },
    nodes: [
      { id: 'a', type: 'crawler', position: { x: 1500, y: 300 }, data: { definition_id: 'definition-a', version: '1', form_data: { count: 3, nested: { allowed: false } } } },
      { id: 'b', type: 'construct', position: { x: 1850, y: 500 }, data: { definition_id: 'definition-b', form_data: {} } },
    ],
    edges: [{ id: 'edge-a-b', source: 'a', target: 'b', source_port_id: 'out-new', target_port_id: 'in-new' }],
  },
}

/** """等待响应式观察与异步接口任务完成。""" */
async function settle() {
  await Vue.nextTick()
  await new Promise(resolve => setImmediate(resolve))
}
/** """为权限变化和关闭竞态提供延迟响应。""" */
function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

/**
 * 运行预览组件真实 setup，替换网络和 Vue Flow 视口以检查只读行为。
 * @param {object} t 测试上下文。
 * @param {object} options 手机断点、权限与接口响应。
 * @returns {object} 页面状态、调用记录和生命周期控制。
 */
function harness(t, options = {}) {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'blueprint-flow' })
  const template = compileTemplate({ source: descriptor.template.content, filename: 'BlueprintFlowDialog.vue', id: 'blueprint-flow', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  const props = Vue.reactive({ modelValue: false, blueprintId: 'blueprint-a' })
  const auth = Vue.reactive({ permissions: options.permissions || ['*'] })
  const isMobile = Vue.ref(options.mobile !== false)
  const hooks = { activated: [], deactivated: [], beforeUnmount: [] }
  const calls = { blueprints: [], nodes: 0, fit: [], viewport: [] }
  const imports = {
    vue: { ...Vue, provide() {}, onActivated: fn => hooks.activated.push(fn), onDeactivated: fn => hooks.deactivated.push(fn), onBeforeUnmount: fn => hooks.beforeUnmount.push(fn) },
    '@vue-flow/core': { VueFlow: {}, Handle: {}, Position: { Right: 'right', Left: 'left' }, useVueFlow: () => ({ setViewport: value => calls.viewport.push(value), fitView: value => calls.fit.push(value) }) },
    '@/api/action': { actionApi: { getNodes: () => { calls.nodes++; return options.nodes?.() || Promise.resolve({ code: 0, data: [{ id: 'definition-a', name: '读取材料', type: 'crawler', inputs: [], handles: [] }, { id: 'definition-b', name: '整理结果', type: 'construct', inputs: [], handles: [] }] }) }, getBlueprint: id => { calls.blueprints.push(id); return options.blueprint?.(id) || Promise.resolve({ code: 0, data: structuredClone(blueprint) }) } } },
    '@/utils/action': { ...nodeUtils, formatDateTime: value => value },
    '@/utils/action/boundaryBinding': boundaryBinding,
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile }) },
    '@/utils/permissions': { PERM }, '@/utils/permissionKit': { hasPerm: code => hasAllForPermissions(auth.permissions, [code]) },
    'element-plus': { ElMessage: { error() {} } },
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    imports[node.source.value] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', {}]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(node.source.value)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', 'console', code.replace('export default', 'return'))(imports, { error() {} })
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup(props, { expose() {}, emit: (event, value) => { if (event === 'update:modelValue') props.modelValue = value } }))
  t.after(() => { hooks.beforeUnmount.forEach(fn => fn()); scope.stop() })
  return { state, props, auth, isMobile, calls, hooks }
}

test('未打开只读流程图时不加载节点定义或蓝图，蓝图仅读权限可呈现快照连线', async t => {
  const { state, props, calls } = harness(t, { permissions: [PERM.operations.action.blueprint.read] })
  await settle()
  assert.equal(calls.nodes, 0)
  assert.deepEqual(calls.blueprints, [])
  props.modelValue = true
  await settle()
  assert.equal(calls.nodes, 0)
  assert.deepEqual(calls.blueprints, ['blueprint-a'])
  assert.equal(state.elements.value.length, 3)
  assert.equal(state.elements.value[0].type, 'blueprintPreview')
  assert.deepEqual(state.elements.value[0].data.previewHandles, [{ id: 'out-new', type: 'source', offset: 50 }])
  assert.equal(state.elements.value[2].sourceHandle, 'out-new')
  assert.equal(state.elements.value[2].targetHandle, 'in-new')
  state.selectedPreviewNodeId.value = 'a'
  assert.equal(state.selectedPreviewNode.value.data.form_data.count, 3)
  assert.equal(state.selectedNodeEdges.value.length, 1)
  assert.deepEqual(state.blueprintData.value.graph, blueprint.graph)
})

test('手机不恢复 PC 平移，桌面继续使用保存的视口', async t => {
  const mobile = harness(t)
  mobile.props.modelValue = true
  await settle()
  assert.equal(mobile.calls.nodes, 1)
  assert.equal(mobile.calls.viewport.length, 0)
  assert.ok(mobile.calls.fit.length > 0)
  assert.equal(mobile.calls.fit.at(-1).minZoom, 0.05)
  assert.equal(mobile.state.nodeDisplayName('a'), '读取材料')
  const desktop = harness(t, { mobile: false })
  desktop.props.modelValue = true
  await settle()
  assert.deepEqual(desktop.calls.viewport.at(-1), blueprint.graph.viewport)
  assert.equal(desktop.calls.fit.length, 0)
  assert.equal(desktop.state.elements.value[0].type, 'definition-a')
})

test('节点读取失败仍能查看已授权蓝图快照，不伪装成空流程', async t => {
  const { state, props } = harness(t, { nodes: async () => { throw new Error('节点读取失败') } })
  props.modelValue = true
  await settle()
  assert.equal(state.error.value, null)
  assert.match(state.nodeConfigError.value, /蓝图内保存/)
  assert.equal(state.elements.value.length, 3)
})

test('关闭预览和失活阻止迟到蓝图回填，也不会移动其它图的视口', async t => {
  const response = deferred()
  const { state, props, calls, hooks } = harness(t, { blueprint: () => response.promise })
  props.modelValue = true
  await settle()
  state.detailVisible.value = true
  hooks.deactivated.forEach(fn => fn())
  response.resolve({ code: 0, data: structuredClone(blueprint) })
  await settle()
  assert.equal(state.blueprintData.value, null)
  assert.equal(state.detailVisible.value, false)
  assert.deepEqual(state.elements.value, [])
  assert.deepEqual(calls.fit, [])
  assert.deepEqual(calls.viewport, [])
})

test('节点读取权限撤销后丢弃旧定义响应，蓝图权限撤销则关闭并清理', async t => {
  const response = deferred()
  const { state, props, auth, calls } = harness(t, { nodes: () => response.promise })
  props.modelValue = true
  await settle()
  auth.permissions = [PERM.operations.action.blueprint.read]
  await settle()
  response.resolve({ code: 0, data: [{ id: 'definition-a', name: '撤权前的节点名', type: 'crawler', inputs: [], handles: [] }] })
  await settle()
  assert.deepEqual(state.nodeTypeConfigs.value, [])
  assert.equal(state.nodeDisplayName('a'), 'definition-a')
  assert.equal(calls.nodes, 1)
  auth.permissions = []
  await settle()
  assert.equal(props.modelValue, false)
  assert.equal(state.blueprintData.value, null)
  assert.deepEqual(state.elements.value, [])
})

test('同一预览窗口切换蓝图 ID 只接受最后一次详情', async t => {
  const pending = { 'blueprint-a': deferred(), 'blueprint-b': deferred() }
  const { state, props } = harness(t, { permissions: [PERM.operations.action.blueprint.read], blueprint: id => pending[id].promise })
  props.modelValue = true
  await settle()
  props.blueprintId = 'blueprint-b'
  await settle()
  pending['blueprint-b'].resolve({ code: 0, data: { ...structuredClone(blueprint), id: 'blueprint-b' } })
  await settle()
  pending['blueprint-a'].resolve({ code: 0, data: structuredClone(blueprint) })
  await settle()
  assert.equal(state.blueprintData.value.id, 'blueprint-b')
})

test('节点目录与画布共用详情入口，往返目录不改变布局和视口', async t => {
  const { state, props, calls } = harness(t)
  props.modelValue = true
  await settle()
  const fits = calls.fit.length
  const snapshot = structuredClone(blueprint.graph)
  state.directoryVisible.value = true
  state.openNodeDetails('b')
  assert.equal(state.directoryVisible.value, false)
  assert.equal(state.detailVisible.value, true)
  assert.equal(state.selectedPreviewNode.value.id, 'b')
  state.directoryVisible.value = true
  state.selectedPreviewNodeId.value = ''
  state.openNodeDetails('a')
  assert.equal(state.selectedPreviewNode.value.id, 'a')
  assert.equal(state.selectedPreviewNode.value.data.form_data.count, 3)
  state.openNodeDetails('不存在节点')
  assert.equal(state.selectedPreviewNode.value.id, 'a')
  assert.deepEqual(state.blueprintData.value.graph, snapshot)
  assert.equal(calls.fit.length, fits)
  assert.equal(calls.viewport.length, 0)
})
