<template>
    <div class="h-screen flex flex-col bg-white">
        <!-- TODO: 此页面尚未完成，暂时用于功能和布局展示 -->
        <Header />

        <div class="px-5 py-3 bg-white border-b border-gray-200 flex items-center shrink-0">
            <el-button type="primary" link @click="$router.back()" class="mb-0!">
                <template #icon>
                    <Icon icon="mdi:arrow-left" />
                </template>
                返回
            </el-button>
            <span class="text-xl font-bold text-gray-800 ml-4">{{ actionData.name || '行动详情' }}</span>
        </div>

        <div class="flex-1 flex overflow-hidden">
            <!-- 流程图区域 -->
            <div class="flex-1 h-full relative bg-gray-50">
                <div v-if="loadingNodeConfigs" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                    <div class="text-center">
                        <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                        <p class="text-gray-600">加载节点配置中...</p>
                    </div>
                </div>
                <VueFlow 
                    v-model="elements" 
                    :node-types="nodeTypes"
                    :default-zoom="1.5" 
                    :min-zoom="0.2" 
                    :max-zoom="4"
                    :nodes-draggable="false"
                    :nodes-connectable="false"
                    :elements-selectable="true"
                    @node-click="handleNodeClick"
                    @pane-click="handlePaneClick"
                    class="h-full w-full"
                >
                    <Background pattern-color="#aaa" :gap="18" />
                    <Controls />
                </VueFlow>
                <div v-if="elements.length === 0 && !loadingNodeConfigs" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                    <div class="text-center text-gray-400">
                        <Icon icon="mdi:graph-outline" class="text-6xl mb-4" />
                        <p>暂无节点数据</p>
                    </div>
                </div>
            </div>

            <!-- 右侧边栏 -->
            <div 
                class="bg-white flex flex-col border-l border-gray-200 relative shrink-0 group"
                :style="{ width: rightSidebarWidth + 'px' }"
            >
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">行动信息</h3>
                </div>
                <div class="p-4 flex flex-col gap-4 flex-1 overflow-y-auto min-h-0">
                    <!-- 基本信息卡片 -->
                    <div class="bg-gray-50 rounded-xl p-4 border border-gray-200">
                        <h4 class="text-sm font-semibold text-gray-800 mb-3">基本信息</h4>
                        <div class="space-y-3">
                            <div>
                                <label class="text-xs text-gray-500">标题</label>
                                <p class="text-sm font-medium text-gray-900 mt-1">{{ actionData.name }}</p>
                            </div>
                            <div>
                                <label class="text-xs text-gray-500">描述</label>
                                <p class="text-sm text-gray-700 mt-1">{{ actionData.description || '无' }}</p>
                            </div>
                            <div>
                                <label class="text-xs text-gray-500">创建时间</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDateTime(actionData.createTime, { includeSecond: true }) }}</p>
                            </div>
                            <div>
                                <label class="text-xs text-gray-500">执行期限</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDuration(actionData.implementation_period) }}</p>
                            </div>
                        </div>
                    </div>

                    <!-- 执行状态卡片 -->
                    <div class="bg-gray-50 rounded-xl p-4 border border-gray-200">
                        <h4 class="text-sm font-semibold text-gray-800 mb-3">执行状态</h4>
                        <div class="space-y-3">
                            <div>
                                <label class="text-xs text-gray-500">总体状态</label>
                                <div class="mt-1">
                                    <el-tag :type="getStatusTagType(actionData.status)" size="small" class="border-0">
                                        {{ getStatusText(actionData.status) }}
                                    </el-tag>
                                </div>
                            </div>
                            <div>
                                <label class="text-xs text-gray-500">总体进度</label>
                                <div class="mt-1">
                                    <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
                                        <span>{{ actionData.progress }}%</span>
                                    </div>
                                    <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                                        <div 
                                            class="h-full bg-linear-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
                                            :style="{ width: actionData.progress + '%' }"
                                        ></div>
                                    </div>
                                </div>
                            </div>
                            <div v-if="actionData.startTime">
                                <label class="text-xs text-gray-500">开始时间</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDateTime(actionData.startTime, { includeSecond: true }) }}</p>
                            </div>
                            <div v-if="actionData.endTime">
                                <label class="text-xs text-gray-500">结束时间</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDateTime(actionData.endTime, { includeSecond: true }) }}</p>
                            </div>
                            <div v-if="actionData.current_executing_node">
                                <label class="text-xs text-gray-500">当前执行节点</label>
                                <p class="text-sm text-blue-600 mt-1 cursor-pointer hover:text-blue-800" @click="scrollToNode(actionData.current_executing_node)">
                                    {{ getNodeName(actionData.current_executing_node) }}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 调整大小手柄 -->
                <div 
                    class="absolute top-0 bottom-0 -left-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startRightResize"
                >
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors" :class="{ 'bg-blue-600!': isRightResizing }"></div>
                </div>
            </div>
        </div>

        <!-- 底部节点详细信息栏 -->
        <div 
            class="bg-white border-t border-gray-200 transition-all duration-300 overflow-hidden"
            :style="{ height: nodeDetailExpanded ? '400px' : '0px' }"
        >
            <div v-if="nodeDetailExpanded" class="h-full flex flex-col">
                <div class="px-6 py-3 border-b border-gray-200 flex items-center justify-between shrink-0">
                    <div class="flex items-center gap-3">
                        <h3 class="text-base font-semibold text-gray-800">节点详细信息</h3>
                        <el-tag v-if="selectedNodeDetail" :type="getStatusTagType(selectedNodeDetail.status)" size="small" class="border-0">
                            {{ getStatusText(selectedNodeDetail.status) }}
                        </el-tag>
                    </div>
                    <el-button type="primary" link size="small" @click="collapseNodeDetail">
                        <template #icon>
                            <Icon :icon="nodeDetailCollapsed ? 'mdi:chevron-up' : 'mdi:chevron-down'" />
                        </template>
                        {{ nodeDetailCollapsed ? '展开' : '折叠' }}
                    </el-button>
                </div>
                <div v-if="selectedNodeDetail" class="flex-1 overflow-y-auto p-6">
                    <div class="space-y-6">
                        <!-- 基本信息 -->
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800 mb-3">基本信息</h4>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="text-xs text-gray-500">节点名称</label>
                                    <p class="text-sm font-medium text-gray-900 mt-1">{{ selectedNodeDetail.name }}</p>
                                </div>
                                <div>
                                    <label class="text-xs text-gray-500">执行状态</label>
                                    <div class="mt-1">
                                        <el-tag :type="getStatusTagType(selectedNodeDetail.status)" size="small" class="border-0">
                                            {{ getStatusText(selectedNodeDetail.status) }}
                                        </el-tag>
                                    </div>
                                </div>
                                <div v-if="selectedNodeDetail.startTime">
                                    <label class="text-xs text-gray-500">开始时间</label>
                                    <p class="text-sm text-gray-700 mt-1">{{ formatDateTime(selectedNodeDetail.startTime, { includeSecond: true }) }}</p>
                                </div>
                                <div v-if="selectedNodeDetail.endTime">
                                    <label class="text-xs text-gray-500">结束时间</label>
                                    <p class="text-sm text-gray-700 mt-1">{{ formatDateTime(selectedNodeDetail.endTime, { includeSecond: true }) }}</p>
                                </div>
                            </div>
                        </div>

                        <!-- 执行结果 -->
                        <div v-if="selectedNodeDetail.result || selectedNodeDetail.errorMessage">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3">执行结果</h4>
                            <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <div v-if="selectedNodeDetail.errorMessage" class="text-sm text-red-600">
                                    <Icon icon="mdi:alert-circle" class="inline mr-2" />
                                    <span class="font-medium">错误信息：</span>
                                    <p class="mt-1 whitespace-pre-wrap">{{ selectedNodeDetail.errorMessage }}</p>
                                </div>
                                <div v-else-if="selectedNodeDetail.result" class="text-sm text-green-600">
                                    <Icon icon="mdi:check-circle" class="inline mr-2" />
                                    <span class="font-medium">执行成功</span>
                                </div>
                            </div>
                        </div>

                        <!-- 输入参数 -->
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center justify-between">
                                <span>输入参数</span>
                                <el-button type="primary" link size="small" @click="toggleInputParamsCollapsed">
                                    <template #icon>
                                        <Icon :icon="inputParamsCollapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'" />
                                    </template>
                                </el-button>
                            </h4>
                            <div v-show="!inputParamsCollapsed" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <pre class="text-xs text-gray-700 overflow-x-auto">{{ formatJSON(selectedNodeDetail.inputParams) }}</pre>
                            </div>
                        </div>

                        <!-- 输出数据 -->
                        <div v-if="selectedNodeDetail.outputData">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center justify-between">
                                <span>输出数据</span>
                                <el-button type="primary" link size="small" @click="toggleOutputDataCollapsed">
                                    <template #icon>
                                        <Icon :icon="outputDataCollapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'" />
                                    </template>
                                </el-button>
                            </h4>
                            <div v-show="!outputDataCollapsed" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <pre class="text-xs text-gray-700 overflow-x-auto">{{ formatJSON(selectedNodeDetail.outputData) }}</pre>
                            </div>
                        </div>

                        <!-- 执行日志 -->
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800 mb-3">执行日志</h4>
                            <div class="bg-gray-50 rounded-lg border border-gray-200 max-h-48 overflow-y-auto">
                                <div 
                                    v-for="(log, index) in selectedNodeDetail.logs" 
                                    :key="index"
                                    class="px-4 py-2 border-b border-gray-200 last:border-b-0"
                                    :class="getLogLevelClass(log.level)"
                                >
                                    <div class="flex items-start gap-2">
                                        <span class="text-xs text-gray-500 shrink-0">{{ formatLogTime(log.timestamp) }}</span>
                                        <span class="text-xs font-medium shrink-0" :class="getLogLevelTextClass(log.level)">
                                            [{{ log.level.toUpperCase() }}]
                                        </span>
                                        <span class="text-xs text-gray-700 flex-1">{{ log.message }}</span>
                                    </div>
                                </div>
                                <div v-if="!selectedNodeDetail.logs || selectedNodeDetail.logs.length === 0" class="px-4 py-8 text-center text-sm text-gray-400">
                                    暂无日志
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-else class="flex-1 flex items-center justify-center text-gray-400">
                    <div class="text-center">
                        <Icon icon="mdi:information-outline" class="text-4xl mb-2" />
                        <p>请点击节点查看详细信息</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, markRaw, h } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from "@/components/Header.vue"
