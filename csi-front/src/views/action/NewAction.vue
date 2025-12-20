<template>
    <div class="h-screen flex flex-col bg-white">
        <Header />

        <div class="px-5 py-3 bg-white border-b border-gray-200 flex items-center">
            <!-- 返回上一级页面 -->
            <el-button type="primary" link @click="$router.back()" class="mb-0!">
                <template #icon>
                    <Icon icon="mdi:arrow-left" />
                </template>
                返回
            </el-button>

            <!-- 标题 -->
            <span class="text-xl font-bold text-gray-800 ml-4">创建标准行动</span>
        </div>

        <div class="flex-1 flex overflow-hidden">
            <!-- 左侧边栏 -->
            <div 
                class="bg-white flex flex-col border-r border-white relative shrink-0 group"
                :style="{ width: sidebarWidth + 'px' }"
            >
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">节点列表</h3>
                </div>
                <div class="flex flex-col select-none overflow-y-auto flex-1 overflow-x-hidden min-h-0" v-loading="loadingNodeConfigs" :element-loading-text="'加载节点配置中...'">
                    <div 
                        v-for="category in nodeCategories" 
                        :key="category.type"
                        class="border-b border-gray-100 last:border-b-0"
                    >
                        <div 
                            class="px-4 py-2 bg-gray-50 hover:bg-gray-100 cursor-pointer flex items-center justify-between transition-colors"
                            @click="toggleCategory(category.type)"
                        >
                            <div class="flex items-center gap-2">
                                <Icon 
                                    :icon="categoryCollapsed[category.type] === true ? 'mdi:chevron-right' : 'mdi:chevron-down'" 
                                    class="text-gray-500 text-sm transition-transform"
                                />
                                <span class="text-sm font-medium text-gray-700">{{ category.label }}</span>
                                <span class="text-xs text-gray-400">({{ category.nodes.length }})</span>
                            </div>
                        </div>
                        <div 
                            v-show="!(categoryCollapsed[category.type] === true)"
                            class="p-4 flex flex-col gap-3"
                        >
                            <el-tooltip
                                v-for="node in category.nodes" 
                                :key="node.key"
                                :content="node.description"
                                placement="right"
                                :show-after="300"
                            >
                                <div 
                                    class="cursor-grab active:cursor-grabbing origin-top-left transition-transform duration-75"
                                    draggable="true" 
                                    @dragstart="onDragStart($event, node.key)"
                                    :style="getNodeWrapperStyle"
                                >
                                    <div class="pointer-events-none w-full">
                                        
                                        <div v-if="isCompact" class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm hover:border-blue-400 transition-colors">
                                            <div class="w-1.5 h-3 rounded-full mr-2" :style="{ backgroundColor: node.color || '#909399' }"></div>
                                            <span class="text-sm text-gray-700 font-medium truncate">{{ node.label }}</span>
                                        </div>

                                        <component 
                                            v-else
                                            :is="node.component"
                                            :id="`sidebar-${node.key}-preview`" 
                                            :data="node.data" 
                                            :show-handle="false"
                                        />
                                    </div>
                                </div>
                            </el-tooltip>
                        </div>
                    </div>
                </div>

                <div 
                    class="absolute top-0 bottom-0 -right-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startLeftResize"
                >
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors" :class="{ 'bg-blue-600!': isResizing }"></div>
                </div>
            </div>

            <!-- 流程图 -->
            <div class="flex-1 h-full relative bg-gray-50" @drop="onDrop" @dragover="onDragOver">
                <VueFlow 
                    v-model="elements" 
                    :node-types="nodeTypes"
                    :default-zoom="1.5" 
                    :min-zoom="0.2" 
                    :max-zoom="4" 
                    fit-view-on-init
                    class="h-full w-full"
                >
                    <Background pattern-color="#aaa" :gap="18" />
                    <Controls />
                </VueFlow>
            </div>

            <!-- 右侧边栏 -->
            <div 
                class="bg-white flex flex-col border-l border-gray-200 relative shrink-0 group"
                :style="{ width: rightSidebarWidth + 'px' }"
            >
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">行动属性</h3>
                </div>
                <div class="p-4 flex flex-col gap-4 flex-1 overflow-hidden">
                    <!-- 标题输入框 -->
                    <div class="flex flex-col gap-2 shrink-0">
                        <label class="text-sm font-medium text-gray-700">标题</label>
                        <el-input
                            v-model="actionTitle"
                            placeholder="请输入行动标题"
                            clearable
                        />
                    </div>

                    <!-- 详细信息输入框 -->
                    <div class="flex flex-col gap-2 flex-1 min-h-0">
                        <label class="text-sm font-medium text-gray-700">详细信息</label>
                        <el-input
                            v-model="actionDescription"
                            type="textarea"
                            placeholder="请输入行动详细信息"
                            resize="vertical"
                            class="flex-1"
                        />
                    </div>

                    <!-- TODO: 期限、资源配置设置 -->
                </div>

                <!-- 底部保存按钮 -->
                <div class="p-4 border-t border-gray-200 shrink-0">
                <el-button 
                        type="primary" 
                        class="w-full"
                        @click="handleSaveAction"
                    >
                        保存行动
                    </el-button>
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
    </div>
