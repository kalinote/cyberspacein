<template>
    <div class="min-h-screen bg-gray-50">
        <Header />

        <div v-if="loading" class="flex items-center justify-center h-96">
            <div class="text-center">
                <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                <p class="text-gray-600">正在连接分析会话...</p>
            </div>
        </div>

        <div v-else-if="error" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div class="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
                <Icon icon="mdi:alert-circle" class="text-red-500 text-5xl mb-4" />
                <h2 class="text-xl font-bold text-gray-900 mb-2">连接失败</h2>
                <p class="text-gray-600 mb-4">{{ error }}</p>
                <button @click="connectSSE" class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                    重新连接
                </button>
            </div>
        </div>

        <template v-else>
        <DetailPageHeader
            :title="sessionData.name"
            :subtitle="sessionData.thread_id"
        >
            <template #tags>
                <el-tag :type="statusTagType" size="default">{{ statusLabel }}</el-tag>
                <el-tag v-if="sessionData.meta?.entity_type" type="info" size="default">
                    {{ sessionData.meta.entity_type }}
                </el-tag>
                <el-tag v-if="sessionData.is_running" type="warning" size="default">运行中</el-tag>
            </template>
        </DetailPageHeader>

        <section class="py-8 bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <div class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center shrink-0">
                            <Icon icon="mdi:identifier" class="text-blue-600 text-2xl" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm text-gray-500">会话 ID</p>
                            <p class="text-sm font-bold text-gray-900 truncate font-mono">{{ sessionData.thread_id }}</p>
                        </div>
                    </div>
                    <div class="bg-linear-to-br from-green-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center shrink-0">
                            <Icon icon="mdi:state-machine" class="text-green-600 text-2xl" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm text-gray-500">状态</p>
                            <p class="text-base font-bold text-gray-900">{{ statusLabel }}</p>
                        </div>
                    </div>
                    <div class="bg-linear-to-br from-amber-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center shrink-0">
                            <Icon icon="mdi:clock-outline" class="text-amber-600 text-2xl" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm text-gray-500">更新时间</p>
                            <p class="text-base font-bold text-gray-900">{{ formatDateTime(sessionData.updated_at, { includeSecond: true }) }}</p>
                        </div>
                    </div>
                    <div class="bg-linear-to-br from-purple-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center shrink-0">
                            <Icon icon="mdi:cube-outline" class="text-purple-600 text-2xl" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm text-gray-500">实体</p>
                            <p class="text-sm font-bold text-gray-900 truncate font-mono">{{ sessionData.meta?.entity_uuid || '-' }}</p>
                            <p class="text-xs text-gray-500 mt-0.5">agent: {{ sessionData.meta?.agent_id?.slice(0, 8) || '-' }}...</p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="py-8 bg-gray-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    <div class="lg:col-span-3 bg-white rounded-xl shadow-sm border border-gray-200">
                        <h2 class="text-xl font-bold text-gray-900 flex items-center p-4 pb-2">
                            <Icon icon="mdi:timeline-text" class="text-blue-600 mr-2" />
                            执行步骤
                        </h2>
                        <div class="overflow-y-auto px-4 pb-4 border-t border-gray-100" style="height: 70vh">
                            <div class="relative">
                                <div
                                    v-for="(step, index) in sessionData.steps"
                                    :key="index"
                                    class="flex gap-4 pb-6 last:pb-0"
                                >
                                    <div class="flex flex-col items-center shrink-0">
                                        <div
                                            class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                                            :class="stepNodeIconBgClass(step.node)"
                                        >
                                            <Icon :icon="stepNodeIcon(step.node)" :class="['text-sm', stepNodeIconColor(step.node)]" />
                                        </div>
                                        <template v-if="index < sessionData.steps.length - 1">
                                            <div class="w-0.5 flex-1 min-h-8 bg-gray-200 mt-1" />
                                        </template>
                                    </div>
                                    <div class="flex-1 min-w-0 pt-0.5">
                                        <div class="flex items-center gap-2 flex-wrap mb-1">
                                            <span class="font-mono text-sm font-semibold text-gray-800">{{ step.node === 'result' ? '运行结果' : step.node }}</span>
                                            <span class="text-xs text-gray-500">{{ formatDateTime(step.ts, { includeSecond: true }) }}</span>
                                            <Icon v-if="step.approval_decision === 'approve'" icon="mdi:check-circle" class="text-green-600 text-base" title="已通过" />
                                            <Icon v-if="step.approval_decision === 'reject'" icon="mdi:close-circle" class="text-red-600 text-base" title="已拒绝" />
                                            <Icon v-if="step.approval_payload && !step.approved_at" icon="mdi:clock-outline" class="text-amber-600 text-base" title="待审批" />
                                            <Icon v-if="step.run_result?.success === true" icon="mdi:check-circle" class="text-green-600 text-base" title="成功" />
                                            <Icon v-if="step.run_result?.success === false" icon="mdi:close-circle" class="text-red-600 text-base" title="失败" />
                                        </div>
                                        <div v-if="step.tool_calls?.length" class="mt-2">
                                            <el-collapse>
                                                <el-collapse-item :name="'step-' + index">
                                                    <template #title>
                                                        <span class="text-sm text-gray-600">{{ step.tool_calls.length }} 个工具调用</span>
                                                    </template>
                                                    <div class="space-y-3 pl-2 border-l-2 border-blue-100">
                                                        <div
                                                            v-for="(tc, ti) in step.tool_calls"
                                                            :key="ti"
                                                            class="text-sm"
                                                        >
                                                            <p class="font-mono font-medium text-blue-700">{{ tc.name }}</p>
                                                            <pre class="mt-1 p-2 bg-gray-50 rounded text-xs overflow-x-auto">{{ JSON.stringify(tc.args, null, 2) }}</pre>
                                                        </div>
                                                    </div>
                                                </el-collapse-item>
                                            </el-collapse>
                                        </div>
                                        <div v-if="step.result_summary" class="mt-2 p-3 rounded-lg border" :class="step.run_result?.success === true ? 'bg-green-50 border-green-200' : step.run_result?.success === false ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'">
                                            <div class="flex items-center gap-2 mb-2">
                                                <Icon v-if="step.run_result?.success === true" icon="mdi:check-circle" class="text-green-600 text-lg" />
                                                <Icon v-if="step.run_result?.success === false" icon="mdi:close-circle" class="text-red-600 text-lg" />
                                                <p class="text-xs font-medium" :class="step.run_result?.success === true ? 'text-green-800' : step.run_result?.success === false ? 'text-red-800' : 'text-gray-600'">
                                                    {{ step.run_result?.success === true ? '执行成功' : step.run_result?.success === false ? '执行失败' : '结果摘要' }} ({{ step.result_summary.content_length }} 字符)
                                                </p>
                                            </div>
                                            <p class="text-sm whitespace-pre-wrap wrap-break-word" :class="step.run_result?.success === true ? 'text-green-900' : step.run_result?.success === false ? 'text-red-900' : 'text-gray-700'">{{ step.result_summary.preview }}</p>
                                            <div v-if="step.run_result?.failure_reason" class="mt-3 pt-3 border-t border-red-300">
                                                <p class="text-xs font-medium text-red-800 mb-1">失败原因</p>
                                                <p class="text-sm text-red-900 whitespace-pre-wrap wrap-break-word">{{ step.run_result.failure_reason }}</p>
                                            </div>
                                        </div>
                                        <div v-if="step.approval_payload?.action_requests?.length" class="mt-2 p-3 bg-amber-50 rounded-lg border border-amber-200">
                                            <p class="text-xs font-medium text-amber-800 mb-2">审批内容</p>
                                            <div
                                                v-for="(ar, ai) in step.approval_payload.action_requests"
                                                :key="ai"
                                                class="text-sm text-gray-700"
                                            >
                                                <p v-if="ar.description" class="mb-1">{{ ar.description }}</p>
                                                <p class="font-mono text-xs">{{ ar.name }}</p>
                                                <pre class="mt-1 p-2 bg-white rounded text-xs overflow-x-auto">{{ JSON.stringify(ar.args, null, 2) }}</pre>
                                            </div>
                                            <template v-if="step.approved_at">
                                                <p class="text-xs text-gray-500 mt-2 flex items-center gap-1">
                                                    <Icon icon="mdi:check-circle" class="text-green-600" />
                                                    已审批于 {{ formatDateTime(step.approved_at, { includeSecond: true }) }}
                                                </p>
                                            </template>
                                            <template v-else>
                                                <div class="flex gap-3 mt-3">
                                                    <el-button type="primary" size="small">通过</el-button>
                                                    <el-button type="danger" size="small">拒绝</el-button>
                                                </div>
                                            </template>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="lg:col-span-1 min-w-0 bg-white rounded-xl shadow-sm border border-gray-200 shrink-0">
                        <h2 class="text-xl font-bold text-gray-900 flex items-center p-4 pb-2">
                            <Icon icon="mdi:format-list-checks" class="text-blue-600 mr-2" />
                            任务列表
                        </h2>
                        <div class="flex flex-col border-t border-gray-100 min-h-0" style="height: 70vh">
                            <div class="flex-4 flex flex-col min-h-0 overflow-y-auto px-4 pt-3">
                                <ul class="space-y-2 min-w-0">
                                    <li
                                        v-for="(todo, index) in sessionData.todos"
                                        :key="index"
                                        class="flex items-center gap-2 py-2 px-3 rounded-lg bg-gray-50 border border-gray-100 min-w-0"
                                    >
                                        <span
                                            v-if="todo.status === 'in_progress'"
                                            class="todo-spinner shrink-0 w-3 h-3 rounded-full border-2 border-blue-600 border-t-transparent"
                                        />
                                        <Icon
                                            v-else
                                            :icon="todoStatusIcon(todo.status)"
                                            :class="['shrink-0 text-base', todoStatusIconColor(todo.status)]"
                                        />
                                        <span class="text-sm text-gray-900 break-all min-w-0">{{ todo.content }}</span>
                                    </li>
                                </ul>
                            </div>
                            <div class="border-t border-gray-200 shrink-0 flex-1 flex flex-col p-3 min-h-0 w-full">
                                <div class="flex-1 min-h-0 w-full flex flex-col">
                                    <el-input
                                        v-model="userMessage"
                                        type="textarea"
                                        placeholder="输入消息与 Agent 对话..."
                                        class="analysis-chat-input w-full"
                                        resize="none"
                                    />
                                </div>
                                <el-button type="primary" class="mt-2 w-full shrink-0" @click="sendMessage">
                                    发送
                                </el-button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        </template>

        <el-dialog
            v-model="showApprovalDialog"
            title="审批请求"
            width="600px"
            :close-on-click-modal="false"
            :show-close="false"
        >
            <div v-if="currentApproval">
                <p class="text-gray-600 mb-4">Agent 正在请求执行以下操作，请确认是否继续：</p>
                <div
                    v-for="(request, index) in currentApproval.payload?.action_requests"
                    :key="index"
                    class="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                    <p class="text-sm font-medium text-gray-900 mb-2">{{ request.description }}</p>
                    <p class="text-xs text-gray-500 mb-1">操作: {{ request.name }}</p>
                    <pre class="text-xs bg-white p-2 rounded overflow-x-auto">{{ JSON.stringify(request.args, null, 2) }}</pre>
                </div>
            </div>
            <template #footer>
                <el-button type="danger" @click="handleReject" :loading="approvalLoading">拒绝</el-button>
                <el-button type="primary" @click="handleApprove" :loading="approvalLoading">批准</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import { Icon } from '@iconify/vue'
