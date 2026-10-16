<template>
    <div :class="{ 'mobile-agent-monitor': isMobile }">
        <Header />

        <header v-if="isMobile" class="mobile-agent-heading">
            <h1>分析中心</h1>
            <p>选择引擎开始分析，或继续已有会话。</p>
            <button v-if="hasPerm(PERM.pages.agent.sessions.visible)" type="button" :disabled="!canViewSessions" @click="canViewSessions && router.push({ name: 'agent-session-list' })"><Icon icon="mdi:message-text-outline" /> 查看分析会话 <Icon icon="mdi:chevron-right" /></button>
        </header>

        <!-- 英雄区域 -->
        <section v-if="!isMobile" class="bg-linear-to-br from-blue-50 to-white py-12">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div class="lg:col-span-2">
                        <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">分析引擎</span>配管中心</h1>
                        <p class="text-gray-600 text-lg mb-6">统一管理分析引擎，从资源调配、提示词模板到分析引擎的全流程控制平台。</p>
                        <div class="flex flex-wrap gap-4">
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:user-circle" class="text-blue-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">人格设定</p>
                                    <p class="text-xl font-bold text-gray-900">10</p>
                                </div>
                            </div>
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:file-document-multiple" class="text-green-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">提示词模板</p>
                                    <p class="text-xl font-bold text-gray-900">5</p>
                                </div>
                            </div>
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:brain" class="text-amber-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">分析引擎</p>
                                    <p class="text-xl font-bold text-gray-900">2</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4">快速创建分析引擎</h3>
                        <div class="space-y-4">
                            <button
                                class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2"
                                @click="router.push({ name: 'agent-session-list' })">
                                <Icon icon="mdi:clipboard-text-search-outline" />
                                <span>分析会话管理</span>
                            </button>
                            <button
                                class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2"
                                @click="router.push('/agent/engine-config')">
                                <Icon icon="mdi:brain" />
                                <span>配置分析引擎</span>
                            </button>
                            <button
                                class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                                <Icon icon="mdi:file-document-multiple" />
                                <span>【可能需要修改】分析工作管理</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 分析引擎列表区域 -->
        <section class="agent-launch-section py-12 bg-linear-to-b from-white to-gray-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between items-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                        <Icon icon="mdi:format-list-bulleted" class="text-blue-600 text-2xl" />
                        <span><span class="text-blue-500">分析引擎</span>列表</span>
                    </h2>
                    <el-button v-if="!isMobile || hasPerm(PERM.pages.agent.config.agents.visible)" type="primary" link :disabled="isMobile && !hasPerm(PERM.pages.agent.config.agents.access)" @click="goToEngineConfig">
                        <template #icon><Icon icon="mdi:arrow-right" /></template>
                        查看全部分析引擎
                    </el-button>
                </div>

                <div v-loading="agentListLoading" element-loading-text="加载中..." class="min-h-48">
                    <div v-if="isMobile && (agentListError || agentOptionsError)" class="mb-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700" role="alert">
                        <p>{{ agentListError || agentOptionsError }}</p>
                        <p v-if="agentList.length" class="mt-1 text-xs">以下保留上次加载的引擎资料，可能不是最新状态。</p>
                        <el-button class="mt-3" :loading="agentListLoading" @click="fetchAgentList(); loadAgentOptions()">重新加载</el-button>
                    </div>
                    <div v-if="!agentListLoading && agentList.length === 0 && (!isMobile || !agentListError)" class="flex flex-col items-center justify-center py-16">
                        <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                        <p class="text-gray-500">暂无分析引擎</p>
                    </div>
                    <div v-else-if="agentList.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <div
                            v-for="item in agentList"
                            :key="item.id"
                            class="agent-launch-card bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow"
                        >
                            <div class="flex items-start justify-between mb-4">
                                <div class="flex-1 min-w-0">
                                    <h3 class="text-lg font-bold text-gray-900 mb-2 truncate">{{ item.name }}</h3>
                                    <p v-if="item.description" class="text-sm text-gray-600 line-clamp-2">{{ item.description }}</p>
                                </div>
                                <div class="ml-3 shrink-0">
                                    <div class="w-12 h-12 rounded-xl flex items-center justify-center bg-blue-100">
                                        <Icon icon="mdi:brain" class="text-2xl text-blue-600" />
                                    </div>
                                </div>
                            </div>

                            <div class="space-y-3 mb-4">
                                <div v-if="item.llm_provider" class="flex items-center justify-between text-sm gap-2">
                                    <span class="text-gray-500 flex items-center gap-2 shrink-0">
                                        <Icon icon="mdi:api" class="text-cyan-500" />
                                        LLM 提供商
                                    </span>
                                    <span class="font-medium text-gray-900 truncate">{{ formatLlmProviderLabel(item.llm_provider) }}</span>
                                </div>
                                <div v-if="item.llm_config && Object.keys(item.llm_config).length" class="flex items-center justify-between text-sm">
                                    <span class="text-gray-500 flex items-center gap-2">
                                        <Icon icon="mdi:cog" class="text-orange-500" />
                                        LLM 配置
                                    </span>
                                    <span class="font-medium text-gray-900">{{ Object.keys(item.llm_config).length }} 项</span>
                                </div>
                                <div v-if="item.tools?.length" class="flex items-center justify-between text-sm gap-2">
                                    <span class="text-gray-500 flex items-center gap-2 shrink-0">
                                        <Icon icon="mdi:tools" class="text-purple-500" />
                                        工具
                                    </span>
                                    <el-tooltip
                                        v-if="item.tools.length > 2"
                                        :content="item.tools.join('、')"
                                        placement="top"
                                    >
                                        <span class="font-medium text-gray-900 truncate cursor-default">
                                            {{ formatToolsLabel(item.tools) }}
                                        </span>
                                    </el-tooltip>
                                    <span v-else class="font-medium text-gray-900 truncate">
                                        {{ formatToolsLabel(item.tools) }}
                                    </span>
                                </div>
                                <div v-if="item.updated_at" class="flex items-center justify-between text-sm">
                                    <span class="text-gray-500 flex items-center gap-2">
                                        <Icon icon="mdi:clock-outline" class="text-amber-500" />
                                        更新时间
                                    </span>
                                    <span class="font-medium text-gray-900">{{ formatModelDate(item.updated_at) }}</span>
                                </div>
                            </div>

                            <div class="pt-4 border-t border-gray-200">
                                <AgentStartButton
                                    button-text="运行"
                                    :agent-options="runAgentOptions"
                                    :preselected-agent-id="item.id"
                                    icon="mdi:play-circle-outline"
                                    block
                                    element-primary
                                    @started="handleAgentStarted"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 分析引擎分类统计 -->
        <section v-if="!isMobile" class="py-12 bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between items-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                        <Icon icon="mdi:chart-bar" class="text-blue-600 text-2xl" />
                        <span><span class="text-blue-500">分析引擎</span>分类统计</span>
                    </h2>
                    <el-radio-group v-model="statsTimeRange" size="small">
                        <el-radio-button label="week">本周</el-radio-button>
                        <el-radio-button label="month">本月</el-radio-button>
                        <el-radio-button label="year">本年</el-radio-button>
                    </el-radio-group>
                </div>

                <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead>
                                <tr class="border-b border-gray-200 bg-gray-50">
                                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">分析引擎类型</th>
                                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">数量</th>
                                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">使用率</th>
                                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">变化趋势</th>
                                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">平均响应时间</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="stat in agentStats"
                                    :key="stat.type"
                                    class="border-b border-gray-100 hover:bg-gray-50"
                                >
                                    <td class="py-3 px-4">
                                        <div class="flex items-center">
                                            <div :class="['w-2 h-2 rounded-full mr-2', stat.colorClass]"></div>
                                            <span class="font-medium">{{ stat.type }}</span>
                                        </div>
                                    </td>
                                    <td class="py-3 px-4">{{ stat.count }}</td>
                                    <td class="py-3 px-4">
                                        <div class="flex items-center">
                                            <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden mr-2" style="max-width: 100px">
                                                <div
                                                    class="h-full bg-blue-500 rounded-full"
                                                    :style="{ width: stat.usageRate }"
                                                ></div>
                                            </div>
                                            <span class="text-sm">{{ stat.usageRate }}</span>
                                        </div>
                                    </td>
                                    <td class="py-3 px-4">
                                        <div :class="['flex items-center', stat.trendClass]">
                                            <Icon :icon="stat.trendIcon" />
                                            <span class="ml-1">{{ stat.trend }}</span>
                                        </div>
                                    </td>
                                    <td class="py-3 px-4">{{ stat.avgResponseTime }}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- 分析引擎性能监控 -->
        <section v-if="!isMobile" class="py-12 bg-linear-to-b from-gray-50 to-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between items-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                        <Icon icon="mdi:monitor-dashboard" class="text-blue-600 text-2xl" />
                        <span><span class="text-blue-500">分析引擎</span>性能监控</span>
                    </h2>
                    <el-button type="primary" link>
                        <template #icon><Icon icon="mdi:settings" /></template>
                        引擎配置
                    </el-button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div
                        v-for="engine in engineStats"
                        :key="engine.id"
                        class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow"
                    >
                        <div class="flex items-start justify-between mb-4">
                            <div class="flex items-center space-x-3">
                                <div :class="['w-12 h-12 rounded-xl flex items-center justify-center', engine.statusBgColor]">
                                    <Icon :icon="engine.icon" :class="['text-2xl', engine.statusIconColor]" />
                                </div>
                                <div>
                                    <h3 class="font-bold text-gray-900">{{ engine.name }}</h3>
                                    <p class="text-sm text-gray-500">{{ engine.description }}</p>
                                </div>
                            </div>
                            <el-tag :type="engine.statusType" size="small">{{ engine.status }}</el-tag>
                        </div>

                        <div class="space-y-4">
                            <div>
                                <div class="flex justify-between text-sm mb-1">
                                    <span class="text-gray-600">CPU 使用率</span>
                                    <span class="font-medium">{{ engine.cpuUsage }}%</span>
                                </div>
                                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                                    <div
                                        class="h-full rounded-full transition-all"
                                        :class="engine.cpuUsage > 80 ? 'bg-red-500' : engine.cpuUsage > 60 ? 'bg-amber-500' : 'bg-green-500'"
                                        :style="{ width: engine.cpuUsage + '%' }"
                                    ></div>
                                </div>
                            </div>

                            <div>
                                <div class="flex justify-between text-sm mb-1">
                                    <span class="text-gray-600">内存使用率</span>
                                    <span class="font-medium">{{ engine.memoryUsage }}%</span>
                                </div>
                                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                                    <div
                                        class="h-full rounded-full transition-all"
                                        :class="engine.memoryUsage > 80 ? 'bg-red-500' : engine.memoryUsage > 60 ? 'bg-amber-500' : 'bg-green-500'"
                                        :style="{ width: engine.memoryUsage + '%' }"
                                    ></div>
                                </div>
                            </div>

                            <div class="grid grid-cols-2 gap-3 pt-3 border-t border-gray-200">
                                <div class="text-center p-3 bg-gray-50 rounded-lg">
                                    <p class="text-sm text-gray-500">请求处理</p>
                                    <p class="text-lg font-bold text-gray-900">{{ engine.requestCount }}</p>
                                </div>
                                <div class="text-center p-3 bg-gray-50 rounded-lg">
                                    <p class="text-sm text-gray-500">响应时间</p>
                                    <p class="text-lg font-bold text-gray-900">{{ engine.avgResponseTime }}</p>
                                </div>
                            </div>

                            <div class="pt-3 border-t border-gray-200">
                                <div class="flex items-center justify-between">
                                    <span class="text-sm text-gray-600">可用性</span>
                                    <span :class="['text-sm font-medium', engine.availability >= 99 ? 'text-green-600' : engine.availability >= 95 ? 'text-amber-600' : 'text-red-600']">
                                        {{ engine.availability }}%
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import { Icon } from '@iconify/vue'
import AgentStartButton from '@/components/agent/AgentStartButton.vue'
import { agentApi } from '@/api/agent'
import { formatDateTime } from '@/utils/action'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'

