import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref } from 'vue'

const source = readFileSync(new URL('../src/views/agent/AgentMonitor.vue', import.meta.url), 'utf8')
const fetchCode = source.slice(source.indexOf('async function fetchAgentList()'), source.indexOf('function goToEngineConfig()'))
const createFetcher = new Function('agentApi', 'ref', `
    let agentListRequest = 0;
    const agentList = ref([{ id: '已加载引擎' }]), agentListLoading = ref(false), agentListError = ref(''), isMobile = ref(true);
    ${fetchCode}
    return { fetchAgentList, agentList, agentListLoading, agentListError };
`)

test('手机引擎加载失败保留既有资料并提供明确错误状态', async () => {
    for (const getAgentList of [
        async () => { throw new Error('网络异常') },
        async () => ({ code: 500 }),
        async () => ({ code: 0, data: null }),
    ]) {
        const state = createFetcher({ getAgentList }, ref)
        await state.fetchAgentList()
        assert.equal(state.agentListError.value, '分析引擎加载失败，请重新加载')
        assert.deepEqual(state.agentList.value, [{ id: '已加载引擎' }])
        assert.equal(state.agentListLoading.value, false)
    }
})

test('引擎有效空结果与重试成功不会留下失败状态', async () => {
    let response = { code: 500 }
    const state = createFetcher({ getAgentList: async () => response }, ref)
    await state.fetchAgentList()
    response = { code: 0, data: { items: [], total: 0 } }
    await state.fetchAgentList()
    assert.equal(state.agentListError.value, '')
    assert.deepEqual(state.agentList.value, [])
    response = { code: 0, data: { items: [{ id: '最新引擎' }], total: 1 } }
    await state.fetchAgentList()
    assert.deepEqual(state.agentList.value, [{ id: '最新引擎' }])
})
