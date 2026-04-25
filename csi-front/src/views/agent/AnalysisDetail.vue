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
                                        :autosize="{ minRows: 3, maxRows: 8 }" placeholder="请输入本次分析的用户提示词（user_prompt）"
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
                                    <div class="flex justify-between gap-3" v-if="agent?.current_session_id">
                                        <span class="text-gray-500">current_session_id</span>
                                        <span class="font-mono text-gray-900 truncate">{{ agent.current_session_id
                                            }}</span>
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
                                <div v-if="!events.length"
                                    class="flex flex-col items-center justify-center h-full min-h-70 text-gray-400">
                                    <Icon icon="mdi:access-point" class="text-2xl text-blue-500 mb-2" />
                                    <p class="text-sm font-medium text-gray-500">等待事件推送</p>
                                </div>

                                <div v-else class="space-y-3 pt-4">
                                    <div v-for="(ev, index) in events" :key="index"
                                        class="rounded-lg border border-gray-100 bg-gray-50 p-3">
                                        <div class="flex items-center gap-2 flex-wrap">
                                            <span class="font-mono text-xs font-semibold text-gray-800">{{ ev.type
                                                }}</span>
                                            <span class="text-xs text-gray-500">{{ formatDateTime(ev.ts, {
                                                includeSecond: true })
                                                }}</span>
                                            <el-tag v-if="ev.type === 'status'" :type="statusTagType" size="small">{{
                                                statusLabel
                                                }}</el-tag>
                                        </div>
                                        <pre class="mt-2 text-xs bg-white p-2 rounded whitespace-pre-wrap wrap-break-word overflow-x-hidden">{{ JSON.stringify(ev.data,
                                null, 2) }}</pre>
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

            <el-dialog v-model="showApprovalDialog" title="审批请求" width="680px" :close-on-click-modal="false"
                :show-close="false">
                <div v-if="pendingApproval">
                    <p class="text-gray-600 mb-4">Agent 请求执行以下操作，请选择批准或拒绝：</p>
                    <div class="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <pre class="text-xs bg-white p-2 rounded overflow-x-auto">{{ JSON.stringify(pendingApproval, null, 2) }}
            </pre>
                    </div>
                    <el-input v-model="approvalReason" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }"
                        placeholder="可选：填写原因/备注（reason）" resize="none" />
                </div>
                <template #footer>
                    <el-button type="danger" @click="submitApproval(false)" :loading="approvalLoading">拒绝</el-button>
                    <el-button type="primary" @click="submitApproval(true)" :loading="approvalLoading">批准</el-button>
                </template>
            </el-dialog>
        </template>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import { agentApi } from '@/api/agent'
import { formatDateTime, TODO_ITEM_STATUS } from '@/utils/action'

const route = useRoute()
const agentId = computed(() => String(route.params.threadId || ''))

const entityUuid = computed(() => (route.query.entity_uuid ? String(route.query.entity_uuid) : ''))
const entityType = computed(() => (route.query.entity_type ? String(route.query.entity_type) : ''))
const extraContextText = computed(() => (route.query.extra_context ? String(route.query.extra_context) : ''))

const pageLoading = ref(true)
const pageError = ref('')

const agent = ref(null)
const sseConnected = ref(false)
const sseError = ref('')

const userPrompt = ref('')
const startLoading = ref(false)
const cancelLoading = ref(false)

const todos = ref([])
const events = ref([])

let eventSource = null
let retryCount = 0
const maxRetries = 3

const showApprovalDialog = ref(false)
const pendingApproval = ref(null)
const approvalReason = ref('')
const approvalLoading = ref(false)

const eventsScrollEl = ref(null)
const isEventsScrollAtBottom = ref(true)

function parseJsonSafe(text) {
    if (text == null || text === '') return null
    try {
        return JSON.parse(text)
    } catch {
        return null
    }
}

function pushEvent(type, data) {
    events.value.push({
        type,
        ts: new Date().toISOString(),
        data
    })
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
    () => events.value.length,
    (newLen, oldLen) => {
        const prevLen = oldLen ?? 0
        if (newLen <= prevLen || !isEventsScrollAtBottom.value || !eventsScrollEl.value) return
        nextTick(() => {
            const el = eventsScrollEl.value
            if (el) el.scrollTop = el.scrollHeight
        })
    }
)

const agentTitle = computed(() => agent.value?.name || '分析详情')
const statusRaw = computed(() => String(agent.value?.status || 'unknown'))

const statusLabelMap = {
    running: '运行中',
    awaiting_approval: '等待审批',
    completed: '已完成',
    failed: '失败',
    paused: '已暂停',
    cancelled: '已取消'
}

const statusTagMap = {
    running: 'primary',
    awaiting_approval: 'warning',
    completed: 'success',
    failed: 'danger',
    paused: 'info',
    cancelled: 'info'
}

const statusLabel = computed(() => statusLabelMap[statusRaw.value] || statusRaw.value)
const statusTagType = computed(() => statusTagMap[statusRaw.value] || 'info')

