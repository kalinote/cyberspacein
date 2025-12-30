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
                <div v-if="loadingNodeConfigs || loadingActionData" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                    <div class="text-center">
                        <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                        <p class="text-gray-600">{{ loadingNodeConfigs ? '加载节点配置中...' : '加载行动数据中...' }}</p>
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
                <div v-if="elements.length === 0 && !loadingNodeConfigs && !loadingActionData" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
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
                                <label class="text-xs text-gray-500">执行期限</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDuration(actionData.implementationPeriod) }}</p>
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
                            <div v-if="actionData.duration">
                                <label class="text-xs text-gray-500">执行时间</label>
                                <p class="text-sm text-gray-700 mt-1">{{ formatDuration(actionData.duration) }}</p>
                            </div>
                            <div v-if="executingNodes.length > 0">
                                <label class="text-xs text-gray-500">当前执行节点</label>
                                <p class="text-sm mt-1">
                                    <span
                                        v-for="(nodeId, index) in executingNodes"
                                        :key="nodeId"
                                    >
                                        <span
                                            class="text-blue-600 cursor-pointer hover:text-blue-800"
                                            @click="scrollToNode(nodeId)"
                                        >
                                            {{ getNodeName(nodeId) }}
                                        </span>
                                        <span v-if="index < executingNodes.length - 1">, </span>
                                    </span>
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
                                    <p class="text-sm font-medium text-gray-900 mt-1">{{ getNodeName(selectedNodeId) }}</p>
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
                        <div v-if="selectedNodeDetail.finished || selectedNodeDetail.errorMessage">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3">执行结果</h4>
                            <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <div v-if="selectedNodeDetail.errorMessage" class="text-sm text-red-600">
                                    <Icon icon="mdi:alert-circle" class="inline mr-2" />
                                    <span class="font-medium">错误信息：</span>
                                    <p class="mt-1 whitespace-pre-wrap">{{ selectedNodeDetail.errorMessage }}</p>
                                </div>
                                <div v-else-if="selectedNodeDetail.finished" class="text-sm text-green-600">
                                    <Icon icon="mdi:check-circle" class="inline mr-2" />
                                    <span class="font-medium">执行成功</span>
                                </div>
                            </div>
                        </div>

                        <!-- 配置参数 -->
                        <div v-if="selectedNodeConfigs">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center justify-between">
                                <span>配置参数</span>
                                <el-button type="primary" link size="small" @click="toggleConfigsCollapsed">
                                    <template #icon>
                                        <Icon :icon="configsCollapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'" />
                                    </template>
                                </el-button>
                            </h4>
                            <div v-show="!configsCollapsed" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <pre class="text-xs overflow-x-auto"><code class="language-json" v-html="highlightJSON(selectedNodeConfigs)"></code></pre>
                            </div>
                        </div>

                        <!-- 输入数据 -->
                        <div v-if="selectedNodeDetail.inputs">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center justify-between">
                                <span>输入数据</span>
                                <el-button type="primary" link size="small" @click="toggleInputsCollapsed">
                                    <template #icon>
                                        <Icon :icon="inputsCollapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'" />
                                    </template>
                                </el-button>
                            </h4>
                            <div v-show="!inputsCollapsed" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <pre class="text-xs overflow-x-auto"><code class="language-json" v-html="highlightJSON(selectedNodeDetail.inputs)"></code></pre>
                            </div>
                        </div>

                        <!-- 输出数据 -->
                        <div v-if="selectedNodeDetail.outputs">
                            <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center justify-between">
                                <span>输出数据</span>
                                <el-button type="primary" link size="small" @click="toggleoutputsCollapsed">
                                    <template #icon>
                                        <Icon :icon="outputsCollapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'" />
                                    </template>
                                </el-button>
                            </h4>
                            <div v-show="!outputsCollapsed" class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <pre class="text-xs overflow-x-auto"><code class="language-json" v-html="highlightJSON(selectedNodeDetail.outputs)"></code></pre>
                            </div>
                        </div>

                        <!-- 执行日志 -->
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800 mb-3">执行日志</h4>
                            <div class="bg-gray-50 rounded-lg border border-gray-200 max-h-48 overflow-y-auto">
                                <div v-if="isLoadingNodeLogs" class="px-4 py-8 text-center text-sm text-gray-400">
                                    <Icon icon="mdi:loading" class="text-2xl text-blue-500 animate-spin mb-2" />
                                    <p>加载日志中...</p>
                                </div>
                                <template v-else>
                                    <div 
                                        v-for="(log, index) in selectedNodeLogs" 
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
                                    <div v-if="!selectedNodeLogs || selectedNodeLogs.length === 0" class="px-4 py-8 text-center text-sm text-gray-400">
                                        暂无日志
                                    </div>
                                </template>
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
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import 'highlight.js/styles/github.css'

