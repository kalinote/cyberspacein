<template>
    <div class="min-h-screen bg-gray-50">
        <Header />

        <div v-if="pageLoading" class="flex items-center justify-center h-96">
            <div class="text-center">
                <Icon icon="mdi:loading" class="block mx-auto text-4xl text-blue-500 animate-spin mb-2" />
                <p class="text-gray-600">正在加载分析详情...</p>
            </div>
        </div>

        <div v-else-if="pageError" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div class="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
                <div class="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-50">
                    <Icon icon="mdi:alert-circle" class="text-red-500 text-5xl leading-none" />
                </div>
                <h2 class="text-xl font-bold text-gray-900 mb-2">加载失败</h2>
                <p class="text-gray-600 mb-4">{{ pageError }}</p>
                <button @click="reload" class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                    重新加载
                </button>
            </div>
        </div>

        <template v-else>
            <DetailPageHeader :title="agentTitle" :subtitle="agentId">
                <template #tags>
                    <el-tag :type="statusTagType" size="default">{{ statusLabel }}</el-tag>
                    <el-tag v-if="agent?.workspace_id" type="info" size="default">workspace: {{ agent.workspace_id
                        }}</el-tag>
                    <el-tag v-if="sseConnected" type="success" size="default">实时连接</el-tag>
                    <el-tag v-else type="warning" size="default">未连接</el-tag>
                </template>
            </DetailPageHeader>

            <section class="py-6 bg-white">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
                        <div class="lg:col-span-8">
                            <div
                                class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100">
                                <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                    <div class="min-w-0">
                                        <p class="text-sm text-gray-500">启动本次分析</p>
                                        <p class="text-xs text-gray-500 mt-1">
                                            将调用 <span class="font-mono">/agent/start</span>，并通过 <span
                                                class="font-mono">/agent/status</span> 实时展示进度
                                        </p>
                                    </div>
                                    <div class="flex gap-2 shrink-0">
                                        <el-button type="primary" :loading="startLoading" :disabled="!canStart"
                                            @click="start">
                                            启动
                                        </el-button>
                                        <el-button type="warning" :loading="cancelLoading" :disabled="!canCancel"
                                            @click="cancel">
                                            取消
                                        </el-button>
                                    </div>
                                </div>
                                <div class="mt-4">
                                    <el-input v-model="userPrompt" type="textarea"
                                        :autosize="{ minRows: 3, maxRows: 8 }"
                                        placeholder="用户提示词（user_prompt），留空则使用服务端模板默认"
                                        resize="none" />
                                    <div class="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                                        <span v-if="entityType">entity_type: <span class="font-mono">{{ entityType
                                                }}</span></span>
                                        <span v-if="entityUuid">entity_uuid: <span class="font-mono">{{ entityUuid
                                                }}</span></span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="lg:col-span-4">
                            <div
                                class="bg-linear-to-br from-gray-50 to-white rounded-xl p-5 shadow-sm border border-gray-100">
                                <p class="text-sm text-gray-500">基础信息</p>
                                <div class="mt-3 space-y-2 text-sm">
                                    <div class="flex justify-between gap-3">
                                        <span class="text-gray-500">agent_id</span>
                                        <span class="font-mono text-gray-900 truncate">{{ agentId }}</span>
                                    </div>
                                    <div class="flex justify-between gap-3">
                                        <span class="text-gray-500">状态</span>
                                        <span class="font-medium text-gray-900">{{ statusLabel }}</span>
                                    </div>
                                    <div class="flex justify-between gap-3" v-if="sessionId">
                                        <span class="text-gray-500">session_id</span>
                                        <span class="font-mono text-gray-900 truncate">{{ sessionId }}</span>
                                    </div>
                                    <div class="flex justify-between gap-3" v-if="agent?.updated_at">
                                        <span class="text-gray-500">更新时间</span>
                                        <span class="text-gray-900">{{ formatDateTime(agent.updated_at, {
                                            includeSecond:
                                            true })
                                            }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="py-8 bg-gray-50">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        <div class="lg:col-span-8 bg-white rounded-xl shadow-sm border border-gray-200">
                            <h2 class="text-xl font-bold text-gray-900 flex items-center p-4 pb-2">
                                <Icon icon="mdi:timeline-text" class="text-blue-600 mr-2" />
                                实时事件
                            </h2>
                            <div ref="eventsScrollEl" class="overflow-y-auto px-4 pb-4 border-t border-gray-100"
                                style="height: 70vh" @scroll="onEventsScroll">
                                <div v-if="!timelineItems.length"
                                    class="flex flex-col items-center justify-center h-full min-h-70 text-gray-400">
                                    <Icon icon="mdi:access-point" class="text-2xl text-blue-500 mb-2" />
                                    <p class="text-sm font-medium text-gray-500">等待事件推送</p>
                                </div>

                                <div v-else class="space-y-3 pt-4">
                                    <div v-for="ev in timelineItems" :key="ev.id"
                                        class="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                                        <AgentSseTimelineItem :item="ev" />
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="lg:col-span-4 min-w-0 bg-white rounded-xl shadow-sm border border-gray-200">
                            <h2 class="text-xl font-bold text-gray-900 flex items-center p-4 pb-2">
                                <Icon icon="mdi:format-list-checks" class="text-blue-600 mr-2" />
                                任务列表（todos）
                            </h2>

                            <div class="border-t border-gray-100" style="height: 70vh">
                                <div class="h-full overflow-y-auto p-4">
                                    <div v-if="!todos.length"
                                        class="flex flex-col items-center justify-center h-full text-gray-400">
                                        <Icon icon="mdi:playlist-remove" class="text-2xl text-gray-400 mb-2" />
                                        <p class="text-sm font-medium text-gray-500">暂无任务</p>
                                    </div>
                                    <ul v-else class="space-y-2 min-w-0">
                                        <li v-for="(todo, index) in todos" :key="index"
                                            class="flex items-start gap-2 py-2 px-3 rounded-lg bg-gray-50 border border-gray-100 min-w-0">
                                            <Icon :icon="todoStatusIcon(todo?.status)"
                                                :class="['shrink-0 text-base mt-0.5', todoStatusIconColor(todo?.status)]" />
                                            <div class="min-w-0">
                                                <p class="text-sm text-gray-900 break-all min-w-0">{{ todo?.content ||
                                                    '-' }}</p>
                                                <p v-if="todo?.status" class="text-xs text-gray-500 mt-0.5">状态：{{
                                                    todo.status }}</p>
                                            </div>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <el-dialog
                v-model="showApprovalDialog"
                :title="approvalDialogTitle"
                width="760px"
                :close-on-click-modal="false"
                :show-close="false"
                @closed="onApprovalDialogClosed"
            >
                <div v-if="pendingApproval">
                    <p class="text-gray-600 mb-4">Agent 请求执行以下操作，请选择批准或拒绝：</p>
                    <AgentApprovalPanel :approval="pendingApproval" />
                    <div v-if="showRejectReason" class="mt-4 pt-4 border-t border-gray-100">
                        <p class="text-sm text-gray-600 mb-2">拒绝理由（可选）</p>
                        <el-input
                            v-model="approvalReason"
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 4 }"
                            placeholder="请填写拒绝原因"
                            resize="none"
                        />
                    </div>
                </div>
                <template #footer>
                    <template v-if="showRejectReason">
                        <el-button @click="cancelRejectFlow" :disabled="approvalLoading">返回</el-button>
                        <el-button type="danger" @click="submitApprovalDecision('reject')" :loading="approvalLoading">确认拒绝</el-button>
                    </template>
                    <template v-else>
                        <el-button type="danger" @click="showRejectReason = true" :loading="approvalLoading">拒绝</el-button>
                        <el-button type="primary" @click="submitApprovalDecision('approve')" :loading="approvalLoading">批准</el-button>
                    </template>
                </template>
            </el-dialog>
        </template>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import AgentSseTimelineItem from '@/components/agent/AgentSseTimelineItem.vue'