import { VueFlow, useVueFlow } from "@vue-flow/core"
import { Background } from "@vue-flow/background"
import { Controls } from "@vue-flow/controls"
import GenericNode from "@/components/action/nodes/GenericNode.vue"
import { actionApi } from '@/api/action'
import { ElMessage } from 'element-plus'
import {
  SOCKET_TYPE_CONFIGS,
  normalizeDefaultValue,
  formatDateTime,
  formatDuration,
  formatJSON,
  formatLogTime,
  getStatusText,
  getStatusTagType,
  getLogLevelClass,
  getLogLevelTextClass,
  getEdgeColor
} from '@/utils/action'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const route = useRoute()
const actionId = computed(() => route.params.id)

const nodeTypeConfigs = ref([])
const loadingNodeConfigs = ref(false)

const fetchNodeConfigs = async () => {
    loadingNodeConfigs.value = true
    try {
        const response = await actionApi.getNodes()
        if (response.code === 0) {
            const nodes = response.data || []
            nodeTypeConfigs.value = nodes.map(node => {
                const processedNode = { ...node }
                if (processedNode.handles) {
                    processedNode.handles = processedNode.handles.map(handle => ({
                        ...handle,
                        id: handle.id || handle.name
                    }))
                }
                if (processedNode.inputs) {
                    processedNode.inputs = processedNode.inputs.map(input => ({
                        ...input,
                        id: input.id || input.name
                    }))
                }
                return processedNode
            })
        } else {
            ElMessage.error(`获取节点配置失败: ${response.message}`)
            nodeTypeConfigs.value = []
        }
    } catch (error) {
        ElMessage.error('获取节点配置失败')
        nodeTypeConfigs.value = []
    } finally {
        loadingNodeConfigs.value = false
    }
}

