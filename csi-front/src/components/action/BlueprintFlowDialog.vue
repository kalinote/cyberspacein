<template>
    <el-dialog v-model="dialogVisible" :title="blueprintData?.name || '蓝图流程图'" width="80%" :before-close="handleClose"
        :center="false" :align-center="true" class="blueprint-flow-dialog">
        <template #default>
            <div class="flex flex-col" style="height: 80vh;">
                <div v-if="blueprintLoading" class="flex-1 flex items-center justify-center">
                    <div class="text-center">
                        <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                        <p class="text-gray-600">加载中...</p>
                    </div>
                </div>

                <div v-else-if="error" class="flex-1 flex items-center justify-center">
                    <div class="text-center">
                        <Icon icon="mdi:alert-circle" class="text-4xl text-red-500 mb-2" />
                        <p class="text-gray-600">{{ error }}</p>
                    </div>
                </div>

                <div v-else class="flex-1 relative bg-gray-50 min-h-0">
                    <VueFlow v-model="elements" :node-types="nodeTypes" :default-zoom="1.5" :min-zoom="0.2"
                        :max-zoom="4" :nodes-draggable="false" :nodes-connectable="false" :elements-selectable="false"
                        class="h-full w-full" @init="handleFlowInit">
                        <Background pattern-color="#aaa" :gap="18" />
                        <Controls />
                    </VueFlow>

                    <div v-if="elements.length === 0"
                        class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                        <div class="text-center text-gray-400">
                            <Icon icon="mdi:graph-outline" class="text-6xl mb-4" />
                            <p>暂无节点数据</p>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex items-center justify-between w-full">
                <div class="text-sm text-gray-500">
                    蓝图ID：{{ blueprintData?.id || '-' }}
                </div>
                <div class="text-sm text-gray-500">
                    更新于：{{ formatDateTime(blueprintData?.updated_at) }}
                </div>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
import { ref, computed, watch, markRaw, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import GenericNode from '@/components/action/nodes/GenericNode.vue'
import { actionApi } from '@/api/action'
import { ElMessage } from 'element-plus'
import {
    SOCKET_TYPE_CONFIGS,
    normalizeDefaultValue,
    getDefaultData,
    getEdgeColor,
    formatDateTime
} from '@/utils/action'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const props = defineProps({
    modelValue: {
        type: Boolean,
        default: false
    },
    blueprintId: {
        type: String,
        default: null
    }
})

const emit = defineEmits(['update:modelValue'])

const dialogVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value)
})

const blueprintLoading = ref(false)
const error = ref(null)
const blueprintData = ref(null)
const nodeTypeConfigs = ref([])
const elements = ref([])
const { setViewport, fitView } = useVueFlow()

const nodeTypes = computed(() => {
    const types = {}
    nodeTypeConfigs.value.forEach(config => {
        types[config.id] = markRaw(GenericNode)
        if (config.type) {
            types[config.type] = markRaw(GenericNode)
        }
    })
    if (nodeTypeConfigs.value.length === 0) {
        types['crawler'] = markRaw(GenericNode)
        types['construct'] = markRaw(GenericNode)
    }
    return types
})

const fetchNodeConfigs = async () => {
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
            throw new Error(response.message || '获取节点配置失败')
        }
    } catch (err) {
        console.error('获取节点配置失败:', err)
        throw err
    }
}

const fetchBlueprint = async () => {
    if (!props.blueprintId) {
        error.value = '蓝图ID不能为空'
        return
    }

    if (blueprintLoading.value) {
        return
    }

    blueprintLoading.value = true
    error.value = null

    try {
        if (nodeTypeConfigs.value.length === 0) {
            await fetchNodeConfigs()
        }

        const response = await actionApi.getBlueprint(props.blueprintId)
        if (response.code === 0) {
            blueprintData.value = response.data
            loadBlueprintData()
        } else {
            error.value = response.message || '获取蓝图数据失败'
            ElMessage.error(error.value)
        }
    } catch (err) {
        error.value = '获取蓝图数据失败'
        ElMessage.error(error.value)
        console.error('获取蓝图数据失败:', err)
    } finally {
        blueprintLoading.value = false
    }
}

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

const loadBlueprintData = () => {
    if (!blueprintData.value || !blueprintData.value.graph) {
        elements.value = []
        return
    }

    if (nodeTypeConfigs.value.length === 0) {
        return
    }

    const graph = blueprintData.value.graph

    const processedNodes = (graph.nodes || []).map(node => {
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

        const nodeData = getDefaultData(config, SOCKET_TYPE_CONFIGS)

        if (config.inputs) {
            config.inputs.forEach(input => {
                const formDataValue = node.data?.form_data?.[input.name]
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

    const processedEdges = (graph.edges || []).map(edge => {
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
                edgeColor = getEdgeColor(sourceHandle.socket_type, SOCKET_TYPE_CONFIGS)
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

    if (graph.viewport) {
        setViewport(graph.viewport)
    } else {
        setTimeout(() => {
            fitView()
        }, 100)
    }
}

const handleFlowInit = () => {
    if (blueprintData.value?.graph?.viewport) {
        setViewport(blueprintData.value.graph.viewport)
    } else {
        setTimeout(() => {
            fitView()
        }, 100)
    }
}

const handleClose = () => {
    dialogVisible.value = false
    blueprintData.value = null
    elements.value = []
    error.value = null
}

watch([() => props.modelValue, () => props.blueprintId], async ([newModelValue, newBlueprintId], [oldModelValue, oldBlueprintId]) => {
    if (newModelValue && newBlueprintId) {
        if (oldModelValue !== newModelValue || oldBlueprintId !== newBlueprintId) {
            await fetchBlueprint()
        }
    } else if (!newModelValue) {
        handleClose()
    }
}, { immediate: false })

onMounted(async () => {
    await fetchNodeConfigs()
})
</script>

<style scoped>
:deep(.blueprint-flow-dialog) {
    display: flex;
    justify-content: center;
    align-items: center;
}

:deep(.blueprint-flow-dialog .el-dialog) {
    height: 80vh;
    max-height: 80vh;
    margin: 0 auto;
    top: 50% !important;
    transform: translateY(-50%) !important;
    display: flex;
    flex-direction: column;
    position: fixed;
}

:deep(.blueprint-flow-dialog .el-dialog__header) {
    flex-shrink: 0;
}

:deep(.blueprint-flow-dialog .el-dialog__body) {
    padding: 20px;
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 0;
}

:deep(.blueprint-flow-dialog .el-dialog__footer) {
    flex-shrink: 0;
}

:deep(.vue-flow__node) {
    cursor: default;
}
</style>
