<template>
    <div :class="isMobile ? 'mobile-analysis-page' : 'min-h-screen bg-gray-50'">
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
            <section v-if="isMobile" class="mobile-analysis-shell" :class="{ 'keyboard-open': keyboardOpen }" aria-label="分析会话">
                <header class="mobile-analysis-heading">
                    <div class="min-w-0">
                        <h1 :title="pageTitle">{{ pageTitle }}</h1>
                        <div class="flex items-center gap-2 mt-1">
                            <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
                            <span class="text-xs" :class="sseConnected ? 'text-emerald-600' : 'text-amber-600'">{{ sseConnected ? '实时连接' : '连接中断' }}</span>
                        </div>
                    </div>
                    <button type="button" @click="showSessionInfo = true"><Icon icon="mdi:information-outline" /> 资料</button>
                </header>
                <div v-if="!sseConnected" class="mobile-session-reconnect">
                    <span>进度连接未就绪，可重新获取最新会话。</span>
                    <button type="button" @click="reload">重新连接</button>
                </div>
                <AgentRealtimeEventsPanel
                    :show-header="false"
                    :timeline-items="timelineItems"
                    :register-events-scroll-el="registerEventsScrollEl"
                    :on-events-scroll="onEventsScroll"
                    :history-loading="historyLoading"
                    :has-more-history="hasMoreHistory"
                    @load-older="loadOlderEvents"
                />
                <AgentTodosPanel :todos="todos" :todo-status-icon="todoStatusIcon" :todo-status-icon-color="todoStatusIconColor" />
                <AgentContinueChatBar
                    :show-status="false"
                    :user-prompt="userPrompt"
                    :send-loading="sendLoading"
                    :cancel-loading="cancelLoading"
                    :can-send-message="canSendMessage"
                    :can-cancel="canCancel"
                    :has-session="Boolean(sessionId)"
                    placeholder="继续提问或补充分析要求"
                    @update:user-prompt="userPrompt = $event"
                    @send="sendMessage"
                    @cancel="cancel"
                />
                <MobileSheet v-model="showSessionInfo" title="会话资料">
                    <dl class="mobile-session-info">
                        <div><dt>分析引擎</dt><dd>{{ pageTitle }}</dd></div>
                        <div><dt>会话标识</dt><dd>{{ sessionId }}</dd></div>
                        <div><dt>引擎标识</dt><dd>{{ agentId }}</dd></div>
                        <div v-if="session?.workspace_id"><dt>工作区</dt><dd>{{ session.workspace_id }}</dd></div>
                        <div v-if="session?.updated_at"><dt>更新时间</dt><dd>{{ formatDateTime(session.updated_at) }}</dd></div>
                        <div v-if="entityType"><dt>材料类型</dt><dd>{{ entityType }}</dd></div>
                        <div v-if="entityUuid"><dt>材料标识</dt><dd>{{ entityUuid }}</dd></div>
                    </dl>
                    <div class="mt-5 border-t border-gray-100 pt-4"><AgentAutoApproveSwitch /></div>
                </MobileSheet>
            </section>
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
                                :history-loading="historyLoading"
                                :has-more-history="hasMoreHistory"
                                @load-older="loadOlderEvents"
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

            </template>

            <component
                :is="isMobile ? ElDrawer : ElDialog"
                v-model="showApprovalDialog"
                :title="approvalDialogTitle"
                width="760px"
                direction="btt"
                size="100%"
                :class="{ 'mobile-agent-approval': isMobile }"
                :modal-class="isMobile ? 'mobile-agent-approval-overlay' : ''"
                :append-to-body="isMobile"
                :close-on-press-escape="!isMobile"
                :close-on-click-modal="false"
                :show-close="false"
                @closed="onApprovalDialogClosed"
            >
                <template v-if="isMobile" #header="{ titleId, titleClass }">
                    <div class="mobile-approval-heading">
                        <h2 :id="titleId" :class="titleClass">{{ approvalDialogTitle }}</h2>
                        <button type="button" @click="router.replace(approvalExit.path)">{{ approvalExit.label }}</button>
                    </div>
                </template>
                <div v-if="pendingApproval">
                    <p v-if="isMobile && !canOperate" class="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">当前账号没有执行审批的权限，可查看请求详情。</p>
                    <p class="text-gray-600 mb-4">Agent 请求执行以下操作，请选择批准或拒绝：</p>
                    <AgentApprovalPanel :approval="pendingApproval" />
                    <div v-if="showRejectReason" class="mt-4 pt-4 border-t border-gray-100">
                        <p class="text-sm text-gray-600 mb-2">拒绝理由（可选）</p>
                        <el-input
                            ref="approvalReasonInput"
                            v-model="approvalReason"
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 4 }"
                            placeholder="请填写拒绝原因"
                            aria-label="审批拒绝理由"
                            resize="none"
                        />
                    </div>
                </div>
                <template #footer>
                    <template v-if="showRejectReason">
                        <el-button @click="cancelRejectFlow" :disabled="approvalLoading">返回</el-button>
                        <el-button type="danger" :disabled="!canOperate" @click="canOperate && submitApprovalDecision('reject')" :loading="approvalLoading">确认拒绝</el-button>
                    </template>
                    <template v-else>
                        <el-button type="danger" :disabled="!canOperate" @click="showRejectReason = true" :loading="approvalLoading">拒绝</el-button>
                        <el-button type="primary" :disabled="!canOperate" @click="canOperate && submitApprovalDecision('approve')" :loading="approvalLoading">批准</el-button>
                    </template>
                </template>
            </component>
        </template>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import AgentRealtimeEventsPanel from '@/components/agent/AgentRealtimeEventsPanel.vue'
