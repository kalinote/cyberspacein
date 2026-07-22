<template>
    <article class="min-w-0 text-gray-800">
        <template v-if="item.kind === 'run_details'">
            <button
                type="button"
                class="group flex w-full min-w-0 items-center gap-2 text-left text-xs text-gray-500 hover:text-gray-800"
                :aria-expanded="expanded"
                @click="toggleExpanded"
            >
                <Icon icon="mdi:progress-wrench" class="shrink-0 text-base" />
                <span class="min-w-0 flex-1 truncate">{{ runDetailsSummary }}</span>
                <Icon
                    icon="mdi:chevron-right"
                    class="shrink-0 text-base transition-transform duration-150"
                    :class="expanded ? 'rotate-90' : ''"
                />
            </button>
            <div v-if="expanded" class="mt-3 ml-2 space-y-3 border-l border-gray-200 pl-4">
                <div v-for="row in runTechnicalRows" :key="row.key" class="min-w-0 text-xs text-gray-600">
                    <div class="flex min-w-0 items-start gap-2">
                        <Icon :icon="row.icon" class="mt-0.5 shrink-0 text-sm" :class="row.iconClass" />
                        <span class="min-w-0 flex-1 wrap-break-word">{{ row.label }}</span>
                        <span class="hidden shrink-0 text-gray-400 sm:inline">{{ row.time }}</span>
                    </div>
                    <pre
                        v-if="row.raw"
                        class="mt-2 max-h-64 overflow-auto rounded-md bg-gray-50 px-3 py-2 font-mono text-[11px] leading-5 text-gray-600 whitespace-pre-wrap wrap-break-word"
                    >{{ row.raw }}</pre>
                </div>
            </div>
        </template>

        <template v-else-if="item.kind === 'user_message'">
            <div class="flex min-w-0 justify-end">
                <div class="min-w-0 max-w-[92%] rounded-2xl rounded-tr-sm bg-slate-100 px-4 py-3 sm:max-w-[85%]">
                    <div class="mb-2 flex items-center justify-end gap-2 text-xs text-gray-500">
                        <span class="hidden sm:inline">{{ formatTime(item.ts) }}</span>
                        <span class="font-medium text-gray-700">用户输入</span>
                        <Icon icon="mdi:account-outline" class="shrink-0 text-base text-emerald-600" />
                    </div>
                    <MarkdownViewer :content="userMessageContent" :breaks="true" custom-class="min-w-0" />
                </div>
            </div>
        </template>

        <template v-else-if="item.kind === 'assistant_reasoning_stream'">
            <button
                type="button"
                class="group flex w-full min-w-0 items-center gap-2 text-left text-sm text-gray-500 hover:text-gray-800"
                :aria-expanded="expanded"
                @click="toggleExpanded"
            >
                <Icon
                    :icon="item.streaming ? 'mdi:head-cog-outline' : 'mdi:brain'"
                    class="shrink-0 text-base text-violet-500"
                    :class="item.streaming ? 'animate-pulse' : ''"
                />
                <span class="font-medium">{{ item.streaming ? '正在思考' : '思考过程' }}</span>
                <span v-if="item.resuming" class="text-xs text-amber-600">后续仍会继续</span>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
                <Icon
                    icon="mdi:chevron-right"
                    class="ml-auto shrink-0 text-base transition-transform duration-150"
                    :class="expanded ? 'rotate-90' : ''"
                />
            </button>
            <div v-if="expanded" class="mt-3 ml-2 border-l border-violet-200 pl-4 text-sm text-gray-600">
                <MarkdownViewer
                    v-if="item.text"
                    :content="item.text"
                    :breaks="true"
                    custom-class="min-w-0"
                />
                <span v-else class="text-xs text-gray-400">等待思考内容…</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'tool_activity'">
            <button
                type="button"
                class="group flex w-full min-w-0 items-start gap-2 text-left text-sm text-gray-500 hover:text-gray-800"
                :aria-expanded="expanded"
                @click="toggleExpanded"
            >
                <Icon
                    icon="mdi:console-line"
                    class="mt-0.5 shrink-0 text-base text-slate-500"
                    :class="item.running ? 'animate-pulse' : ''"
                />
                <span class="shrink-0 font-medium">{{ toolActivityLabel }}</span>
                <span v-if="toolNames" class="min-w-0 flex-1 wrap-break-word text-gray-400">{{ toolNames }}</span>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.updatedTs || item.ts) }}</span>
                <Icon
                    icon="mdi:chevron-right"
                    class="mt-0.5 shrink-0 text-base transition-transform duration-150"
                    :class="expanded ? 'rotate-90' : ''"
                />
            </button>
            <div v-if="expanded" class="mt-3 ml-2 space-y-4 border-l border-gray-200 pl-4">
                <div v-for="tool in toolDetails" :key="tool.key" class="min-w-0">
                    <div class="flex min-w-0 items-center gap-2 text-xs">
                        <Icon :icon="tool.icon" class="shrink-0 text-sm" :class="tool.iconClass" />
                        <code class="min-w-0 wrap-break-word font-medium text-gray-800">{{ tool.name }}</code>
                        <span class="text-gray-400">{{ tool.statusLabel }}</span>
                    </div>
                    <div v-if="tool.argumentsText" class="mt-2 min-w-0">
                        <p class="mb-1 text-[11px] text-gray-400">参数</p>
                        <pre class="max-h-56 overflow-auto rounded-md bg-gray-50 px-3 py-2 font-mono text-[11px] leading-5 text-gray-600 whitespace-pre-wrap wrap-break-word">{{ tool.argumentsText }}</pre>
                    </div>
                    <div v-if="tool.detail" class="mt-2 min-w-0">
                        <p class="mb-1 text-[11px] text-gray-400">结果</p>
                        <p class="text-xs leading-5 whitespace-pre-wrap wrap-break-word" :class="tool.status === 'error' ? 'text-red-700' : 'text-gray-600'">{{ tool.detail }}</p>
                    </div>
                </div>
                <MarkdownViewer
                    v-if="item.assistantContent"
                    :content="item.assistantContent"
                    :breaks="true"
                    custom-class="min-w-0 text-sm text-gray-600"
                />
                <p v-if="toolUsageText" class="text-[11px] text-gray-400">用量：{{ toolUsageText }}</p>
                <p v-if="toolErrorText" class="border-l-2 border-red-400 pl-3 text-xs text-red-700 whitespace-pre-wrap wrap-break-word">{{ toolErrorText }}</p>
            </div>
        </template>

        <template v-else-if="item.kind === 'assistant_stream'">
            <div class="mb-2 flex items-center gap-2 text-xs text-gray-500">
                <Icon icon="mdi:creation-outline" class="shrink-0 text-base text-blue-600" />
                <span class="font-medium text-gray-700">分析引擎</span>
                <span v-if="item.streaming" class="text-blue-600">正在输出</span>
                <span class="hidden sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
            <div class="min-w-0">
                <MarkdownViewer v-if="item.text" :content="item.text" :breaks="true" custom-class="min-w-0" />
                <span v-else class="text-xs text-gray-400">等待输出…</span>
                <span
                    v-if="item.streaming"
                    class="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 rounded-sm bg-blue-500 align-middle animate-pulse"
                    aria-hidden="true"
                />
            </div>
        </template>

        <template v-else-if="item.kind === 'progress'">
            <div class="mb-2 flex items-center gap-2 text-xs text-gray-500">
                <Icon icon="mdi:text-long" class="shrink-0 text-base text-blue-500" />
                <span class="font-medium text-gray-700">进度更新</span>
                <span v-if="item.payload?.tool_hint" class="text-amber-600">工具提示</span>
                <span class="hidden sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
            <MarkdownViewer
                :content="String(item.payload?.content ?? '—')"
                :breaks="true"
                custom-class="min-w-0 text-sm"
            />
        </template>

        <template v-else-if="item.kind === 'todos'">
            <div class="flex min-w-0 items-start gap-2 text-sm text-gray-500">
                <Icon icon="mdi:format-list-checks" class="mt-0.5 shrink-0 text-base text-emerald-600" />
                <div class="min-w-0 flex-1">
                    <p><span class="font-medium text-gray-700">更新了任务列表</span> · {{ item.todoCount ?? 0 }} 项</p>
                    <p v-if="item.todoPreview" class="mt-1 text-xs text-gray-400 wrap-break-word">{{ item.todoPreview }}</p>
                </div>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'approval_required'">
            <div class="flex min-w-0 items-start gap-2 text-sm" :class="approvalColorClass">
                <Icon :icon="approvalIcon" class="mt-0.5 shrink-0 text-base" />
                <div class="min-w-0 flex-1">
                    <p class="font-medium">
                        {{ approvalPending ? '等待审批' : `审批${approvalResolutionLabel || '已处理'}` }}
                        <span class="font-normal opacity-75">· {{ approvalSourceLabel }}</span>
                    </p>
                    <p v-if="approvalEntityLine" class="mt-1 text-xs opacity-80 wrap-break-word">{{ approvalEntityLine }}</p>
                    <p v-if="approvalReasonText" class="mt-1 text-xs opacity-80 whitespace-pre-wrap wrap-break-word">说明：{{ approvalReasonText }}</p>
                    <p v-if="rejectReasons.length" class="mt-1 text-xs opacity-80">审批意见：{{ rejectReasons.join('；') }}</p>
                </div>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'notification'">
            <div class="flex min-w-0 items-start gap-2 text-sm" :class="notificationTextClass">
                <Icon :icon="notificationIcon" class="mt-0.5 shrink-0 text-base" />
                <div class="min-w-0 flex-1">
                    <p class="font-medium">{{ notificationTitle }}</p>
                    <p class="mt-1 whitespace-pre-wrap wrap-break-word">{{ item.payload?.message ?? '—' }}</p>
                </div>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.payload?.created_at || item.ts) }}</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'task_submitted'">
            <div class="flex min-w-0 items-start gap-2 text-sm" :class="item.payload?.success ? 'text-green-700' : 'text-red-700'">
                <Icon :icon="item.payload?.success ? 'mdi:check-circle-outline' : 'mdi:alert-circle-outline'" class="mt-0.5 shrink-0 text-base" />
                <div class="min-w-0 flex-1">
                    <p class="font-medium">任务结果{{ item.payload?.success ? '已提交' : '提交失败' }}</p>
                    <p v-if="item.payload?.short_summary" class="mt-1 text-gray-700 whitespace-pre-wrap wrap-break-word">{{ item.payload.short_summary }}</p>
                </div>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'result'">
            <div class="flex min-w-0 items-start gap-2 text-sm">
                <Icon :icon="resultIcon" class="mt-0.5 shrink-0 text-base" :class="resultIconClass" />
                <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span class="font-medium text-gray-800">{{ resultStopReasonLabel || '本轮结束' }}</span>
                        <span v-if="resultSessionStatusLabel" class="text-xs" :class="resultIconClass">{{ resultSessionStatusLabel }}</span>
                    </div>
                    <p v-if="resultSummary" class="mt-2 text-gray-700 whitespace-pre-wrap wrap-break-word">{{ resultSummary }}</p>
                    <MarkdownViewer
                        v-if="resultUserMarkdown"
                        :content="resultUserMarkdown"
                        :breaks="true"
                        custom-class="mt-3 min-w-0"
                    />
                    <p v-if="resultToolsLine" class="mt-2 text-xs text-gray-400">使用工具：{{ resultToolsLine }}</p>
                    <div v-if="resultErrorText" class="mt-3 border-l-2 border-red-400 pl-3">
                        <p class="text-xs font-medium text-red-700">错误信息</p>
                        <pre class="mt-1 text-xs text-red-700 whitespace-pre-wrap wrap-break-word">{{ resultErrorText }}</pre>
                    </div>
                </div>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
            </div>
        </template>

        <template v-else-if="item.kind === 'parse_error'">
            <button
                type="button"
                class="flex w-full min-w-0 items-start gap-2 text-left text-sm text-red-700"
                :aria-expanded="expanded"
                @click="toggleExpanded"
            >
                <Icon icon="mdi:alert-outline" class="mt-0.5 shrink-0 text-base" />
                <span class="min-w-0 flex-1 wrap-break-word">{{ item.sseType }} 解析失败：{{ item.error }}</span>
                <Icon icon="mdi:chevron-right" class="shrink-0 text-base transition-transform duration-150" :class="expanded ? 'rotate-90' : ''" />
            </button>
            <pre v-if="expanded" class="mt-3 ml-6 max-h-56 overflow-auto rounded-md bg-red-50 px-3 py-2 text-xs text-red-800 whitespace-pre-wrap wrap-break-word">{{ item.rawSnippet }}</pre>
        </template>

        <template v-else-if="item.kind === 'system'">
            <div class="flex min-w-0 items-start gap-2 text-sm text-red-700">
                <Icon icon="mdi:alert-circle-outline" class="mt-0.5 shrink-0 text-base" />
                <div class="min-w-0 flex-1">
                    <p class="font-medium">{{ item.systemSubtype || '系统错误' }}</p>
                    <p class="mt-1 whitespace-pre-wrap wrap-break-word">{{ systemMessage }}</p>
                    <pre v-if="item.metaJson" class="mt-2 max-h-48 overflow-auto rounded-md bg-red-50 px-3 py-2 text-xs whitespace-pre-wrap wrap-break-word">{{ item.metaJson }}</pre>
                </div>
            </div>
        </template>

        <template v-else>
            <button
                type="button"
                class="flex w-full min-w-0 items-start gap-2 text-left text-sm text-gray-500 hover:text-gray-800"
                :aria-expanded="expanded"
                @click="toggleExpanded"
            >
                <Icon icon="mdi:code-json" class="mt-0.5 shrink-0 text-base" />
                <span class="min-w-0 flex-1 font-mono wrap-break-word">{{ item.sseType || item.kind || '未知事件' }}</span>
                <span class="hidden shrink-0 text-xs text-gray-400 sm:inline">{{ formatTime(item.ts) }}</span>
                <Icon icon="mdi:chevron-right" class="shrink-0 text-base transition-transform duration-150" :class="expanded ? 'rotate-90' : ''" />
            </button>
            <pre v-if="expanded" class="mt-3 ml-6 max-h-64 overflow-auto rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-600 whitespace-pre-wrap wrap-break-word">{{ unknownRaw }}</pre>
        </template>
    </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import MarkdownViewer from '@/components/common/MarkdownViewer.vue'
