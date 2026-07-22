import { computed, nextTick, onUnmounted, ref, toValue, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'
import {
    appendReasoningStreamDelta,
    appendStreamDelta,
    closeStreamInTimeline,
    parseAgentSseData,
    stringifyJsonSafe,
} from '@/utils/agentSse'
import { getAgentAutoApproveValue } from '@/composables/useAgentAutoApprove'
import { getApprovalSourceLabel, isApprovalAwaitingUserAction } from '@/utils/agentApproval'
import { TODO_ITEM_STATUS } from '@/utils/action'
import { AgentSseError, openAuthenticatedSse } from '@/utils/agentSseClient'
import { fetchReplayBatch } from '@/utils/agentSseReplay'
import {
    getAgentSessionStatusLabel,
    getAgentSessionStatusTagType,
    isAgentSessionTerminalStatus,
} from '@/utils/agent/sessionStatus'

const DEFAULT_REPLAY_PAGE_SIZE = 20
const AGENT_SSE_TIMELINE_EVENT_TYPES = new Set([
    'notification',
    'debug_prompt',
    'progress',
    'step',
    'task_submitted',
    'stream',
    'stream_end',
    'reasoning_stream',
])

/**
 * @param {object} options
 * @param {import('vue').MaybeRefOrGetter<string>} options.sessionId
 * @param {import('vue').MaybeRefOrGetter<string>} [options.agentId]
 * @param {import('vue').MaybeRefOrGetter<string>} [options.agentIdFallback]
 * @param {import('vue').MaybeRefOrGetter<string>} [options.entityUuid]
 * @param {import('vue').MaybeRefOrGetter<string>} [options.entityType]
 * @param {import('vue').MaybeRefOrGetter<string|object>} [options.injectionParam]
 * @param {number} [options.replayPageSize]
 */
export function useAgentSessionStream(options = {}) {
    const session = ref(null)
    const sessionRuntimeStatus = ref('unknown')
    const sseConnected = ref(false)
    const sseError = ref('')

    const userPrompt = ref('')
    const sendLoading = ref(false)
    const cancelLoading = ref(false)

    const todos = ref([])
    const timelineItems = ref([])

    const replayPageSize = Number(options.replayPageSize) > 0 ? Number(options.replayPageSize) : DEFAULT_REPLAY_PAGE_SIZE
    const historyOffset = ref(0)
    const hasMoreHistory = ref(true)
    const historyLoading = ref(false)
    const replayReadyForPagination = ref(false)

    let timelineSeq = 0
    function nextTimelineId() {
        timelineSeq += 1
        return timelineSeq
    }

    /** @type {AbortController | null} */
    let streamAbortController = null
    /** @type {ReturnType<typeof setTimeout> | null} */
    let retryTimer = null
    let connectionGeneration = 0
    let retryCount = 0
    const maxRetries = 3

    let initialReplayPending = false
    let initialReplayCount = 0
    /** @type {ReturnType<typeof setTimeout> | null} */
    let initialReplayIdleTimer = null
    /** @type {ReturnType<typeof setTimeout> | null} */
    let loadOlderDebounceTimer = null

    const showApprovalDialog = ref(false)
    const pendingApproval = ref(null)
    const approvalReason = ref('')
    const showRejectReason = ref(false)
    const approvalLoading = ref(false)

    const eventsScrollEl = ref(null)
    const isEventsScrollAtBottom = ref(true)
    /** @type {ResizeObserver | null} */
    let eventsScrollResizeObserver = null

    const sessionId = computed(() => String(toValue(options.sessionId) || ''))
    const resolvedAgentId = computed(() => {
        const fromSession = session.value?.agent_id
        if (fromSession) return String(fromSession)
        const direct = toValue(options.agentId)
        if (direct) return String(direct)
        const fallback = toValue(options.agentIdFallback)
        return fallback ? String(fallback) : ''
    })
    const entityUuid = computed(() => String(toValue(options.entityUuid) || ''))
    const entityType = computed(() => String(toValue(options.entityType) || ''))

    const approvalDialogTitle = computed(() => {
        const label = getApprovalSourceLabel(pendingApproval.value?.source)
        return `审批请求 · ${label}`
    })

    function pushSystemTimeline(systemSubtype, message, payload = null) {
        const ts = new Date().toISOString()
        let metaJson = null
        if (payload != null && typeof payload === 'object') {
            try {
                metaJson = stringifyJsonSafe(payload, 2)
            } catch {
                metaJson = null
            }
        } else if (payload != null) {
            metaJson = String(payload)
        }
        timelineItems.value.push({
            id: nextTimelineId(),
            sseType: 'system',
            kind: 'system',
            ts,
            systemSubtype,
            message,
            metaJson,
        })
    }

    function pushParseErrorTimeline(sseType, raw, error, ts, ingestOpts = {}) {
        const items = ingestOpts.targetItems ?? timelineItems.value
        const idFn = ingestOpts.nextIdFn ?? nextTimelineId
        items.push({
            id: idFn(),
            sseType,
            kind: 'parse_error',
            ts,
            error: error || 'parse',
            rawSnippet: String(raw ?? '').slice(0, 4000),
        })
    }

    function pushParsedTimeline(sseType, ts, payload, ingestOpts = {}) {
        const items = ingestOpts.targetItems ?? timelineItems.value
        const idFn = ingestOpts.nextIdFn ?? nextTimelineId
        items.push({
            id: idFn(),
            sseType,
            kind: sseType,
            ts,
            payload,
        })
    }

    function findTimelineApprovalIndexInItems(items, requestId) {
        const id = requestId != null ? String(requestId) : ''
        if (!id) return -1
        for (let i = items.length - 1; i >= 0; i--) {
            const it = items[i]
            if (it?.kind === 'approval_required' && it.payload?.approval_request_id === id) {
                return i
            }
        }
        return -1
    }

    function onApprovalDialogClosed() {
        pendingApproval.value = null
    }

    function closeApprovalDialog() {
        showRejectReason.value = false
        approvalReason.value = ''
        showApprovalDialog.value = false
    }

    function clearApprovalDialogState() {
        showRejectReason.value = false
        approvalReason.value = ''
        pendingApproval.value = null
        showApprovalDialog.value = false
    }

    function handleApprovalRequiredEvent(raw) {
        noteInitialReplayEvent()
        const ts = new Date().toISOString()
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline('approval_required', raw, p.error, ts)
            return
        }
        const envelope = p.value
        const requestId = envelope?.approval_request_id

        if (isApprovalAwaitingUserAction(envelope)) {
            pushParsedTimeline('approval_required', ts, envelope)
            pendingApproval.value = envelope
            showRejectReason.value = false
            approvalReason.value = ''
            showApprovalDialog.value = true
            return
        }

        const idx = findTimelineApprovalIndexInItems(timelineItems.value, requestId)
        if (idx >= 0) {
            timelineItems.value[idx].payload = envelope
        } else {
            pushParsedTimeline('approval_required', ts, envelope)
        }

        if (pendingApproval.value?.approval_request_id === requestId) {
            closeApprovalDialog()
        }
    }

    function ingestSseNamedEvent(sseType, raw, ingestOpts = {}) {
        const items = ingestOpts.targetItems ?? timelineItems.value
        const idFn = ingestOpts.nextIdFn ?? nextTimelineId
        const ts = new Date().toISOString()
        if (sseType === 'reasoning_stream') {
            const p = parseAgentSseData(raw)
            if (!p.ok) {
                pushParseErrorTimeline('reasoning_stream', raw, p.error, ts, ingestOpts)
                return
            }
            appendReasoningStreamDelta(items, p.value?.delta ?? '', ts, idFn)
            return
        }
        if (sseType === 'stream') {
            const p = parseAgentSseData(raw)
            if (!p.ok) {
                pushParseErrorTimeline('stream', raw, p.error, ts, ingestOpts)
                return
            }
            appendStreamDelta(items, p.value?.delta ?? '', ts, idFn)
            return
        }
        if (sseType === 'stream_end') {
            const p = parseAgentSseData(raw)
            const payload = p.ok && p.value && typeof p.value === 'object' ? p.value : {}
            closeStreamInTimeline(items, payload, ts, idFn)
            return
        }
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline(sseType, raw, p.error, ts, ingestOpts)
            return
        }
        pushParsedTimeline(sseType, ts, p.value, ingestOpts)
    }

    function ingestApprovalRequiredToItems(raw, ingestOpts = {}) {
        const items = ingestOpts.targetItems ?? timelineItems.value
        const ts = new Date().toISOString()
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline('approval_required', raw, p.error, ts, ingestOpts)
            return
        }
        const envelope = p.value
        const requestId = envelope?.approval_request_id
        const idx = findTimelineApprovalIndexInItems(items, requestId)
        if (idx >= 0) {
            items[idx].payload = envelope
        } else {
            pushParsedTimeline('approval_required', ts, envelope, ingestOpts)
        }
    }

    function ingestTodosToItems(raw, ingestOpts = {}) {
        const items = ingestOpts.targetItems ?? timelineItems.value
        const idFn = ingestOpts.nextIdFn ?? nextTimelineId
        const ts = new Date().toISOString()
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline('todos', raw, p.error, ts, ingestOpts)
            return
        }
        const list = normalizeTodosPayload(p.value)
        let completed = 0
        let inProgress = 0
        let waiting = 0
        for (const t of list) {
            const s = t?.status
            if (s === TODO_ITEM_STATUS.COMPLETED || s === 'completed') completed++
            else if (s === TODO_ITEM_STATUS.IN_PROGRESS || s === 'in_progress') inProgress++
            else waiting++
        }
        const total = list.length
        items.push({
            id: idFn(),
            sseType: 'todos',
            kind: 'todos',
            ts,
            payload: p.value,
            todoCount: total,
            todoPreview: `共 ${total} 项，已完成 ${completed} 项，正在进行 ${inProgress} 项，等待进行 ${waiting} 项`,
        })
    }

    function buildTimelineBatch(events) {
        const batchItems = []
        const ingestOpts = {
            targetItems: batchItems,
            nextIdFn: nextTimelineId,
        }
        for (const ev of events) {
            if (ev.type === 'todos') {
                ingestTodosToItems(ev.data, ingestOpts)
            } else if (ev.type === 'approval_required') {
                ingestApprovalRequiredToItems(ev.data, ingestOpts)
            } else {
                ingestSseNamedEvent(ev.type, ev.data, ingestOpts)
            }
        }
        return batchItems
    }

    async function prependTimelineBatch(batchItems) {
        if (!batchItems.length) return
        const el = eventsScrollEl.value
        const prevHeight = el?.scrollHeight ?? 0
        timelineItems.value = [...batchItems, ...timelineItems.value]
        await nextTick()
        if (el) {
            el.scrollTop += el.scrollHeight - prevHeight
        }
    }

    function clearInitialReplayTracking() {
        initialReplayPending = false
        initialReplayCount = 0
        replayReadyForPagination.value = false
        if (initialReplayIdleTimer) {
            clearTimeout(initialReplayIdleTimer)
            initialReplayIdleTimer = null
        }
    }

    function finalizeInitialReplay() {
        if (!initialReplayPending) return
        initialReplayPending = false
        if (initialReplayIdleTimer) {
            clearTimeout(initialReplayIdleTimer)
            initialReplayIdleTimer = null
        }
        hasMoreHistory.value = initialReplayCount >= replayPageSize
        historyOffset.value = replayPageSize
        replayReadyForPagination.value = true
    }

    function scheduleInitialReplayFinalize() {
        if (initialReplayIdleTimer) clearTimeout(initialReplayIdleTimer)
        initialReplayIdleTimer = setTimeout(finalizeInitialReplay, 400)
    }

    function startInitialReplayTracking() {
        clearInitialReplayTracking()
        initialReplayPending = true
        initialReplayCount = 0
        scheduleInitialReplayFinalize()
    }

    function noteInitialReplayEvent() {
        if (!initialReplayPending) return
        initialReplayCount += 1
        scheduleInitialReplayFinalize()
    }

    async function loadOlderEvents() {
        if (!hasMoreHistory.value || historyLoading.value) return
        if (!resolvedAgentId.value || !sessionId.value) return

        historyLoading.value = true
        try {
            const url = agentApi.getAgentStatusUrl(resolvedAgentId.value, sessionId.value, {
                limit: replayPageSize,
                offset: historyOffset.value,
            })
            const { events } = await fetchReplayBatch(url, { expectedLimit: replayPageSize })
            if (!events.length) {
                hasMoreHistory.value = false
                return
            }
            const batchItems = buildTimelineBatch(events)
            await prependTimelineBatch(batchItems)
            historyOffset.value += replayPageSize
            if (events.length < replayPageSize) {
                hasMoreHistory.value = false
            }
        } catch (error) {
            ElMessage.error(error?.message || '加载历史事件失败')
        } finally {
            historyLoading.value = false
        }
    }

    function normalizeTodosPayload(raw) {
        if (Array.isArray(raw)) return raw
        if (raw && typeof raw === 'object') {
            if (Array.isArray(raw.todos)) return raw.todos
            if (Array.isArray(raw.items)) return raw.items
            if (Array.isArray(raw.data)) return raw.data
        }
        return []
    }

    function updateEventsScrollState() {
        const el = eventsScrollEl.value
        if (!el) return
        isEventsScrollAtBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 50
    }

    function onEventsScroll() {
        updateEventsScrollState()
        if (!replayReadyForPagination.value) return
        const el = eventsScrollEl.value
        if (!el) return
        if (el.scrollTop < 80 && hasMoreHistory.value && !historyLoading.value) {
            if (loadOlderDebounceTimer) clearTimeout(loadOlderDebounceTimer)
            loadOlderDebounceTimer = setTimeout(() => {
                loadOlderEvents()
            }, 300)
        }
    }

    function teardownEventsScrollObserver() {
        if (eventsScrollResizeObserver) {
            eventsScrollResizeObserver.disconnect()
            eventsScrollResizeObserver = null
        }
    }

    /** @param {boolean} [force] */
    function scrollEventsToBottom(force = false) {
        if (!force && !isEventsScrollAtBottom.value) return
        const el = eventsScrollEl.value
        if (!el) return
        el.scrollTop = el.scrollHeight
    }

    /** @param {HTMLElement | null} el */
    function registerEventsScrollEl(el) {
        teardownEventsScrollObserver()
        eventsScrollEl.value = el
        if (!el) return
        updateEventsScrollState()
        scrollEventsToBottom(true)
        const content = el.firstElementChild
        if (content) {
            eventsScrollResizeObserver = new ResizeObserver(() => {
                scrollEventsToBottom()
            })
            eventsScrollResizeObserver.observe(content)
        }
    }

    watch(
        () => timelineItems.value,
        () => {
            scrollEventsToBottom()
        },
        { deep: true, flush: 'post' }
    )

    onUnmounted(() => {
        teardownEventsScrollObserver()
        disconnectSSE()
    })

    const statusRaw = computed(() => {
        const runtime = String(sessionRuntimeStatus.value || 'unknown')
        const persisted = session.value?.status ? String(session.value.status) : ''
        if (isAgentSessionTerminalStatus(persisted) && runtime === 'running') {
            return persisted
        }
        if (runtime !== 'unknown') return runtime
        return persisted || 'unknown'
    })

    const statusLabel = computed(() => getAgentSessionStatusLabel(statusRaw.value))
    const statusTagType = computed(() => getAgentSessionStatusTagType(statusRaw.value))

    const canSendMessage = computed(
        () =>
            Boolean(resolvedAgentId.value) &&
            Boolean(sessionId.value) &&
            isAgentSessionTerminalStatus(statusRaw.value) &&
            userPrompt.value.trim().length > 0 &&
            !sendLoading.value
    )

    const canCancel = computed(
        () =>
            Boolean(resolvedAgentId.value) &&
            Boolean(sessionId.value) &&
            (statusRaw.value === 'running' || statusRaw.value === 'awaiting_approval') &&
            !cancelLoading.value
    )

    function todoStatusIcon(s) {
        if (s === TODO_ITEM_STATUS.PENDING || s === 'pending') return 'mdi:circle-outline'
        if (s === TODO_ITEM_STATUS.IN_PROGRESS || s === 'in_progress') return 'mdi:progress-clock'
        if (s === TODO_ITEM_STATUS.COMPLETED || s === 'completed') return 'mdi:check-circle'
        return 'mdi:circle-outline'
    }

    function todoStatusIconColor(s) {
        if (s === TODO_ITEM_STATUS.PENDING || s === 'pending') return 'text-gray-400'
        if (s === TODO_ITEM_STATUS.IN_PROGRESS || s === 'in_progress') return 'text-amber-600'
        if (s === TODO_ITEM_STATUS.COMPLETED || s === 'completed') return 'text-green-600'
        return 'text-gray-400'
    }

    function applySessionRuntimeStatus(nextStatus) {
        const s = String(nextStatus ?? '').trim()
        if (!s) return
        sessionRuntimeStatus.value = s
        if (session.value && typeof session.value === 'object') {
            session.value = { ...session.value, status: s }
        }
    }

    function applyStatusFromSsePayload(raw) {
        const text = String(raw ?? '').trim()
        if (!text) return
        try {
            const x = JSON.parse(text)
            if (typeof x === 'string') {
                applySessionRuntimeStatus(x)
            } else if (x && typeof x === 'object' && x.status != null) {
                applySessionRuntimeStatus(x.status)
            }
        } catch {
            applySessionRuntimeStatus(text)
        }
    }

    function onTodosSse(raw) {
        noteInitialReplayEvent()
        const ts = new Date().toISOString()
        applyTodosFromSsePayload(raw)
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline('todos', raw, p.error, ts)
            return
        }
        ingestTodosToItems(raw)
    }

    function applyTodosFromSsePayload(raw) {
        const text = String(raw ?? '').trim()
        if (!text) {
            todos.value = []
            return
        }
        try {
            const x = JSON.parse(text)
            todos.value = normalizeTodosPayload(x)
        } catch {
            todos.value = []
        }
    }

    async function loadSessionDetail() {
        if (!sessionId.value) throw new Error('缺少 session_id 参数')
        const res = await agentApi.getAgentSessionDetail(sessionId.value)
        if (res?.code !== 0) {
            throw new Error(res?.message || '获取会话详情失败')
        }
        const raw = res?.data && typeof res.data === 'object' ? res.data : null
        session.value = raw
        if (raw?.status) {
            sessionRuntimeStatus.value = String(raw.status)
        }
    }

    async function runSseAttempt(url, generation) {
        const controller = new AbortController()
        streamAbortController = controller
        try {
            await openAuthenticatedSse(url, {
                signal: controller.signal,
                onOpen: () => {
                    if (generation !== connectionGeneration || controller.signal.aborted) return
                    sseConnected.value = true
                    sseError.value = ''
                    retryCount = 0
                    pushSystemTimeline('sse_open', '实时通道已建立')
                },
                onEvent: (event) => {
                    if (generation !== connectionGeneration || controller.signal.aborted) return
                    const type = event?.type || 'message'
                    const raw = event?.data ?? ''
                    if (type === 'user_message') {
                        noteInitialReplayEvent()
                        ingestSseNamedEvent(type, raw)
                    } else if (type === 'status') {
                        noteInitialReplayEvent()
                        ingestSseNamedEvent(type, raw)
                        applyStatusFromSsePayload(raw)
                    } else if (type === 'todos') {
                        onTodosSse(raw)
                    } else if (type === 'result') {
                        noteInitialReplayEvent()
                        ingestSseNamedEvent(type, raw)
                        applyStatusFromSsePayload(raw)
                    } else if (type === 'approval_required') {
                        handleApprovalRequiredEvent(raw)
                    } else if (type === 'message' || AGENT_SSE_TIMELINE_EVENT_TYPES.has(type)) {
                        noteInitialReplayEvent()
                        ingestSseNamedEvent(type, raw)
                    }
                },
            })
            if (generation !== connectionGeneration || controller.signal.aborted) return
            throw new AgentSseError('实时连接已中断', {
                kind: 'network',
                retryable: true,
            })
        } catch (error) {
            if (
                generation !== connectionGeneration ||
                controller.signal.aborted ||
                error?.name === 'AbortError'
            ) return

            sseConnected.value = false
            if (error?.retryable && retryCount < maxRetries) {
                retryCount++
                const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 10000)
                pushSystemTimeline('sse_retry', `第 ${retryCount} 次重连，${delay}ms 后执行`)
                retryTimer = setTimeout(() => {
                    retryTimer = null
                    if (
                        generation === connectionGeneration &&
                        sessionId.value &&
                        resolvedAgentId.value
                    ) {
                        void runSseAttempt(url, generation)
                    }
                }, delay)
                return
            }

            sseError.value = error?.retryable
                ? 'SSE 连接失败，请刷新页面重试'
                : error?.message || '创建 SSE 连接失败'
            pushSystemTimeline('sse_error', sseError.value)
            if (error?.kind !== 'unauthorized' && error?.kind !== 'forbidden') {
                ElMessage.error(sseError.value)
            }
        } finally {
            if (streamAbortController === controller) streamAbortController = null
        }
    }

    function connectSSE() {
        if (!resolvedAgentId.value) {
            sseError.value = '缺少 agent_id 参数'
            return
        }
        if (!sessionId.value) {
            sseError.value = ''
            return
        }

        disconnectSSE()
        const url = agentApi.getAgentStatusUrl(resolvedAgentId.value, sessionId.value, {
            limit: replayPageSize,
            offset: 0,
        })
        startInitialReplayTracking()
        void runSseAttempt(url, connectionGeneration)
    }

    function disconnectSSE() {
        connectionGeneration++
        retryCount = 0
        if (retryTimer) {
            clearTimeout(retryTimer)
            retryTimer = null
        }
        if (streamAbortController) {
            streamAbortController.abort()
            streamAbortController = null
        }
        clearInitialReplayTracking()
        sseConnected.value = false
    }

    function parseInjectionParam() {
        const raw = toValue(options.injectionParam)
        if (raw == null) return undefined
        if (typeof raw === 'object') return raw
        const text = String(raw).trim()
        if (!text) return undefined
        try {
            const obj = JSON.parse(text)
            return obj && typeof obj === 'object' ? obj : undefined
        } catch {
            return undefined
        }
    }

    function buildMessageInjectionParam() {
        const merged = { ...(parseInjectionParam() || {}) }
        if (entityUuid.value) merged.entity_uuid = entityUuid.value
        if (entityType.value) merged.entity_type = entityType.value
        return merged
    }

    async function sendMessage() {
        if (!canSendMessage.value) return
        const trimmedPrompt = userPrompt.value.trim()
        if (!trimmedPrompt) return
        try {
            sendLoading.value = true
            const injectionParam = buildMessageInjectionParam()
            const res = await agentApi.sendAgentMessage({
                agent_id: resolvedAgentId.value,
                session_id: sessionId.value,
                user_prompt: trimmedPrompt,
                injection_param:
                    Object.keys(injectionParam).length > 0 ? injectionParam : {},
                auto_approve: getAgentAutoApproveValue(),
            })
            if (res?.code !== 0) {
                ElMessage.error(res?.message || '发送失败')
                return
            }
            ElMessage.success('已提交续聊请求')
            pushSystemTimeline('client_message', '已提交续聊消息', res?.data || {})
            userPrompt.value = ''
        } catch (e) {
            ElMessage.error(e?.message || '发送失败，请稍后重试')
        } finally {
            sendLoading.value = false
        }
    }

    async function cancel() {
        if (!canCancel.value) return
        try {
            cancelLoading.value = true
            const res = await agentApi.cancelAgent({
                agent_id: resolvedAgentId.value,
                session_id: sessionId.value,
                reason: '用户取消',
            })
            if (res?.code !== 0) {
                ElMessage.error(res?.message || '取消失败')
                return
            }
            ElMessage.success(res?.message || '已提交取消请求')
            pushSystemTimeline('client_cancel', '已提交取消请求', res?.data || {})
        } catch (e) {
            ElMessage.error(e?.message || '取消失败，请稍后重试')
        } finally {
            cancelLoading.value = false
        }
    }

    function cancelRejectFlow() {
        showRejectReason.value = false
        approvalReason.value = ''
    }

    async function submitApprovalDecision(action) {
        if (!sessionId.value) {
            ElMessage.warning('缺少 session_id，无法提交审批')
            return
        }
        try {
            approvalLoading.value = true
            const decision =
                action === 'approve'
                    ? { action: 'approve' }
                    : {
                          action: 'reject',
                          reason: approvalReason.value?.trim() || undefined,
                      }
            const res = await agentApi.approveAgent({
                agent_id: resolvedAgentId.value,
                session_id: sessionId.value,
                approval_request_id: pendingApproval.value?.approval_request_id,
                decisions: [decision],
            })
            if (res?.code !== 0) {
                ElMessage.error(res?.message || '审批提交失败')
                return
            }
            ElMessage.success(res?.message || '审批已提交')
            pushSystemTimeline('client_approve', '审批已提交', { decision })
            closeApprovalDialog()
        } catch (e) {
            ElMessage.error(e?.message || '审批提交失败，请稍后重试')
        } finally {
            approvalLoading.value = false
        }
    }

    function resetStreamState() {
        timelineItems.value = []
        timelineSeq = 0
        todos.value = []
        sessionRuntimeStatus.value = 'unknown'
        historyOffset.value = 0
        hasMoreHistory.value = true
        historyLoading.value = false
        clearInitialReplayTracking()
        if (loadOlderDebounceTimer) {
            clearTimeout(loadOlderDebounceTimer)
            loadOlderDebounceTimer = null
        }
        clearApprovalDialogState()
    }

    async function reloadSession({ loadDetail = true } = {}) {
        disconnectSSE()
        resetStreamState()
        if (loadDetail && sessionId.value) {
            try {
                await loadSessionDetail()
            } catch (e) {
                throw e
            }
        }
        if (sessionId.value && resolvedAgentId.value) {
            await nextTick()
            connectSSE()
        }
    }

    async function startStreamForSession({ loadDetail = false } = {}) {
        resetStreamState()
        if (loadDetail && sessionId.value) {
            try {
                await loadSessionDetail()
            } catch {
                // 嵌入场景可仅依赖 SSE
            }
        }
        if (sessionId.value && resolvedAgentId.value) {
            await nextTick()
            connectSSE()
        }
    }

    return {
        session,
        agentId: resolvedAgentId,
        sessionId,
        sessionRuntimeStatus,
        sseConnected,
        sseError,
        userPrompt,
        sendLoading,
        cancelLoading,
        todos,
        timelineItems,
        hasMoreHistory,
        historyLoading,
        showApprovalDialog,
        pendingApproval,
        approvalReason,
        showRejectReason,
        approvalLoading,
        approvalDialogTitle,
        eventsScrollEl,
        registerEventsScrollEl,
        scrollEventsToBottom,
        onEventsScroll,
        statusRaw,
        statusLabel,
        statusTagType,
        canSendMessage,
        canCancel,
        todoStatusIcon,
        todoStatusIconColor,
        entityUuid,
        entityType,
        loadSessionDetail,
        connectSSE,
        disconnectSSE,
        sendMessage,
        cancel,
        cancelRejectFlow,
        submitApprovalDecision,
        onApprovalDialogClosed,
        closeApprovalDialog,
        clearApprovalDialogState,
        resetStreamState,
        reloadSession,
        startStreamForSession,
        pushSystemTimeline,
    }
}