defineOptions({ name: 'AgentMonitor' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const canViewSessions = computed(() => hasPerm(PERM.pages.agent.sessions.access) && hasPerm(PERM.operations.agent.session.read))
const statsTimeRange = ref('week')
const agentList = ref([])
const agentListLoading = ref(false)
const agentListError = ref('')
const agentOptionsError = ref('')
const agentOptions = ref([])
let agentListRequest = 0

const runAgentOptions = computed(() =>
    agentOptions.value.map((item) => ({
        label: item.label,
        value: item.value,
    }))
)

const LLM_PROVIDER_OPTIONS = [
    { value: 'openai', label: 'OpenAI 兼容' },
    { value: 'anthropic', label: 'Anthropic Claude 兼容' }
]

const formatLlmProviderLabel = (value) => {
    const opt = LLM_PROVIDER_OPTIONS.find((item) => item.value === value)
    return opt?.label ?? value ?? '-'
}

const formatModelDate = (dateStr) => formatDateTime(dateStr, { includeSecond: true })

const formatToolsLabel = (tools) => {
    if (!tools?.length) return '-'
    if (tools.length <= 2) return tools.join('、')
    return `${tools.slice(0, 2).join('、')}等${tools.length}个工具`
}

async function fetchAgentList() {
    const requestId = ++agentListRequest
    agentListLoading.value = true
    agentListError.value = ''
    try {
        const response = await agentApi.getAgentList({
            page: 1,
            page_size: 6
        })
        if (requestId !== agentListRequest) return
        const data = response?.code === 0 && response.data
            ? response.data
            : Array.isArray(response?.items) && typeof response.total === 'number' ? response : null
        if (!data || !Array.isArray(data.items)) throw new Error('引擎列表返回无效')
        agentList.value = data.items
    } catch {
        if (requestId !== agentListRequest) return
        agentListError.value = '分析引擎加载失败，请重新加载'
        if (!isMobile.value) agentList.value = []
    } finally {
        if (requestId === agentListRequest) agentListLoading.value = false
    }
}

function goToEngineConfig() {
    router.push({ name: 'agent-engine-config' })
}

async function loadAgentOptions() {
    agentOptionsError.value = ''
    try {
        const res = await agentApi.getAgentsConfigList()
        if (res?.code !== 0 || !Array.isArray(res.data)) throw new Error('引擎选项返回无效')
        const list = res.data
        agentOptions.value = list.map((item) => ({
            label: item.name,
            value: item.id,
        }))
    } catch {
        agentOptions.value = []
        agentOptionsError.value = '可运行引擎选项加载失败，请重新加载后发起分析'
    }
}

function handleAgentStarted({ agentId, sessionId }) {
    router.push({
        name: 'agent-analysis-detail',
        params: { sessionId: String(sessionId) },
        query: { agent_id: String(agentId) },
    })
}

onMounted(() => {
    fetchAgentList()
    loadAgentOptions()
})
const agentStats = ref([
                {
                    type: '网络安全',
                    count: '15',
                    usageRate: '85%',
                    trend: '+3.2%',
                    avgResponseTime: '1.2s',
                    colorClass: 'bg-blue-500',
                    trendClass: 'text-green-600',
                    trendIcon: 'mdi:trending-up'
                },
                {
                    type: '舆情监控',
                    count: '12',
                    usageRate: '72%',
                    trend: '+5.8%',
                    avgResponseTime: '0.9s',
                    colorClass: 'bg-green-500',
                    trendClass: 'text-green-600',
                    trendIcon: 'mdi:trending-up'
                },
                {
                    type: '情报收集',
                    count: '8',
                    usageRate: '68%',
                    trend: '-1.5%',
                    avgResponseTime: '1.5s',
                    colorClass: 'bg-purple-500',
                    trendClass: 'text-red-600',
                    trendIcon: 'mdi:trending-down'
                },
                {
                    type: '数据挖掘',
                    count: '10',
                    usageRate: '91%',
                    trend: '+2.3%',
                    avgResponseTime: '2.1s',
                    colorClass: 'bg-amber-500',
                    trendClass: 'text-green-600',
                    trendIcon: 'mdi:trending-up'
                }
            ])
const engineStats = ref([
                {
                    id: 1,
                    name: 'GPT-4 Turbo',
                    description: 'OpenAI 分析引擎',
                    status: '正常',
                    statusType: 'success',
                    icon: 'mdi:brain',
                    statusBgColor: 'bg-blue-100',
                    statusIconColor: 'text-blue-600',
                    cpuUsage: 45,
                    memoryUsage: 62,
                    requestCount: '1.2K',
                    avgResponseTime: '1.1s',
                    availability: 99.8
                },
                {
                    id: 2,
                    name: 'Claude 3.5',
                    description: 'Anthropic 分析引擎',
                    status: '正常',
                    statusType: 'success',
                    icon: 'mdi:robot',
                    statusBgColor: 'bg-green-100',
                    statusIconColor: 'text-green-600',
                    cpuUsage: 38,
                    memoryUsage: 55,
                    requestCount: '980',
                    avgResponseTime: '0.9s',
                    availability: 99.5
                },
                {
                    id: 3,
                    name: '本地分析引擎',
                    description: '自研分析引擎',
                    status: '警告',
                    statusType: 'warning',
                    icon: 'mdi:server',
                    statusBgColor: 'bg-amber-100',
                    statusIconColor: 'text-amber-600',
                    cpuUsage: 78,
                    memoryUsage: 85,
                    requestCount: '650',
                    avgResponseTime: '2.3s',
                    availability: 94.2
                }
            ])
</script>

<style scoped>
.mobile-agent-heading { padding: 20px 16px; background: #fff; }
.mobile-agent-heading h1 { font-size: 24px; font-weight: 700; color: #0f172a; }
.mobile-agent-heading p { margin: 6px 0 16px; color: #64748b; font-size: 14px; }
.mobile-agent-heading button { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 52px; padding: 12px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; font-size: 15px; text-align: left; }
.mobile-agent-heading button > svg:last-child { margin-left: auto; }
.mobile-agent-heading button:disabled { opacity: .5; }
.mobile-agent-monitor .agent-launch-section { padding: 16px 0; background: #f8fafc; }
.mobile-agent-monitor .agent-launch-section > div > div:first-child { margin-bottom: 14px; gap: 8px; }
.mobile-agent-monitor .agent-launch-section h2 { font-size: 18px; }
.mobile-agent-monitor .agent-launch-card { padding: 16px; box-shadow: none; border-color: #e2e8f0; }
.mobile-agent-monitor .agent-launch-card :deep(button) { min-height: 44px; }
</style>