import { formatDateTime } from '@/utils/action'
import { stringifyJsonSafe } from '@/utils/agentSse'
import {
    getApprovalSourceLabel,
    getEntityTypeLabel,
    getModifyEntityPayload,
    getWikiCreatePayload,
    getWikiEditOperationLabel,
    getWikiEditPayload,
    isApprovalAwaitingUserAction,
    truncateUuid,
} from '@/utils/agentApproval'

const props = defineProps({
    item: {
        type: Object,
        required: true,
    },
})

const expanded = ref(false)

function toggleExpanded() {
    expanded.value = !expanded.value
}

function formatTime(ts) {
    return formatDateTime(ts, { includeSecond: true })
}

const RUNTIME_STATUS_LABEL = {
    idle: '空闲',
    unknown: '未知',
    running: '运行中',
    awaiting_approval: '等待审批',
    completed: '已完成',
    failed: '失败',
    paused: '已暂停',
    cancelled: '已取消',
}

const RESULT_STOP_REASON_LABEL = {
    completed: '任务完成',
    tool_error: '工具调用错误',
    error: '运行错误',
    empty_final_response: '最终回复为空',
    max_iterations: '达到迭代上限',
    awaiting_approval: '等待人工审批',
}

const runTechnicalRows = computed(() => {
    return (props.item.technicalItems || []).map((raw, index) => {
        let label = raw.message || raw.systemSubtype || raw.sseType || raw.kind || '运行事件'
        let icon = 'mdi:circle-small'
        let iconClass = 'text-gray-400'
        let detail = ''
        if (raw.kind === 'status') {
            const status = String(raw.payload?.status || 'unknown')
            label = `会话状态 · ${RUNTIME_STATUS_LABEL[status] || status}`
            icon = 'mdi:state-machine'
            iconClass = 'text-blue-500'
        } else if (raw.kind === 'debug_prompt') {
            label = `调试提示词${raw.payload?.model ? ` · ${raw.payload.model}` : ''}`
            icon = 'mdi:bug-outline'
            iconClass = 'text-violet-500'
            detail = stringifyJsonSafe(raw.payload, 2)
        } else if (raw.kind === 'step') {
            label = `迭代 #${raw.payload?.iteration ?? raw.payload?.step?.iteration ?? '—'}`
            icon = 'mdi:stairs'
            detail = stringifyJsonSafe(raw.payload, 2)
        } else if (raw.kind === 'system') {
            icon = raw.systemSubtype === 'sse_open' ? 'mdi:access-point-check' : 'mdi:cog-outline'
            iconClass = raw.systemSubtype === 'sse_open' ? 'text-green-500' : 'text-gray-400'
            detail = raw.metaJson || ''
        }
        return {
            key: raw.displayKey || raw.id || `${raw.kind}-${index}`,
            label,
            icon,
            iconClass,
            raw: detail,
            time: formatTime(raw.ts),
        }
    })
})

