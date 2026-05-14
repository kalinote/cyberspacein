export function parseAgentSseData(raw) {
    const text = String(raw ?? '').trim()
    if (!text) return { ok: false, error: 'empty', value: null }
    try {
        return { ok: true, error: null, value: JSON.parse(text) }
    } catch (e) {
        return { ok: false, error: e?.message || 'parse', value: null }
    }
}

export function normalizeTodosListFromPayload(x) {
    if (Array.isArray(x)) return x
    if (x && typeof x === 'object') {
        if (Array.isArray(x.todos)) return x.todos
        if (Array.isArray(x.items)) return x.items
        if (Array.isArray(x.data)) return x.data
    }
    return []
}

export function appendStreamDelta(items, delta, ts, nextId) {
    const d = String(delta ?? '')
    const last = items[items.length - 1]
    if (last && last.kind === 'assistant_stream' && last.streaming === true) {
        last.text = String(last.text ?? '') + d
        last.updatedTs = ts
        return { merged: true }
    }
    items.push({
        id: nextId(),
        sseType: 'stream',
        kind: 'assistant_stream',
        ts,
        updatedTs: ts,
        text: d,
        streaming: true,
        resuming: false,
    })
    return { merged: false }
}

export function closeStreamInTimeline(items, streamEndPayload, ts, nextId) {
    for (let i = items.length - 1; i >= 0; i--) {
        const it = items[i]
        if (it && it.kind === 'assistant_stream' && it.streaming === true) {
            it.streaming = false
            it.resuming = Boolean(streamEndPayload && streamEndPayload.resuming)
            it.streamEndTs = ts
            return { closed: true }
        }
    }
    items.push({
        id: nextId(),
        sseType: 'stream_end',
        kind: 'system',
        ts,
        systemSubtype: 'stream_end_orphan',
        message: '收到流结束信号，但未找到进行中的流式输出',
        payload: streamEndPayload ?? null,
    })
    return { closed: false }
}

export function stringifyJsonSafe(value, space = 2) {
    try {
        return JSON.stringify(value, null, space)
    } catch {
        return String(value)
    }
}
