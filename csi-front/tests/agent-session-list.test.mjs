import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref } from 'vue'

const source = readFileSync(new URL('../src/views/agent/AgentSessionList.vue', import.meta.url), 'utf8')
const fetchCode = source.slice(source.indexOf('async function fetchSessions()'), source.indexOf('async function loadAgentOptions()'))
const lifecycleCode = source.slice(source.indexOf('onDeactivated(() =>'), source.indexOf('onUnmounted(() =>'))
const createFetcher = new Function('agentApi', 'ref', `
  let sessionRequest = 0;
  let needsSessionRefresh = false;
  const hooks = {};
  const onDeactivated = callback => { hooks.deactivate = callback };
  const onActivated = callback => { hooks.activate = callback };
  const mobileFiltersOpen = ref(true);
  const loading = ref(false), fetchError = ref(''), sessions = ref([{ id: '原有会话' }]);
  const pagination = ref({ page: 1, pageSize: 20, total: 1 });
  const buildQueryParams = () => ({ page: 1, page_size: 20 });
  ${fetchCode}
  ${lifecycleCode}
  return { fetchSessions, loading, fetchError, sessions, pagination, mobileFiltersOpen, hooks };
`)

test('会话接口失败显示错误，保留原有数据而不伪装成空列表', async () => {
    for (const getAgentSessionList of [
        async () => { throw new Error('网络中断') },
        async () => ({ code: 500, message: '服务异常' }),
        async () => ({ code: 0, data: null }),
    ]) {
        const state = createFetcher({ getAgentSessionList }, ref)
        await state.fetchSessions()
        assert.equal(state.fetchError.value, '会话加载失败，请重试')
        assert.deepEqual(state.sessions.value, [{ id: '原有会话' }])
        assert.equal(state.loading.value, false)
    }
})

test('有效空结果正常清空列表并允许重试后恢复数据', async () => {
    let response = { code: 0, data: { items: [], total: 0, page: 1, page_size: 20 } }
    const state = createFetcher({ getAgentSessionList: async () => response }, ref)
    await state.fetchSessions()
    assert.equal(state.fetchError.value, '')
    assert.deepEqual(state.sessions.value, [])
    response = { items: [{ id: '新会话' }], total: 1, page: 2, page_size: 20 }
    await state.fetchSessions()
    assert.deepEqual(state.sessions.value, [{ id: '新会话' }])
    assert.equal(state.pagination.value.page, 2)
})

test('缓存离开关闭筛选抽屉并拒绝旧响应，回来重新加载当前筛选', async () => {
    const pending = []
    const state = createFetcher({ getAgentSessionList: () => new Promise(resolve => pending.push(resolve)) }, ref)
    const oldRequest = state.fetchSessions()
    state.hooks.deactivate()
    assert.equal(state.mobileFiltersOpen.value, false)
    assert.equal(state.loading.value, false)
    pending[0]({ code: 0, data: { items: [{ id: '过期会话' }], total: 1 } })
    await oldRequest
    assert.deepEqual(state.sessions.value, [{ id: '原有会话' }])
    state.hooks.activate()
    assert.equal(pending.length, 2)
    assert.equal(state.loading.value, true)
    pending[1]({ code: 0, data: { items: [{ id: '最新会话' }], total: 1 } })
    await Promise.resolve()
    await Promise.resolve()
    assert.deepEqual(state.sessions.value, [{ id: '最新会话' }])
    assert.equal(state.loading.value, false)
})
