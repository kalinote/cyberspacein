import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import { normalizeRecentVisit } from '../src/utils/recentVisitPolicy.js'
import { hasAllForPermissions } from '../src/utils/permissionPolicy.js'
import { PERM } from '../src/utils/permissions.js'

const storageKey = 'csi_recent_visits_v1'
const articlePermissions = [PERM.pages.search.access, PERM.operations.content.article.read]
const articleRoute = { name: 'article-detail', params: { uuid: 'article-1' }, query: { redirect: 'https://example.com', token: '不应保存' } }
const recentSource = readFileSync(new URL('../src/stores/recentVisits.js', import.meta.url), 'utf8')
  .replace(/^import .*\r?\n/gm, '')
  .replace(/^export /gm, '')
const loadRecentStore = new Function('computed', 'ref', 'watch', 'getAuthState', 'normalizeRecentVisit', 'sessionStorage', `${recentSource}\nreturn { recentVisits, rememberRecentVisit, clearRecentVisits }`)
const { descriptor } = parse(readFileSync(new URL('../src/components/mobile/MobileWorkbench.vue', import.meta.url), 'utf8'))
const workbenchSource = compileScript(descriptor, { id: 'mobile-workbench-test' }).content
  .replace(/^import .*\r?\n/gm, '')
  .replace('export default', 'return')

/** """用真实响应式登录状态与内存存储加载最近访问模块。""" */
function createRecentHarness(t, saved = null, blockedStorage = false) {
  const auth = reactive({ accessToken: '测试令牌', sessionId: 'session-1', user: { id: 'user-1' }, permissions: [...articlePermissions] })
  const storage = new Map(saved == null ? [] : [[storageKey, saved]])
  const sessionStorage = {
    getItem(key) { if (blockedStorage) throw new Error('禁止存储'); return storage.get(key) ?? null },
    setItem(key, value) { if (blockedStorage) throw new Error('禁止存储'); storage.set(key, value) },
    removeItem(key) { if (blockedStorage) throw new Error('禁止存储'); storage.delete(key) },
  }
  const scope = effectScope()
  const store = scope.run(() => loadRecentStore(computed, ref, watch, () => auth, normalizeRecentVisit, sessionStorage))
  t.after(() => scope.stop())
  return { auth, storage, store }
}

/**
 * 加载工作台真实 setup，替换接口、定时器与生命周期以验证权限和异步边界。
 * @param {object} t 测试上下文。
 * @param {object} options 初始权限、激活状态和接口替身。
 * @returns {object} 工作台状态、请求记录与生命周期控制入口。
 */
function createWorkbenchHarness(t, options = {}) {
  const auth = reactive({ user: { id: 'user-1' }, permissions: options.permissions || ['*'] })
  const props = reactive({ active: options.active ?? true })
  const calls = []
  const intervals = new Set()
  const hooks = { mounted: [], activated: [], deactivated: [], beforeUnmount: [] }
  const invoke = (method, params, config) => {
    calls.push({ method, params, config })
    return options.request?.(method, params, config) ?? Promise.resolve(method === 'stats'
      ? { code: 0, data: { firing: 2, acknowledged: 1 } }
      : method === 'summary'
        ? { code: 0, data: { running: 3, failed: 4, partially_completed: 5 } }
        : { items: [], total: 0 })
  }
  const bindings = {
    computed, reactive, ref, watch, useRouter: () => ({ push() {} }), Icon: {},
    onMounted: hook => hooks.mounted.push(hook), onActivated: hook => hooks.activated.push(hook),
    onDeactivated: hook => hooks.deactivated.push(hook), onBeforeUnmount: hook => hooks.beforeUnmount.push(hook),
    getAuthState: () => auth, PERM,
    hasAll: codes => hasAllForPermissions(auth.permissions, codes), hasPerm: code => hasAllForPermissions(auth.permissions, [code]),
    recentVisits: ref([]), clearRecentVisits() {},
    getStatusTagType() {}, getStatusText() {}, getAgentSessionStatusLabel() {}, getAgentSessionStatusTagType() {},
    alertApi: { getStats: config => invoke('stats', undefined, config), getInstances: (params, config) => invoke('alerts', params, config) },
    actionApi: { getActionHistorySummary: config => invoke('summary', undefined, config), getActionHistory: (params, config) => invoke('actions', params, config) },
    agentApi: { getAgentSessionList: (params, config) => invoke('sessions', params, config) },
    window: { setInterval: callback => { intervals.add(callback); return callback }, clearInterval: id => intervals.delete(id) },
    document: { visibilityState: 'visible' },
  }
  const component = new Function(...Object.keys(bindings), workbenchSource)(...Object.values(bindings))
  const scope = effectScope()
  const page = scope.run(() => component.setup(props, { expose() {} }))
  t.after(() => { page.deactivate(); scope.stop() })
  return { auth, props, page, hooks, calls, intervals }
}

test('最近访问仅持久化内部路由必要字段，并保留标题与八条去重记录', t => {
  const { store, storage } = createRecentHarness(t)
  store.rememberRecentVisit(articleRoute, '调查材料')
  store.rememberRecentVisit(articleRoute)
  assert.equal(store.recentVisits.value.length, 1)
  assert.equal(store.recentVisits.value[0].title, '调查材料')
  assert.deepEqual(store.recentVisits.value[0].query, {})
  assert.doesNotMatch(storage.get(storageKey), /redirect|不应保存/)
  for (let i = 2; i <= 10; i++) store.rememberRecentVisit({ name: 'article-detail', params: { uuid: `article-${i}` } })
  assert.equal(store.recentVisits.value.length, 8)
  assert.equal(store.recentVisits.value[0].params.uuid, 'article-10')
})