hljs.registerLanguage('json', json)

import {
  normalizeDefaultValue,
  getDefaultData,
  formatDateTime,
  formatDuration,
  formatLogTime,
  getStatusText,
  getStatusTagType,
  getLogLevelClass,
  getLogLevelTextClass
} from '@/utils/action'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const route = useRoute()
const actionId = computed(() => route.params.id)

const nodeTypeConfigs = ref([])
const loadingNodeConfigs = ref(false)
const loadingActionData = ref(false)

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
                class: [
                    isSelected.value ? 'ring-2 ring-blue-500 ring-offset-2' : '',
                    'relative'
                ].filter(Boolean).join(' '),
            }, [
                h(GenericNode, {
                    id: props.id,
                    data: props.data,
                    disabled: true,
                    showHandle: true
                }),
                nodeStatus.value === 'running' ? h('div', {
                    class: 'absolute bg-gradient-to-r from-green-500 via-emerald-400 to-green-500 transition-all duration-300 z-[1]',
                    style: { 
                        top: '12px',
                        left: '12px',
                        height: '2px',
                        width: `calc(${progress.value}% - 24px)`,
                        borderRadius: '2px'
                    }
                }) : null
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
const { setViewport, getNodes, fitView, getViewport } = useVueFlow()

const actionData = ref({
    id: '',
    name: '',
    description: '',
    status: 'pending',
    progress: 0,
    startTime: null,
    endTime: null,
    implementationPeriod: 3600,
    resource: {},
    graph: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 }
    },
    node_details: {}
})

const selectedNodeId = ref(null)
const nodeDetailCollapsed = ref(false)
const configsCollapsed = ref(false)
const inputsCollapsed = ref(false)
const outputsCollapsed = ref(false)

const nodeLogs = ref({})
const loadingNodeLogs = ref({})
const loadedNodeLogs = ref(new Set())

const nodeDetailExpanded = computed(() => {
    return selectedNodeId.value !== null && !nodeDetailCollapsed.value
})

const selectedNodeDetail = computed(() => {
    if (!selectedNodeId.value) return null
    return actionData.value.node_details[selectedNodeId.value] || null
})

const selectedNodeConfigs = computed(() => {
    if (!selectedNodeId.value || !actionData.value.graph?.nodes) return null
    const node = actionData.value.graph.nodes.find(n => n.id === selectedNodeId.value)
    return node?.data?.form_data || null
})

const selectedNodeLogs = computed(() => {
    if (!selectedNodeId.value) return []
    return nodeLogs.value[selectedNodeId.value] || []
})

const isLoadingNodeLogs = computed(() => {
    if (!selectedNodeId.value) return false
    return loadingNodeLogs.value[selectedNodeId.value] || false
})

