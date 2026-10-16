import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, ref } from 'vue'

const source = readFileSync(new URL('../src/components/agent/AgentStartButton.vue', import.meta.url), 'utf8')
const confirmCode = source.slice(source.indexOf('async function handleConfirm(payload)'), source.indexOf('defineExpose({ openDialog })'))
const createStart = new Function('agentApi', 'ref', 'computed', `
    let startRequest = 0;
    const props = { disabled: false };
    const internalLoading = ref(false), dialogVisible = ref(true), canStart = ref(true);
    const loading = computed(() => internalLoading.value);
    const emitted = [], notices = [], hooks = {};
    const emit = (...args) => emitted.push(args);
    const ElMessage = { success: value => notices.push(value), error: value => notices.push(value) };
    const onDeactivated = callback => { hooks.deactivate = callback };
    const onUnmounted = callback => { hooks.unmount = callback };
    ${confirmCode}
    return { handleConfirm, emitted, notices, hooks, internalLoading, dialogVisible };
`)

test('缓存离开关闭启动弹窗，迟到成功不会触发旧页面导航', async () => {
    let complete
    const state = createStart({ startAgent: () => new Promise(resolve => { complete = resolve }) }, ref, computed)
    const request = state.handleConfirm({ agent_id: '测试引擎' })
    state.hooks.deactivate()
    assert.equal(state.dialogVisible.value, false)
    assert.equal(state.internalLoading.value, false)
    complete({ code: 0, data: { agent_id: '测试引擎', session_id: '已启动会话' } })
    await request
    assert.equal(state.emitted.some(([event]) => event === 'started'), false)
    assert.deepEqual(state.notices, [])
})

test('页面卸载后旧启动请求不推送导航，当前请求仍正常返回会话', async () => {
    let complete
    const state = createStart({ startAgent: () => new Promise(resolve => { complete = resolve }) }, ref, computed)
    const oldRequest = state.handleConfirm({ agent_id: '测试引擎' })
    state.hooks.unmount()
    complete({ code: 0, data: { agent_id: '测试引擎', session_id: '旧会话' } })
    await oldRequest
    assert.equal(state.emitted.some(([event]) => event === 'started'), false)

    const active = createStart({ startAgent: async () => ({ code: 0, data: { agent_id: '测试引擎', session_id: '当前会话' } }) }, ref, computed)
    await active.handleConfirm({ agent_id: '测试引擎' })
    assert.equal(active.emitted.find(([event]) => event === 'started')[1].sessionId, '当前会话')
    assert.equal(active.internalLoading.value, false)
})