</template>

<script setup>
import { ref, computed, onUnmounted, onMounted, markRaw } from 'vue'
import { Icon } from '@iconify/vue'
import Header from "@/components/Header.vue"
import { VueFlow, useVueFlow } from "@vue-flow/core"
import { Background } from "@vue-flow/background"
import { Controls } from "@vue-flow/controls"
import GenericNode from "@/components/action/nodes/GenericNode.vue"
import { actionApi } from '@/api/action'
import { ElMessage } from 'element-plus'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

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

const INPUT_TYPE_DEFAULTS = {
    'int': null,
    'string': '',
    'textarea': '',
    'select': null,
    'checkbox': false,
    'checkbox-group': [],
    'radio-group': null,
    'boolean': false,
    'datetime': null,
    'tags': []
}

const normalizeDefaultValue = (type, value) => {
    if (value === undefined || value === null) {
        return INPUT_TYPE_DEFAULTS[type] ?? null
    }
    
    switch (type) {
        case 'int':
            const numValue = Number(value)
            return isNaN(numValue) ? null : numValue
            
        case 'boolean':
        case 'checkbox':
            return Boolean(value)
            
        case 'tags':
        case 'checkbox-group':
            return Array.isArray(value) ? value : []
            
        case 'string':
        case 'textarea':
        case 'select':
        case 'radio-group':
        case 'datetime':
            return value
            
        default:
            return value
    }
}

const socketTypeConfigs = ref([
    // 基本数据类型
    {
        socket_type: 'basic_type_boolean',
        color: '#409eff',
        custom_style: {}
    },
    // 扩展数据类型
    {
        socket_type: 'platform',
        color: '#409eff',
        custom_style: {}
    },
    {
        socket_type: 'keywords',
        color: '#f56c6c',
        custom_style: {}
    },
    {
        socket_type: 'crawler_results',
        color: '#67c23a',
        custom_style: {}
    },
    {
        socket_type: 'generic_data',
        color: '#ff69b4',
        custom_style: {}
    },
    {
        socket_type: 'rabbitmq_data',
        color: '#ff9800',
        custom_style: {}
    },
    {
        socket_type: 'es_data',
        color: '#722ed1',
        custom_style: {}
    },
    {
        socket_type: 'mongo_data',
        color: '#13c2c2',
        custom_style: {}
    }
])

const getDefaultData = (config) => {
    const data = {
        config: config,
        socketTypeConfigs: socketTypeConfigs.value
    }
    
    if (config.inputs) {
        config.inputs.forEach(input => {
            data[input.id] = normalizeDefaultValue(input.type, input.default)
        })
    }
    
    return data
}

const getNodeColor = (config) => {
    if (config.handles && config.handles.length > 0) {
        const firstHandle = config.handles[0]
        const socketConfig = socketTypeConfigs.value.find(
            s => s.socket_type === firstHandle.socket_type
        )
        return socketConfig?.color || '#909399'
    }
    return '#909399'
}

const sidebarNodes = computed(() => {
    return nodeTypeConfigs.value.map(config => ({
        key: config.id,
        label: config.name,
        type: config.type,
        color: getNodeColor(config),
        description: config.description,
        component: markRaw(GenericNode),
        data: getDefaultData(config)
    }))
})