const runDetailsSummary = computed(() => {
    const items = props.item.technicalItems || []
    const connected = items.some((entry) => entry.kind === 'system' && entry.systemSubtype === 'sse_open')
    const statusItem = [...items].reverse().find((entry) => entry.kind === 'status')
    const status = String(props.item.runtimeStatus || statusItem?.payload?.status || '')
    const parts = []
    if (connected) parts.push('实时通道已建立')
    if (status) parts.push(RUNTIME_STATUS_LABEL[status] || status)
    parts.push(`${items.length} 条运行记录`)
    return parts.join(' · ')
})

const userMessageContent = computed(() => String(props.item.payload?.content ?? '—'))

const toolDetails = computed(() => {
    const calls = Array.isArray(props.item.toolCalls) ? props.item.toolCalls : []
    const events = Array.isArray(props.item.toolEvents) ? props.item.toolEvents : []
    const count = Math.max(calls.length, events.length)
    const details = []
    for (let index = 0; index < count; index++) {
        const call = calls[index] || null
        const event = events[index] || null
        const status = event?.status || (props.item.running ? 'running' : 'unknown')
        const args = call?.arguments
        const hasArguments = args != null && (
            typeof args !== 'object'
            || Array.isArray(args)
            || Object.keys(args).length > 0
        )
        details.push({
            key: `${call?.name || event?.name || 'tool'}-${index}`,
            name: call?.name || event?.name || '未知工具',
            status,
            statusLabel: status === 'ok' ? '已完成' : status === 'error' ? '失败' : status === 'running' ? '运行中' : '',
            icon: status === 'ok' ? 'mdi:check-circle-outline' : status === 'error' ? 'mdi:alert-circle-outline' : 'mdi:progress-clock',
            iconClass: status === 'ok' ? 'text-green-600' : status === 'error' ? 'text-red-600' : 'text-amber-500',
            argumentsText: hasArguments ? stringifyJsonSafe(args, 2) : '',
            detail: event?.detail ? String(event.detail) : '',
        })
    }
    return details
})

