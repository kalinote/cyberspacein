import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, effectScope, markRaw, nextTick, reactive, ref, watch } from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'

/** """创建可控制完成顺序的接口响应。""" */
function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

/**
 * 执行页面真实 setup，保留 Vue 响应式行为并隔离所有后端写入。
 * @param {object} t 测试上下文。
 * @param {string} file 相对 src 的组件路径。
 * @param {object} options 替身接口、路由、权限及属性。
 * @returns {object} 页面状态、生命周期回调及事件记录。
 */
function harness(t, file, options = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const source = compileScript(descriptor, { id: file }).content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\r?\n/gm, '').replace('export default', 'return')
  const auth = reactive({ permissions: options.permissions || ['*'] })
  const route = reactive(options.route || { params: { id: 'platform-a' } })
  const hooks = { mounted: [], activated: [], deactivated: [], beforeUnmount: [] }
  const events = []
  const messages = []
  const props = reactive(options.props || {})
  const bindings = {
    ref, computed, reactive, watch, nextTick, markRaw,
    onMounted: fn => hooks.mounted.push(fn), onActivated: fn => hooks.activated.push(fn), onDeactivated: fn => hooks.deactivated.push(fn), onBeforeUnmount: fn => hooks.beforeUnmount.push(fn),
    useRoute: () => route, useRouter: () => ({ push: path => events.push(['navigate', path]) }), useMobileViewport: () => ({ isMobile: ref(options.mobile !== false) }),
    hasPerm: code => hasAllForPermissions(auth.permissions, [code]), hasAll: codes => hasAllForPermissions(auth.permissions, codes), PERM,
    platformApi: options.platformApi || {}, actionApi: options.actionApi || {}, searchApi: options.searchApi || {}, highlightApi: {},
    getPaginatedData: async (api, params) => api(params), getCosUrl: value => value, formatDate: value => value, formatDateTime: value => value,
    buildActionRunRequest: (...args) => ({ args }), INPUT_TYPE_DEFAULTS: { string: '', int: null },
    ElMessage: { error: value => messages.push(value), success: value => messages.push(value), warning: value => messages.push(value), info: value => messages.push(value) },
    ElNotification: value => messages.push(value), ElMessageBox: { confirm: options.confirm || (() => Promise.resolve()) },
    Icon: {}, Header: {}, FunctionalPageHeader: {}, DetailPageHeader: {}, TagInput: {}, MobileSheet: {}, MobilePlatformDetail: {}, MobileBlueprintList: {},
    ActionBlueprintCard: {}, BlueprintFlowDialog: {}, TemplateParamsDialog: {}, BlueprintPublishDialog: {}, BlueprintEncapsulateDialog: {}, BlueprintRunControl: {}, BlueprintPinButton: {}, InputRenderer: {},
    echarts: {}, window: { removeEventListener() {} }, console: { error() {} },
  }
  const component = new Function(...Object.keys(bindings), source)(...Object.values(bindings))
  const scope = effectScope()
  const page = scope.run(() => component.setup(props, { expose() {}, emit: (...args) => events.push(args) }))
  t.after(() => { hooks.beforeUnmount.forEach(fn => fn()); scope.stop() })
  return { page, hooks, props, events, messages, auth, route }
}

const paginated = (items, page = 1) => ({ items, pagination: { total: items.length, page, pageSize: 10 } })

test('平台手机搜索使用真实查询字段，较早请求不会覆盖新筛选结果', async t => {
  const pending = [deferred(), deferred()]
  const calls = []
  const { page } = harness(t, 'views/platform/PlatformList.vue', { platformApi: { getPlatformList: params => { calls.push(params); return pending[calls.length - 1].promise } } })
  const first = page.fetchPlatformList()
  page.searchKeyword.value = ' 平台乙 '
  page.selectedStatus.value = '活跃'
  page.selectedType.value = 'article'
  const second = page.fetchPlatformList()
  pending[1].resolve(paginated([{ id: 'b' }]))
  await second
  pending[0].resolve(paginated([{ id: 'a' }]))
  await first
  assert.deepEqual(calls[1], { page: 1, page_size: 10, search: '平台乙', status: '活跃', type: 'article' })
  assert.equal(page.platformList.value[0].id, 'b')
  assert.equal(page.loading.value, false)
})

test('平台无读取或创建权限时不请求接口，停用页面不接受迟到列表', async t => {
  let calls = 0
  const response = deferred()
  const { page, hooks, auth } = harness(t, 'views/platform/PlatformList.vue', { permissions: [], platformApi: { getPlatformList() { calls++; return response.promise }, getPlatformFilterSubCategory() { calls++ } } })
  await page.fetchPlatformList()
  await page.handleAddPlatform()
  assert.equal(calls, 0)
  auth.permissions = ['*']
  const pending = page.fetchPlatformList()
  hooks.deactivated.forEach(fn => fn())
  response.resolve(paginated([{ id: '迟到平台' }]))
  await pending
  assert.deepEqual(page.platformList.value, [])
})

test('平台新增先校验必要字段，失败保留步骤和输入，成功才进入确认', async t => {
  const { page } = harness(t, 'views/platform/PlatformList.vue')
  let invalid = true
  let fields
  page.formRef.value = { validateField: async value => { fields = value; if (invalid) throw new Error('名称缺失') } }
  page.formData.value.url = 'https://example.test'
  await page.nextCreateStep()
  assert.equal(page.mobileCreateStep.value, 0)
  assert.equal(page.formData.value.url, 'https://example.test')
  invalid = false
  await page.nextCreateStep()
  assert.deepEqual(fields, ['name', 'url', 'type', 'category', 'sub_category'])
  assert.equal(page.mobileCreateStep.value, 1)
  await page.nextCreateStep()
  assert.equal(page.mobileCreateStep.value, 2)
})

