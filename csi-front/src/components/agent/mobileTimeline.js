const PROCESS_KINDS = new Set(['assistant_reasoning_stream', 'tool_activity', 'todos'])

/**
 * 将连续过程事件折叠成组，保留消息、审批、失败及结果的原始顺序。
 * @param {Array} items 已整理的事件时间线。
 * @returns {Array} 可直接渲染的事件或过程分组。
 */
export function groupMobileTimeline(items) {
    const groups = []
    for (const item of items) {
        const process = PROCESS_KINDS.has(item.kind) && !item.error
            && !(item.toolEvents || []).some(event => event.status === 'error' || event.error)
        const previous = groups.at(-1)
        if (process && previous?.kind === 'process_group') {
            previous.items.push(item)
        } else if (process) {
            groups.push({ kind: 'process_group', displayKey: `process-${item.displayKey || item.id}`, items: [item] })
        } else {
            groups.push(item)
        }
    }
    return groups
}
