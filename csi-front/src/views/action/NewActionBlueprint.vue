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
            <span class="text-xl font-bold text-gray-800 ml-4">创建标准行动蓝图</span>
        </div>

        <div class="flex-1 flex overflow-hidden">
            <!-- 左侧边栏 -->
            <div class="bg-white flex flex-col border-r border-white relative shrink-0 group"
                :style="{ width: sidebarWidth + 'px' }">
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">节点列表</h3>
                </div>
                <div class="flex flex-col select-none overflow-y-auto flex-1 overflow-x-hidden min-h-0"
                    v-loading="loadingNodeConfigs" :element-loading-text="'加载节点配置中...'">
                    <div v-for="category in nodeCategories" :key="category.type"
                        class="border-b border-gray-100 last:border-b-0">
                        <div class="px-4 py-2 bg-gray-50 hover:bg-gray-100 cursor-pointer flex items-center justify-between transition-colors"
                            @click="toggleCategory(category.type)">
                            <div class="flex items-center gap-2">
                                <Icon
                                    :icon="categoryCollapsed[category.type] === true ? 'mdi:chevron-right' : 'mdi:chevron-down'"
                                    class="text-gray-500 text-sm transition-transform" />
                                <span class="text-sm font-medium text-gray-700">{{ category.label }}</span>
                                <span class="text-xs text-gray-400">({{ category.nodes.length }})</span>
                            </div>
                        </div>
                        <div v-show="!(categoryCollapsed[category.type] === true)" class="p-4 flex flex-col gap-3">
                            <el-tooltip v-for="node in category.nodes" :key="node.key" :content="node.description"
                                placement="right" :show-after="300">
                                <div class="cursor-grab active:cursor-grabbing origin-top-left transition-transform duration-75"
                                    draggable="true" @dragstart="onDragStart($event, node.key)"
                                    :style="getNodeWrapperStyle">
                                    <div class="pointer-events-none w-full">
                                        <div v-if="isCompact"
                                            class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm hover:border-blue-400 transition-colors">
                                            <div class="w-1.5 h-3 rounded-full mr-2"
                                                :style="{ backgroundColor: node.color || '#909399' }"></div>
                                            <span class="text-sm text-gray-700 font-medium truncate">{{ node.label
                                                }}</span>
                                        </div>

                                        <component v-else :is="node.component" :id="`sidebar-${node.key}-preview`"
                                            :data="node.data" :show-handle="false" />
                                    </div>
                                </div>
                            </el-tooltip>
                        </div>
                    </div>
                </div>

                <div class="absolute top-0 bottom-0 -right-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startLeftResize">
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors"
                        :class="{ 'bg-blue-600!': isResizing }"></div>
                </div>
            </div>

            <!-- 流程图 -->
            <div class="flex-1 h-full relative bg-gray-50" @drop="onDrop" @dragover="onDragOver">
                <VueFlow v-model="elements" :node-types="nodeTypes" :default-zoom="1.5" :min-zoom="0.2" :max-zoom="4"
                    fit-view-on-init class="h-full w-full">
                    <Background pattern-color="#aaa" :gap="18" />
                    <Controls />
                </VueFlow>
            </div>

            <!-- 右侧边栏 -->
            <div class="bg-white flex flex-col border-l border-gray-200 relative shrink-0 group"
                :style="{ width: rightSidebarWidth + 'px' }">
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">行动属性</h3>
                </div>
                <el-form ref="actionFormRef" :model="actionForm" :rules="actionFormRules"
                    class="p-4 flex flex-col gap-4 flex-1 overflow-y-auto" label-width="auto" label-position="top">
                    <!-- 标题输入框 -->
                    <el-form-item prop="title" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">标题</span>
                        </template>
                        <el-input v-model="actionForm.title" placeholder="请输入行动标题" clearable />
                    </el-form-item>

                    <!-- 版本号输入框 -->
                    <el-form-item prop="version" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">版本号</span>
                        </template>
                        <el-input v-model="actionForm.version" placeholder="请输入版本号" clearable />
                    </el-form-item>

                    <!-- 执行期限输入框 -->
                    <el-form-item prop="implementation_period" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">执行期限(秒)</span>
                        </template>
                        <el-input-number v-model="actionForm.implementation_period" :min="1" placeholder="请输入执行期限" class="w-full" />
                    </el-form-item>

                    <!-- 详细信息输入框 -->
                    <el-form-item prop="description" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">详细信息</span>
                        </template>
                        <el-input v-model="actionForm.description" type="textarea" placeholder="请输入行动详细信息"
                            resize="vertical" :autosize="{ minRows: 3, maxRows: 10 }" />
                    </el-form-item>

                    <!-- 任务目标输入框 -->
                    <el-form-item prop="target" class="shrink-0 mb-0 -mt-2">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">任务目标</span>
                        </template>
                        <el-input v-model="actionForm.target" type="textarea" placeholder="请输入任务目标" resize="vertical"
                            :autosize="{ minRows: 3, maxRows: 10 }" />
                    </el-form-item>

                    <!-- TODO: 期限、资源配置设置 -->
                </el-form>

                <!-- 底部保存按钮 -->
                <div class="p-4 border-t border-gray-200 shrink-0">
                    <el-button type="primary" class="w-full" @click="handleSaveAction">
                        保存行动蓝图
                    </el-button>
                </div>

                <!-- 调整大小手柄 -->
                <div class="absolute top-0 bottom-0 -left-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startRightResize">
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors"
                        :class="{ 'bg-blue-600!': isRightResizing }"></div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from "@/components/Header.vue"