const socketTypeConfigs = ref(SOCKET_TYPE_CONFIGS)

const StatusAwareNode = {
    components: { GenericNode },
    props: ['id', 'data', 'selected'],
    setup(props) {
        const executionStatus = computed(() => props.data?.executionStatus || null)
        const nodeStatus = computed(() => executionStatus.value?.status || 'pending')
        const progress = computed(() => executionStatus.value?.progress || 0)
        const isSelected = computed(() => props.selected)

        return () => {
            return h('div', {
                class: isSelected.value ? 'ring-2 ring-blue-500 ring-offset-2' : '',
                style: {
                    position: 'relative'
                }
            }, [
                nodeStatus.value === 'running' ? h('div', {
                    class: 'absolute top-0 left-0 h-0.5 bg-green-500 transition-all duration-300 z-10',
                    style: { 
                        width: progress.value + '%',
                        borderRadius: '8px 8px 0 0'
                    }
                }) : null,
                h(GenericNode, {
                    id: props.id,
                    data: props.data,
                    disabled: true,
                    showHandle: true
                })
            ])
        }
    }
}

const nodeTypes = computed(() => {
    const types = {}
    nodeTypeConfigs.value.forEach(config => {
        types[config.id] = markRaw(StatusAwareNode)
        if (config.type) {
            types[config.type] = markRaw(StatusAwareNode)
        }
    })
    if (nodeTypeConfigs.value.length === 0) {
        types['crawler'] = markRaw(StatusAwareNode)
        types['construct'] = markRaw(StatusAwareNode)
    }
    return types
})