import AgentApprovalPanel from '@/components/agent/approval/AgentApprovalPanel.vue'
import { agentApi } from '@/api/agent'
import {
    appendStreamDelta,
    closeStreamInTimeline,
    parseAgentSseData,
    stringifyJsonSafe,
} from '@/utils/agentSse'
import { getApprovalSourceLabel, isApprovalAwaitingUserAction } from '@/utils/agentApproval'
import { formatDateTime, TODO_ITEM_STATUS } from '@/utils/action'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => String(route.params.threadId || ''))
const sessionId = computed(() => (route.query.session_id ? String(route.query.session_id) : ''))

const entityUuid = computed(() => (route.query.entity_uuid ? String(route.query.entity_uuid) : ''))
const entityType = computed(() => (route.query.entity_type ? String(route.query.entity_type) : ''))
const extraContextText = computed(() => (route.query.extra_context ? String(route.query.extra_context) : ''))

const pageLoading = ref(true)
const pageError = ref('')

const agent = ref(null)
const sessionRuntimeStatus = ref('unknown')
const sseConnected = ref(false)
const sseError = ref('')

const userPrompt = ref('')
const startLoading = ref(false)
const cancelLoading = ref(false)

const todos = ref([])
const timelineItems = ref([])

let timelineSeq = 0
function nextTimelineId() {
    timelineSeq += 1
    return timelineSeq
}