const toolActivityLabel = computed(() => {
    const count = Math.max(props.item.toolCalls?.length || 0, props.item.toolEvents?.length || 0)
    return `${props.item.running ? '正在运行' : '已运行'} ${count} 个工具`
})

const toolNames = computed(() => {
    const names = toolDetails.value.map((tool) => tool.name).filter(Boolean)
    return [...new Set(names)].join('、')
})

const toolUsageText = computed(() => {
    const usage = props.item.usage
    if (!usage || typeof usage !== 'object' || !Object.keys(usage).length) return ''
    return Object.entries(usage).map(([key, value]) => `${key} ${value}`).join(' · ')
})

const toolErrorText = computed(() => {
    const error = props.item.error
    if (error == null || error === '') return ''
    return typeof error === 'string' ? error : stringifyJsonSafe(error, 2)
})

const approvalPending = computed(() => isApprovalAwaitingUserAction(props.item.payload))
const approvalSourceLabel = computed(() => getApprovalSourceLabel(props.item.payload?.source))
const modifyEntityPayload = computed(() => getModifyEntityPayload(props.item.payload))
const wikiCreatePayload = computed(() => getWikiCreatePayload(props.item.payload))
const wikiEditPayload = computed(() => getWikiEditPayload(props.item.payload))

const approvalResolutionLabel = computed(() => {
    const labels = { approved: '已通过', rejected: '已拒绝', mixed: '混合处理' }
    const resolution = props.item.payload?.resolution
    return resolution ? labels[resolution] || String(resolution) : ''
})

