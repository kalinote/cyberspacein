import test from 'node:test'
import assert from 'node:assert/strict'
import { groupMobileTimeline } from '../src/components/agent/mobileTimeline.js'

test('移动会话只折叠相邻过程事件，保留正文、审批和结果顺序', () => {
    const items = [
        { id: 1, kind: 'user_message', text: '分析要求' },
        { id: 2, kind: 'assistant_reasoning_stream' },
        { id: 3, kind: 'tool_activity' },
        { id: 4, kind: 'assistant_stream', text: '分析结论' },
        { id: 5, kind: 'approval_required' },
        { id: 6, kind: 'todos' },
        { id: 7, kind: 'task_submitted' },
        { id: 8, kind: 'result' },
    ]
    const grouped = groupMobileTimeline(items)
    assert.deepEqual(grouped.map(item => item.kind), ['user_message', 'process_group', 'assistant_stream', 'approval_required', 'process_group', 'task_submitted', 'result'])
    assert.deepEqual(grouped.flatMap(item => item.items || [item]), items)
    assert.equal(items[1].items, undefined)
})

test('工具失败与系统错误保持直接可读，不藏入过程折叠组', () => {
    const items = [
        { id: 1, kind: 'tool_activity', error: '执行失败' },
        { id: 2, kind: 'tool_activity', toolEvents: [{ status: 'error' }] },
        { id: 3, kind: 'system', systemSubtype: 'sse_error' },
        { id: 4, kind: 'notification' },
    ]
    assert.deepEqual(groupMobileTimeline(items), items)
})

test('过程分组标识随流式更新保持稳定且空会话可渲染', () => {
    const first = { id: 1, displayKey: 'event-1', kind: 'assistant_reasoning_stream' }
    assert.equal(groupMobileTimeline([first])[0].displayKey, groupMobileTimeline([first, { id: 2, kind: 'tool_activity' }])[0].displayKey)
    assert.deepEqual(groupMobileTimeline([]), [])
})
