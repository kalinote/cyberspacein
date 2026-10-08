import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, nextTick, ref, toValue, watch } from 'vue'

// 使用真实会话组合函数，注入可控接口响应以验证切换与卸载边界。
const source = readFileSync(new URL('../src/composables/useAgentSessionStream.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
    .replace('export function useAgentSessionStream', 'function useAgentSessionStream')
const createComposable = new Function('computed', 'nextTick', 'onUnmounted', 'ref', 'toValue', 'watch', 'agentApi', `${source}\nreturn useAgentSessionStream`)

test('快速切换会话时，迟到详情不覆盖当前会话或状态', async () => {
    const pending = []
    const useStream = createComposable(computed, nextTick, () => {}, ref, toValue, watch, {
        getAgentSessionDetail: () => new Promise(resolve => pending.push(resolve)),
    })
    const sessionId = ref('session-a')
    const stream = useStream({ sessionId })
    const oldRequest = stream.loadSessionDetail()
    sessionId.value = 'session-b'
    const newRequest = stream.loadSessionDetail()
    pending[1]({ code: 0, data: { id: 'session-b', agent_id: 'agent-b', status: 'completed' } })
    await newRequest
    pending[0]({ code: 0, data: { id: 'session-a', agent_id: 'agent-a', status: 'running' } })
    assert.equal(await oldRequest, false)
    assert.equal(stream.session.value.id, 'session-b')
    assert.equal(stream.sessionRuntimeStatus.value, 'completed')
})

test('断开会话后，尚未返回的详情不能恢复页面状态', async () => {
    let resolveDetail
    const useStream = createComposable(computed, nextTick, () => {}, ref, toValue, watch, {
        getAgentSessionDetail: () => new Promise(resolve => { resolveDetail = resolve }),
    })
    const stream = useStream({ sessionId: ref('session-a') })
    const request = stream.loadSessionDetail()
    stream.disconnectSSE()
    resolveDetail({ code: 0, data: { id: 'session-a', status: 'running' } })
    assert.equal(await request, false)
    assert.equal(stream.session.value, null)
    assert.equal(stream.sessionRuntimeStatus.value, 'unknown')
})