const elements = ref([])
const { setViewport, getNodes, fitView } = useVueFlow()

const actionData = ref({
    id: '',
    name: '',
    description: '',
    status: 'pending',
    progress: 0,
    createTime: null,
    startTime: null,
    endTime: null,
    implementation_period: 3600,
    resource: {},
    current_executing_node: null,
    graph: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 }
    },
    node_execution_status: {},
    node_details: {}
})

const selectedNodeId = ref(null)
const nodeDetailCollapsed = ref(false)
const inputParamsCollapsed = ref(false)
const outputDataCollapsed = ref(false)

const nodeDetailExpanded = computed(() => {
    return selectedNodeId.value !== null && !nodeDetailCollapsed.value
})

const selectedNodeDetail = computed(() => {
    if (!selectedNodeId.value) return null
    return actionData.value.node_details[selectedNodeId.value] || null
})

const rightSidebarWidth = ref(400)
const isRightResizing = ref(false)
const minRightSidebarWidth = 300
const maxRightSidebarWidth = 800

const startRightResize = () => {
    isRightResizing.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onRightResize)
    window.addEventListener('mouseup', stopRightResize)
}

const onRightResize = (event) => {
    if (!isRightResizing.value) return
    const newWidth = window.innerWidth - event.clientX
    if (newWidth < minRightSidebarWidth) {
        rightSidebarWidth.value = minRightSidebarWidth
    } else if (newWidth > maxRightSidebarWidth) {
        rightSidebarWidth.value = maxRightSidebarWidth
    } else {
        rightSidebarWidth.value = newWidth
    }
}

const stopRightResize = () => {
    isRightResizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onRightResize)
    window.removeEventListener('mouseup', stopRightResize)
}

const handleNodeClick = (event) => {
    const nodeId = event.node.id
    selectedNodeId.value = nodeId
    nodeDetailCollapsed.value = false
}

const handlePaneClick = () => {
    selectedNodeId.value = null
}

const collapseNodeDetail = () => {
    nodeDetailCollapsed.value = !nodeDetailCollapsed.value
}

const toggleInputParamsCollapsed = () => {
    inputParamsCollapsed.value = !inputParamsCollapsed.value
}

const toggleOutputDataCollapsed = () => {
    outputDataCollapsed.value = !outputDataCollapsed.value
}

const scrollToNode = (nodeId) => {
    const nodes = getNodes.value
    const node = nodes.find(n => n.id === nodeId)
    if (node) {
        selectedNodeId.value = nodeId
        nodeDetailCollapsed.value = false
    }
}