const nodeCategories = computed(() => {
    const categories = {}
    
    sidebarNodes.value.forEach(node => {
        if (!categories[node.type]) {
            categories[node.type] = {
                type: node.type,
                label: node.type,
                nodes: []
            }
        }
        categories[node.type].nodes.push(node)
    })
    
    return Object.values(categories)
})

const categoryCollapsed = ref({})

const toggleCategory = (type) => {
    categoryCollapsed.value[type] = !(categoryCollapsed.value[type] === true)
}

const nodeTypes = computed(() => {
    const types = {}
    nodeTypeConfigs.value.forEach(config => {
        types[config.id] = markRaw(GenericNode)
    })
    return types
})

const elements = ref([])
const { addEdges, addNodes, onConnect, screenToFlowCoordinate, onNodesInitialized, updateNode, isValidConnection, getNodes, getEdges, getViewport } = useVueFlow()

isValidConnection.value = (connection) => {
    const sourceNode = elements.value.find(el => el.id === connection.source)
    const targetNode = elements.value.find(el => el.id === connection.target)
    
    if (!sourceNode || !targetNode) return false
    
    const sourceConfig = nodeTypeConfigs.value.find(c => c.id === sourceNode.type)
    const targetConfig = nodeTypeConfigs.value.find(c => c.id === targetNode.type)
    
    if (!sourceConfig || !targetConfig) return false
    
    const sourceHandle = sourceConfig.handles.find(h => h.id === connection.sourceHandle)
    const targetHandle = targetConfig.handles.find(h => h.id === connection.targetHandle)
    
    if (!sourceHandle || !targetHandle) return false
    
    // 如果源接口或目标接口是 generic_data 类型，允许连接到任意类型
    if (sourceHandle.socket_type === 'generic_data' || targetHandle.socket_type === 'generic_data') {
        return true
    }
    
    // 如果目标接口的 allowed_socket_types 包含 generic_data，允许任意类型连接
    if (targetHandle.allowed_socket_types.includes('generic_data')) {
        return true
    }
    
    return targetHandle.allowed_socket_types.includes(sourceHandle.socket_type)
}

const createNodeFromConfig = (configId, position) => {
    const config = nodeTypeConfigs.value.find(c => c.id === configId)
    if (!config) return null
    
    return {
        id: `node-${Date.now()}`,
        type: config.id,
        position: position,
        data: getDefaultData(config)
    }
}

// 左侧边栏拖拽与样式逻辑
const sidebarWidth = ref(400)
const isResizing = ref(false)
const minSidebarWidth = 150
const maxSidebarWidth = 600

// 右侧边栏拖拽与样式逻辑
const rightSidebarWidth = ref(400)
const isRightResizing = ref(false)
const minRightSidebarWidth = 300
const maxRightSidebarWidth = 800

// 行动表单数据
const actionTitle = ref('')
const actionDescription = ref('')

// 配置常量
const BASE_NODE_WIDTH = 300   // 节点组件的最小设计宽度
const SIDEBAR_PADDING = 32    // p-4 * 2
const COMPACT_THRESHOLD = 240 // 低于此宽度切换为标题模式

// 是否处于紧凑模式
const isCompact = computed(() => sidebarWidth.value < COMPACT_THRESHOLD)

// 动态计算节点容器样式
const getNodeWrapperStyle = computed(() => {
    if (isCompact.value) {
        return { width: '100%', marginBottom: '0px' }
    }

    const availableWidth = sidebarWidth.value - SIDEBAR_PADDING
    
    //节点拉伸
    if (availableWidth >= BASE_NODE_WIDTH) {
        return {
            width: '100%', // 强制填满容器，配合内部组件的 block 属性实现拉伸
            transform: 'scale(1)',
            marginBottom: '0px'
        }
    }

    // 侧边栏介于 240px - 300px 之间需要缩放
    // 强制容器宽度为 300px 并整体缩小
    const scale = availableWidth / BASE_NODE_WIDTH
    const marginBottom = `-${(1 - scale) * 120}px` // 补偿缩放产生的底部空白

    return {
        width: `${BASE_NODE_WIDTH}px`, // 锁定渲染宽度，防止被压扁
        transform: `scale(${scale})`,
        marginBottom: marginBottom
    }
})

// 拖拽调整大小逻辑
const startLeftResize = () => {
    isResizing.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onLeftResize)
    window.addEventListener('mouseup', stopLeftResize)
}