import AgentContinueChatBar from '@/components/agent/AgentContinueChatBar.vue'
import AgentApprovalPanel from '@/components/agent/approval/AgentApprovalPanel.vue'
import AgentAutoApproveSwitch from '@/components/agent/AgentAutoApproveSwitch.vue'
import AgentTodosPanel from '@/components/agent/AgentTodosPanel.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { ElDialog, ElDrawer } from 'element-plus'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { rememberRecentVisit } from '@/stores/recentVisits'
import { useAgentSessionStream } from '@/composables/useAgentSessionStream'
import { formatDateTime } from '@/utils/action'

const route = useRoute()
const router = useRouter()
const { isMobile, keyboardOpen } = useMobileViewport()
const showSessionInfo = ref(false)
const canOperate = computed(() => !isMobile.value || hasPerm(PERM.operations.agent.agent.execute))
const approvalReasonInput = ref(null)
const approvalExit = computed(() => {
    if (hasPerm(PERM.pages.agent.sessions.visible) && hasPerm(PERM.pages.agent.sessions.access)
        && hasPerm(PERM.operations.agent.session.read)) {
        return { path: '/agent/sessions', label: '返回会话列表' }
    }
    const back = window.history.state?.back
    if (typeof back === 'string' && back.startsWith('/')) {
        const previous = router.resolve(back)
        if (previous.matched.length && previous.path !== route.path && !['login', '403'].includes(previous.name)
            && (!previous.meta.requiresAuth || hasPerm(previous.meta.pagePermission))) {
            return { path: back, label: '返回上一页' }
        }
    }
    const fallback = router.getRoutes().find(record => record.path !== route.path && !record.path.includes(':')
        && record.meta?.requiresAuth && record.meta.pagePermission && hasPerm(record.meta.pagePermission))
    return { path: fallback?.path || '/403', label: fallback ? '返回可用页面' : '返回访问说明' }
})
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
let pageRequest = 0

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
    hasMoreHistory,
    historyLoading,
    loadOlderEvents,
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

watch(showRejectReason, async (show) => {
    if (!show || !isMobile.value) return
    await nextTick()
    if (!showRejectReason.value) return
    approvalReasonInput.value?.focus()
    approvalReasonInput.value?.textarea?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
})

const pageTitle = computed(() => session.value?.agent_name || '分析详情')

async function reload() {
    const requestId = ++pageRequest
    const requestedSession = sessionId.value
    pageLoading.value = true
    pageError.value = ''
    session.value = null
    try {
        await reloadSession({ loadDetail: true })
        if (requestId === pageRequest && requestedSession === sessionId.value && session.value) {
            rememberRecentVisit(route, `${session.value.agent_name || '分析'} 会话`)
        }
    } catch (e) {
        if (requestId !== pageRequest) return
        pageError.value = e?.message || '加载失败'
    } finally {
        if (requestId === pageRequest) pageLoading.value = false
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
    pageRequest += 1
    disconnectSSE()
})
</script>

<style scoped>
.mobile-analysis-shell { position: fixed; z-index: 80; top: calc(var(--mobile-viewport-top, 0px) + var(--mobile-header-height)); left: 0; right: 0; height: calc(var(--mobile-viewport-height, 100dvh) - var(--mobile-header-height) - var(--mobile-nav-height)); display: flex; flex-direction: column; min-height: 0; background: #fff; }
.mobile-analysis-shell.keyboard-open { height: calc(var(--mobile-viewport-height, 100dvh) - var(--mobile-header-height)); }
.mobile-analysis-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #e2e8f0; flex-shrink: 0; }
.mobile-analysis-heading h1 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 17px; font-weight: 700; }
.mobile-analysis-heading button { display: flex; align-items: center; gap: 4px; min-height: 44px; flex-shrink: 0; color: #2563eb; font-size: 13px; }
.mobile-session-reconnect { display: flex; align-items: center; gap: 8px; padding: 4px 16px; font-size: 12px; background: #fffbeb; color: #92400e; }
.mobile-session-reconnect button { min-height: 44px; flex-shrink: 0; color: #2563eb; }
.mobile-session-info > div { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 12px; padding: 10px 0; font-size: 14px; }
.mobile-session-info dt { color: #64748b; }
.mobile-session-info dd { margin: 0; overflow-wrap: anywhere; }
</style>

<style>
@media (max-width: 767px) {
    .mobile-agent-approval-overlay { top: var(--mobile-viewport-top, 0px); bottom: auto; height: var(--mobile-viewport-height, 100dvh); }
    .mobile-agent-approval .el-drawer__header { margin-bottom: 0; padding: 20px 20px 12px; color: #0f172a; font-weight: 700; }
    .mobile-approval-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; width: 100%; }
    .mobile-approval-heading h2 { flex: 1; min-width: 0; font-size: 17px; overflow-wrap: anywhere; }
    .mobile-approval-heading button { flex-shrink: 0; min-height: 44px; color: #2563eb; font-size: 13px; font-weight: 400; }
    .mobile-agent-approval .el-drawer__body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
    .mobile-agent-approval .el-drawer__footer { display: flex; gap: 10px; padding: 12px 20px max(16px, env(safe-area-inset-bottom)); border-top: 1px solid #e2e8f0; }
    .mobile-agent-approval .el-drawer__footer button { flex: 1; min-height: 44px; margin: 0; }
}
</style>