const getNodeName = (nodeId) => {
    const detail = actionData.value.node_details[nodeId]
    if (detail) return detail.name
    const node = elements.value.find(el => el.id === nodeId && !el.source)
    if (node?.data?.config) return node.data.config.name
    return nodeId
}


const loadActionData = () => {
    if (nodeTypeConfigs.value.length === 0) {
        return
    }
    
    const mockData = {
        id: actionId.value,
        name: '测试行动的标题',
        description: '测试行动的详细信息，这是一个用于测试的行动描述。',
        status: 'running',
        progress: 45,
        createTime: '2024-01-20T10:00:00Z',
        startTime: '2024-01-20T10:05:00Z',
        endTime: null,
        implementation_period: 3600,
        resource: {},
        current_executing_node: 'node-1766409613714',
        graph: {
            nodes: [
                {
                    id: 'node-1766409613714',
                    type: 'crawler',
                    position: { x: 776.0293153124745, y: 248.393213519107 },
                    data: {
                        definition_id: '4215c71cb06428eaed6ea8c0e2bb8c51',
                        version: '1.0.0',
                        form_data: { page: 2 }
                    }
                },
                {
                    id: 'node-1766409614971',
                    type: 'construct',
                    position: { x: 377.5024829894806, y: 130.68347764321777 },
                    data: {
                        definition_id: 'cb2e84f0531879570d4127bdaa79bc3d',
                        version: '1.0.0',
                        form_data: {
                            keywords: ['原神', '明日方舟']
                        }
                    }
                },
                {
                    id: 'node-1766409619604',
                    type: 'construct',
                    position: { x: 384.0443109513752, y: 346.47903965632696 },
                    data: {
                        definition_id: 'a39ba2f46e678df78ffc63321f79d371',
                        version: '1.0.0',
                        form_data: {
                            platforms: ['bilibili', '微博']
                        }
                    }
                }
            ],
            edges: [
                {
                    id: 'vueflow__edge-node-1766409619604c5c840162ee803f90173ef3880dba422-node-1766409613714f79b7a7211a9c06ed8e31badc8a723be',
                    source: 'node-1766409619604',
                    sourceHandle: 'c5c840162ee803f90173ef3880dba422',
                    target: 'node-1766409613714',
                    targetHandle: 'f79b7a7211a9c06ed8e31badc8a723be'
                },
                {
                    id: 'vueflow__edge-node-17664096149714c125fe2b716968454ccfb65759108f5-node-17664096137143d35d9a35af9b9dda3633be10783001d',
                    source: 'node-1766409614971',
                    sourceHandle: '4c125fe2b716968454ccfb65759108f5',
                    target: 'node-1766409613714',
                    targetHandle: '3d35d9a35af9b9dda3633be10783001d'
                }
            ],
            viewport: {
                x: -405.66799728486785,
                y: 18.0875452553704,
                zoom: 1.7411011265922482
            }
        },
        node_execution_status: {
            'node-1766409613714': {
                status: 'running',
                progress: 65,
                startTime: '2024-01-20T10:05:00Z',
                endTime: null
            },
            'node-1766409614971': {
                status: 'completed',
                progress: 100,
                startTime: '2024-01-20T10:05:00Z',
                endTime: '2024-01-20T10:15:00Z'
            },
            'node-1766409619604': {
                status: 'completed',
                progress: 100,
                startTime: '2024-01-20T10:05:00Z',
                endTime: '2024-01-20T10:12:00Z'
            }
        },
        node_details: {
            'node-1766409613714': {
                name: '爬虫节点',
                status: 'running',
                startTime: '2024-01-20T10:05:00Z',
                endTime: null,
                result: null,
                inputParams: {
                    page: 2,
                    platforms: ['bilibili', '微博'],
                    keywords: ['原神', '明日方舟']
                },
                outputData: null,
                errorMessage: null,
                logs: [
                    { timestamp: '2024-01-20T10:05:00Z', level: 'info', message: '开始执行爬虫任务...' },
                    { timestamp: '2024-01-20T10:05:05Z', level: 'info', message: '连接到目标平台...' },
                    { timestamp: '2024-01-20T10:05:10Z', level: 'info', message: '正在获取数据，进度 30%...' },
                    { timestamp: '2024-01-20T10:05:15Z', level: 'info', message: '正在获取数据，进度 65%...' }
                ]
            },
            'node-1766409614971': {
                name: '关键词构建节点',
                status: 'completed',
                startTime: '2024-01-20T10:05:00Z',
                endTime: '2024-01-20T10:15:00Z',
                result: 'success',
                inputParams: {
                    keywords: ['原神', '明日方舟']
                },
                outputData: {
                    processed_keywords: ['原神', '明日方舟', 'Genshin Impact', 'Arknights'],
                    count: 4
                },
                errorMessage: null,
                logs: [
                    { timestamp: '2024-01-20T10:05:00Z', level: 'info', message: '开始处理关键词...' },
                    { timestamp: '2024-01-20T10:05:05Z', level: 'info', message: '扩展关键词列表...' },
                    { timestamp: '2024-01-20T10:15:00Z', level: 'info', message: '关键词处理完成，共生成 4 个关键词' }
                ]
            },
            'node-1766409619604': {
                name: '平台构建节点',
                status: 'completed',
                startTime: '2024-01-20T10:05:00Z',
                endTime: '2024-01-20T10:12:00Z',
                result: 'success',
                inputParams: {
                    platforms: ['bilibili', '微博']
                },
                outputData: {
                    platform_configs: {
                        'bilibili': { enabled: true, api_key: '***' },
                        '微博': { enabled: true, api_key: '***' }
                    }
                },
                errorMessage: null,
                logs: [
                    { timestamp: '2024-01-20T10:05:00Z', level: 'info', message: '开始配置平台...' },
                    { timestamp: '2024-01-20T10:10:00Z', level: 'info', message: '平台配置完成' },
                    { timestamp: '2024-01-20T10:12:00Z', level: 'info', message: '所有平台已就绪' }
                ]
            }
        }
    }
    
    actionData.value = mockData
    
    const findNodeConfigByFormData = (formData, nodeType) => {
        if (!formData || !nodeTypeConfigs.value.length) return null
        
        const formDataKeys = Object.keys(formData)
        if (formDataKeys.length === 0) return null
        
        let bestMatch = null
        let maxMatchCount = 0
        
        const candidates = nodeTypeConfigs.value.filter(c => c.type === nodeType)
        
        for (const candidate of candidates) {
            if (!candidate.inputs || candidate.inputs.length === 0) continue
            
            const inputNames = candidate.inputs.map(input => input.name || input.id).filter(Boolean)
            const matchCount = formDataKeys.filter(key => inputNames.includes(key)).length
            
            if (matchCount > maxMatchCount) {
                maxMatchCount = matchCount
                bestMatch = candidate
            }
        }
        
        return maxMatchCount > 0 ? bestMatch : null
    }
    
    const processedNodes = mockData.graph.nodes.map(node => {
        let config = null
        
        if (node.data?.definition_id) {
            config = nodeTypeConfigs.value.find(c => c.id === node.data.definition_id)
        }
        if (!config) {
            config = nodeTypeConfigs.value.find(c => c.id === node.type)
        }
        if (!config && node.data?.form_data) {
            config = findNodeConfigByFormData(node.data.form_data, node.type)
        }
        if (!config) {
            config = nodeTypeConfigs.value.find(c => c.type === node.type)
        }
        
        if (!config) {
            const fallbackConfig = {
                id: node.type,
                name: node.data?.definition_id || node.type,
                type: node.type,
                description: '节点配置未找到',
                inputs: [],
                handles: []
            }
            config = fallbackConfig
        }
        
        const nodeData = {
            config: config,
            socketTypeConfigs: socketTypeConfigs.value,
            executionStatus: mockData.node_execution_status[node.id] || null
        }
        
        if (config.inputs) {
            config.inputs.forEach(input => {
                const formDataValue = node.data.form_data?.[input.name]
                nodeData[input.id] = normalizeDefaultValue(input.type, formDataValue)
            })
        }
        
        return {
            id: node.id,
            type: config.id,
            position: node.position,
            data: nodeData,
            selected: false
        }
    })
    
    const processedEdges = mockData.graph.edges.map(edge => {
        const sourceNode = processedNodes.find(n => n.id === edge.source)
        const targetNode = processedNodes.find(n => n.id === edge.target)
        
        let edgeColor = '#909399'
        let finalSourceHandle = edge.sourceHandle || null
        let finalTargetHandle = edge.targetHandle || null
        
        if (sourceNode && sourceNode.data?.config?.handles) {
            let sourceHandle = sourceNode.data.config.handles.find(h => h.id === edge.sourceHandle)
            
            if (!sourceHandle && targetNode && targetNode.data?.config?.handles) {
                const targetHandle = targetNode.data.config.handles.find(h => h.id === edge.targetHandle)
                if (targetHandle) {
                    sourceHandle = sourceNode.data.config.handles.find(h => 
                        h.socket_type === targetHandle.socket_type && h.position === 'right'
                    )
                    if (sourceHandle) {
                        finalSourceHandle = sourceHandle.id
                    }
                }
            }
            
            if (sourceHandle) {
                edgeColor = getEdgeColor(sourceHandle.socket_type, socketTypeConfigs.value)
            }
        }
        
        if (targetNode && targetNode.data?.config?.handles) {
            let targetHandle = targetNode.data.config.handles.find(h => h.id === edge.targetHandle)
            if (!targetHandle && sourceNode && sourceNode.data?.config?.handles) {
                const sourceHandle = sourceNode.data.config.handles.find(h => h.id === finalSourceHandle)
                if (sourceHandle) {
                    targetHandle = targetNode.data.config.handles.find(h => 
                        h.socket_type === sourceHandle.socket_type && h.position === 'left'
                    )
                    if (targetHandle) {
                        finalTargetHandle = targetHandle.id
                    }
                }
            }
        }
        
        return {
            id: edge.id,
            source: edge.source,
            sourceHandle: finalSourceHandle,
            target: edge.target,
            targetHandle: finalTargetHandle,
            style: {
                stroke: edgeColor,
                strokeWidth: 3
            }
        }
    })
    
    elements.value = [...processedNodes, ...processedEdges]
    
    if (mockData.graph.viewport) {
        setViewport(mockData.graph.viewport)
    } else {
        setTimeout(() => {
            fitView()
        }, 100)
    }
}

