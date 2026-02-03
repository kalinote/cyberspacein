<template>
    <div>
        <Header />

        <!-- 英雄区域 -->
        <section class="bg-linear-to-br from-blue-50 to-white py-12">
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
                                @click="$router.push('/agent/new')">
                                <Icon icon="mdi:rocket-launch-outline" />
                                <span>新建分析引擎</span>
                            </button>
                            <button
                                class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2"
                                @click="$router.push('/agent/engine-config')">
                                <Icon icon="mdi:brain" />
                                <span>配置分析引擎</span>
                            </button>
                            <button
                                class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                                <Icon icon="mdi:file-document-multiple" />
                                <span>分析工作管理</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 分析引擎列表区域 -->
        <section class="py-12 bg-linear-to-b from-white to-gray-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between items-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                        <Icon icon="mdi:format-list-bulleted" class="text-blue-600 text-2xl" />
                        <span><span class="text-blue-500">分析引擎</span>列表</span>
                    </h2>
                    <el-button type="primary" link>
                        <template #icon><Icon icon="mdi:arrow-right" /></template>
                        查看全部分析引擎
                    </el-button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div
                        v-for="agent in agents"
                        :key="agent.id"
                        class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow"
                    >
                        <div class="flex items-start justify-between mb-4">
                            <div class="flex-1">
                                <h3 class="text-lg font-bold text-gray-900 mb-2">{{ agent.name }}</h3>
                                <el-tag :type="agent.statusType" size="small">{{ agent.status }}</el-tag>
                            </div>
                            <div class="ml-3 shrink-0">
                                <div :class="['w-12 h-12 rounded-xl flex items-center justify-center', agent.typeBgColor]">
                                    <Icon :icon="agent.typeIcon" :class="['text-2xl', agent.typeIconColor]" />
                                </div>
                            </div>
                        </div>

                        <div class="space-y-3 mb-4">
                            <div class="flex items-center justify-between text-sm">
                                <span class="text-gray-500 flex items-center gap-2">
                                    <Icon icon="mdi:account-circle" class="text-blue-500" />
                                    人格设定
                                </span>
                                <span class="font-medium text-gray-900">{{ agent.personality }}</span>
                            </div>
                            <div class="flex items-center justify-between text-sm">
                                <span class="text-gray-500 flex items-center gap-2">
                                    <Icon icon="mdi:brain" class="text-green-500" />
                                    分析引擎
                                </span>
                                <span class="font-medium text-gray-900">{{ agent.engine }}</span>
                            </div>
                            <div class="flex items-center justify-between text-sm">
                                <span class="text-gray-500 flex items-center gap-2">
                                    <Icon icon="mdi:file-document-multiple" class="text-purple-500" />
                                    提示词模板
                                </span>
                                <span class="font-medium text-gray-900">{{ agent.templateCount }} 个</span>
                            </div>
                            <div class="flex items-center justify-between text-sm">
                                <span class="text-gray-500 flex items-center gap-2">
                                    <Icon icon="mdi:calendar" class="text-amber-500" />
                                    创建时间
                                </span>
                                <span class="font-medium text-gray-900">{{ agent.createdAt }}</span>
                            </div>
                        </div>

                        <div class="pt-4 border-t border-gray-200">
                            <div class="flex items-center gap-2">
                                <el-button type="primary" link size="small" class="flex-1">
                                    <template #icon><Icon icon="mdi:eye" /></template>
                                    查看详情
                                </el-button>
                                <el-button type="primary" link size="small">
                                    <template #icon><Icon icon="mdi:pencil" /></template>
                                    编辑
                                </el-button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 分析引擎分类统计 -->
        <section class="py-12 bg-white">
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
        <section class="py-12 bg-linear-to-b from-gray-50 to-white">
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

<script>
import Header from '@/components/Header.vue'
import { Icon } from '@iconify/vue'

export default {
    name: 'AgentMonitor',
    components: {
        Header,
        Icon
    },
    data() {
        return {
            statsTimeRange: 'week',
            agents: [
                {
                    id: 1,
                    name: '网络安全分析分析引擎',
                    status: '运行中',
                    statusType: 'success',
                    personality: '技术专家',
                    engine: 'GPT-4 Turbo',
                    templateCount: 3,
                    createdAt: '2025-01-05',
                    typeIcon: 'mdi:shield-check',
                    typeBgColor: 'bg-blue-100',
                    typeIconColor: 'text-blue-600'
                },
                {
                    id: 2,
                    name: '舆情监控分析引擎',
                    status: '运行中',
                    statusType: 'success',
                    personality: '分析师',
                    engine: 'Claude 3.5',
                    templateCount: 5,
                    createdAt: '2025-01-03',
                    typeIcon: 'mdi:chart-line',
                    typeBgColor: 'bg-green-100',
                    typeIconColor: 'text-green-600'
                },
                {
                    id: 3,
                    name: '情报收集分析引擎',
                    status: '待启动',
                    statusType: 'warning',
                    personality: '研究员',
                    engine: 'GPT-4 Turbo',
                    templateCount: 2,
                    createdAt: '2025-01-07',
                    typeIcon: 'mdi:database-search',
                    typeBgColor: 'bg-purple-100',
                    typeIconColor: 'text-purple-600'
                },
                {
                    id: 4,
                    name: '数据挖掘分析引擎',
                    status: '运行中',
                    statusType: 'success',
                    personality: '数据科学家',
                    engine: 'Claude 3.5',
                    templateCount: 4,
                    createdAt: '2025-01-04',
                    typeIcon: 'mdi:chart-box',
                    typeBgColor: 'bg-amber-100',
                    typeIconColor: 'text-amber-600'
                },
                {
                    id: 5,
                    name: '威胁检测分析引擎',
                    status: '暂停',
                    statusType: 'info',
                    personality: '安全专家',
                    engine: 'GPT-4 Turbo',
                    templateCount: 6,
                    createdAt: '2025-01-02',
                    typeIcon: 'mdi:alert-octagon',
                    typeBgColor: 'bg-red-100',
                    typeIconColor: 'text-red-600'
                },
                {
                    id: 6,
                    name: '内容分析分析引擎',
                    status: '已完成',
                    statusType: '',
                    personality: '编辑',
                    engine: 'Claude 3.5',
                    templateCount: 3,
                    createdAt: '2024-12-28',
                    typeIcon: 'mdi:text-box-search',
                    typeBgColor: 'bg-indigo-100',
                    typeIconColor: 'text-indigo-600'
                }
            ],
            agentStats: [
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
            ],
            engineStats: [
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
            ]
        }
    }
}
</script>