const approvalIcon = computed(() => {
    if (approvalPending.value) return 'mdi:shield-alert-outline'
    if (props.item.payload?.resolution === 'approved') return 'mdi:shield-check-outline'
    if (props.item.payload?.resolution === 'rejected') return 'mdi:shield-remove-outline'
    return 'mdi:shield-outline'
})

const approvalColorClass = computed(() => {
    if (approvalPending.value) return 'text-amber-700'
    if (props.item.payload?.resolution === 'approved') return 'text-green-700'
    if (props.item.payload?.resolution === 'rejected') return 'text-red-700'
    return 'text-gray-600'
})

const approvalEntityLine = computed(() => {
    if (modifyEntityPayload.value) {
        const type = getEntityTypeLabel(modifyEntityPayload.value.entity_type)
        const uuid = modifyEntityPayload.value.entity_uuid ? truncateUuid(modifyEntityPayload.value.entity_uuid) : ''
        return ['实体', type, uuid].filter(Boolean).join(' · ')
    }
    if (wikiCreatePayload.value) return `新建页面 · ${wikiCreatePayload.value.title || '未命名'}`
    if (wikiEditPayload.value) {
        const operation = getWikiEditOperationLabel(wikiEditPayload.value.operation)
        const wikiId = wikiEditPayload.value.wiki_id ? truncateUuid(wikiEditPayload.value.wiki_id) : ''
        return ['编辑页面', operation, wikiId].filter(Boolean).join(' · ')
    }
    return ''
})