let pollingInterval = null

const startPolling = () => {
    if (pollingInterval) return
    
    pollingInterval = setInterval(() => {
        if (document.hidden) return
        
        const mockUpdate = {
            progress: Math.min(actionData.value.progress + Math.random() * 2, 100),
            node_execution_status: { ...actionData.value.node_execution_status }
        }
        
        Object.keys(mockUpdate.node_execution_status).forEach(nodeId => {
            const status = mockUpdate.node_execution_status[nodeId]
            if (status.status === 'running') {
                status.progress = Math.min(status.progress + Math.random() * 3, 100)
                if (status.progress >= 100) {
                    status.status = 'completed'
                    status.endTime = new Date().toISOString()
                }
            }
        })
        
        actionData.value.progress = mockUpdate.progress
        actionData.value.node_execution_status = mockUpdate.node_execution_status
        
        elements.value.forEach(el => {
            if (el.id && !el.source && mockUpdate.node_execution_status[el.id] && el.data) {
                el.data.executionStatus = mockUpdate.node_execution_status[el.id]
            }
        })
    }, 5000)
}

const stopPolling = () => {
    if (pollingInterval) {
        clearInterval(pollingInterval)
        pollingInterval = null
    }
}

const handleVisibilityChange = () => {
    if (document.hidden) {
        stopPolling()
    } else {
        startPolling()
    }
}

watch(selectedNodeId, (newId) => {
    elements.value.forEach(el => {
        if (el.id && !el.source) {
            el.selected = el.id === newId
        }
    })
})

onMounted(async () => {
    await fetchNodeConfigs()
    if (nodeTypeConfigs.value.length > 0) {
        loadActionData()
        startPolling()
    } else {
        ElMessage.error('节点配置加载失败，请刷新页面重试')
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('mousemove', onRightResize)
    window.removeEventListener('mouseup', stopRightResize)
})
</script>

<style scoped>
:deep(.vue-flow__node) {
    cursor: pointer;
}
</style>