const executingNodes = computed(() => {
    if (!actionData.value.node_details) return []
    return Object.keys(actionData.value.node_details)
        .filter(nodeId => actionData.value.node_details[nodeId]?.status === 'running')
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

const fetchNodeLogs = async (nodeId) => {
    if (loadedNodeLogs.value.has(nodeId)) {
        return
    }
    
    loadingNodeLogs.value[nodeId] = true
    
    try {
        // TODO: 后续将通过 API 接口获取节点日志
        // const response = await actionApi.getNodeLogs(actionId.value, nodeId)
        // if (response.code === 0) {
        //     nodeLogs.value[nodeId] = response.data || []
        // }
        
        // 生成模拟日志数据
        const startTime = actionData.value.node_details[nodeId]?.startTime 
            ? new Date(actionData.value.node_details[nodeId].startTime) 
            : new Date()
        
        const mockLogs = []
        
        mockLogs.push(
                { timestamp: new Date(startTime.getTime() + 0 * 1000).toISOString(), level: 'fatal', message: '日志功能尚未完成' },
                { timestamp: new Date(startTime.getTime() + 1 * 1000).toISOString(), level: 'info', message: '这是一条普通日志' },
                { timestamp: new Date(startTime.getTime() + 3 * 1000).toISOString(), level: 'warning', message: '这是一条警告日志' },
                { timestamp: new Date(startTime.getTime() + 6 * 1000).toISOString(), level: 'error', message: '这是一条错误日志' },
                { timestamp: new Date(startTime.getTime() + 10 * 1000).toISOString(), level: 'fatal', message: '这是一条致命日志' },
                { timestamp: new Date(startTime.getTime() + 30 * 1000).toISOString(), level: 'debug', message: '这是一条调试输出' }
            )
        
        nodeLogs.value[nodeId] = mockLogs
        loadedNodeLogs.value.add(nodeId)
    } catch (error) {
        console.error('获取节点日志失败:', error)
        nodeLogs.value[nodeId] = []
    } finally {
        loadingNodeLogs.value[nodeId] = false
    }
}

const handleNodeClick = (event) => {
    const nodeId = event.node.id
    selectedNodeId.value = nodeId
    nodeDetailCollapsed.value = false
    
    if (!loadedNodeLogs.value.has(nodeId)) {
        fetchNodeLogs(nodeId)
    }
}

const handlePaneClick = () => {
    selectedNodeId.value = null
}

const collapseNodeDetail = () => {
    nodeDetailCollapsed.value = !nodeDetailCollapsed.value
}

const toggleConfigsCollapsed = () => {
    configsCollapsed.value = !configsCollapsed.value
}

const toggleInputsCollapsed = () => {
    inputsCollapsed.value = !inputsCollapsed.value
}

const toggleoutputsCollapsed = () => {
    outputsCollapsed.value = !outputsCollapsed.value
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
    const node = elements.value.find(el => el.id === nodeId && !el.source)
    return node?.data?.config?.name || nodeId
}

const highlightJSON = (obj) => {
    if (!obj) return '无'
    try {
        const jsonString = JSON.stringify(obj, null, 2)
        const highlighted = hljs.highlight(jsonString, { language: 'json' })
        return highlighted.value
    } catch {
        return String(obj)
    }
}


const loadActionData = async () => {
    if (nodeTypeConfigs.value.length === 0) {
        return
    }
    
    loadingActionData.value = true
    try {
        const response = await actionApi.getActionDetail(actionId.value)
        if (response.code !== 0) {
            ElMessage.error(`获取行动详情失败: ${response.message || '未知错误'}`)
            return
        }
        
        const apiData = response.data
        if (!apiData) {
            ElMessage.error('获取行动详情失败: 数据为空')
            return
        }
        
        const transformedData = {
            id: apiData.id,
            name: apiData.name || '',
            description: apiData.description || '',
            status: apiData.status || 'pending',
            duration: apiData.duration || 0,
            progress: apiData.progress || 0,
            startTime: apiData.start_at || null,
            endTime: apiData.finished_at || null,
            implementationPeriod: apiData.implementation_period || 3600,
            resource: apiData.resource || {},
            graph: apiData.graph || {
                nodes: [],
                edges: [],
                viewport: { x: 0, y: 0, zoom: 1 }
            },
            node_details: Object.fromEntries(
                Object.entries(apiData.node_details || {}).map(([nodeId, detail]) => [
                    nodeId,
                    {
                        ...detail,
                        startTime: detail.start_at || null,
                        endTime: detail.finished_at || null,
                        errorMessage: detail.error_message || null,
                        finished: detail.status === 'completed' || detail.status === 'failed'
                    }
                ])
            )
        }
        
        actionData.value = transformedData
    
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
    
    const processedNodes = transformedData.graph.nodes.map(node => {
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
        
        const nodeData = getDefaultData(config)
        const nodeDetail = transformedData.node_details[node.id]
        if (nodeDetail) {
            nodeData.executionStatus = {
                status: nodeDetail.status,
                progress: nodeDetail.progress || 0,
                startTime: nodeDetail.startTime,
                endTime: nodeDetail.endTime
            }
        } else {
            nodeData.executionStatus = null
        }
        
        if (config.inputs) {
            config.inputs.forEach(input => {
                const formDataValue = node.data.form_data?.[input.name]
                if (formDataValue !== undefined && formDataValue !== null) {
                    nodeData[input.id] = normalizeDefaultValue(input.type, formDataValue)
                }
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
    
    const processedEdges = transformedData.graph.edges.map(edge => {
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
                        h.handle_name === targetHandle.handle_name && h.position === 'right'
                    )
                    if (sourceHandle) {
                        finalSourceHandle = sourceHandle.id
                    }
                }
            }
            
            if (sourceHandle) {
                edgeColor = sourceHandle.color || '#909399'
            }
        }
        
        if (targetNode && targetNode.data?.config?.handles) {
            let targetHandle = targetNode.data.config.handles.find(h => h.id === edge.targetHandle)
            if (!targetHandle && sourceNode && sourceNode.data?.config?.handles) {
                const sourceHandle = sourceNode.data.config.handles.find(h => h.id === finalSourceHandle)
                if (sourceHandle) {
                    targetHandle = targetNode.data.config.handles.find(h => 
                        h.handle_name === sourceHandle.handle_name && h.position === 'left'
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
    
    if (transformedData.graph.viewport) {
        setViewport(transformedData.graph.viewport)
    } else {
        setTimeout(() => {
            fitView()
        }, 100)
    }
    } catch (error) {
        console.error('获取行动详情失败:', error)
        ElMessage.error('获取行动详情失败，请稍后重试')
    } finally {
        loadingActionData.value = false
    }
}

const updateActionData = async () => {
    if (nodeTypeConfigs.value.length === 0) {
        return
    }
    
    try {
        const response = await actionApi.getActionDetail(actionId.value)
        if (response.code !== 0) {
            return
        }
        
        const apiData = response.data
        if (!apiData) {
            return
        }
        
        const transformedNodeDetails = Object.fromEntries(
            Object.entries(apiData.node_details || {}).map(([nodeId, detail]) => [
                nodeId,
                {
                    ...detail,
                    startTime: detail.start_at || null,
                    endTime: detail.finished_at || null,
                    errorMessage: detail.error_message || null,
                    finished: detail.status === 'completed' || detail.status === 'failed'
                }
            ])
        )
        
        actionData.value.status = apiData.status || 'pending'
        actionData.value.progress = apiData.progress || 0
        actionData.value.duration = apiData.duration || 0
        actionData.value.startTime = apiData.start_at || null
        actionData.value.endTime = apiData.finished_at || null
        actionData.value.node_details = transformedNodeDetails
        
        elements.value.forEach(el => {
            if (el.id && !el.source && transformedNodeDetails[el.id] && el.data) {
                const nodeDetail = transformedNodeDetails[el.id]
                el.data.executionStatus = {
                    status: nodeDetail.status,
                    progress: nodeDetail.progress || 0,
                    startTime: nodeDetail.startTime,
                    endTime: nodeDetail.endTime
                }
            }
        })
    } catch (error) {
        console.error('更新行动详情失败:', error)
    }
}

let pollingInterval = null

const startPolling = () => {
    if (pollingInterval) return
    
    pollingInterval = setInterval(async () => {
        if (document.hidden) return
        if (loadingActionData.value) return
        
        await updateActionData()
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
        await loadActionData()
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