const approvalReasonText = computed(() => (
    modifyEntityPayload.value?.reason
    ?? wikiCreatePayload.value?.reason
    ?? wikiEditPayload.value?.reason
    ?? ''
))

const rejectReasons = computed(() => {
    const reasons = props.item.payload?.reject_reasons
    return Array.isArray(reasons) ? reasons.filter(Boolean) : []
})

const notificationIcon = computed(() => {
    if (props.item.payload?.level === 'error') return 'mdi:alert-circle-outline'
    if (props.item.payload?.level === 'warning') return 'mdi:alert-outline'
    return 'mdi:information-outline'
})

const notificationTextClass = computed(() => {
    if (props.item.payload?.level === 'error') return 'text-red-700'
    if (props.item.payload?.level === 'warning') return 'text-amber-700'
    return 'text-blue-700'
})

const notificationTitle = computed(() => {
    if (props.item.payload?.level === 'error') return '运行错误'
    if (props.item.payload?.level === 'warning') return '运行警告'
    return '运行通知'
})

const resultSummary = computed(() => props.item.displaySummary ?? props.item.payload?.result?.short_summary ?? '')
const resultUserMarkdown = computed(() => props.item.displayUserMarkdown ?? props.item.payload?.result?.user_markdown ?? '')

const resultToolsLine = computed(() => {
    const tools = props.item.payload?.result?.tools_used
    return Array.isArray(tools) && tools.length ? [...new Set(tools)].join('、') : ''
})

const resultStopReasonLabel = computed(() => {
    const reason = String(props.item.payload?.result?.stop_reason || '')
    return RESULT_STOP_REASON_LABEL[reason] || reason
})

const resultStatusKey = computed(() => String(props.item.payload?.status || ''))
const resultSessionStatusLabel = computed(() => RUNTIME_STATUS_LABEL[resultStatusKey.value] || resultStatusKey.value)

const resultIcon = computed(() => {
    if (resultStatusKey.value === 'completed') return 'mdi:check-circle-outline'
    if (resultStatusKey.value === 'failed') return 'mdi:alert-circle-outline'
    if (resultStatusKey.value === 'cancelled') return 'mdi:cancel'
    if (resultStatusKey.value === 'paused') return 'mdi:pause-circle-outline'
    return 'mdi:flag-checkered'
})

const resultIconClass = computed(() => {
    if (resultStatusKey.value === 'completed') return 'text-green-600'
    if (resultStatusKey.value === 'failed') return 'text-red-600'
    if (resultStatusKey.value === 'paused') return 'text-amber-600'
    return 'text-gray-500'
})

const resultErrorText = computed(() => {
    if (resultStatusKey.value !== 'failed') return ''
    const error = props.item.payload?.error
    if (error == null) return ''
    return typeof error === 'string' ? error.trim() : stringifyJsonSafe(error, 2)
})

const systemMessage = computed(() => {
    if (props.item.message != null && props.item.message !== '') return String(props.item.message)
    return typeof props.item.payload === 'string'
        ? props.item.payload
        : stringifyJsonSafe(props.item.payload, 2)
})

const unknownRaw = computed(() => {
    return typeof props.item.payload === 'string'
        ? props.item.payload
        : stringifyJsonSafe(props.item.payload ?? props.item, 2)
})
</script>
