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
            <DetailPageHeader :title="pageTitle" :subtitle="sessionId">
                <template #tags>
                    <el-tag :type="statusTagType" size="default">{{ statusLabel }}</el-tag>
                    <el-tag v-if="session?.workspace_id" type="info" size="default">workspace: {{ session.workspace_id
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
                                        <p class="text-sm text-gray-500">继续对话</p>
                                        <p class="text-xs text-gray-500 mt-1">
                                            将调用 <span class="font-mono">/agent/message</span>，并通过 <span
                                                class="font-mono">/agent/status</span> 实时展示进度
                                        </p>
                                    </div>
                                    <AgentAutoApproveSwitch />
                                </div>
                                <AgentContinueChatBar
                                    class="mt-4"
                                    :compact="false"
                                    :show-status="false"
                                    :user-prompt="userPrompt"
                                    :send-loading="sendLoading"
                                    :cancel-loading="cancelLoading"
                                    :can-send-message="canSendMessage"
                                    :can-cancel="canCancel"
                                    :has-session="Boolean(sessionId)"
                                    @update:user-prompt="userPrompt = $event"
                                    @send="sendMessage"
                                    @cancel="cancel"
                                />
                                <div class="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                                    <span v-if="entityType">entity_type: <span class="font-mono">{{ entityType
                                            }}</span></span>
                                    <span v-if="entityUuid">entity_uuid: <span class="font-mono">{{ entityUuid
                                            }}</span></span>
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
                                    <div class="flex justify-between gap-3" v-if="session?.updated_at">
                                        <span class="text-gray-500">更新时间</span>
                                        <span class="text-gray-900">{{ formatDateTime(session.updated_at, {
                                            includeSecond: true,
                                        }) }}</span>
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
                        <div class="lg:col-span-8 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col min-h-0" style="height: 70vh">
                            <AgentRealtimeEventsPanel
                                class="h-full min-h-0"
                                :timeline-items="timelineItems"
                                :register-events-scroll-el="registerEventsScrollEl"
                                :on-events-scroll="onEventsScroll"
                                scroll-class="border-t border-gray-100"
                            />
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import AgentRealtimeEventsPanel from '@/components/agent/AgentRealtimeEventsPanel.vue'
import AgentContinueChatBar from '@/components/agent/AgentContinueChatBar.vue'
import AgentApprovalPanel from '@/components/agent/approval/AgentApprovalPanel.vue'
import AgentAutoApproveSwitch from '@/components/agent/AgentAutoApproveSwitch.vue'
import { useAgentSessionStream } from '@/composables/useAgentSessionStream'
import { formatDateTime } from '@/utils/action'

const route = useRoute()
const sessionId = computed(() => String(route.params.sessionId || ''))
const agentIdFromQuery = computed(() => (route.query.agent_id ? String(route.query.agent_id) : ''))
const injectionParamText = computed(() =>
    route.query.injection_param ? String(route.query.injection_param) : ''
)

const injectionParamPreview = computed(() => {
    const raw = injectionParamText.value.trim()
    if (!raw) return null
    try {
        const obj = JSON.parse(raw)
        return obj && typeof obj === 'object' ? obj : null
    } catch {
        return null
    }
})

const entityUuid = computed(() =>
    String(injectionParamPreview.value?.entity_uuid ?? '')
)
const entityType = computed(() =>
    String(injectionParamPreview.value?.entity_type ?? '')
)

const pageLoading = ref(true)
const pageError = ref('')

const stream = useAgentSessionStream({
    sessionId,
    agentIdFallback: agentIdFromQuery,
    injectionParam: injectionParamText,
})

const {
    session,
    agentId,
    userPrompt,
    sendLoading,
    cancelLoading,
    todos,
    timelineItems,
    sseConnected,
    showApprovalDialog,
    pendingApproval,
    approvalReason,
    showRejectReason,
    approvalLoading,
    approvalDialogTitle,
    registerEventsScrollEl,
    onEventsScroll,
    statusLabel,
    statusTagType,
    canSendMessage,
    canCancel,
    todoStatusIcon,
    todoStatusIconColor,
    disconnectSSE,
    reloadSession,
    sendMessage,
    cancel,
    cancelRejectFlow,
    submitApprovalDecision,
    onApprovalDialogClosed,
} = stream

const pageTitle = computed(() => session.value?.agent_name || '分析详情')

async function reload() {
    pageLoading.value = true
    pageError.value = ''
    session.value = null
    try {
        await reloadSession({ loadDetail: true })
    } catch (e) {
        pageError.value = e?.message || '加载失败'
    } finally {
        pageLoading.value = false
    }
}

watch(sessionId, (sid, oldSid) => {
    if (sid === oldSid) return
    reload()
})

onMounted(() => {
    reload()
})

onUnmounted(() => {
    disconnectSSE()
})
</script>
