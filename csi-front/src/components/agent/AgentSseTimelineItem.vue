<template>
    <div class="min-w-0">
        <div v-if="item.kind === 'assistant_stream'" class="flex gap-3 min-w-0">
            <div class="mt-1.5 h-8 w-1 shrink-0 rounded-full bg-blue-500/80" />
            <div
                class="min-w-0 flex-1 rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-sm ring-1 ring-gray-100/80">
                <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                    <span class="font-medium text-gray-700">模型输出</span>
                    <span>{{ formatTime(item.ts) }}</span>
                    <span v-if="item.streaming"
                        class="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">输出中</span>
                    <span v-else class="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600">已结束</span>
                </div>
                <div class="min-w-0">
                    <MarkdownViewer
                        v-if="item.text"
                        :content="item.text"
                        :breaks="true"
                        custom-class="min-w-0"
                    />
                    <span v-if="item.streaming" class="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 rounded-sm bg-blue-500 align-middle animate-pulse" aria-hidden="true" />
                </div>
                <p v-if="item.resuming" class="mt-2 text-xs text-amber-700">继续生成中…</p>
            </div>
        </div>

        <div v-else-if="item.kind === 'status'"
            class="rounded-lg border border-gray-100 bg-linear-to-r from-slate-50 to-white px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2">
                <Icon icon="mdi:state-machine" class="text-lg text-slate-600 shrink-0" />
                <span class="text-xs font-semibold text-gray-700">会话状态</span>
                <span class="text-xs text-gray-400">{{ formatTime(item.ts) }}</span>
                <span
                    class="rounded-md bg-white px-2 py-0.5 text-xs font-mono font-medium text-gray-900 ring-1 ring-gray-200">{{ statusText }}</span>
            </div>
        </div>

        <div v-else-if="item.kind === 'progress'"
            class="rounded-lg border border-gray-100 bg-white px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                <Icon icon="mdi:text-long" class="text-base text-blue-600" />
                <span class="font-semibold text-gray-700">进度</span>
                <span v-if="item.payload?.tool_hint"
                    class="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">工具提示</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <p class="mt-2 text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ item.payload?.content ?? '—' }}</p>
        </div>

        <div v-else-if="item.kind === 'step'"
            class="rounded-lg border border-indigo-100 bg-indigo-50/40 px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                <Icon icon="mdi:stairs" class="text-base text-indigo-600" />
                <span class="font-semibold text-gray-800">步骤</span>
                <span class="rounded bg-white/80 px-1.5 py-0.5 font-mono text-[11px]">#{{ item.payload?.iteration ?? '—' }}</span>
                <span class="rounded bg-indigo-100/80 px-1.5 py-0.5 text-[11px] font-medium text-indigo-900">{{ phaseLabel }}</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <template v-if="item.payload?.phase === 'before_tools'">
                <p class="mt-2 text-sm text-gray-800">即将调用工具：</p>
                <ul class="mt-1.5 flex flex-wrap gap-1.5">
                    <li v-for="(tc, idx) in beforeToolCalls" :key="idx"
                        class="rounded-md bg-white px-2 py-1 text-xs font-mono text-indigo-900 ring-1 ring-indigo-100">
                        {{ tc.name }}
                    </li>
                </ul>
            </template>
            <template v-else-if="item.payload?.phase === 'after_iteration'">
                <MarkdownViewer
                    v-if="afterStepContent"
                    :content="afterStepContent"
                    :breaks="true"
                    custom-class="mt-2 rounded-lg border border-gray-100 bg-white/90 p-3"
                />
                <p v-if="afterToolNames.length" class="mt-2 text-xs text-gray-600">工具：{{ afterToolNames.join('、') }}</p>
                <el-collapse v-if="afterArgsJson" v-model="stepCollapse" class="mt-2 border-0">
                    <el-collapse-item title="参数（JSON）" name="args">
                        <pre class="max-h-48 overflow-auto rounded bg-white p-2 text-[11px] text-gray-800 ring-1 ring-gray-100 whitespace-pre-wrap">{{ afterArgsJson }}</pre>
                    </el-collapse-item>
                </el-collapse>
            </template>
            <template v-else>
                <pre class="mt-2 max-h-40 overflow-auto rounded bg-white p-2 text-xs ring-1 ring-gray-100">{{ stepFallbackJson }}</pre>
            </template>
        </div>

        <div v-else-if="item.kind === 'todos'"
            class="rounded-lg border border-emerald-100 bg-emerald-50/30 px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                <Icon icon="mdi:format-list-checks" class="text-base text-emerald-600" />
                <span class="font-semibold text-gray-800">待办已更新</span>
                <span class="rounded bg-white px-1.5 py-0.5 font-medium text-emerald-800">{{ item.todoCount ?? 0 }} 项</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <p v-if="item.todoPreview" class="mt-2 text-xs text-gray-600 line-clamp-2">预览：{{ item.todoPreview }}</p>
        </div>

        <div v-else-if="item.kind === 'approval_required'" class="rounded-lg border px-3 py-2.5 shadow-sm"
            :class="approvalCardClass">
            <div class="flex flex-wrap items-center gap-2 text-xs">
                <Icon icon="mdi:shield-check" class="text-base shrink-0" :class="approvalIconClass" />
                <span class="font-semibold text-gray-900">审批</span>
                <span class="rounded bg-white/80 px-1.5 py-0.5 text-[11px] text-gray-700">{{ approvalSourceLabel }}</span>
                <span v-if="approvalResolutionLabel" class="rounded-md px-2 py-0.5 text-[11px] font-medium"
                    :class="approvalBadgeClass">{{ approvalResolutionLabel }}</span>
                <span class="text-gray-500">{{ formatTime(item.ts) }}</span>
            </div>
            <p v-if="approvalEntityTypeLabel" class="mt-2 text-sm text-gray-800">
                实体：<span class="font-medium">{{ approvalEntityTypeLabel }}</span>
                <span v-if="approvalEntityUuidShort" class="ml-1 font-mono text-xs text-gray-500">{{ approvalEntityUuidShort }}</span>
            </p>
            <p v-if="approvalModificationCount" class="mt-1 text-xs text-gray-600">修改项 {{ approvalModificationCount }} 个</p>
            <p v-if="approvalReasonText" class="mt-1 text-sm text-gray-700 whitespace-pre-wrap wrap-break-word line-clamp-3">说明：{{ approvalReasonText }}</p>
            <p v-if="approvalPending" class="mt-2 text-xs text-blue-700">已弹出审批对话框，请在对话框中操作。</p>
            <ul v-else-if="rejectReasons.length" class="mt-2 list-disc pl-4 text-sm text-gray-800">
                <li v-for="(r, i) in rejectReasons" :key="i">{{ r }}</li>
            </ul>
        </div>

        <div v-else-if="item.kind === 'notification'" class="rounded-lg border-l-4 bg-white px-3 py-2.5 shadow-sm ring-1 ring-gray-100"
            :class="notificationBorderClass">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                <Icon :icon="notificationIcon" class="text-base" :class="notificationIconColor" />
                <span class="font-semibold text-gray-800">通知</span>
                <span class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[11px]">{{ item.payload?.level ?? 'info' }}</span>
                <span>{{ formatTime(item.payload?.created_at || item.ts) }}</span>
            </div>
            <p class="mt-2 text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ item.payload?.message ?? '—' }}</p>
        </div>

        <div v-else-if="item.kind === 'task_submitted'"
            class="rounded-lg border px-3 py-2.5 shadow-sm"
            :class="item.payload?.success ? 'border-green-200 bg-green-50/40' : 'border-red-200 bg-red-50/40'">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                <Icon :icon="item.payload?.success ? 'mdi:check-circle' : 'mdi:alert-circle'"
                    :class="item.payload?.success ? 'text-green-600' : 'text-red-600'" class="text-lg" />
                <span class="font-semibold text-gray-900">任务结果已提交</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <p class="mt-2 text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ item.payload?.short_summary ?? '—' }}</p>
        </div>

        <div v-else-if="item.kind === 'result'"
            class="rounded-xl border border-blue-100 bg-linear-to-br from-blue-50/80 to-white px-4 py-3 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                <Icon icon="mdi:flag-checkered" class="text-lg text-blue-600" />
                <span class="font-semibold text-gray-900">本轮结束</span>
                <span class="rounded-md bg-white px-2 py-0.5 font-mono text-xs ring-1 ring-gray-200">{{ item.payload?.status ?? '—' }}</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <p v-if="resultSummary" class="mt-2 text-sm font-medium text-gray-900">{{ resultSummary }}</p>
            <MarkdownViewer
                v-if="resultUserMarkdown"
                :content="resultUserMarkdown"
                custom-class="mt-2 rounded-lg border border-gray-100 bg-white/90 p-3"
            />
            <el-collapse v-model="resultCollapse" class="mt-2 border-0">
                <el-collapse-item v-if="resultToolsLine" title="使用工具" name="tools">
                    <p class="text-sm text-gray-800">{{ resultToolsLine }}</p>
                </el-collapse-item>
                <el-collapse-item v-if="resultStopReason" title="停止原因" name="stop">
                    <p class="text-sm text-gray-800 font-mono">{{ resultStopReason }}</p>
                </el-collapse-item>
                <el-collapse-item v-if="resultPayloadJson" title="payload（JSON）" name="payload">
                    <pre class="max-h-56 overflow-auto rounded bg-gray-50 p-2 text-xs whitespace-pre-wrap">{{ resultPayloadJson }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="item.payload?.error != null" title="错误" name="err">
                    <pre class="max-h-40 overflow-auto text-xs whitespace-pre-wrap">{{ stringifyJsonSafe(item.payload.error) }}</pre>
                </el-collapse-item>
            </el-collapse>
        </div>

        <div v-else-if="item.kind === 'debug_prompt'"
            class="rounded-lg border border-violet-200 bg-violet-50/30 px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                <Icon icon="mdi:bug" class="text-base text-violet-600" />
                <span class="font-semibold text-gray-900">调试提示词</span>
                <span v-if="item.payload?.model" class="font-mono text-[11px] text-gray-500">{{ item.payload.model }}</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <el-collapse v-model="debugCollapse" class="mt-2 border-0">
                <el-collapse-item title="系统提示" name="sys">
                    <pre class="max-h-48 overflow-auto rounded bg-white p-2 text-xs whitespace-pre-wrap ring-1 ring-gray-100">{{ item.payload?.system_prompt ?? '' }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="item.payload?.extra_system_suffix" title="系统后缀" name="suf">
                    <pre class="max-h-32 overflow-auto rounded bg-white p-2 text-xs whitespace-pre-wrap ring-1 ring-gray-100">{{ item.payload.extra_system_suffix }}</pre>
                </el-collapse-item>
                <el-collapse-item title="用户提示" name="usr">
                    <pre class="max-h-48 overflow-auto rounded bg-white p-2 text-xs whitespace-pre-wrap ring-1 ring-gray-100">{{ item.payload?.user_prompt ?? '' }}</pre>
                </el-collapse-item>
                <el-collapse-item title="内存快照" name="mem">
                    <pre class="max-h-48 overflow-auto rounded bg-white p-2 text-xs whitespace-pre-wrap ring-1 ring-gray-100">{{ memorySnapshotText }}</pre>
                </el-collapse-item>
            </el-collapse>
        </div>

        <div v-else-if="item.kind === 'system'"
            class="rounded-md border border-dashed border-gray-200 bg-gray-50/80 px-3 py-2 text-xs text-gray-600">
            <span class="font-mono text-[11px] text-gray-500">{{ item.systemSubtype || 'system' }}</span>
            <span class="mx-2 text-gray-300">|</span>
            <span>{{ formatTime(item.ts) }}</span>
            <p class="mt-1 text-gray-700">{{ systemMessage }}</p>
            <pre v-if="item.metaJson" class="mt-1 max-h-24 overflow-auto rounded bg-white p-1.5 text-[10px] text-gray-600">{{ item.metaJson }}</pre>
        </div>

        <div v-else-if="item.kind === 'parse_error'"
            class="rounded-lg border border-red-100 bg-red-50/50 px-3 py-2.5 text-sm text-red-900">
            <div class="flex flex-wrap items-center gap-2 text-xs font-semibold">
                <Icon icon="mdi:alert" class="text-lg" />
                <span>{{ item.sseType }}</span>
                <span class="font-normal text-red-700/80">解析失败：{{ item.error }}</span>
                <span class="text-gray-500">{{ formatTime(item.ts) }}</span>
            </div>
            <pre class="mt-2 max-h-32 overflow-auto rounded bg-white p-2 text-xs text-gray-800 whitespace-pre-wrap">{{ item.rawSnippet }}</pre>
        </div>

        <div v-else class="rounded-lg border border-amber-100 bg-amber-50/40 px-3 py-2.5 shadow-sm">
            <div class="flex flex-wrap items-center gap-2 text-xs text-gray-700">
                <Icon icon="mdi:help-circle-outline" class="text-base text-amber-700" />
                <span class="font-mono font-semibold">{{ item.sseType }}</span>
                <span>{{ formatTime(item.ts) }}</span>
            </div>
            <el-collapse v-model="unknownCollapse" class="mt-2 border-0">
                <el-collapse-item title="原始数据" name="raw">
                    <pre class="max-h-48 overflow-auto rounded bg-white p-2 text-xs whitespace-pre-wrap">{{ unknownRaw }}</pre>
                </el-collapse-item>
            </el-collapse>
        </div>
    </div>
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
    isApprovalAwaitingUserAction,
    truncateUuid,
} from '@/utils/agentApproval'

const props = defineProps({
    item: {
        type: Object,
        required: true,
    },
})

const stepCollapse = ref([])
const resultCollapse = ref([])
const debugCollapse = ref(['sys'])
const unknownCollapse = ref([])

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

const statusText = computed(() => {
    const s = props.item.payload?.status
    const key = s != null ? String(s) : ''
    return RUNTIME_STATUS_LABEL[key] || key || '—'
})

const phaseLabel = computed(() => {
    const p = props.item.payload?.phase
    if (p === 'before_tools') return '执行工具前'
    if (p === 'after_iteration') return '迭代结束后'
    return p ? String(p) : '—'
})

const beforeToolCalls = computed(() => {
    const list = props.item.payload?.tool_calls
    return Array.isArray(list) ? list : []
})

const afterStepContent = computed(() => props.item.payload?.step?.content ?? '')

const afterToolNames = computed(() => {
    const calls = props.item.payload?.step?.tool_calls
    if (!Array.isArray(calls)) return []
    return calls.map((c) => c?.name).filter(Boolean)
})

const afterArgsJson = computed(() => {
    const calls = props.item.payload?.step?.tool_calls
    if (!Array.isArray(calls) || !calls.length) return ''
    try {
        const parts = calls.map((c) => `${c?.name || '?'}: ${JSON.stringify(c?.arguments ?? {}, null, 0)}`)
        return parts.join('\n\n')
    } catch {
        return ''
    }
})

const stepFallbackJson = computed(() => stringifyJsonSafe(props.item.payload, 2))

const approvalPending = computed(() => isApprovalAwaitingUserAction(props.item.payload))

const approvalSourceLabel = computed(() => getApprovalSourceLabel(props.item.payload?.source))

const modifyEntityPayload = computed(() => getModifyEntityPayload(props.item.payload))

const approvalEntityTypeLabel = computed(() => {
    const type = modifyEntityPayload.value?.entity_type
    return type ? getEntityTypeLabel(type) : ''
})

const approvalEntityUuidShort = computed(() => {
    const uuid = modifyEntityPayload.value?.entity_uuid
    return uuid ? truncateUuid(uuid) : ''
})

const approvalModificationCount = computed(() => {
    const list = modifyEntityPayload.value?.modifications
    return Array.isArray(list) ? list.length : 0
})

const approvalReasonText = computed(() => modifyEntityPayload.value?.reason ?? '')

const rejectReasons = computed(() => {
    const r = props.item.payload?.reject_reasons
    return Array.isArray(r) ? r.filter(Boolean) : []
})

const RESOLUTION_LABEL = {
    approved: '已通过',
    rejected: '已拒绝',
    mixed: '混合结果',
}

const approvalResolutionLabel = computed(() => {
    const r = props.item.payload?.resolution
    if (r == null) return ''
    return RESOLUTION_LABEL[r] || String(r)
})

const approvalCardClass = computed(() =>
    approvalPending.value
        ? 'border-amber-200 bg-amber-50/50'
        : 'border-gray-200 bg-gray-50/80'
)

const approvalIconClass = computed(() =>
    approvalPending.value ? 'text-amber-600' : 'text-gray-600'
)

const approvalBadgeClass = computed(() => {
    const r = props.item.payload?.resolution
    if (r === 'approved') return 'bg-green-100 text-green-900'
    if (r === 'rejected') return 'bg-red-100 text-red-900'
    if (r === 'mixed') return 'bg-amber-100 text-amber-900'
    return 'bg-gray-200 text-gray-800'
})

const notificationBorderClass = computed(() => {
    const lv = props.item.payload?.level
    if (lv === 'error') return 'border-l-red-500'
    if (lv === 'warning') return 'border-l-amber-500'
    return 'border-l-blue-500'
})

const notificationIcon = computed(() => {
    const lv = props.item.payload?.level
    if (lv === 'error') return 'mdi:close-circle'
    if (lv === 'warning') return 'mdi:alert'
    return 'mdi:information'
})

const notificationIconColor = computed(() => {
    const lv = props.item.payload?.level
    if (lv === 'error') return 'text-red-600'
    if (lv === 'warning') return 'text-amber-600'
    return 'text-blue-600'
})

const resultSummary = computed(() => props.item.payload?.result?.short_summary ?? '')
const resultUserMarkdown = computed(() => props.item.payload?.result?.user_markdown ?? '')

const resultToolsLine = computed(() => {
    const t = props.item.payload?.result?.tools_used
    if (!Array.isArray(t) || !t.length) return ''
    return t.join('、')
})

const resultStopReason = computed(() => {
    const s = props.item.payload?.result?.stop_reason
    return s != null && s !== '' ? String(s) : ''
})

const resultPayloadJson = computed(() => {
    const p = props.item.payload?.result?.payload
    if (p == null) return ''
    return stringifyJsonSafe(p, 2)
})

const memorySnapshotText = computed(() => {
    const m = props.item.payload?.memory_snapshot
    if (!m || typeof m !== 'object') return '—'
    return stringifyJsonSafe(m, 2)
})

const systemMessage = computed(() => {
    if (props.item.message != null && props.item.message !== '') return String(props.item.message)
    if (typeof props.item.payload === 'string') return props.item.payload
    return stringifyJsonSafe(props.item.payload, 2)
})

const unknownRaw = computed(() => {
    if (typeof props.item.payload === 'string') return props.item.payload
    return stringifyJsonSafe(props.item.payload, 2)
})
</script>