import { formatDateTime } from '@/utils/action'
import { agentApi } from '@/api/agent'
import { ElMessage } from 'element-plus'

const route = useRoute()
const threadId = computed(() => route.params.threadId)

const userMessage = ref('')
const sessionData = ref({
    name: '加载中...',
    thread_id: '',
    status: 'running',
    meta: {},
    steps: [],
    todos: [],
    pending_approval: null,
    updated_at: '',
    is_running: false
})
const loading = ref(true)
const error = ref(null)
let eventSource = null
let retryCount = 0
const maxRetries = 3

const showApprovalDialog = ref(false)
const currentApproval = ref(null)
const approvalLoading = ref(false)
const approvalThreadId = ref('')

function sendMessage() {
    if (!userMessage.value.trim()) return
    userMessage.value = ''
}

const statusLabelMap = {
    running: '运行中',
    awaiting_approval: '等待审批',
    completed: '已完成',
    cancelled: '已取消',
    paused: '已暂停'
}

const statusTagMap = {
    running: 'primary',
    awaiting_approval: 'warning',
    completed: 'success',
    cancelled: 'info',
    paused: 'info'
}

const statusLabel = computed(() => statusLabelMap[sessionData.value.status] || sessionData.value.status)
const statusTagType = computed(() => statusTagMap[sessionData.value.status] || 'info')