let eventSource = null
let retryCount = 0
const maxRetries = 3

const showApprovalDialog = ref(false)
const pendingApproval = ref(null)
const approvalReason = ref('')
const showRejectReason = ref(false)
const approvalLoading = ref(false)

const approvalDialogTitle = computed(() => {
    const label = getApprovalSourceLabel(pendingApproval.value?.source)
    return `审批请求 · ${label}`
})

const eventsScrollEl = ref(null)
const isEventsScrollAtBottom = ref(true)

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

function pushParseErrorTimeline(sseType, raw, error, ts) {
    timelineItems.value.push({
        id: nextTimelineId(),
        sseType,
        kind: 'parse_error',
        ts,
        error: error || 'parse',
        rawSnippet: String(raw ?? '').slice(0, 4000),
    })
}

function pushParsedTimeline(sseType, ts, payload) {
    timelineItems.value.push({
        id: nextTimelineId(),
        sseType,
        kind: sseType,
        ts,
        payload,
    })
}

function findTimelineApprovalIndex(requestId) {
    const id = requestId != null ? String(requestId) : ''
    if (!id) return -1
    for (let i = timelineItems.value.length - 1; i >= 0; i--) {
        const it = timelineItems.value[i]
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

    const idx = findTimelineApprovalIndex(requestId)
    if (idx >= 0) {
        timelineItems.value[idx].payload = envelope
    } else {
        pushParsedTimeline('approval_required', ts, envelope)
    }

    if (pendingApproval.value?.approval_request_id === requestId) {
        closeApprovalDialog()
    }
}

function ingestSseNamedEvent(sseType, raw) {
    const ts = new Date().toISOString()
    if (sseType === 'stream') {
        const p = parseAgentSseData(raw)
        if (!p.ok) {
            pushParseErrorTimeline('stream', raw, p.error, ts)
            return
        }
        appendStreamDelta(timelineItems.value, p.value?.delta ?? '', ts, nextTimelineId)
        return
    }
    if (sseType === 'stream_end') {
        const p = parseAgentSseData(raw)
        const payload = p.ok && p.value && typeof p.value === 'object' ? p.value : {}
        closeStreamInTimeline(timelineItems.value, payload, ts, nextTimelineId)
        return
    }
    const p = parseAgentSseData(raw)
    if (!p.ok) {
        pushParseErrorTimeline(sseType, raw, p.error, ts)
        return
    }
    pushParsedTimeline(sseType, ts, p.value)
}

function mergeAgent(partial) {
    const p = partial && typeof partial === 'object' ? partial : {}
    agent.value = { ...(agent.value || {}), ...p }
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

function onEventsScroll() {
    const el = eventsScrollEl.value
    if (!el) return
    isEventsScrollAtBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 50
}

watch(
    () => timelineItems.value,
    () => {
        if (!isEventsScrollAtBottom.value || !eventsScrollEl.value) return
        nextTick(() => {
            const el = eventsScrollEl.value
            if (el) el.scrollTop = el.scrollHeight
        })
    },
    { deep: true }
)

const agentTitle = computed(() => agent.value?.name || '分析详情')
const statusRaw = computed(() => String(sessionRuntimeStatus.value || 'unknown'))

const statusLabelMap = {
    unknown: '未知',
    idle: '空闲',
    running: '运行中',
    awaiting_approval: '等待审批',
    completed: '已完成',
    failed: '失败',
    paused: '已暂停',
    cancelled: '已取消'
}

const statusTagMap = {
    unknown: 'info',
    idle: 'info',
    running: 'primary',
    awaiting_approval: 'warning',
    completed: 'success',
    failed: 'danger',
    paused: 'info',
    cancelled: 'info'
}

const statusLabel = computed(() => statusLabelMap[statusRaw.value] || statusRaw.value)
const statusTagType = computed(() => statusTagMap[statusRaw.value] || 'info')

const canStart = computed(() => Boolean(agentId.value) && !startLoading.value)
const canCancel = computed(
    () =>
        Boolean(agentId.value) &&
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

function applyStatusFromSsePayload(raw) {
    const text = String(raw ?? '').trim()
    if (!text) return
    try {
        const x = JSON.parse(text)
        if (typeof x === 'string') {
            sessionRuntimeStatus.value = x
        } else if (x && typeof x === 'object' && x.status != null) {
            sessionRuntimeStatus.value = String(x.status)
        }
    } catch {
        sessionRuntimeStatus.value = text
    }
}

function onTodosSse(raw) {
    const ts = new Date().toISOString()
    applyTodosFromSsePayload(raw)
    const p = parseAgentSseData(raw)
    if (!p.ok) {
        pushParseErrorTimeline('todos', raw, p.error, ts)
        return
    }
    const list = todos.value
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
    timelineItems.value.push({
        id: nextTimelineId(),
        sseType: 'todos',
        kind: 'todos',
        ts,
        payload: p.value,
        todoCount: total,
        todoPreview: `共 ${total} 项，已完成 ${completed} 项，正在进行 ${inProgress} 项，等待进行 ${waiting} 项`,
    })
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

async function loadAgentDetail() {
    if (!agentId.value) throw new Error('缺少 agent_id 参数')
    const res = await agentApi.getAgentDetail(agentId.value)
    if (res?.code !== 0) {
        throw new Error(res?.message || '获取 Agent 详情失败')
    }
    const raw = res?.data && typeof res.data === 'object' ? { ...res.data } : {}
    delete raw.status
    delete raw.todos
    delete raw.pending_approval
    delete raw.current_session_id
    mergeAgent(raw)
}

function connectSSE() {
    if (!agentId.value) {
        sseError.value = '缺少 agent_id 参数'
        return
    }
    if (!sessionId.value) {
        sseError.value = ''
        return
    }

    disconnectSSE()

    try {
        const url = agentApi.getAgentStatusUrl(agentId.value, sessionId.value)
        eventSource = new EventSource(url)

        eventSource.onopen = () => {
            sseConnected.value = true
            sseError.value = ''
            retryCount = 0
            pushSystemTimeline('sse_open', '实时通道已建立')
        }

        eventSource.onerror = () => {
            sseConnected.value = false
            if (eventSource) {
                eventSource.close()
                eventSource = null
            }

            if (retryCount < maxRetries) {
                retryCount++
                const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 10000)
                pushSystemTimeline('sse_retry', `第 ${retryCount} 次重连，${delay}ms 后执行`)
                setTimeout(() => {
                    if (retryCount <= maxRetries && sessionId.value && agentId.value) connectSSE()
                }, delay)
            } else {
                sseError.value = 'SSE 连接失败，请刷新页面重试'
                pushSystemTimeline('sse_error', sseError.value)
                ElMessage.error('实时连接中断，请稍后重试')
            }
        }

        eventSource.addEventListener('status', (event) => {
            const raw = event.data ?? ''
            ingestSseNamedEvent('status', raw)
            applyStatusFromSsePayload(raw)
        })
        eventSource.addEventListener('todos', (event) => {
            const raw = event.data ?? ''
            onTodosSse(raw)
        })

        const sseNamedEvents = [
            'notification',
            'result',
            'debug_prompt',
            'progress',
            'step',
            'task_submitted',
            'stream',
            'stream_end',
        ]
        for (const name of sseNamedEvents) {
            eventSource.addEventListener(name, (event) => {
                ingestSseNamedEvent(name, event.data ?? '')
            })
        }
        eventSource.addEventListener('approval_required', (event) => {
            handleApprovalRequiredEvent(event.data ?? '')
        })
        eventSource.onmessage = (event) => {
            ingestSseNamedEvent('message', event.data ?? '')
        }
    } catch (e) {
        sseConnected.value = false
        sseError.value = e?.message || '创建 SSE 连接失败'
        pushSystemTimeline('sse_error', sseError.value)
    }
}

function disconnectSSE() {
    if (eventSource) {
        eventSource.close()
        eventSource = null
    }
    sseConnected.value = false
}

function parseExtraContext() {
    const text = extraContextText.value.trim()
    if (!text) return undefined
    try {
        const obj = JSON.parse(text)
        return obj && typeof obj === 'object' ? obj : undefined
    } catch {
        return undefined
    }
}

async function start() {
    if (!canStart.value) return
    try {
        startLoading.value = true
        const trimmedPrompt = userPrompt.value.trim()
        const payload = {
            agent_id: agentId.value,
            user_prompt: trimmedPrompt.length > 0 ? trimmedPrompt : null,
            entity_uuid: entityUuid.value || null,
            entity_type: entityType.value || null,
            extra_context: parseExtraContext(),
            debug: true
        }
        const res = await agentApi.startAgent(payload)
        if (res?.code !== 0) {
            ElMessage.error(res?.message || '启动失败')
            return
        }
        const sid = res?.data?.session_id
        if (!sid) {
            ElMessage.error('未返回 session_id，无法订阅进度')
            return
        }
        ElMessage.success('已提交启动请求')
        pushSystemTimeline('client_start', '已提交启动分析', res?.data || {})
        await router.replace({
            path: route.path,
            query: { ...route.query, session_id: String(sid) }
        })
    } catch (e) {
        ElMessage.error(e?.message || '启动失败，请稍后重试')
    } finally {
        startLoading.value = false
    }
}

async function cancel() {
    if (!canCancel.value) return
    try {
        cancelLoading.value = true
        const res = await agentApi.cancelAgent({
            agent_id: agentId.value,
            session_id: sessionId.value,
            reason: '用户取消'
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
            agent_id: agentId.value,
            session_id: sessionId.value,
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

async function reload() {
    disconnectSSE()
    pageLoading.value = true
    pageError.value = ''
    timelineItems.value = []
    timelineSeq = 0
    todos.value = []
    sessionRuntimeStatus.value = 'unknown'
    clearApprovalDialogState()
    try {
        await loadAgentDetail()
    } catch (e) {
        pageError.value = e?.message || '加载失败'
    } finally {
        pageLoading.value = false
        if (sessionId.value && agentId.value) {
            await nextTick()
            connectSSE()
        }
    }
}

watch(sessionId, (sid, oldSid) => {
    if (sid === oldSid) return
    disconnectSSE()
    sessionRuntimeStatus.value = 'unknown'
    todos.value = []
    timelineItems.value = []
    timelineSeq = 0
    if (!sid || !agentId.value) return
    if (pageLoading.value) return
    connectSSE()
})

watch(agentId, async (id, oldId) => {
    if (!id) return
    if (oldId && id !== oldId) {
        const { session_id: _removed, ...restQuery } = route.query
        await router.replace({
            path: `/agent/analysis/${id}`,
            query: restQuery
        })
        reload()
    }
})

onMounted(() => {
    reload()
})

onUnmounted(() => {
    disconnectSSE()
})
</script>