test('最近访问仅恢复同一会话，换会话和退出同步清除内存与存储', t => {
  const saved = JSON.stringify({ sessionId: 'session-1', items: [{ ...articleRoute, title: '旧账号材料' }] })
  const { auth, store, storage } = createRecentHarness(t, saved)
  assert.equal(store.recentVisits.value.length, 1)
  auth.sessionId = 'session-2'
  auth.user = { id: 'user-2' }
  assert.equal(store.recentVisits.value.length, 0)
  assert.equal(storage.has(storageKey), false)
  store.rememberRecentVisit(articleRoute, '新账号材料')
  auth.accessToken = null
  assert.equal(store.recentVisits.value.length, 0)
  assert.equal(storage.has(storageKey), false)
})

test('撤销读取权限立即隐藏历史入口，通配管理员权限仍可读取', t => {
  const { auth, store } = createRecentHarness(t)
  store.rememberRecentVisit(articleRoute)
  auth.permissions = [PERM.pages.search.access]
  assert.equal(store.recentVisits.value.length, 0)
  store.rememberRecentVisit(articleRoute, '无读取权限时不能保存')
  auth.permissions = ['*']
  assert.equal(store.recentVisits.value.length, 1)
  assert.notEqual(store.recentVisits.value[0].title, '无读取权限时不能保存')
})

test('畸形存储记录与原型键不会破坏最近访问，有效记录可安全降级标题', t => {
  const saved = JSON.stringify({ sessionId: 'session-1', items: [
    null, {}, { name: '__proto__' }, { name: 'constructor' }, { name: { toString: null } },
    { ...articleRoute, title: { toString: null } }, { name: 'article-detail', params: { uuid: '../../outside' } },
  ] })
  const { store } = createRecentHarness(t, saved)
  assert.doesNotThrow(() => store.recentVisits.value)
  assert.equal(store.recentVisits.value.length, 1)
  assert.match(store.recentVisits.value[0].title, /^文章阅读/)
  for (const invalid of ['{', 'null', '[]', JSON.stringify({ sessionId: 'another', items: [articleRoute] })]) {
    assert.deepEqual(createRecentHarness(t, invalid).store.recentVisits.value, [])
  }
})

test('禁止浏览器存储时最近访问仍可在内存记录和清除', t => {
  const { store } = createRecentHarness(t, null, true)
  assert.doesNotThrow(() => store.rememberRecentVisit(articleRoute))
  assert.equal(store.recentVisits.value.length, 1)
  store.clearRecentVisits()
  assert.equal(store.recentVisits.value.length, 0)
})

test('会话最近访问只保存所属引擎标识，不携带注入参数或外部链接', () => {
  const item = normalizeRecentVisit({ name: 'agent-analysis-detail', params: { sessionId: 'session-a' }, query: { agent_id: 'agent-a', injection_param: '私有实体参数', redirect: '//example.com' } }, ['*'])
  assert.deepEqual(item.query, { agent_id: 'agent-a' })
  assert.equal(normalizeRecentVisit({ name: 'agent-analysis-detail', params: { sessionId: 'session-a' }, query: { agent_id: '//example.com' } }, ['*']), null)
})

test('缓存首页隐藏期间挂载手机工作台不会请求，激活后只创建一个轮询', async t => {
  const { props, page, hooks, calls, intervals } = createWorkbenchHarness(t, { active: false })
  for (const hook of hooks.mounted) hook()
  for (const hook of hooks.activated) hook()
  assert.equal(calls.length, 0)
  props.active = true
  await nextTick()
  await page.refresh()
  assert.equal(intervals.size, 1)
  assert.ok(calls.every(call => call.config?.silent === true))
  props.active = false
  await nextTick()
  assert.equal(intervals.size, 0)
  const count = calls.length
  await page.refresh()
  assert.equal(calls.length, count)
})

test('工作台独立处理失败区块，真实汇总字段不伪装成成功空数据', async t => {
  const { page } = createWorkbenchHarness(t, { request: method => method === 'stats' ? Promise.reject(new Error('网络不可用')) : undefined })
  page.activate()
  await page.refresh()
  assert.equal(page.alerts.error, true)
  assert.equal(page.alerts.data, null)
  assert.equal(page.actions.error, false)
  assert.equal(page.actions.data.failed, 4)
  assert.equal(page.actions.data.partial, 5)
  assert.equal(page.sessions.error, false)
})

test('撤销权限和停用工作台后，旧响应不能恢复此前可读的告警', async t => {
  const pending = []
  const permissions = [PERM.pages.system.alert.visible, PERM.pages.system.alert.access, PERM.operations.alert.instance.read]
  const { page, auth, calls } = createWorkbenchHarness(t, { permissions, request: () => new Promise(resolve => pending.push(resolve)) })
  page.activate()
  assert.equal(calls.length, 3)
  auth.permissions = []
  await nextTick()
  for (const resolve of pending.splice(0)) resolve({ code: 0, data: { firing: 10, items: [{ id: '不可再读' }] } })
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(page.alerts.data, null)
  auth.permissions = permissions
  await nextTick()
  page.deactivate()
  for (const resolve of pending.splice(0)) resolve({ code: 0, data: { firing: 10, items: [{ id: '已离页' }] } })
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(page.alerts.data, null)
})