const onLeftResize = (event) => {
    if (!isResizing.value) return
    let newWidth = event.clientX
    if (newWidth < minSidebarWidth) newWidth = minSidebarWidth
    if (newWidth > maxSidebarWidth) newWidth = maxSidebarWidth
    sidebarWidth.value = newWidth
}

const stopLeftResize = () => {
    isResizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onLeftResize)
    window.removeEventListener('mouseup', stopLeftResize)
}

// 右侧边栏调整大小逻辑
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

onMounted(() => {
    fetchNodeConfigs()
})

onUnmounted(() => {
    window.removeEventListener('mousemove', onLeftResize)
    window.removeEventListener('mouseup', stopLeftResize)
    window.removeEventListener('mousemove', onRightResize)
    window.removeEventListener('mouseup', stopRightResize)
})

// 流程图逻辑
onConnect((params) => {
    const sourceNode = elements.value.find(el => el.id === params.source)
    if (!sourceNode) {
        addEdges(params)
        return
    }
    
    const sourceConfig = nodeTypeConfigs.value.find(c => c.id === sourceNode.type)
    if (!sourceConfig) {
        addEdges(params)
        return
    }
    
    const sourceHandle = sourceConfig.handles.find(h => h.id === params.sourceHandle)
    if (!sourceHandle) {
        addEdges(params)
        return
    }
    
    const socketConfig = socketTypeConfigs.value.find(s => s.socket_type === sourceHandle.socket_type)
    const edgeColor = socketConfig?.color || '#909399'
    
    const edgeWithStyle = {
        ...params,
        style: {
            stroke: edgeColor,
            strokeWidth: 3
        }
    }
    
    addEdges([edgeWithStyle])
})

const onDragStart = (event, nodeType) => {
    if (event.dataTransfer) {
        event.dataTransfer.setData('application/vueflow', nodeType)
        event.dataTransfer.effectAllowed = 'move'
    }
}

const onDragOver = (event) => {
    event.preventDefault()
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

const onDrop = (event) => {
    event.preventDefault()
    const nodeKey = event.dataTransfer?.getData('application/vueflow')
    if (nodeKey) {
        const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
        const newNode = createNodeFromConfig(nodeKey, position)
        if (!newNode) return
        const { off } = onNodesInitialized(() => {
            updateNode(newNode.id, (node) => ({
                position: { 
                    x: node.position.x - node.dimensions.width / 2, 
                    y: node.position.y - node.dimensions.height / 2 
                },
            }))
            off()
        })
        addNodes([newNode])
    }
}

const handleSaveAction = () => {
    if (!actionTitle.value || actionTitle.value.trim() === '') {
        ElMessage.error('请输入行动标题')
        return
    }
    
    const nodes = getNodes.value
    const edges = getEdges.value
    const viewport = getViewport()
    
    if (!nodes || nodes.length === 0) {
        ElMessage.error('请至少添加一个节点')
        return
    }
    
    const processedNodes = nodes.map(node => {
        const config = node.data?.config
        if (!config) {
            return null
        }
        
        const formData = {}
        if (config.inputs && config.inputs.length > 0) {
            config.inputs.forEach(input => {
                formData[input.name] = node.data[input.id]
            })
        }
        
        return {
            id: node.id,
            type: config.type,
            position: {
                x: node.position.x,
                y: node.position.y
            },
            data: {
                definition_id: config.id,
                version: config.version,
                form_data: formData
            }
        }
    }).filter(node => node !== null)
    
    const processedEdges = edges.map(edge => ({
        id: edge.id,
        source: edge.source,
        sourceHandle: edge.sourceHandle,
        target: edge.target,
        targetHandle: edge.targetHandle
    }))
    
    const actionData = {
        name: actionTitle.value,
        description: actionDescription.value || '',
        implementation_period: 3600,
        resource: {},
        graph: {
            nodes: processedNodes,
            edges: processedEdges,
            viewport: {
                x: viewport.x,
                y: viewport.y,
                zoom: viewport.zoom
            }
        }
    }
    
    console.log('===== 保存行动数据 =====')
    console.log(JSON.stringify(actionData, null, 2))
    console.log('=======================')
    
    ElMessage.success('数据已构造完成，请在控制台查看')
}
</script>