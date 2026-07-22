import { openAuthenticatedSse } from '@/utils/agentSseClient'

export const AGENT_SSE_REPLAY_EVENT_TYPES = [
    'user_message',
    'status',
    'todos',
    'result',
    'notification',
    'debug_prompt',
    'progress',
    'step',
    'task_submitted',
    'stream',
    'stream_end',
    'reasoning_stream',
    'approval_required',
]

/**
 * 通过临时鉴权连接拉取一页 SSE 回放（不含后续实时事件）。
 * @param {string} url
 * @param {{ expectedLimit: number, eventTypes?: string[], idleMs?: number }} options
 * @returns {Promise<{ events: Array<{ type: string, data: string, lastEventId: string }> }>}
 */
export function fetchReplayBatch(url, { expectedLimit, eventTypes = AGENT_SSE_REPLAY_EVENT_TYPES, idleMs = 400 } = {}) {
    return new Promise((resolve, reject) => {
        /** @type {Array<{ type: string, data: string, lastEventId: string }>} */
        const events = []
        let finished = false
        /** @type {ReturnType<typeof setTimeout> | null} */
        let idleTimer = null
        const controller = new AbortController()
        const allowedTypes = new Set(eventTypes)

        function finish() {
            if (finished) return
            finished = true
            if (idleTimer) clearTimeout(idleTimer)
            controller.abort()
            resolve({ events })
        }

        function scheduleIdleFinish() {
            if (idleTimer) clearTimeout(idleTimer)
            idleTimer = setTimeout(finish, idleMs)
        }

        scheduleIdleFinish()
        openAuthenticatedSse(url, {
            signal: controller.signal,
            onOpen: scheduleIdleFinish,
            onEvent: (event) => {
                if (finished || (event.type !== 'message' && !allowedTypes.has(event.type))) return
                if (events.length >= expectedLimit) return
                events.push(event)
                scheduleIdleFinish()
                if (events.length >= expectedLimit) finish()
            },
        }).then(finish).catch((error) => {
            if (finished && controller.signal.aborted) return
            finished = true
            if (idleTimer) clearTimeout(idleTimer)
            controller.abort()
            reject(error)
        })
    })
}
