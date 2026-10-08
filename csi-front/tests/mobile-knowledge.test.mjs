import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from 'vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { PERM } from '../src/utils/permissions.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'
import { normalizeRecentVisit } from '../src/utils/recentVisitPolicy.js'
import { KNOWLEDGE_DESTINATIONS } from '../src/utils/knowledgeNavigation.js'

/**
 * 加载真实组件状态，隔离网络和生命周期以验证资料入口的异步操作。
 * @param {object} t 测试上下文。
 * @param {string} file 源码相对路径。
 * @param {object} options 可替换的接口与属性。
 * @returns {object} 页面状态、事件、权限与生命周期钩子。
 */
function mountPage(t, file, options = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const code = compileScript(descriptor, { id: 'mobile-knowledge-test' }).content.replace(/^import .*\r?\n/gm, '').replace('export default', 'return')
  const permissions = ref(options.permissions || ['*'])
  const props = reactive({ modelValue: false, initialTemplate: 'blank', ...options.props })
  const hooks = { mounted: [], activated: [], deactivated: [], beforeUnmount: [] }
  const emitted = [], notices = [], navigations = []
  const mobile = ref(true)
  const hasPerm = code => hasAllForPermissions(permissions.value, [code])
  const bindings = {
    ref, computed, reactive, watch, PERM, hasPerm, guardPermission: hasPerm,
    useRouter: () => ({ push: target => navigations.push(target) }),
    useRoute: () => reactive(options.route || { path: '/target/wiki', name: 'wiki-page-list' }),
    useMobileViewport: () => ({ isMobile: mobile, keyboardOpen: ref(false) }),
    onMounted: hook => hooks.mounted.push(hook), onActivated: hook => hooks.activated.push(hook),
    onDeactivated: hook => hooks.deactivated.push(hook), onBeforeUnmount: hook => hooks.beforeUnmount.push(hook),
    Icon: {}, Header: {}, FunctionalPageHeader: {}, MobileKnowledgeNav: {}, MobileSheet: {}, MobileActionBar: {}, EvidenceCreateDialog: {}, EvidenceUsageTour: {},
    KNOWLEDGE_DESTINATIONS, CHAIN_STATUS: { draft: '草稿', active: '分析中' },
    EVIDENCE_TEMPLATES: [{ id: 'blank' }, { id: 'proof' }], makeEvidenceGraph: (template, title) => ({ template, title, nodes: [], edges: [] }),
    evidenceApi: { list: async () => ({ data: { items: [], total: 0 } }), ...options.api },
    ElMessage: { success: value => notices.push(value) },
    ElMessageBox: { confirm: options.confirm || (() => Promise.resolve()), close: options.close || (() => {}) },
  }
  const component = new Function(...Object.keys(bindings), code)(...Object.values(bindings))
  const scope = effectScope()
  const page = scope.run(() => component.setup(props, { expose() {}, emit: (...args) => emitted.push(args) }))
  t.after(() => { hooks.beforeUnmount.forEach(hook => hook()); scope.stop() })
  return { page, props, permissions, hooks, emitted, notices, navigations, mobile }
}

test('资料分类按可见权限展示，只有专题权限也有可用资料入口', t => {
  const wiki = PERM.pages.target.wiki
  const { page, permissions } = mountPage(t, 'components/mobile/MobileKnowledgeNav.vue', { permissions: [wiki.visible, wiki.access] })
  assert.deepEqual(page.entries.value.map(item => item.path), ['/target/wiki'])
  assert.equal(page.activePath.value, '/target/wiki')
  permissions.value = ['*']
  assert.deepEqual(page.entries.value.map(item => item.label), ['检索', '重点', '专题', '证据'])
})

