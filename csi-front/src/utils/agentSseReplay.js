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
 * 通过临时 EventSource 拉取一页 SSE 回放（不含后续实时事件）。
 * @param {string} url
 * @param {{ expectedLimit: number, eventTypes?: string[], idleMs?: number }} options
 * @returns {Promise<{ events: Array<{ type: string, data: string, lastEventId: string }> }>}
 */
export function fetchReplayBatch(url, { expectedLimit, eventTypes = AGENT_SSE_REPLAY_EVENT_TYPES, idleMs = 400 } = {}) {
    return new Promise((resolve) => {
        /** @type {Array<{ type: string, data: string, lastEventId: string }>} */
        const events = []
        let finished = false
        /** @type {ReturnType<typeof setTimeout> | null} */
        let idleTimer = null
        /** @type {EventSource | null} */
        let es = null

        function finish() {
            if (finished) return
            finished = true
            if (idleTimer) clearTimeout(idleTimer)
            if (es) {
                es.close()
                es = null
            }
            resolve({ events })
        }

        function scheduleIdleFinish() {
            if (idleTimer) clearTimeout(idleTimer)
            idleTimer = setTimeout(finish, idleMs)
        }

        function onNamedEvent(type) {
            return (event) => {
                if (finished) return
                if (events.length >= expectedLimit) return
                events.push({
                    type,
                    data: event.data ?? '',
                    lastEventId: event.lastEventId ?? '',
                })
                scheduleIdleFinish()
                if (events.length >= expectedLimit) finish()
            }
        }

        try {
            es = new EventSource(url)
            es.onerror = () => finish()
            for (const name of eventTypes) {
                es.addEventListener(name, onNamedEvent(name))
            }
            es.onmessage = onNamedEvent('message')
            scheduleIdleFinish()
        } catch {
            finish()
        }
    })
}