import { VueFlow, useVueFlow } from "@vue-flow/core"
import { Background } from "@vue-flow/background"
import { Controls } from "@vue-flow/controls"
import GenericNode from "@/components/action/nodes/GenericNode.vue"
import { actionApi } from '@/api/action'
import { ElMessage } from 'element-plus'
import {
    getDefaultData,
    getNodeColor
} from '@/utils/action'
import { useSidebarResize } from '@/utils/action/useSidebarResize'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const router = useRouter()

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

/**
 * 验证节点连接是否有效
 * 规则：
 * 1. source handle 只能连接 target handle
 * 2. 每个 target handle 只能接受一个上游连接
 * 3. 每个 source handle 可以连接多个下游 target handle
 * 4. handle 必须兼容（ID相同或在兼容列表中）
 */
isValidConnection.value = (connection) => {
    // 1. 基础验证：节点是否存在
    const sourceNode = elements.value.find(el => el.id === connection.source)
    const targetNode = elements.value.find(el => el.id === connection.target)

    if (!sourceNode || !targetNode) return false

    // 2. 获取节点配置
    const sourceConfig = nodeTypeConfigs.value.find(c => c.id === sourceNode.type)
    const targetConfig = nodeTypeConfigs.value.find(c => c.id === targetNode.type)

    if (!sourceConfig || !targetConfig) return false

    // 3. 获取 handle 配置
    const sourceHandle = sourceConfig.handles.find(h => h.id === connection.sourceHandle)
    const targetHandle = targetConfig.handles.find(h => h.id === connection.targetHandle)

    if (!sourceHandle || !targetHandle) return false

    // 4. 类型验证：source 只能连接 target
    if (sourceHandle.type !== 'source' || targetHandle.type !== 'target') {
        return false
    }

    // 5. 检查 target handle 是否已被连接（每个输入只能有一个连接）
    const existingConnection = elements.value.find(el => 
        el.source && // 是边（edge），不是节点
        el.target === connection.target && 
        el.targetHandle === connection.targetHandle
    )
    
    if (existingConnection) {
        return false // target handle 已有连接，不允许重复连接
    }

    // 6. Handle 兼容性检查
    const sourceHandleId = sourceHandle.id
    const targetHandleId = targetHandle.id

    // 如果两者id相同，允许连接
    if (sourceHandleId === targetHandleId) {
        return true
    }

    // 检查目标handle的other_compatible_interfaces是否包含源handle的id
    const targetCompatibleInterfaces = targetHandle.other_compatible_interfaces || []
    return targetCompatibleInterfaces.includes(sourceHandleId)
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

// 左侧边栏调整
const { 
  sidebarWidth, 
  isResizing, 
  startResize: startLeftResize 
} = useSidebarResize(400, 150, 600, 'left')

// 右侧边栏调整
const { 
  sidebarWidth: rightSidebarWidth, 
  isResizing: isRightResizing, 
  startResize: startRightResize 
} = useSidebarResize(400, 300, 800, 'right')

// 行动表单数据
const actionFormRef = ref(null)
const actionForm = ref({
    title: '',
    version: '1.0.0',
    implementation_period: 3600,
    description: '',
    target: ''
})

const actionFormRules = {
    title: [
        { required: true, message: '请输入行动标题', trigger: 'blur' }
    ],
    version: [
        { required: true, message: '请输入版本号', trigger: 'blur' }
    ],
    target: [
        { required: true, message: '请输入任务目标', trigger: 'blur' }
    ]
}

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

onMounted(() => {
    fetchNodeConfigs()
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

    const edgeColor = sourceHandle.color || '#909399'

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

const handleSaveAction = async () => {
    if (!actionFormRef.value) return

    try {
        await actionFormRef.value.validate()
    } catch {
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
        name: actionForm.value.title,
        version: actionForm.value.version,
        description: actionForm.value.description || '',
        target: actionForm.value.target,
        implementation_period: actionForm.value.implementation_period,
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

    const response = await actionApi.createActionBlueprint(actionData)
    if (response.code === 0) {
        ElMessage.success('新增行动蓝图成功')
        router.push('/action')
    } else {
        ElMessage.error(`新增行动蓝图失败: ${response.message}`)
    }
}
</script>