function todoStatusLabel(s) {
    const m = { pending: '待处理', in_progress: '进行中', completed: '已完成' }
    return m[s] || s
}

function todoStatusTagType(s) {
    const m = { pending: 'info', in_progress: 'warning', completed: 'success' }
    return m[s] || ''
}

function stepNodeIcon(node) {
    if (node === 'model') return 'mdi:robot'
    if (node === 'tools') return 'mdi:wrench'
    if (node === '__interrupt__') return 'mdi:hand-back-right'
    if (node === 'result') return 'mdi:flag-checkered'
    return 'mdi:circle-small'
}

function stepNodeIconBgClass(node) {
    if (node === 'model') return 'bg-blue-100'
    if (node === 'tools') return 'bg-green-100'
    if (node === '__interrupt__') return 'bg-amber-100'
    if (node === 'result') return 'bg-emerald-100'
    return 'bg-gray-100'
}

function stepNodeIconColor(node) {
    if (node === 'model') return 'text-blue-600'
    if (node === 'tools') return 'text-green-600'
    if (node === '__interrupt__') return 'text-amber-600'
    if (node === 'result') return 'text-emerald-600'
    return 'text-gray-500'
}

function todoStatusIcon(s) {
    if (s === 'pending') return 'mdi:circle-outline'
    if (s === 'in_progress') return 'mdi:progress-clock'
    if (s === 'completed') return 'mdi:check-circle'
    return 'mdi:circle-outline'
}