const canStart = computed(() => Boolean(agentId.value) && userPrompt.value.trim().length > 0 && !startLoading.value)
const canCancel = computed(() => Boolean(agentId.value) && (statusRaw.value === 'running' || statusRaw.value === 'awaiting_approval') && !cancelLoading.value)

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

async function loadAgentDetail() {
    if (!agentId.value) throw new Error('缺少 agent_id 参数')
    const res = await agentApi.getAgentDetail(agentId.value)
    if (res?.code !== 0) {
        throw new Error(res?.message || '获取 Agent 详情失败')
    }
    mergeAgent(res?.data || {})
    todos.value = normalizeTodosPayload(res?.data?.todos)
    if (res?.data?.pending_approval) {
        pendingApproval.value = res.data.pending_approval
    }
}

function connectSSE() {
    if (!agentId.value) {
        sseError.value = '缺少 agent_id 参数'
        return
    }

    disconnectSSE()

    try {
        const url = agentApi.getAgentStatusUrl(agentId.value)
        eventSource = new EventSource(url)

        eventSource.onopen = () => {
            sseConnected.value = true
            sseError.value = ''
            retryCount = 0
            pushEvent('sse_open', { ok: true })
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
                pushEvent('sse_retry', { retryCount, delay })
                setTimeout(() => {
                    if (retryCount <= maxRetries) connectSSE()
                }, delay)
            } else {
                sseError.value = 'SSE 连接失败，请刷新页面重试'
                pushEvent('sse_error', { message: sseError.value })
                ElMessage.error('实时连接中断，请稍后重试')
            }
        }

        eventSource.addEventListener('status', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            mergeAgent(payload)
            pushEvent('status', payload)
        })

        eventSource.addEventListener('todos', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            const list = normalizeTodosPayload(payload)
            todos.value = list
            pushEvent('todos', payload)
        })

        eventSource.addEventListener('notification', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            pushEvent('notification', payload)
        })

        eventSource.addEventListener('approval_required', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            pendingApproval.value = payload
            showApprovalDialog.value = true
            pushEvent('approval_required', payload)
        })

        eventSource.addEventListener('result', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            mergeAgent({ result: payload })
            pushEvent('result', payload)
        })

        eventSource.addEventListener('debug_prompt', (event) => {
            const payload = parseJsonSafe(event.data)
            if (!payload) return
            pushEvent('debug_prompt', payload)
        })
    } catch (e) {
        sseConnected.value = false
        sseError.value = e?.message || '创建 SSE 连接失败'
        pushEvent('sse_error', { message: sseError.value })
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
    const obj = parseJsonSafe(text)
    return obj && typeof obj === 'object' ? obj : undefined
}

async function start() {
    if (!canStart.value) return
    try {
        startLoading.value = true
        const payload = {
            agent_id: agentId.value,
            user_prompt: userPrompt.value.trim(),
            entity_uuid: entityUuid.value || null,
            entity_type: entityType.value || null,
            extra_context: parseExtraContext()
        }
        const res = await agentApi.startAgent(payload)
        if (res?.code !== 0) {
            ElMessage.error(res?.message || '启动失败')
            return
        }
        ElMessage.success('已提交启动请求')
        pushEvent('start', res?.data || {})
        connectSSE()
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
        const res = await agentApi.cancelAgent({ agent_id: agentId.value, reason: '用户取消' })
        if (res?.code !== 0) {
            ElMessage.error(res?.message || '取消失败')
            return
        }
        ElMessage.success(res?.message || '已提交取消请求')
        pushEvent('cancel', res?.data || {})
    } catch (e) {
        ElMessage.error(e?.message || '取消失败，请稍后重试')
    } finally {
        cancelLoading.value = false
    }
}

async function submitApproval(approved) {
    try {
        approvalLoading.value = true
        const decision = {
            action: approved ? 'approve' : 'reject',
            approved,
            reason: approvalReason.value?.trim() || undefined
        }
        const res = await agentApi.approveAgent({
            agent_id: agentId.value,
            decisions: [decision]
        })
        if (res?.code !== 0) {
            ElMessage.error(res?.message || '审批提交失败')
            return
        }
        ElMessage.success(res?.message || '审批已提交')
        pushEvent('approve', { decision })
        showApprovalDialog.value = false
        pendingApproval.value = null
        approvalReason.value = ''
    } catch (e) {
        ElMessage.error(e?.message || '审批提交失败，请稍后重试')
    } finally {
        approvalLoading.value = false
    }
}

async function reload() {
    pageLoading.value = true
    pageError.value = ''
    events.value = []
    todos.value = []
    pendingApproval.value = null
    approvalReason.value = ''
    try {
        await loadAgentDetail()
        connectSSE()
    } catch (e) {
        pageError.value = e?.message || '加载失败'
    } finally {
        pageLoading.value = false
    }
}

onMounted(() => {
    reload()
})

onUnmounted(() => {
    disconnectSSE()
})
</script>