test('平台同组件切换 ID 后只接受新平台资料，并用新平台名称搜索情报', async t => {
  const pending = { 'platform-a': deferred(), 'platform-b': deferred() }
  const searches = []
  const { page, route } = harness(t, 'views/details/PlatformDetail.vue', {
    platformApi: { getPlatformDetail: id => pending[id].promise, getPlatformNewDataStatus: async () => ({ data: { buckets: [] } }) },
    searchApi: { searchEntity: async params => { searches.push(params); return { code: 0, data: { items: [], total: 0 } } } },
  })
  const first = page.loadPlatformDetail()
  route.params.id = 'platform-b'
  await nextTick()
  pending['platform-b'].resolve({ code: 0, data: { id: 'platform-b', name: '新平台', tags: [], sections: [] } })
  await nextTick(); await nextTick()
  pending['platform-a'].resolve({ code: 0, data: { id: 'platform-a', name: '旧平台' } })
  await first
  assert.equal(page.platformDetail.value.uuid, 'platform-b')
  assert.deepEqual(searches.map(params => params.platform), ['新平台'])
})

test('蓝图手机置顶筛选走服务端，详情按需请求且关闭后不接受迟到详情', async t => {
  const listCalls = []
  const { page } = harness(t, 'views/action/ActionBlueprintList.vue', { actionApi: { getBlueprintsBaseInfo: async params => { listCalls.push(params); return paginated([]) } } })
  page.mobilePinned.value = 'false'
  await page.fetchBlueprints()
  assert.equal(listCalls[0].is_pinned, false)
  const response = deferred()
  const mobile = harness(t, 'components/action/MobileBlueprintList.vue', { props: { blueprints: [], pagination: {}, pinned: '' }, actionApi: { getBlueprint: () => response.promise } })
  const request = mobile.page.openDetail({ id: 'blueprint-a', title: '测试蓝图' })
  await nextTick()
  mobile.page.detailVisible.value = false
  await nextTick()
  response.resolve({ code: 0, data: { id: 'blueprint-a', is_template: true } })
  await request
  assert.equal(mobile.page.detail.value, null)
})

test('蓝图手机禁止无执行权限运行，封装准备完成时已离页不弹出窗口', async t => {
  let runCalls = 0
  const response = deferred()
  const { page, auth, hooks } = harness(t, 'views/action/ActionBlueprintList.vue', { permissions: [PERM.operations.action.blueprint.read], actionApi: { runAction: () => { runCalls++ }, getBlueprint: () => response.promise, getNodes: async () => ({ data: [] }), validateBlueprint: async () => ({ data: { valid: true } }) } })
  await page.createActionFromBlueprint({ id: 'blueprint-a' })
  assert.equal(runCalls, 0)
  auth.permissions = ['*']
  const request = page.openEncapsulateDialog({ id: 'blueprint-a' })
  hooks.deactivated.forEach(fn => fn())
  response.resolve({ data: { interface: { inputs: [], outputs: [] } } })
  await request
  assert.equal(page.encapsulateDialogVisible.value, false)
})

test('模板参数请求失败不伪装成无参数模板，关闭后旧响应不回填', async t => {
  const response = deferred()
  const { page, props, events } = harness(t, 'components/action/template/TemplateParamsDialog.vue', { props: { modelValue: true, blueprintId: 'a' }, actionApi: { getBlueprint: () => response.promise } })
  const request = page.fetchBlueprintData()
  props.modelValue = false
  await nextTick()
  response.resolve({ code: 0, data: { template: { params: [] } } })
  await request
  assert.equal(page.blueprintData.value, null)
  const failed = harness(t, 'components/action/template/TemplateParamsDialog.vue', { props: { modelValue: true, blueprintId: 'b' }, actionApi: { getBlueprint: async () => { throw new Error('网络中断') } } })
  await failed.page.fetchBlueprintData()
  await failed.page.handleSubmit()
  assert.match(failed.page.loadError.value, /加载失败/)
  assert.equal(failed.events.length, 0)
  assert.equal(events.length, 0)
})

test('蓝图读取权限撤销立即清理已打开详情和运行设置', async t => {
  const { page, auth } = harness(t, 'components/action/MobileBlueprintList.vue', { props: { blueprints: [], pagination: {}, pinned: '' }, actionApi: { getBlueprint: async () => ({ code: 0, data: { id: 'a', is_template: true, template: { params: [] } } }) } })
  await page.openDetail({ id: 'a' })
  page.runVisible.value = true
  auth.permissions = []
  await nextTick()
  assert.equal(page.detailVisible.value, false)
  assert.equal(page.runVisible.value, false)
  assert.equal(page.detail.value, null)
})

test('异步准备封装与另一蓝图发布使用独立目标，不能串写蓝图', async t => {
  const response = deferred()
  const writes = []
  const { page } = harness(t, 'views/action/ActionBlueprintList.vue', { actionApi: {
    getBlueprint: () => response.promise, getNodes: async () => ({ data: [] }), validateBlueprint: async () => ({ data: { valid: true } }),
    encapsulateBlueprint: async (id, data) => { writes.push({ id, data }); return { data: {} } }, getBlueprintsBaseInfo: async () => paginated([]),
  } })
  const prepare = page.openEncapsulateDialog({ id: '待封装蓝图' })
  page.openPublishDialog({ id: '待发布蓝图' })
  response.resolve({ data: { interface: {} } })
  await prepare
  await page.handleEncapsulate({ node_name: '测试节点', mode: 'create' })
  assert.equal(writes[0].id, '待封装蓝图')
  assert.equal(page.selectedBlueprintForRelease.value.id, '待发布蓝图')
})