function todoStatusIconColor(s) {
    if (s === 'pending') return 'text-gray-400'
    if (s === 'in_progress') return 'text-amber-600'
    if (s === 'completed') return 'text-green-600'
    return 'text-gray-400'
}

function handleApprovalRequired(data) {
    console.log('收到审批请求:', data)
    currentApproval.value = data
    approvalThreadId.value = data.thread_id
    showApprovalDialog.value = true
    
    if (data.payload) {
        sessionData.value.pending_approval = data.payload
    }
}

async function handleApprove() {
    try {
        approvalLoading.value = true
        
        const response = await agentApi.approveAgent({
            thread_id: approvalThreadId.value,
            decisions: [{ type: 'approve' }]
        })
        
        if (response.code === 0) {
            ElMessage.success('已批准审批请求')
            showApprovalDialog.value = false
            currentApproval.value = null
            sessionData.value.pending_approval = null
        } else {
            ElMessage.error(response.message || '审批失败')
        }
    } catch (err) {
        console.error('审批失败:', err)
        ElMessage.error('审批失败，请稍后重试')
    } finally {
        approvalLoading.value = false
    }
}

async function handleReject() {
    try {
        approvalLoading.value = true
        
        const response = await agentApi.approveAgent({
            thread_id: approvalThreadId.value,
            decisions: [{ type: 'reject' }]
        })
        
        if (response.code === 0) {
            ElMessage.success('已拒绝审批请求')
            showApprovalDialog.value = false
            currentApproval.value = null
            sessionData.value.pending_approval = null
        } else {
            ElMessage.error(response.message || '审批失败')
        }
    } catch (err) {
        console.error('审批失败:', err)
        ElMessage.error('审批失败，请稍后重试')
    } finally {
        approvalLoading.value = false
    }
}

function handleResult(data) {
    const result = data?.result
    if (!result) return
    const summary = result.summary ?? ''
    const newStep = {
        node: 'result',
        ts: new Date().toISOString(),
        result_summary: { preview: summary, content_length: summary.length },
        run_result: { success: result.success, failure_reason: result.failure_reason }
    }
    const steps = sessionData.value.steps || []
    const last = steps[steps.length - 1]
    if (last?.node === 'result') {
        sessionData.value.steps = steps.slice(0, -1).concat(newStep)
    } else {
        sessionData.value.steps = [...steps, newStep]
    }
}

function connectSSE() {
    if (!threadId.value) {
        error.value = '缺少 thread_id 参数'
        loading.value = false
        return
    }

    try {
        const url = agentApi.getAgentStatusUrl(threadId.value)
        eventSource = new EventSource(url)

        eventSource.onopen = () => {
            console.log('SSE 连接已建立')
            retryCount = 0
            error.value = null
        }

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                
                if (data.type === 'status' && data.data) {
                    sessionData.value = data.data
                    loading.value = false
                } else if (data.type === 'approval_required' && data.data) {
                    handleApprovalRequired(data.data)
                } else if (data.type === 'result' && data.data) {
                    handleResult(data.data)
                }
            } catch (err) {
                console.error('解析 SSE 数据失败:', err)
            }
        }

        eventSource.onerror = (err) => {
            console.error('SSE 连接错误:', err)
            
            if (eventSource) {
                eventSource.close()
                eventSource = null
            }

            if (sessionData.value.status === 'completed' || sessionData.value.status === 'cancelled') {
                console.log('任务已结束，不再重连')
                loading.value = false
                return
            }

            if (retryCount < maxRetries) {
                retryCount++
                const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 10000)
                console.log(`${delay}ms 后重试第 ${retryCount} 次...`)
                
                setTimeout(() => {
                    if (retryCount <= maxRetries) {
                        connectSSE()
                    }
                }, delay)
            } else {
                error.value = 'SSE 连接失败，请刷新页面重试'
                loading.value = false
                ElMessage.error('实时连接中断，请刷新页面')
            }
        }
    } catch (err) {
        console.error('创建 SSE 连接失败:', err)
        error.value = '创建连接失败'
        loading.value = false
    }
}

function disconnectSSE() {
    if (eventSource) {
        eventSource.close()
        eventSource = null
        console.log('SSE 连接已关闭')
    }
}

onMounted(() => {
    connectSSE()
})

onUnmounted(() => {
    disconnectSSE()
})
</script>

<style scoped>
.todo-spinner {
    animation: todo-spin 0.8s linear infinite;
}
@keyframes todo-spin {
    to {
        transform: rotate(360deg);
    }
}
.analysis-chat-input {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}
.analysis-chat-input :deep(.el-textarea) {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}
.analysis-chat-input :deep(.el-textarea__inner) {
    flex: 1;
    min-height: 0;
    width: 100%;
}
</style>
