import { getAuthState } from '@/stores/auth'
import { handleApiAuthorizationFailure } from '@/utils/request'

export class AgentSseError extends Error {
    constructor(message, { code = null, status = null, kind = 'protocol', retryable = false } = {}) {
        super(message)
        this.name = 'AgentSseError'
        this.code = code
        this.status = status
        this.kind = kind
        this.retryable = retryable
    }
}

/**
 * 使用 Bearer Token 建立 SSE 连接并逐条派发事件。
 * @param {string} url
 * @param {{ signal?: AbortSignal, onOpen?: () => void, onEvent?: (event: { type: string, data: string, lastEventId: string }) => void }} options
 */
export async function openAuthenticatedSse(url, { signal, onOpen, onEvent } = {}) {
    const token = getAuthState().accessToken
    if (!token) {
        const message = '未登录或登录状态无效'
        await handleApiAuthorizationFailure({
            code: 240100,
            message,
            requestUrl: url,
        })
        throw new AgentSseError(message, { code: 240100, kind: 'unauthorized' })
    }

    let response
    try {
        response = await fetch(url, {
            method: 'GET',
            headers: {
                Accept: 'text/event-stream',
                Authorization: `Bearer ${token}`,
            },
            cache: 'no-store',
            signal,
        })
    } catch (error) {
        if (signal?.aborted || error?.name === 'AbortError') throw error
        throw new AgentSseError(error?.message || '无法连接实时事件服务', {
            kind: 'network',
            retryable: true,
        })
    }

    const contentType = String(response.headers.get('content-type') || '').toLowerCase()
    if (!response.ok || !contentType.includes('text/event-stream')) {
        let payload = null
        let responseText = ''
        try {
            responseText = await response.text()
            payload = responseText ? JSON.parse(responseText) : null
        } catch {
            payload = null
        }

        const code = typeof payload?.code === 'number' ? payload.code : null
        const message = payload?.message || responseText || (
            response.ok ? '实时事件服务返回了无效响应' : `实时事件服务请求失败（HTTP ${response.status}）`
        )
        const failureKind = await handleApiAuthorizationFailure({
            code,
            httpStatus: response.status,
            message,
            requestUrl: url,
        })
        const retryable = failureKind === 'other' && (
            response.status === 408 || response.status === 429 || response.status >= 500
        )
        throw new AgentSseError(message, {
            code,
            status: response.status,
            kind: failureKind === 'other' ? 'protocol' : failureKind,
            retryable,
        })
    }
    if (!response.body) {
        throw new AgentSseError('实时事件响应不支持流式读取')
    }

    onOpen?.()

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let eventType = ''
    let dataLines = []
    let lastEventId = ''

    function dispatchEvent() {
        if (dataLines.length > 0) {
            onEvent?.({
                type: eventType || 'message',
                data: dataLines.join('\n'),
                lastEventId,
            })
        }
        eventType = ''
        dataLines = []
    }

    function consumeLine(rawLine) {
        const line = rawLine.startsWith('\uFEFF') ? rawLine.slice(1) : rawLine
        if (!line) {
            dispatchEvent()
            return
        }
        if (line.startsWith(':')) return

        const colonIndex = line.indexOf(':')
        const field = colonIndex >= 0 ? line.slice(0, colonIndex) : line
        let value = colonIndex >= 0 ? line.slice(colonIndex + 1) : ''
        if (value.startsWith(' ')) value = value.slice(1)

        if (field === 'event') eventType = value
        else if (field === 'data') dataLines.push(value)
        else if (field === 'id' && !value.includes('\0')) lastEventId = value
    }

    function drainBuffer(final = false) {
        while (buffer) {
            const match = /[\r\n]/.exec(buffer)
            if (!match) break
            const index = match.index
            if (!final && buffer[index] === '\r' && index === buffer.length - 1) break
            const newlineLength = buffer[index] === '\r' && buffer[index + 1] === '\n' ? 2 : 1
            consumeLine(buffer.slice(0, index))
            buffer = buffer.slice(index + newlineLength)
        }
        if (final && buffer) {
            consumeLine(buffer)
            buffer = ''
        }
    }

    try {
        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            drainBuffer()
        }
        buffer += decoder.decode()
        drainBuffer(true)
        dispatchEvent()
    } finally {
        reader.releaseLock()
    }
}
