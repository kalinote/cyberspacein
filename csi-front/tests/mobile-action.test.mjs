import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { ref } from 'vue'
import { babelParse, compileScript, parse } from 'vue/compiler-sfc'
import { ACTION_STATUS } from '../src/utils/action/status.js'
import { PERM } from '../src/utils/permissions.js'
import { fetchMobileActionPage } from '../src/components/action/mobile/mobileActionData.js'

/**
 * 加载真实移动行动控制逻辑，替换权限、确认弹窗和网络调用。
 * @param {object} options 权限、确认行为以及接口实现。
 * @returns {object} 操作入口、请求记录和提示记录。
 */
function loadOperations({ allowed = true, confirm = async () => {}, api = {} } = {}) {
  const requests = []
  const messages = []
  const imports = {
    vue: { ref },
    'element-plus': { ElMessage: { success: text => messages.push(text), error: text => messages.push(text) }, ElMessageBox: { confirm } },
    '@/api/action': { actionApi: Object.fromEntries(['pauseAction', 'resumeAction', 'stopAction', 'retryAction'].map(method => [method,
      api[method] || (async id => { requests.push({ method, id }); return { code: 0, data: { action_id: 'new-action' } } })
    ])) },
    '@/utils/action': { ACTION_STATUS },
    '@/utils/permissions': { PERM },
    '@/utils/permissionKit': { guardPermission: permission => allowed && permission === PERM.operations.action.instance.execute }
  }
  let code = readFileSync(new URL('../src/components/action/mobile/actionOperations.js', import.meta.url), 'utf8')
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(node.source.value)}][${JSON.stringify(specifier.imported.name)}];`).join('\n') + code.slice(node.end)
  }
  const module = new Function('imports', `${code.replaceAll('export function', 'function')}\nreturn { getActionOperations, useMobileActionOperations }`)(imports)
  return { ...module, requests, messages }
}

test('行动状态只提供既有可执行操作，等待与终止状态不能误恢复', () => {
  const { getActionOperations } = loadOperations()
  assert.deepEqual(getActionOperations(ACTION_STATUS.RUNNING), ['pause', 'stop'])
  assert.deepEqual(getActionOperations(ACTION_STATUS.PAUSED), ['resume', 'stop'])
  for (const status of [ACTION_STATUS.FAILED, ACTION_STATUS.TIMEOUT, ACTION_STATUS.COMPLETED, ACTION_STATUS.PARTIALLY_COMPLETED]) assert.deepEqual(getActionOperations(status), ['retry'])
  for (const status of [ACTION_STATUS.QUEUED, ACTION_STATUS.WAITING, ACTION_STATUS.AWAITING_APPROVAL, ACTION_STATUS.STOPPED, ACTION_STATUS.CANCELLED]) assert.deepEqual(getActionOperations(status), [])
})

test('权限拒绝与不允许的状态不请求操作接口', async () => {
  let confirms = 0
  const denied = loadOperations({ allowed: false, confirm: async () => confirms++ })
  await denied.useMobileActionOperations().operateAction({ id: 'one', status: 'running' }, 'pause')
  assert.equal(confirms, 0)
  assert.equal(denied.requests.length, 0)
  const readOnly = loadOperations()
  await readOnly.useMobileActionOperations().operateAction({ id: 'two', status: 'stopped' }, 'resume')
  assert.equal(readOnly.requests.length, 0)
})

test('取消停止确认不会调用接口，也不会遗留加载状态', async () => {
  const module = loadOperations({ confirm: async () => { throw 'cancel' } })
  const state = module.useMobileActionOperations()
  await state.operateAction({ id: 'one', status: 'running' }, 'stop')
  assert.equal(module.requests.length, 0)
  assert.equal(module.messages.length, 0)
  assert.equal(state.busyId.value, '')
})

test('确认与请求期间重复点击仅执行一次，成功后刷新来源列表', async () => {
  let confirmAction
  let updates = 0
  const module = loadOperations({ confirm: () => new Promise(resolve => { confirmAction = resolve }) })
  const state = module.useMobileActionOperations({ onUpdated: async () => updates++ })
  const action = { action_id: 'scheduled-action', status: 'running' }
  const pending = state.operateAction(action, 'pause')
  assert.equal(state.busyId.value, 'scheduled-action')
  await state.operateAction(action, 'stop')
  confirmAction()
  await pending
  assert.deepEqual(module.requests, [{ method: 'pauseAction', id: 'scheduled-action' }])
  assert.equal(updates, 1)
  assert.equal(state.busyId.value, '')
})

test('失败与已完成行动都通过重放接口创建新行动，并交付新标识', async () => {
  for (const status of ['failed', 'timeout', 'completed', 'partially_completed']) {
    const module = loadOperations()
    const created = []
    const state = module.useMobileActionOperations({ onCreated: id => created.push(id) })
    await state.operateAction({ id: 'old-action', status }, 'retry')
    assert.deepEqual(module.requests, [{ method: 'retryAction', id: 'old-action' }])
    assert.deepEqual(created, ['new-action'])
  }
})

test('接口失败或重放缺少新行动标识时不报告成功，释放操作锁以便重试', async () => {
  const module = loadOperations({ api: { retryAction: async () => ({ code: 0, data: {} }) } })
  let created = false
  const state = module.useMobileActionOperations({ onCreated: () => { created = true } })
  await state.operateAction({ id: 'one', status: 'failed' }, 'retry')
  assert.equal(created, false)
  assert.deepEqual(module.messages, ['重试失败'])
  assert.equal(state.busyId.value, '')
})

/**
 * 使用真实历史页脚本验证缓存页面轮询生命周期。
 * @param {Function} loadPage 模拟分页请求。
 * @returns {object} 页面状态、生命周期回调及定时器记录。
 */
function loadHistory(loadPage = async () => ({ items: [], pagination: { total: 0, page: 1, pageSize: 20 } })) {
  const hooks = { onMounted: [], onUnmounted: [], onActivated: [], onDeactivated: [] }
  const timers = new Map()
  const listeners = new Map()
  const previousWindow = globalThis.window
  const previousDocument = globalThis.document
  let timerId = 0
  globalThis.window = { setInterval: callback => { timers.set(++timerId, callback); return timerId }, clearInterval: id => timers.delete(id) }
  globalThis.document = { addEventListener: (name, callback) => listeners.set(name, callback), removeEventListener: name => listeners.delete(name) }
  const imports = {
    vue: { ...Vue, ...Object.fromEntries(Object.keys(hooks).map(name => [name, callback => hooks[name].push(callback)])) },
    'vue-router': { useRouter: () => ({ push() {} }) },
    'element-plus': { ElMessage: { success() {}, error() {} }, ElMessageBox: {} },
    '@/utils/action': { ACTION_STATUS },
    '@/utils/request': { getPaginatedData: loadPage },
    '@/components/action/mobile/mobileActionData': { fetchMobileActionPage: loadPage },
    '@/api/action': { actionApi: { getActionHistory() {}, getActionHistorySummary: async () => ({ code: 0, data: {} }) } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: ref(true) }) },
    '@/components/action/mobile/actionOperations': { useMobileActionOperations: () => ({ busyId: ref(''), operateAction() {} }) }
  }
  const { descriptor } = parse(readFileSync(new URL('../src/views/action/ActionHistory.vue', import.meta.url), 'utf8'))
  let code = compileScript(descriptor, { id: 'mobile-history' }).content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    imports[node.source.value] ||= {}
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(node.source.value)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const state = component.setup({}, { expose() {} })
  return { state, hooks, timers, listeners, restore: () => { globalThis.window = previousWindow; globalThis.document = previousDocument } }
}

test('历史页进入缓存时停止轮询和监听，返回时只恢复一个定时器', async () => {
  const page = loadHistory()
  try {
    page.hooks.onMounted.forEach(callback => callback())
    await Vue.nextTick()
    assert.equal(page.timers.size, 1)
    page.hooks.onDeactivated.forEach(callback => callback())
    assert.equal(page.timers.size, 0)
    assert.equal(page.listeners.size, 0)
    page.hooks.onActivated.forEach(callback => callback())
    page.hooks.onActivated.forEach(callback => callback())
    await Vue.nextTick()
    assert.equal(page.timers.size, 1)
    assert.equal(page.listeners.size, 1)
    page.hooks.onUnmounted.forEach(callback => callback())
    assert.equal(page.timers.size, 0)
  } finally { page.restore() }
})

test('历史页离开时未完成的请求不会继续执行排队刷新', async () => {
  let resolvePage
  let requests = 0
  const page = loadHistory(() => { requests++; return new Promise(resolve => { resolvePage = resolve }) })
  try {
    page.hooks.onMounted.forEach(callback => callback())
    await page.state.fetchActions(false)
    page.hooks.onDeactivated.forEach(callback => callback())
    resolvePage({ items: [], pagination: { total: 0, page: 1, pageSize: 20 } })
    await Vue.nextTick()
    await Vue.nextTick()
    assert.equal(requests, 1)
    assert.equal(page.timers.size, 0)
  } finally { page.restore() }
})

test('历史页进入缓存关闭日期面板，返回时保留筛选但不重新打开面板', () => {
  const page = loadHistory()
  try {
    page.state.filters.value.dateRange = ['2026-10-01', '2026-10-07']
    page.state.mobileDateVisible.value = true
    page.hooks.onDeactivated.forEach(callback => callback())
    assert.equal(page.state.mobileDateVisible.value, false)
    assert.deepEqual(page.state.filters.value.dateRange, ['2026-10-01', '2026-10-07'])
    page.hooks.onActivated.forEach(callback => callback())
    assert.equal(page.state.mobileDateVisible.value, false)
    page.hooks.onUnmounted.forEach(callback => callback())
  } finally { page.restore() }
})

test('移动行动分页兼容两种成功封装，保留真实空列表', async () => {
  for (const wrapped of [true, false]) {
    const data = { items: [], total: 0, page: 2, page_size: 20, total_pages: 0 }
    const response = await fetchMobileActionPage(async () => wrapped ? { code: 0, data } : data, { page: 2, page_size: 20 })
    assert.deepEqual(response.items, [])
    assert.equal(response.pagination.page, 2)
    assert.equal(response.pagination.pageSize, 20)
  }
})

test('移动行动分页保留网络及业务错误，不将错误转换成空列表', async () => {
  await assert.rejects(fetchMobileActionPage(async () => { throw new Error('网络中断') }, {}), /网络中断/)
  await assert.rejects(fetchMobileActionPage(async () => ({ code: 403, message: '无读取权限' }), {}), /无读取权限/)
  await assert.rejects(fetchMobileActionPage(async () => ({ code: 0, data: {} }), {}), /列表数据暂不可用/)
})
