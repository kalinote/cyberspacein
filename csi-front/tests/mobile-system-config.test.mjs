import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript, compileTemplate, babelParse } from 'vue/compiler-sfc'
import * as policy from '../src/utils/systemConfigPolicy.js'
import * as coordination from '../src/utils/systemConfigCoordination.js'
import { findNavItemByKey } from '../src/utils/configCenterNav.js'
import { PERM } from '../src/utils/permissions.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'

/**
 * 加载真实配置组件，以隔离接口验证手机草稿与权限行为。
 * @param {string} path 组件路径。
 * @param {object} options 接口、属性和确认框替身。
 * @returns {object} 组件状态、事件和清理方法。
 */
function loadComponent(path, { api = {}, props = {}, confirm = async () => {}, permissions = ['*'], mobile = true } = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: path })
  const events = []
  const hooks = { leave: [], mounted: [], activated: [], deactivated: [], beforeUnmount: [] }
  const auth = Vue.reactive({ permissions })
  const isMobile = Vue.ref(mobile)
  const windowEvents = new Map()
  let confirmationsClosed = 0
  const imports = {
    vue: { ...Vue, onMounted: fn => hooks.mounted.push(fn), onBeforeUnmount: fn => hooks.beforeUnmount.push(fn), onActivated: fn => hooks.activated.push(fn), onDeactivated: fn => hooks.deactivated.push(fn) },
    'vue-router': { onBeforeRouteLeave: fn => hooks.leave.push(fn) },
    'element-plus': { ElMessage: { success() {}, warning() {}, error() {} }, ElMessageBox: { confirm, close: () => { confirmationsClosed++ } } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile }) },
    '@/utils/permissions': { PERM },
    '@/utils/permissionKit': { hasPerm: code => hasAllForPermissions(auth.permissions, [code]) },
    '@/api/system': { systemApi: api },
    '@/utils/systemConfigPolicy': policy,
    '@/utils/systemConfigCoordination': coordination,
    '@/utils/configCenterNav': { findNavItemByKey },
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', {}]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const window = { addEventListener: (name, fn) => windowEvents.set(name, fn), removeEventListener: name => windowEvents.delete(name), scrollTo() {} }
  const component = new Function('imports', 'window', code.replace('export default', 'return'))(imports, window)
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup(props, { expose() {}, emit: (...args) => events.push(args) }))
  const template = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  return { state, events, hooks, auth, isMobile, windowEvents, get confirmationsClosed() { return confirmationsClosed }, stop: () => { hooks.beforeUnmount.forEach(fn => fn()); scope.stop() } }
}

/** """控制接口或确认框何时完成，以验证异步边界。""" */
function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

const pagePath = 'views/system/SystemConfigHome.vue'
const pickerPath = 'components/system/GroupPermissionPicker.vue'
const fixture = {
  version: 8,
  groups: [{ key: 'search', label: '搜索' }, { key: 'security', label: '认证' }],
  fields: [
    { key: 'cache', label: '缓存', group: 'search', apply_mode: 'runtime', editable: true, value_type: 'integer', value: 600 },
    { key: 'secret', label: '凭据', group: 'security', apply_mode: 'runtime', editable: true, sensitive: true, configured: true },
    { key: 'workers', label: '进程', group: 'search', apply_mode: 'restart', editable: true, value: 2 },
    { key: 'readonly', label: '基础设施', group: 'security', apply_mode: 'readonly', editable: false, value: '固定' },
  ],
}

test('手机配置目录按真实类别与生效方式分组，不重复字段且搜索仍受类别约束', async () => {
  const page = loadComponent(pagePath, { api: { getSystemConfig: async () => ({ data: fixture }) } })
  await page.state.loadConfig()
  assert.deepEqual(page.state.mobileConfigGroups.value.map(group => [group.key, group.count]), [['search', 1], ['security', 1]])
  assert.deepEqual(page.state.visibleGroups.value.map(group => group.fields.map(field => field.key)), [['cache'], ['secret']])
  page.state.activeGroup.value = 'search'
  assert.equal(page.state.visibleGroups.value.length, 1)
  page.state.searchQuery.value = '凭据'
  assert.equal(page.state.visibleGroups.value.length, 0)
  page.stop()
})