test('专题与证据最近访问需要各自的页面和读取权限，并剔除编辑参数', () => {
  for (const [name, page, read] of [
    ['wiki-detail', PERM.pages.target.wiki.access, PERM.operations.target.wiki.read],
    ['evidence-editor', PERM.pages.evidence.access, PERM.operations.evidence.chain.read],
  ]) {
    const route = { name, params: { id: 'record-1' }, query: { draft: '私有草稿', redirect: 'https://example.com' } }
    assert.equal(normalizeRecentVisit(route, [page]), null)
    assert.deepEqual(normalizeRecentVisit(route, [page, read]).query, {})
    assert.equal(normalizeRecentVisit({ ...route, params: { id: '../outside' } }, ['*']), null)
  }
  assert.equal(normalizeRecentVisit({ name: 'wiki-editor', params: { id: 'record-1' } }, ['*']), null)
})

test('证据列表较早搜索的迟到响应不能覆盖当前结果，失败保留旧数据', async t => {
  const pending = []
  const { page } = mountPage(t, 'views/evidence/EvidenceList.vue', { api: { list: params => new Promise((resolve, reject) => pending.push({ params, resolve, reject })) } })
  page.activate()
  page.appliedQuery.value = '当前关键词'
  const latest = page.load()
  pending[1].resolve({ data: { items: [{ id: 'current' }], total: 1 } })
  await latest
  pending[0].resolve({ data: { items: [{ id: 'old' }], total: 1 } })
  await nextTick()
  assert.equal(page.items.value[0].id, 'current')
  assert.equal(pending[1].params.q, '当前关键词')
  const failed = page.load()
  pending[2].reject(new Error('网络异常'))
  await failed
  assert.equal(page.error.value, '网络异常')
  assert.equal(page.items.value[0].id, 'current')
})

test('证据列表离页清除弹层并保留已应用筛选和页码，撤权清空结果', async t => {
  const calls = []
  const { page, permissions } = mountPage(t, 'views/evidence/EvidenceList.vue', { api: { list: async params => { calls.push(params); return { data: { items: [{ id: 'chain' }], total: 40 } } } } })
  page.activate()
  page.appliedQuery.value = '证据'
  page.appliedStatus.value = 'active'
  page.page.value = 2
  page.filterVisible.value = page.actionsVisible.value = page.createVisible.value = true
  page.deactivate()
  assert.equal(page.filterVisible.value || page.actionsVisible.value || page.createVisible.value, false)
  page.activate()
  await nextTick()
  assert.equal(calls.at(-1).page, 2)
  assert.equal(calls.at(-1).status, 'active')
  permissions.value = []
  await nextTick()
  assert.deepEqual(page.items.value, [])
  assert.equal(page.actionsVisible.value, false)
  assert.equal(page.selectedChain.value, null)
})

test('手机和桌面切换保留未提交草稿，分页仍使用已应用条件且提交只请求一次', async t => {
  const calls = []
  const { page, mobile } = mountPage(t, 'views/evidence/EvidenceList.vue', { api: { list: async params => { calls.push(params); return { data: { items: [], total: 60 } } } } })
  page.activate()
  await nextTick()
  page.page.value = 2
  await nextTick()
  calls.length = 0
  page.query.value = '已应用关键词'
  await page.applyFilters('active')
  await nextTick()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].page, 1)
  assert.equal(calls[0].status, 'active')
  page.query.value = '尚未提交的关键词'
  page.filterVisible.value = true
  mobile.value = false
  await nextTick()
  assert.equal(page.query.value, '尚未提交的关键词')
  assert.equal(page.filterVisible.value, false)
  page.page.value = 2
  await nextTick()
  assert.equal(calls.at(-1).q, '已应用关键词')
  page.status.value = 'draft'
  mobile.value = true
  await nextTick()
  assert.equal(page.appliedQuery.value, '已应用关键词')
  assert.equal(page.appliedStatus.value, 'active')
  assert.equal(page.query.value, '尚未提交的关键词')
  mobile.value = false
  await nextTick()
  await page.applyFilters()
  await nextTick()
  assert.equal(calls.at(-1).q, '尚未提交的关键词')
  assert.equal(calls.at(-1).status, 'draft')
})

