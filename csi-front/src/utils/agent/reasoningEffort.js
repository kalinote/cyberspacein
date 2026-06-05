/** @typedef {null | 'low' | 'medium' | 'high' | 'xhigh' | 'max'} ReasoningEffort */

export const REASONING_EFFORT_STEPS = [
    { value: null, label: '关闭' },
    { value: 'low', label: '低' },
    { value: 'medium', label: '中' },
    { value: 'high', label: '高' },
    { value: 'xhigh', label: '超高' },
    { value: 'max', label: '最高' },
]

/**
 * @param {ReasoningEffort | string | undefined} effort
 * @returns {number}
 */
export function reasoningEffortToIndex(effort) {
    const normalized = effort == null || effort === '' ? null : String(effort)
    const idx = REASONING_EFFORT_STEPS.findIndex((s) => s.value === normalized)
    return idx >= 0 ? idx : 0
}

/**
 * @param {number} index
 * @returns {ReasoningEffort}
 */
export function indexToReasoningEffort(index) {
    const i = Number(index)
    if (!Number.isFinite(i)) return null
    const step = REASONING_EFFORT_STEPS[Math.min(Math.max(0, i), REASONING_EFFORT_STEPS.length - 1)]
    return step?.value ?? null
}

/**
 * @param {ReasoningEffort | string | undefined} effort
 * @returns {string}
 */
export function formatReasoningEffortLabel(effort) {
    const idx = reasoningEffortToIndex(effort)
    return REASONING_EFFORT_STEPS[idx]?.label ?? '关闭'
}

/**
 * @param {number} index
 * @returns {string}
 */
export function formatReasoningEffortTooltip(index) {
    return formatReasoningEffortLabel(indexToReasoningEffort(index))
}