test('手机单项草稿保留敏感空值语义，分组预览提交原修订号且放弃不影响其它组', async () => {
  const calls = []
  const page = loadComponent(pagePath, { api: {
    getSystemConfig: async () => ({ data: fixture }),
    previewSystemConfig: async body => { calls.push(body); return { data: { runtime_fields: Object.keys(body.changes), warnings: [] } } },
  } })
  await page.state.loadConfig()
  page.state.mobileFieldKey.value = 'secret'
  assert.equal(page.state.form.secret, '')
  page.state.form.cache = 601
  page.state.form.workers = 3
  page.state.form.readonly = '不应提交'
  await page.state.openPreview('runtime')
  assert.deepEqual(calls, [{ expected_version: 8, changes: { cache: 601 } }])
  page.state.resetChanges('runtime')
  assert.deepEqual(page.state.allChanges.value, { workers: 3 })
  page.stop()
})

test('手机离页取消保留修改，确认离页才允许路由切换', async () => {
  let accept = false
  const page = loadComponent(pagePath, { api: { getSystemConfig: async () => ({ data: fixture }) }, confirm: async () => { if (!accept) throw new Error('取消') } })
  await page.state.loadConfig()
  page.state.form.cache = 601
  assert.equal(await page.hooks.leave[0](), false)
  assert.equal(page.state.form.cache, 601)
  accept = true
  assert.equal(await page.hooks.leave[0](), true)
  assert.deepEqual(page.state.allChanges.value, {})
  assert.equal(page.state.form.cache, 600)
  page.stop()
})

test('手机搜索和单项选择保留隐藏分类以及未知权限，通配符与禁用状态禁止变更', () => {
  const props = Vue.reactive({ modelValue: ['known-a', 'unknown'], disabled: false, permCodes: [
    { permKey: 'known-a', name: '查看用户', category: '管理/用户', enabled: true },
    { permKey: 'known-b', name: '查看任务', category: '任务', enabled: true },
  ] })
  const picker = loadComponent(pickerPath, { props })
  picker.state.category.value = '任务'
  picker.state.searchKeyword.value = '查看'
  assert.deepEqual(picker.state.mobilePermissionGroups.value.map(group => group.label), ['任务'])
  picker.state.toggleMobilePermission('known-b', true)
  assert.deepEqual(picker.events.at(-1), ['update:modelValue', ['known-a', 'known-b', 'unknown']])
  props.modelValue = ['*']
  picker.state.toggleMobilePermission('known-b', true)
  assert.equal(picker.events.length, 1)
  props.modelValue = ['known-a']
  props.disabled = true
  picker.state.toggleMobilePermission('known-a', false)
  assert.equal(picker.events.length, 1)
  picker.stop()
})

test('配置预览等待期间继续编辑，不展示陈旧预览也不能保存未经预览的值', async () => {
  const response = deferred()
  const writes = []
  const previews = []
  const page = loadComponent(pagePath, { api: {
    getSystemConfig: async () => ({ data: structuredClone(fixture) }),
    previewSystemConfig: body => { previews.push(structuredClone(body)); return response.promise },
    applyRuntimeSystemConfig: async body => { writes.push(body); return { data: { version: 9 } } },
  } })
  await page.state.loadConfig()
  page.state.form.cache = 601
  const request = page.state.openPreview('runtime')
  page.state.form.cache = 900
  response.resolve({ data: { runtime_fields: ['cache'], warnings: [] } })
  await request
  await page.state.applyChanges()
  assert.deepEqual(previews, [{ expected_version: 8, changes: { cache: 601 } }])
  assert.equal(page.state.previewVisible.value, false)
  assert.equal(page.state.previewData.value, null)
  assert.deepEqual(writes, [])
  page.stop()
})

test('已展示的预览仍核对修订号和草稿，变化后禁止保存', async () => {
  let writes = 0
  const page = loadComponent(pagePath, { api: {
    getSystemConfig: async () => ({ data: structuredClone(fixture) }),
    previewSystemConfig: async () => ({ data: { runtime_fields: ['cache'], warnings: [] } }),
    applyRuntimeSystemConfig: async () => { writes++ },
  } })
  await page.state.loadConfig()
  page.state.form.cache = 601
  await page.state.openPreview('runtime')
  page.state.form.cache = 602
  await page.state.applyChanges()
  assert.equal(writes, 0)
  await page.state.openPreview('runtime')
  page.state.configData.value.version = 9
  await page.state.applyChanges()
  assert.equal(writes, 0)
  page.stop()
})

