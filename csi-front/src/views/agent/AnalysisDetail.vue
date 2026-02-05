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
    "thread_id": "7afbe117-2751-45e2-9b2d-22e4de239480",
    "status": "completed",
    "fields": {
        "entity_uuid": "26c794c2a721b0d832580b779b65a450",
        "entity_type": "article",
        "agent_id": "63927dc31c2f44cc1c3603bad327c1bf"
    },
    "steps": [
        {
            "node": "model",
            "ts": "2026-02-04T23:12:04.395723",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "in_progress"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "pending"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "pending"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "pending"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "pending"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "pending"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:04.406682"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:04.417740"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:04.431514",
            "result_summary": {
                "content_length": 346,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'in_progress'}, {'content': '读取目标文章的clean_content字段', 'status': 'pending'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:09.161618",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "in_progress"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "pending"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "pending"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "pending"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "pending"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:09.171708"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:09.184025"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:09.195419",
            "result_summary": {
                "content_length": 348,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'in_progress'}, {'content': '..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:12.635819",
            "tool_calls": [
                {
                    "name": "get_entity",
                    "args": {
                        "uuid": "26c794c2a721b0d832580b779b65a450",
                        "entity_type": "article",
                        "fields": [
                            "clean_content"
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:12.648748"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:12.660662"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:12.684579",
            "result_summary": {
                "content_length": 3215,
                "preview": "{\"clean_content\": \"“Scattered LAPSUS$ Hunters”是一个新的暗网勒索软件团伙，由三大勒索软件团伙Scattered Spider、Lapsus$和ShinyHunters合并而成，近期，该团伙推出了基于Tor的暗网数据泄露网站，其中包含42家受害公司。推出该..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:17.640862",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "completed"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "in_progress"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "pending"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "pending"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "pending"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:17.654088"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:17.668095"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:17.684034",
            "result_summary": {
                "content_length": 350,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'completed'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:23.127140",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "completed"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "completed"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "in_progress"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "pending"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "pending"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:23.138203"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:23.151718"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:23.169065",
            "result_summary": {
                "content_length": 352,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'completed'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:35.626993",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "completed"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "completed"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "completed"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "in_progress"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "pending"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:35.639345"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:35.654813"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:35.670576",
            "result_summary": {
                "content_length": 354,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'completed'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:12:40.781287",
            "tool_calls": [
                {
                    "name": "modify_entity",
                    "args": {
                        "uuid": "26c794c2a721b0d832580b779b65a450",
                        "entity_type": "article",
                        "field": "keywords",
                        "value": [
                            "Scattered LAPSUS$ Hunters",
                            "Salesforce",
                            "暗网",
                            "勒索软件",
                            "数据泄露",
                            "OAuth",
                            "供应链攻击",
                            "Tor",
                            "ShinyHunters",
                            "Telegram"
                        ]
                    }
                }
            ]
        },
        {
            "node": "__interrupt__",
            "ts": "2026-02-04T23:12:40.795218",
            "approval_decision": "approve",
            "approval_decision_detail": {
                "type": "approve"
            },
            "approved_at": "2026-02-04T23:12:59.188512",
            "approval_payload": {
                "action_requests": [
                    {
                        "name": "modify_entity",
                        "args": {
                            "uuid": "26c794c2a721b0d832580b779b65a450",
                            "entity_type": "article",
                            "field": "keywords",
                            "value": [
                                "Scattered LAPSUS$ Hunters",
                                "Salesforce",
                                "暗网",
                                "勒索软件",
                                "数据泄露",
                                "OAuth",
                                "供应链攻击",
                                "Tor",
                                "ShinyHunters",
                                "Telegram"
                            ]
                        },
                        "description": "Agent 尝试修改 keywords 字段，请确认是否继续。"
                    }
                ],
                "review_configs": [
                    {
                        "action_name": "modify_entity",
                        "allowed_decisions": [
                            "approve",
                            "reject"
                        ]
                    }
                ]
            }
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:12:59.213396",
            "tool_calls": [
                {
                    "name": "modify_entity",
                    "args": {
                        "uuid": "26c794c2a721b0d832580b779b65a450",
                        "entity_type": "article",
                        "field": "keywords",
                        "value": [
                            "Scattered LAPSUS$ Hunters",
                            "Salesforce",
                            "暗网",
                            "勒索软件",
                            "数据泄露",
                            "OAuth",
                            "供应链攻击",
                            "Tor",
                            "ShinyHunters",
                            "Telegram"
                        ]
                    }
                }
            ]
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:12:59.226880"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:12:59.263928",
            "result_summary": {
                "content_length": 128,
                "preview": "{\"success\": true, \"message\": \"字段已更新\", \"uuid\": \"26c794c2a721b0d832580b779b65a450\", \"entity_type\": \"article\", \"field\": \"keywords\"}"
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:13:03.612662",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "completed"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "completed"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "completed"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "completed"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "in_progress"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:13:03.627763"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:13:03.641602"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:13:03.660672",
            "result_summary": {
                "content_length": 356,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'completed'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:13:18.653897",
            "tool_calls": [
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "content": "创建任务分解和进度跟踪",
                                "status": "completed"
                            },
                            {
                                "content": "读取目标文章的clean_content字段",
                                "status": "completed"
                            },
                            {
                                "content": "检查clean_content是否为空",
                                "status": "completed"
                            },
                            {
                                "content": "执行关键词提取（原文提取、去重、排序）",
                                "status": "completed"
                            },
                            {
                                "content": "将关键词写入keywords字段",
                                "status": "completed"
                            },
                            {
                                "content": "输出最终结果",
                                "status": "completed"
                            }
                        ]
                    }
                }
            ]
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:13:18.668498"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:13:18.685538"
        },
        {
            "node": "tools",
            "ts": "2026-02-04T23:13:18.702646",
            "result_summary": {
                "content_length": 354,
                "preview": "Updated todo list to [{'content': '创建任务分解和进度跟踪', 'status': 'completed'}, {'content': '读取目标文章的clean_content字段', 'status': 'completed'}, {'content': '检查..."
            }
        },
        {
            "node": "model",
            "ts": "2026-02-04T23:13:20.396834",
            "result_summary": {
                "content_length": 48,
                "preview": "**任务完成** - 关键词提取任务已成功执行完毕，所有步骤均已完成，关键词已成功写入目标字段。"
            }
        },
        {
            "node": "HumanInTheLoopMiddleware.after_model",
            "ts": "2026-02-04T23:13:20.411802"
        },
        {
            "node": "TodoListMiddleware.after_model",
            "ts": "2026-02-04T23:13:20.430712"
        }
    ],
    "todos": [
        {
            "content": "创建任务分解和进度跟踪",
            "status": "completed"
        },
        {
            "content": "读取目标文章的clean_content字段",
            "status": "completed"
        },
        {
            "content": "检查clean_content是否为空",
            "status": "completed"
        },
        {
            "content": "执行关键词提取（原文提取、去重、排序）",
            "status": "completed"
        },
        {
            "content": "将关键词写入keywords字段",
            "status": "completed"
        },
        {
            "content": "输出最终结果",
            "status": "completed"
        }
    ],
    "pending_approval": null,
    "updated_at": "2026-02-04T23:13:20.443000",
    "is_running": false
}
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