test('离页主动关闭删除确认，迟到确认不能解除下一次删除的操作锁', async t => {
  const confirmations = []
  let closed = 0
  const writes = []
  const { page } = mountPage(t, 'views/evidence/EvidenceList.vue', {
    confirm: () => new Promise(resolve => confirmations.push(resolve)),
    close: () => { closed++ },
    api: { remove: async (...args) => writes.push(args) },
  })
  page.activate()
  const first = page.remove({ id: '旧条目', title: '旧条目', revision: 1 })
  page.deactivate()
  assert.equal(closed, 1)
  assert.equal(page.removingId.value, '')
  page.activate()
  const second = page.remove({ id: '新条目', title: '新条目', revision: 2 })
  confirmations[0]()
  await first
  assert.equal(page.removingId.value, '新条目')
  assert.deepEqual(writes, [])
  confirmations[1]()
  await second
  assert.deepEqual(writes, [['新条目', 2]])
  assert.equal(page.removingId.value, '')
})

test('删除确认离页后即使返回也不提交旧操作，正常删除携带修订号', async t => {
  let confirm
  const calls = []
  const state = mountPage(t, 'views/evidence/EvidenceList.vue', { confirm: () => new Promise(resolve => { confirm = resolve }), api: { remove: async (...args) => calls.push(args) } })
  state.page.activate()
  const request = state.page.remove({ id: 'chain', title: '测试', revision: 7 })
  state.page.deactivate()
  state.page.activate()
  confirm()
  await request
  assert.deepEqual(calls, [])
  const current = state.page.remove({ id: 'chain', title: '测试', revision: 8 })
  confirm()
  await current
  assert.deepEqual(calls, [['chain', 8]])
})

test('新建证据链须完成手机两步并有创建权限，提交保留选中模板和目的', async t => {
  const calls = []
  const { page, props, permissions, navigations } = mountPage(t, 'components/evidence/EvidenceCreateDialog.vue', { api: { create: async payload => { calls.push(payload); return { data: { id: 'new-chain' } } } } })
  props.modelValue = true
  await nextTick()
  page.title.value = '  测试判断  '
  page.purpose.value = ' 核验材料 '
  await page.create()
  assert.equal(calls.length, 0)
  page.step.value = 2
  page.template.value = 'proof'
  permissions.value = []
  await page.create()
  assert.equal(calls.length, 0)
  permissions.value = ['*']
  await page.create()
  assert.deepEqual(calls[0], { template: 'proof', title: '测试判断', purpose: '核验材料', nodes: [], edges: [] })
  assert.deepEqual(navigations, ['/evidence/chains/new-chain'])
})

test('关闭或离开创建表单后，迟到成功不跳转也不覆盖新草稿', async t => {
  let finish
  const state = mountPage(t, 'components/evidence/EvidenceCreateDialog.vue', { api: { create: () => new Promise(resolve => { finish = resolve }) } })
  state.props.modelValue = true
  await nextTick()
  state.page.title.value = '旧草稿'
  state.page.step.value = 2
  const request = state.page.create()
  state.props.modelValue = false
  await nextTick()
  state.props.modelValue = true
  await nextTick()
  state.page.title.value = '当前草稿'
  finish({ data: { id: 'old-chain' } })
  await request
  assert.deepEqual(state.navigations, [])
  assert.equal(state.page.title.value, '当前草稿')
  assert.equal(state.page.step.value, 1)
  assert.equal(state.emitted.some(([name]) => name === 'created'), false)
})

test('创建失败保留资料和步骤，禁止重复提交并允许重试', async t => {
  let fail
  let calls = 0
  const state = mountPage(t, 'components/evidence/EvidenceCreateDialog.vue', { api: { create: () => { calls += 1; return new Promise((resolve, reject) => { fail = reject }) } } })
  state.props.modelValue = true
  await nextTick()
  state.page.title.value = '需要保留'
  state.page.step.value = 2
  const request = state.page.create()
  await state.page.create()
  assert.equal(calls, 1)
  fail(new Error('版本服务不可用'))
  await request
  assert.equal(state.page.title.value, '需要保留')
  assert.equal(state.page.step.value, 2)
  assert.equal(state.page.error.value, '版本服务不可用')
  assert.equal(state.page.busy.value, false)
})
