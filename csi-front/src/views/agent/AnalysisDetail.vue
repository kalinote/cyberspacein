<template>
    <div class="min-h-screen bg-gray-50">
        <Header />

        <DetailPageHeader
            title="分析详情"
            :subtitle="sessionData.thread_id"
        >
            <template #tags>
                <el-tag :type="statusTagType" size="default">{{ statusLabel }}</el-tag>
                <el-tag v-if="sessionData.fields?.entity_type" type="info" size="default">
                    {{ sessionData.fields.entity_type }}
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
                            <p class="text-sm font-bold text-gray-900 truncate font-mono">{{ sessionData.fields?.entity_uuid || '-' }}</p>
                            <p class="text-xs text-gray-500 mt-0.5">agent: {{ sessionData.fields?.agent_id?.slice(0, 8) || '-' }}...</p>
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
                                            <span class="font-mono text-sm font-semibold text-gray-800">{{ step.node }}</span>
                                            <span class="text-xs text-gray-500">{{ formatDateTime(step.ts, { includeSecond: true }) }}</span>
                                            <Icon v-if="step.approval_decision === 'approve'" icon="mdi:check-circle" class="text-green-600 text-base" title="已通过" />
                                            <Icon v-if="step.approval_decision === 'reject'" icon="mdi:close-circle" class="text-red-600 text-base" title="已拒绝" />
                                            <Icon v-if="step.approval_payload && !step.approved_at" icon="mdi:clock-outline" class="text-amber-600 text-base" title="待审批" />
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
                                        <div v-if="step.result_summary" class="mt-2 p-2 bg-gray-50 rounded-lg border border-gray-100">
                                            <p class="text-xs text-gray-500 mb-1">结果摘要 ({{ step.result_summary.content_length }} 字符)</p>
                                            <p class="text-sm text-gray-700 wrap-break-word line-clamp-2">{{ step.result_summary.preview }}</p>
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
                                        <Icon
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
    </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import { Icon } from '@iconify/vue'
import { formatDateTime } from '@/utils/action'

const userMessage = ref('')
const sessionData = computed(() => MOCK_SESSION_DATA)

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
    return 'mdi:circle-small'
}

function stepNodeIconBgClass(node) {
    if (node === 'model') return 'bg-blue-100'
    if (node === 'tools') return 'bg-green-100'
    if (node === '__interrupt__') return 'bg-amber-100'
    return 'bg-gray-100'
}

function stepNodeIconColor(node) {
    if (node === 'model') return 'text-blue-600'
    if (node === 'tools') return 'text-green-600'
    if (node === '__interrupt__') return 'text-amber-600'
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

const MOCK_SESSION_DATA = {
    thread_id: 'ec0dce9b-518a-45eb-ad78-782f5a57df1c',
    status: 'awaiting_approval',
    fields: {
        entity_uuid: 'a8d093df14bb1fc02c4e73cc873ca996',
        entity_type: 'article',
        agent_id: '63927dc31c2f44cc1c3603bad327c1bf'
    },
    steps: [
        { node: 'model', ts: '2026-02-04T16:56:04.173169', tool_calls: [{ name: 'write_todos', args: { todos: [{ content: '创建任务分解和进度跟踪', status: 'in_progress' }, { content: '读取article实体的clean_content字段', status: 'pending' }] } }] },
        { node: 'HumanInTheLoopMiddleware.after_model', ts: '2026-02-04T16:56:04.183525' },
        { node: 'TodoListMiddleware.after_model', ts: '2026-02-04T16:56:04.194118' },
        { node: 'tools', ts: '2026-02-04T16:56:04.210196', result_summary: { content_length: 427, preview: "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'in_progress'}, ..." } },
        { node: 'model', ts: '2026-02-04T16:56:13.612369', tool_calls: [{ name: 'get_entity', args: { uuid: 'a8d093df14bb1fc02c4e73cc873ca996', entity_type: 'article', fields: ['clean_content'] } }] },
        { node: 'tools', ts: '2026-02-04T16:56:13.645356', result_summary: { content_length: 627, preview: '{"clean_content": "How to instantly change all text on your website..."' } },
        { node: 'model', ts: '2026-02-04T16:56:45.119721', tool_calls: [{ name: 'modify_entity', args: { uuid: 'a8d093df14bb1fc02c4e73cc873ca996', entity_type: 'article', field: 'keywords', value: ['text-transform', 'lowercase', 'css', 'website'] } }] },
        { node: '__interrupt__', ts: '2026-02-04T16:56:45.133077', approval_payload: { action_requests: [{ name: 'modify_entity', args: { uuid: 'a8d093df14bb1fc02c4e73cc873ca996', entity_type: 'article', field: 'keywords', value: ['text-transform', 'lowercase', 'css', 'website', 'characters', 'uppercase', 'blog'] }, description: 'Agent 尝试修改 keywords 字段，请确认是否继续。' }], review_configs: [{ action_name: 'modify_entity', allowed_decisions: ['approve', 'reject'] }] } },
        { node: '__interrupt__', ts: '2026-02-04T16:56:50.556861', approval_decision: 'approve', approved_at: '2026-02-04T16:56:50.556861', approval_payload: { action_requests: [{ name: 'modify_entity', args: { uuid: 'a8d093df14bb1fc02c4e73cc873ca996', entity_type: 'article', field: 'keywords', value: ['text-transform', 'lowercase', 'css', 'website', 'characters', 'uppercase', 'blog'] }, description: 'Agent 尝试修改 keywords 字段，请确认是否继续。' }], review_configs: [{ action_name: 'modify_entity', allowed_decisions: ['approve', 'reject'] }] } },
        { node: 'tools', ts: '2026-02-04T16:56:50.642043', result_summary: { content_length: 128, preview: '{"success": true, "message": "字段已更新", "uuid": "a8d093df14bb1fc02c4e73cc873ca996"...' } },
        { node: 'model', ts: '2026-02-04T16:57:13.349315', result_summary: { content_length: 60, preview: '**任务完成** - 关键词提取任务已成功执行，所有步骤均按Workflow要求完成。' } }
    ],
    todos: [
        { content: '创建任务分解和进度跟踪', status: 'completed' },
        { content: '读取UUID为a8d093df14bb1fc02c4e73cc873ca996的article实体的clean_content字段', status: 'completed' },
        { content: '检查clean_content字段是否为空或None', status: 'completed' },
        { content: '对clean_content内容进行关键词提取（原文提取、去重、语言一致性、权重排序）', status: 'completed' },
        { content: '将关键词列表写入keywords字段', status: 'completed' },
        { content: '输出最终结果和原因说明', status: 'completed' }
    ],
    pending_approval: {
        payload: {
            action_requests: [
                {
                    name: 'modify_entity',
                    args: {
                        uuid: 'a8d093df14bb1fc02c4e73cc873ca996',
                        entity_type: 'article',
                        field: 'keywords',
                        value: ['text-transform', 'lowercase', 'css', 'website', 'characters', 'uppercase', 'blog']
                    },
                    description: 'Agent 尝试修改 keywords 字段，请确认是否继续。'
                }
            ],
            review_configs: [
                { action_name: 'modify_entity', allowed_decisions: ['approve', 'reject'] }
            ]
        },
        thread_id: 'ec0dce9b-518a-45eb-ad78-782f5a57df1c'
    },
    updated_at: '2026-02-04T16:57:13.390000',
    is_running: false
}
</script>

<style scoped>
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
