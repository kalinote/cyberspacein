import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { babelParse, compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import * as resourceData from '../src/components/action/mobile/resources/mobileResourceData.js'
import * as formatters from '../src/utils/action/formatters.js'
import { ACTION_STATUS } from '../src/utils/action/status.js'
import * as typedValues from '../src/utils/typedKeyValue.js'

/**
 * 编译真实移动资源组件并替换外部接口，保留真实响应式状态和模板。
 * @param {object} t 测试上下文。
 * @param {string} name 资源组件名。
 * @param {object} options 模拟权限、接口及属性。
 * @returns {object} 状态、生命周期、事件和渲染入口。
 */
function mount(t, name = 'MobileActionResources', options = {}) {
  const file = options.componentPath || `components/action/mobile/resources/${name}.vue`
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: file })
  const props = Vue.reactive({ activeTab: 'nodes', keyword: '', label: '行动节点', ...options.props })
  const denied = Vue.ref(options.denied || [])
  const hooks = [], events = [], notices = []
  const imports = {
    vue: { ...Vue, onMounted() {}, onBeforeUnmount: callback => hooks.push(callback) },
    '@iconify/vue': { Icon: {} },
    'element-plus': { ElMessage: { success: text => notices.push(text), error: text => notices.push(text) } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: Vue.ref(true) }) },
    '@/api/action': { actionApi: {
      getNodes: async () => ({ code: 0, data: [] }),
      getBaseComponents: async () => ({ code: 0, data: { items: [{ id: 'component', name: '组件' }], total: 1 } }),
      getNodeHandles: async () => ({ code: 0, data: { items: [], total: 0 } }),
      getEncapsulatedNodes: async () => ({ code: 0, data: { items: [], total: 0 } }),
      getAccountList: async () => ({ code: 0, data: { items: [], total: 0 } }),
      getAllNodeHandles: async () => ({ code: 0, data: [] }),
      getNodeTypeFilter: async () => ({ code: 0, data: [{ 普通节点: 'ordinary' }] }),
      ...options.api,
    } },
    '@/api/platform': { platformApi: { getPlatformFilterPlatforms: async () => ({ code: 0, data: [{ id: 'platform', name: '平台' }] }) } },
    '@/utils/permissions': { PERM }, '@/utils/permissionKit': { hasPerm: code => typeof code === 'string' && Boolean(code) && !denied.value.includes(code) },
    '@/utils/action': { ...formatters, ACTION_STATUS, INPUT_TYPES: ['text', 'select', 'comment'] },
    './mobileResourceData': resourceData, '@/utils/typedKeyValue': typedValues,
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', { name: specifier.local.name }]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup(props, { expose() {}, emit: (...args) => events.push(args) }))
  const template = compileTemplate({ source: descriptor.template.content, filename: file, id: file, compilerOptions: { mode: 'function', bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  const render = new Function('Vue', template.code)({ ...Vue, resolveComponent: name => ({ name }), resolveDirective: () => ({}), withDirectives: node => node })
  t.after(() => { hooks.forEach(callback => callback()); scope.stop() })
  return { state, props, denied, hooks, events, notices, render: () => render({}, [], props, Vue.proxyRefs(state)) }
}

test('节点表单完整校验隐藏分组，序列化沿用桌面注释输入和组件超时语义', () => {
  const draft = resourceData.makeResourceDraft('nodes')
  assert.equal(resourceData.validateResourceDraft('nodes', draft).step, 0)
  Object.assign(draft, { name: '采集节点', type: 'ordinary' })
  assert.equal(resourceData.validateResourceDraft('nodes', draft).step, 1)
  draft.related_components = ['component']
  draft.component_timeouts = { component: '35', removed: 90 }
  draft.handles = [{ id: '', type: 'source', position: 'right' }]
  assert.equal(resourceData.validateResourceDraft('nodes', draft).step, 2)
  draft.handles[0].id = 'handle'
  draft.inputs = [{ name: 'invalid-name', type: 'comment', position: 'center', label: '说明', required: true, default: '不应提交' }]
  assert.equal(resourceData.validateResourceDraft('nodes', draft).step, 3)
  draft.inputs[0].name = 'help_text'
  assert.equal(resourceData.validateResourceDraft('nodes', draft), null)
  const payload = resourceData.resourcePayload('nodes', draft)
  assert.deepEqual(payload.component_timeouts, { component: 35 })
  assert.equal(payload.inputs[0].required, false)
  assert.equal(payload.inputs[0].default, '')
  assert.deepEqual(payload.handles[0], { id: 'handle', type: 'source', position: 'right' })
})

test('账号与接口载荷保留现有字段规则，编辑草稿不污染详情原对象', () => {
  const source = { platform_id: 'platform', account_name: '账号', credentials: { username: 'name', password: 'secret', phone: '', email: 'a@example.com' }, rate_limit: { strategy: 'none', max_requests: 99 } }
  const draft = resourceData.makeResourceDraft('accounts', source)
  draft.credentials.username = '改名'
  assert.equal(source.credentials.username, 'name')
  assert.deepEqual(resourceData.resourcePayload('accounts', draft), { platform_id: 'platform', account_name: '账号', credentials: { username: '改名', password: 'secret', email: 'a@example.com' }, rate_limit: {} })
  const handle = resourceData.makeResourceDraft('nodeHandles')
  handle.handle_name = 'bad-name'
  assert.ok(resourceData.validateResourceDraft('nodeHandles', handle))
  Object.assign(handle, { handle_name: 'content', type: 'value', label: '内容' })
  assert.equal(resourceData.validateResourceDraft('nodeHandles', handle), null)
  assert.deepEqual(resourceData.resourcePayload('nodeHandles', handle), { handle_name: 'content', type: 'value', label: '内容', color: '#409EFF', other_compatible_interfaces: [] })
})

test('旧节点的空配置和默认值沿用桌面标准化规则', () => {
  const draft = resourceData.makeResourceDraft('nodes', { command_args: null, related_components: null, component_timeouts: null, handles: [{ custom_style: null }], inputs: [{ default: 0, options: null, custom_style: null, custom_props: null }] })
  assert.deepEqual(draft.command_args, ['main:run'])
  assert.deepEqual(draft.related_components, [])
  assert.deepEqual(draft.component_timeouts, {})
  assert.deepEqual(draft.handles[0].custom_style, {})
  assert.equal(draft.inputs[0].default, '0')
  assert.deepEqual(draft.inputs[0].options, [])
  assert.deepEqual(draft.inputs[0].custom_props, {})
})

test('手机目录未加载、统计失败或字段缺失时显示未知，真实零值和桌面逻辑保留', async t => {
  let response = null
  const { state } = mount(t, 'ActionResourceConfig', { componentPath: 'views/action/ActionResourceConfig.vue', api: { getStatistics: async () => { if (!response) throw new Error('网络失败'); return response } } })
  assert.equal(state.getResourceCount('accounts'), -1)
  await state.fetchStatistics()
  assert.equal(state.getResourceCount('accounts'), -1)
  state.isMobile.value = false
  assert.equal(state.getResourceCount('accounts'), 0)
  state.isMobile.value = true
  response = { code: 0, data: { account_count: 5, node_count: 0 } }
  await state.fetchStatistics()
  assert.equal(state.getResourceCount('accounts'), 5)
  assert.equal(state.getResourceCount('nodes'), 0)
  assert.equal(state.getResourceCount('encapsulatedNodes'), -1)
  assert.equal(state.getResourceCount('baseComponents'), -1)
  response = { code: 500, message: '统计不可用' }
  await state.fetchStatistics()
  assert.equal(state.getResourceCount('accounts'), -1)
})

test('撤销账号详情读取权限后立即清空资料，迟到详情不会重新显示', async t => {
  let finish
  const { state, denied } = mount(t, 'MobileActionResources', { props: { activeTab: 'accounts' }, api: { getAccountDetail: () => new Promise(resolve => { finish = resolve }) } })
  const request = state.openDetail({ id: 'account' })
  denied.value.push(PERM.operations.action.account.detailRead)
  await Vue.nextTick()
  assert.equal(state.detailVisible.value, false)
  finish({ code: 0, data: { id: 'account', credentials: { username: '旧凭证' } } })
  await request
  assert.equal(state.detail.value, null)
})

test('详情切换到编辑的弹层状态保持连续，供断点切换时保留当前草稿', async t => {
  const { state, events } = mount(t)
  state.detail.value = { id: 'node', definition_origin: 'user', name: '节点' }
  state.detailVisible.value = true
  await state.openEditor(state.detail.value)
  const last = events.filter(event => event[0] === 'overlayChange').at(-1)
  assert.deepEqual(last, ['overlayChange', true])
  assert.equal(state.draft.value.name, '节点')
  state.formVisible.value = false
  assert.deepEqual(events.at(-1), ['overlayChange', false])
})

test('切换资源模块后节点迟到响应不能覆盖接口列表', async t => {
  let finishNodes
  const { state, props } = mount(t, 'MobileActionResources', { api: {
    getNodes: () => new Promise(resolve => { finishNodes = resolve }),
    getNodeHandles: async () => ({ items: [{ id: 'handle', label: '当前接口' }], total: 1 }),
  } })
  props.activeTab = 'nodeHandles'
  await Vue.nextTick()
  finishNodes({ code: 0, data: [{ id: '旧节点' }] })
  await Vue.nextTick()
  assert.equal(state.items.value[0].id, 'handle')
  assert.equal(state.loading.value, false)
})

test('读取权限独立生效，账号列表权限不授权凭证详情', async t => {
  let calls = 0
  const denied = mount(t, 'MobileActionResources', { denied: [PERM.operations.action.node.read], api: { getNodes: async () => { calls++; return {} } } })
  await denied.state.load()
  assert.equal(calls, 0)
  const account = mount(t, 'MobileActionResources', { props: { activeTab: 'accounts' }, denied: [PERM.operations.action.account.detailRead], api: { getAccountDetail: async () => { calls++; return {} } } })
  await account.state.openDetail({ id: 'account' })
  assert.equal(calls, 0)
  assert.equal(account.state.detailVisible.value, false)
})

test('详情乱序与关闭不会显示旧资料，账号详情不显示密码', async t => {
  const pending = []
  const { state } = mount(t, 'MobileActionResources', { props: { activeTab: 'accounts' }, api: { getAccountDetail: () => new Promise(resolve => pending.push(resolve)) } })
  const first = state.openDetail({ id: 'old' })
  const second = state.openDetail({ id: 'new' })
  pending[1]({ code: 0, data: { id: 'new', credentials: { password: '不展示', username: '当前账号' } } })
  await second
  pending[0]({ code: 0, data: { id: 'old' } })
  await first
  assert.equal(state.detail.value.id, 'new')
  assert.doesNotMatch(JSON.stringify(state.detailFields.value), /不展示|password/)
  const closing = state.openDetail({ id: 'closing' })
  state.detailVisible.value = false
  await Vue.nextTick()
  pending[2]({ code: 0, data: { id: 'closing' } })
  await closing
  assert.equal(state.detail.value, null)
})

test('节点分组保存定位隐藏组错误，禁止重复提交且失败保留草稿', async t => {
  let finish
  const writes = []
  const { state } = mount(t, 'MobileActionResources', { api: { createNode: payload => { writes.push(payload); return new Promise(resolve => { finish = resolve }) } } })
  await state.openEditor()
  Object.assign(state.draft.value, { name: '节点', type: 'ordinary' })
  state.formStep.value = 3
  await state.save()
  assert.equal(state.formStep.value, 1)
  assert.equal(writes.length, 0)
  state.draft.value.related_components = ['component']
  const request = state.save()
  await state.save()
  assert.equal(writes.length, 1)
  finish({ code: 500, message: '保存失败' })
  await request
  assert.equal(state.formVisible.value, true)
  assert.equal(state.draft.value.name, '节点')
  assert.equal(state.formError.value, '保存失败')
  assert.equal(state.saving.value, false)
})

test('切换模块关闭全部弹层，迟到保存不会关闭新模块表单', async t => {
  let finish
  const { state, props } = mount(t, 'MobileActionResources', { api: { createNode: () => new Promise(resolve => { finish = resolve }) } })
  await state.openEditor()
  Object.assign(state.draft.value, { name: '节点', type: 'ordinary', related_components: ['component'] })
  const pending = state.save()
  props.activeTab = 'nodeHandles'
  await Vue.nextTick()
  assert.equal(state.formVisible.value, false)
  assert.equal(state.confirmVisible.value, false)
  await state.openEditor()
  state.draft.value.label = '新接口草稿'
  finish({ code: 0 })
  await pending
  assert.equal(state.formVisible.value, true)
  assert.equal(state.draft.value.label, '新接口草稿')
})

test('原生节点不能编辑删除，启停需二次确认且离页不再调用接口', async t => {
  let writes = 0
  const { state, hooks } = mount(t, 'MobileActionResources', { api: { setNativeNodeEnabled: async () => { writes++; return { code: 0 } } } })
  const node = { id: 'native', name: '系统节点', definition_origin: 'backend_builtin', enabled: true }
  state.detail.value = node
  assert.equal(state.canEditDetail.value, false)
  assert.equal(state.canDeleteDetail.value, false)
  state.askMutation('toggle', node)
  assert.equal(writes, 0)
  assert.match(state.confirmation.value.message, /在途行动不受影响/)
  hooks.forEach(callback => callback())
  await state.performMutation()
  assert.equal(writes, 0)
})

test('封装节点保留引用约束与最后版本删除说明，不进行图形编辑', async t => {
  const { state } = mount(t, 'MobileActionResources', { props: { activeTab: 'encapsulatedNodes' } })
  const version = { id: 'version', name: '封装节点', definition_version: 2, is_latest: true, draft_reference_count: 1 }
  state.detailMode.value = 'version'
  state.detail.value = { node: version, references: [{ blueprint_id: 'blueprint' }] }
  state.selectedFamily.value = { versions: [version] }
  state.askMutation('delete', version)
  assert.equal(state.confirmVisible.value, false)
  version.draft_reference_count = 0
  state.detail.value.references = []
  state.askMutation('delete', version)
  assert.match(state.confirmation.value.message, /最后一个有效版本/)
  assert.match(state.confirmation.value.message, /再次封装会从 v1 开始/)
})

test('键值按项编辑保留类型，非法JSON、重复名称或提交期间均不写回主草稿', t => {
  const { state, events, props } = mount(t, 'MobileResourceKeyValues', { props: { modelValue: { existing: 3, nested: { a: true } } } })
  state.edit('nested')
  state.draftValue.value = '{'
  state.apply()
  assert.equal(events.length, 0)
  assert.match(state.error.value, /JSON/)
  state.draftValue.value = '{"a":false}'
  state.apply()
  assert.deepEqual(events[0], ['update:modelValue', { existing: 3, nested: { a: false } }])
  state.edit('')
  state.draftKey.value = 'existing'
  state.apply()
  assert.equal(events.length, 1)
  assert.match(state.error.value, /已存在/)
  props.disabled = true
  state.draftKey.value = 'new'
  state.apply()
  state.remove()
  assert.equal(events.length, 1)
})
