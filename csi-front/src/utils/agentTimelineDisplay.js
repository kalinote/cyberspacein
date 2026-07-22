import { stringifyJsonSafe } from '@/utils/agentSse'

function normalizeComparableText(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function buildToolCallKey(call) {
    return `${call?.name || call?.tool || '?'}|${stringifyJsonSafe(call?.arguments ?? {}, 0)}`
}

/**
 * 将原始 SSE 时间线转换为适合连续阅读的展示条目。
 * 技术事件会集中到运行详情，同一轮工具步骤会合并，重复回答只保留一份。
 */
export function buildAgentTimelineDisplay(rawItems) {
    const slots = []
    const technicalItems = []
    const toolGroups = new Map()
    let turnIndex = 0
    let latestRuntimeStatus = ''

    for (const rawItem of Array.isArray(rawItems) ? rawItems : []) {
        if (!rawItem || typeof rawItem !== 'object') continue

        const item = {
            ...rawItem,
            displayKey: `event-${rawItem.id}`,
            displayTurn: turnIndex,
        }

        if (item.kind === 'status' && item.payload?.status != null) {
            latestRuntimeStatus = String(item.payload.status)
        } else if (item.kind === 'result' && item.payload?.status != null) {
            latestRuntimeStatus = String(item.payload.status)
        }

        if (item.kind === 'user_message') {
            turnIndex += 1
            item.displayTurn = turnIndex
            slots.push(item)
            continue
        }

        item.displayTurn = turnIndex
        const systemSubtype = String(item.systemSubtype || '').toLowerCase()
        const isSystemError = item.kind === 'system' && /error|failed/.test(systemSubtype)
        if (
            item.kind === 'status'
            || item.kind === 'debug_prompt'
            || (item.kind === 'system' && !isSystemError)
        ) {
            technicalItems.push(item)
            continue
        }

        if (item.kind !== 'step') {
            slots.push(item)
            continue
        }

        const phase = item.payload?.phase
        const step = item.payload?.step && typeof item.payload.step === 'object'
            ? item.payload.step
            : null
        const iteration = item.payload?.iteration ?? step?.iteration ?? '—'
        const beforeCalls = Array.isArray(item.payload?.tool_calls) ? item.payload.tool_calls : []
        const afterCalls = Array.isArray(step?.tool_calls) ? step.tool_calls : []
        const toolEvents = Array.isArray(step?.tool_events) ? step.tool_events : []
        const groupKey = `${turnIndex}:${item.payload?.session_id || ''}:${iteration}`
        const existingGroup = toolGroups.get(groupKey)
        const hasToolActivity = beforeCalls.length || afterCalls.length || toolEvents.length || existingGroup

        if (hasToolActivity) {
            let group = existingGroup
            if (!group) {
                group = {
                    id: `tool-${item.id}`,
                    displayKey: `tool-${item.id}`,
                    displayTurn: turnIndex,
                    kind: 'tool_activity',
                    sseType: 'step',
                    ts: item.ts,
                    updatedTs: item.updatedTs || item.ts,
                    iteration,
                    running: phase === 'before_tools',
                    toolCalls: [],
                    toolEvents: [],
                    usage: {},
                    error: null,
                    stopReason: null,
                    assistantContent: '',
                    rawItems: [],
                }
                toolGroups.set(groupKey, group)
                slots.push(group)
            }

            const knownCalls = new Set(group.toolCalls.map(buildToolCallKey))
            for (const call of [...beforeCalls, ...afterCalls]) {
                const key = buildToolCallKey(call)
                if (knownCalls.has(key)) continue
                knownCalls.add(key)
                group.toolCalls.push({
                    name: call?.name || call?.tool || '?',
                    arguments: call?.arguments ?? {},
                })
            }
            group.rawItems.push(item)
            group.updatedTs = item.updatedTs || item.ts || group.updatedTs

            if (phase === 'after_iteration') {
                group.running = false
                group.toolEvents = toolEvents
                group.usage = step?.usage && typeof step.usage === 'object' ? step.usage : {}
                group.error = step?.error ?? null
                group.stopReason = step?.stop_reason ?? null
                group.assistantContent = String(step?.content ?? '')
            }
            continue
        }

        const stepContent = String(step?.content ?? '').trim()
        if (stepContent) {
            slots.push({
                ...item,
                kind: 'step_answer_candidate',
                text: stepContent,
                streaming: false,
                resuming: false,
            })
        } else {
            technicalItems.push(item)
        }
    }

    const answerTextsByTurn = new Map()
    const toolNamesByTurn = new Map()
    for (const item of slots) {
        if (item.kind === 'assistant_stream') {
            const normalized = normalizeComparableText(item.text)
            if (!normalized) continue
            if (!answerTextsByTurn.has(item.displayTurn)) answerTextsByTurn.set(item.displayTurn, new Set())
            answerTextsByTurn.get(item.displayTurn).add(normalized)
        } else if (item.kind === 'task_submitted') {
            const normalized = normalizeComparableText(item.payload?.short_summary)
            if (!normalized) continue
            if (!answerTextsByTurn.has(item.displayTurn)) answerTextsByTurn.set(item.displayTurn, new Set())
            answerTextsByTurn.get(item.displayTurn).add(normalized)
        } else if (item.kind === 'tool_activity') {
            if (!toolNamesByTurn.has(item.displayTurn)) toolNamesByTurn.set(item.displayTurn, new Set())
            const names = toolNamesByTurn.get(item.displayTurn)
            for (const call of item.toolCalls || []) names.add(String(call?.name || ''))
            for (const event of item.toolEvents || []) names.add(String(event?.name || ''))
            names.delete('')
        }
    }

    const activityItems = []
    const lastTodosByTurn = new Map()
    for (const item of slots) {
        if (!answerTextsByTurn.has(item.displayTurn)) answerTextsByTurn.set(item.displayTurn, new Set())
        const turnAnswers = answerTextsByTurn.get(item.displayTurn)

        if (item.kind === 'progress' && item.payload?.tool_hint) {
            const hintParts = String(item.payload?.content || '')
                .split(/[\s,，、]+/)
                .map((part) => part.trim())
                .filter(Boolean)
            const toolNames = toolNamesByTurn.get(item.displayTurn)
            if (hintParts.length && toolNames && hintParts.every((part) => toolNames.has(part))) continue
        }

        if (item.kind === 'todos') {
            const todosKey = stringifyJsonSafe(item.payload?.todos ?? item.payload ?? [], 0)
            if (lastTodosByTurn.get(item.displayTurn) === todosKey) continue
            lastTodosByTurn.set(item.displayTurn, todosKey)
        }

        if (item.kind === 'step_answer_candidate') {
            const normalized = normalizeComparableText(item.text)
            if (!normalized || turnAnswers.has(normalized)) continue
            turnAnswers.add(normalized)
            activityItems.push({
                ...item,
                displayKey: `step-answer-${item.id}`,
                kind: 'assistant_stream',
                sseType: 'stream',
            })
            continue
        }

        if (item.kind === 'result') {
            const resultMarkdown = String(item.payload?.result?.user_markdown ?? '')
            const resultSummary = String(item.payload?.result?.short_summary ?? '')
            const markdownNormalized = normalizeComparableText(resultMarkdown)
            const summaryNormalized = normalizeComparableText(resultSummary)
            activityItems.push({
                ...item,
                displayUserMarkdown: markdownNormalized && !turnAnswers.has(markdownNormalized)
                    ? resultMarkdown
                    : '',
                displaySummary: summaryNormalized
                    && summaryNormalized !== markdownNormalized
                    && !turnAnswers.has(summaryNormalized)
                    ? resultSummary
                    : '',
            })
            if (markdownNormalized) turnAnswers.add(markdownNormalized)
            continue
        }

        activityItems.push(item)
    }

    return {
        activityItems,
        runDetails: technicalItems.length
            ? {
                id: 'run-details',
                displayKey: 'run-details',
                kind: 'run_details',
                ts: technicalItems[0]?.ts,
                runtimeStatus: latestRuntimeStatus,
                technicalItems,
            }
            : null,
    }
}