test('保存固定预览快照，响应期间的新普通值和敏感草稿继续保持未保存', async () => {
  const response = deferred()
  const writes = []
  const page = loadComponent(pagePath, { api: {
    getSystemConfig: async () => ({ data: structuredClone(fixture) }),
    previewSystemConfig: async () => ({ data: { runtime_fields: ['cache', 'secret'], warnings: [] } }),
    applyRuntimeSystemConfig: body => { writes.push(structuredClone(body)); return response.promise },
  } })
  await page.state.loadConfig()
  page.state.form.cache = 601
  page.state.form.secret = '测试值甲'
  await page.state.openPreview('runtime')
  const request = page.state.applyChanges()
  page.state.form.cache = 602
  page.state.form.secret = '测试值乙'
  response.resolve({ data: { version: 9 } })
  await request
  assert.deepEqual(writes, [{ expected_version: 8, changes: { cache: 601, secret: '测试值甲' } }])
  assert.deepEqual(page.state.allChanges.value, { cache: 602, secret: '测试值乙' })
  assert.equal(page.state.original.cache, 601)
  assert.equal(page.state.configData.value.version, 9)
  page.stop()
})

test('重启配置保存后的刷新保留请求期间新增的其它组草稿', async () => {
  const response = deferred()
  let reads = 0
  const page = loadComponent(pagePath, { api: {
    getSystemConfig: async () => { reads++; const data = structuredClone(fixture); if (reads > 1) { data.version = 9; data.fields.find(field => field.key === 'workers').value = 3 } return { data } },
    previewSystemConfig: async () => ({ data: { restart_fields: ['workers'], warnings: [] } }),
    stagePendingSystemConfig: () => response.promise,
  } })
  await page.state.loadConfig()
  page.state.form.workers = 3
  await page.state.openPreview('restart')
  const request = page.state.applyChanges()
  page.state.form.cache = 700
  response.resolve({ data: { version: 9, restart_required: true } })
  await request
  assert.equal(reads, 2)
  assert.deepEqual(page.state.allChanges.value, { cache: 700 })
  page.stop()
})

test('无读取权限不发请求，仅读取权限不能预览、保存或执行管理操作', async () => {
  let reads = 0
  let confirmations = 0
  const page = loadComponent(pagePath, { permissions: [], confirm: async () => { confirmations++ }, api: { getSystemConfig: async () => { reads++; return { data: structuredClone(fixture) } } } })
  await page.state.loadConfig()
  await page.state.openHistory()
  assert.equal(reads, 0)
  page.auth.permissions = [PERM.operations.system.config.read]
  await Vue.nextTick(); await Vue.nextTick()
  assert.equal(reads, 1)
  assert.equal(page.state.canUpdate.value, false)
  assert.equal(page.state.canExecute.value, false)
  page.state.form.cache = 601
  page.state.historyDetail.value = { version: 7, restore_runtime_fields: ['cache'] }
  page.state.coordinationData.value = { proposed_version: 9, coordination_token: '测试令牌', differences: [] }
  await page.state.openPreview('runtime')
  await page.state.applyChanges()
  await page.state.cancelPending()
  await page.state.restoreHistory()
  await page.state.openCoordination()
  await page.state.commitCoordination()
  assert.equal(confirmations, 0)
  assert.equal(page.state.previewVisible.value, false)
  page.stop()
})

test('读取撤权清理缓存，之后重新授权也不能接纳撤权前的迟到配置响应', async () => {
  const responses = [deferred(), deferred()]
  let reads = 0
  const page = loadComponent(pagePath, { api: { getSystemConfig: () => responses[reads++].promise } })
  const first = page.state.loadConfig()
  page.auth.permissions = []
  assert.equal(page.state.configData.value, null)
  page.auth.permissions = ['*']
  responses[0].resolve({ data: { ...structuredClone(fixture), version: 100 } })
  await first
  assert.equal(page.state.configData.value, null)
  responses[1].resolve({ data: structuredClone(fixture) })
  await Vue.nextTick(); await Vue.nextTick()
  assert.equal(page.state.configData.value.version, 8)
  page.stop()
})

