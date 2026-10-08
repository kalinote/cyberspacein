import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { nextTick, ref, watch, effectScope } from 'vue'
import { PERM } from '../src/utils/permissions.js'

const source = readFileSync(new URL('../src/views/agent/AnalysisDetail.vue', import.meta.url), 'utf8')
const watchCode = source.slice(source.indexOf('watch(showRejectReason,'), source.indexOf('const pageTitle'))
const registerFocus = new Function('watch', 'nextTick', 'showRejectReason', 'isMobile', 'approvalReasonInput', watchCode)
const exitCode = source.slice(source.indexOf('const approvalExit = computed(() => {') + 'const approvalExit = computed(() => {'.length, source.indexOf('const sessionId ='))
const resolveExit = new Function('hasPerm', 'PERM', 'router', 'route', 'window', exitCode.replace(/\}\)\s*$/, ''))

test('手机展开拒绝理由后聚焦并滚动输入框，桌面保持原交互', async () => {
    for (const mobile of [true, false]) {
        const scope = effectScope()
        const show = ref(false)
        const calls = []
        scope.run(() => registerFocus(watch, nextTick, show, ref(mobile), ref({
            focus: () => calls.push('focus'),
            textarea: { scrollIntoView: options => calls.push(options) },
        })))
        show.value = true
        await nextTick()
        await nextTick()
        assert.deepEqual(calls, mobile ? ['focus', { block: 'nearest', inline: 'nearest' }] : [])
        scope.stop()
    }
})

test('审批退出优先可用会话列表，无列表权限时回到有权限的入口', () => {
    const router = {
        getRoutes: () => [{ path: '/', meta: { requiresAuth: true, pagePermission: PERM.pages.overview.access } }],
        resolve: () => ({ matched: [], meta: {} }),
    }
    const route = { path: '/agent/analysis/演示' }
    assert.deepEqual(resolveExit(() => true, PERM, router, route, { history: { state: {} } }), { path: '/agent/sessions', label: '返回会话列表' })
    assert.deepEqual(resolveExit(code => code === PERM.pages.overview.access, PERM, router, route, { history: { state: {} } }), { path: '/', label: '返回可用页面' })
    assert.deepEqual(resolveExit(() => false, PERM, router, route, { history: { state: {} } }), { path: '/403', label: '返回访问说明' })
})