for (const operation of ['cancelPending', 'restoreHistory', 'commitCoordination']) {
  test(`${operation} 等待确认时离页再激活，旧确认不得写入`, async () => {
    const confirmation = deferred()
    const writes = []
    const page = loadComponent(pagePath, { confirm: () => confirmation.promise, api: {
      getSystemConfig: async () => ({ data: structuredClone(fixture) }),
      cancelPendingSystemConfig: async body => writes.push(body), restoreSystemConfigHistory: async body => writes.push(body), commitSystemConfigCoordination: async body => writes.push(body),
    } })
    await page.state.loadConfig()
    page.state.historyDetail.value = { version: 7, restore_runtime_fields: ['cache'] }
    page.state.coordinationData.value = { proposed_version: 9, coordination_token: '测试令牌', differences: [] }
    const request = page.state[operation]()
    page.hooks.deactivated.forEach(fn => fn())
    page.hooks.activated.forEach(fn => fn())
    confirmation.resolve()
    await request
    assert.deepEqual(writes, [])
    assert.equal(page.confirmationsClosed, 1)
    page.stop()
  })

  test(`${operation} 确认过程中执行权限被撤回，不调用写接口`, async () => {
    const confirmation = deferred()
    let writes = 0
    const page = loadComponent(pagePath, { confirm: () => confirmation.promise, api: {
      getSystemConfig: async () => ({ data: structuredClone(fixture) }),
      cancelPendingSystemConfig: async () => { writes++ }, restoreSystemConfigHistory: async () => { writes++ }, commitSystemConfigCoordination: async () => { writes++ },
    } })
    await page.state.loadConfig()
    page.state.historyDetail.value = { version: 7, restore_runtime_fields: ['cache'] }
    page.state.coordinationData.value = { proposed_version: 9, coordination_token: '测试令牌', differences: [] }
    const request = page.state[operation]()
    page.auth.permissions = [PERM.operations.system.config.read, PERM.operations.system.config.update]
    confirmation.resolve()
    await request
    assert.equal(writes, 0)
    page.stop()
  })
}

test('失活关闭全部弹层并禁止旧响应恢复，桌面缓存返回保留未保存草稿', async () => {
  const history = deferred()
  let reads = 0
  const page = loadComponent(pagePath, { mobile: false, api: { getSystemConfig: async () => { reads++; return { data: structuredClone(fixture) } }, getSystemConfigHistoryDetail: () => history.promise } })
  await page.state.loadConfig()
  page.state.form.cache = 701
  page.state.mobileFieldKey.value = 'cache'
  page.state.previewVisible.value = true
  page.state.coordinationVisible.value = true
  page.state.historyVisible.value = true
  const request = page.state.openHistoryDetail(7)
  assert.equal(await page.hooks.leave[0](), true)
  page.hooks.deactivated.forEach(fn => fn())
  for (const key of ['previewVisible', 'coordinationVisible', 'historyVisible', 'historyDetailVisible']) assert.equal(page.state[key].value, false)
  assert.equal(page.state.mobileFieldKey.value, '')
  history.resolve({ data: { version: 7 } })
  await request
  assert.equal(page.state.historyDetail.value, null)
  page.hooks.activated.forEach(fn => fn())
  assert.equal(reads, 1)
  assert.equal(page.state.form.cache, 701)
  page.hooks.deactivated.forEach(fn => fn())
  page.stop()
  assert.equal(page.confirmationsClosed, 0)
})

test('手机离页后的 beforeunload 不再拦截其它页面', async () => {
  const page = loadComponent(pagePath, { api: { getSystemConfig: async () => ({ data: structuredClone(fixture) }) } })
  await page.state.loadConfig()
  page.state.form.cache = 601
  let prevented = 0
  const event = { preventDefault() { prevented++ } }
  page.state.protectMobileDraft(event)
  assert.equal(prevented, 1)
  page.hooks.deactivated.forEach(fn => fn())
  page.state.protectMobileDraft(event)
  assert.equal(prevented, 1)
  page.stop()
})

test('主动关闭确认框未结束 Promise 时不会在下次离页误关其它页面弹窗', async () => {
  const confirmation = deferred()
  const page = loadComponent(pagePath, { confirm: () => confirmation.promise, api: { getSystemConfig: async () => ({ data: structuredClone(fixture) }) } })
  await page.state.loadConfig()
  const request = page.state.cancelPending()
  assert.equal(page.state.pendingConfirmations.size, 1)
  page.hooks.deactivated.forEach(fn => fn())
  assert.equal(page.confirmationsClosed, 1)
  assert.equal(page.state.pendingConfirmations.size, 0)
  page.hooks.activated.forEach(fn => fn())
  page.hooks.deactivated.forEach(fn => fn())
  assert.equal(page.confirmationsClosed, 1)
  confirmation.resolve()
  await request
  assert.equal(page.state.pendingConfirmations.size, 0)
  page.stop()
  assert.equal(page.confirmationsClosed, 1)
})
