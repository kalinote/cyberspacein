<template>
    <el-dialog v-model="dialogVisible" :title="blueprintData?.name || '蓝图流程图'" :width="isMobile ? '100%' : '80%'" :before-close="handleClose"
        :fullscreen="isMobile" :append-to-body="isMobile" :center="false" :align-center="!isMobile" class="blueprint-flow-dialog" :class="{ 'mobile-blueprint-flow-dialog': isMobile }" @opened="handleFlowInit">
        <template #default>
            <div class="flex flex-col" :class="{ 'mobile-blueprint-flow-content': isMobile }" :style="isMobile ? undefined : { height: '80vh' }">
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
                        <el-button v-if="canReadBlueprint" class="mt-4" @click="fetchBlueprint">重新加载</el-button>
                    </div>
                </div>

                <template v-else>
                <div v-if="isMobile" class="mobile-flow-tools"><el-button @click="handleFlowInit"><Icon icon="mdi:fit-to-screen-outline" />适应画面</el-button><el-button @click="selectedPreviewNodeId = ''; directoryVisible = true; detailVisible = true">节点目录 {{ blueprintData?.graph?.nodes?.length || 0 }}</el-button><el-button @click="selectedPreviewNodeId = ''; directoryVisible = false; detailVisible = true">蓝图信息</el-button></div>
                <p v-if="nodeConfigError" class="mobile-flow-notice">{{ nodeConfigError }}</p>
                <div class="flex-1 relative bg-gray-50 min-h-0">
                    <VueFlow v-model="elements" :node-types="nodeTypes" :edge-types="edgeTypes" :default-zoom="1.5"
                        :min-zoom="isMobile ? 0.05 : 0.2" :max-zoom="4" :nodes-draggable="false" :nodes-connectable="false"
                        :elements-selectable="false" :delete-key-code="null" class="h-full w-full" @init="handleFlowInit" @nodes-initialized="handleFlowInit"
                        v-on="isMobile || !nodeTypeConfigs.length ? { nodeClick: ({ node }) => openNodeDetails(node.id) } : {}">
                        <template #node-blueprintPreview="{ id, data }"><div class="blueprint-preview-node"><Handle v-for="handle in data.previewHandles" :key="`${handle.type}-${handle.id}`" :id="handle.id" :type="handle.type" :position="handle.type === 'source' ? Position.Right : Position.Left" :style="{ top: `${handle.offset}%` }" :connectable="false" /><button class="nodrag nopan" @click.stop="openNodeDetails(id)"><strong>{{ data.previewLabel }}</strong><span>{{ data.config?.type || '流程节点' }}</span><small>查看节点详情</small></button></div></template>
                        <Background pattern-color="#aaa" :gap="18" />
                        <Controls :show-interactive="false" />
                    </VueFlow>

                    <div v-if="elements.length === 0"
                        class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                        <div class="text-center text-gray-400">
                            <Icon icon="mdi:graph-outline" class="text-6xl mb-4" />
                            <p>暂无节点数据</p>
                        </div>
                    </div>
                </div>
                </template>
            </div>
        </template>

        <template #footer>
            <div v-if="isMobile" class="mobile-flow-footer"><span>拖动查看 · 双指缩放 · 点按节点查看资料</span><el-button @click="handleClose">关闭预览</el-button></div>
            <div v-else class="flex items-center justify-between w-full">
                <div class="text-sm text-gray-500">
                    蓝图ID：{{ blueprintData?.id || '-' }}
                </div>
                <div class="text-sm text-gray-500">
                    更新于：{{ formatDateTime(blueprintData?.updated_at) }}
                </div>
            </div>
        </template>
    </el-dialog>
    <MobileSheet v-model="detailVisible" :title="directoryVisible ? '节点目录' : selectedPreviewNode ? nodeDisplayName(selectedPreviewNode.id) : '蓝图信息'">
        <div v-if="directoryVisible" class="blueprint-node-directory"><button v-for="node in blueprintData?.graph?.nodes || []" :key="node.id" @click="openNodeDetails(node.id)"><span><strong>{{ nodeDisplayName(node.id) }}</strong><small>{{ node.type || '流程节点' }}</small></span><Icon icon="mdi:chevron-right" /></button><el-empty v-if="!blueprintData?.graph?.nodes?.length" description="暂无节点" :image-size="48" /></div>
        <div v-else-if="selectedPreviewNode" class="blueprint-preview-detail"><p v-if="!canReadNodes" class="mobile-flow-notice">当前展示蓝图中保存的节点信息</p><dl><dt>节点 ID</dt><dd>{{ selectedPreviewNode.id }}</dd><dt>定义 ID</dt><dd>{{ selectedPreviewNode.data?.definition_id || selectedPreviewNode.type }}</dd><dt>定义版本</dt><dd>{{ selectedPreviewNode.data?.node_definition_version || selectedPreviewNode.data?.version || '—' }}</dd></dl><h3>节点参数</h3><article v-for="(value, key) in selectedPreviewNode.data?.form_data || {}" :key="key"><strong>{{ key }}</strong><pre>{{ formatPreviewValue(value) }}</pre></article><p v-if="!Object.keys(selectedPreviewNode.data?.form_data || {}).length">未保存节点参数</p><h3>流程连接</h3><button v-for="edge in selectedNodeEdges" :key="edge.id" class="blueprint-related-node" @click="openNodeDetails(edge.source === selectedPreviewNode.id ? edge.target : edge.source)"><span>{{ edge.source === selectedPreviewNode.id ? '输出至' : '来自' }} {{ nodeDisplayName(edge.source === selectedPreviewNode.id ? edge.target : edge.source) }}</span><Icon icon="mdi:chevron-right" /></button><p v-if="!selectedNodeEdges.length">暂无数据连线</p></div>
        <div v-else-if="blueprintData" class="blueprint-preview-detail"><h3>{{ blueprintData.name }}</h3><p>{{ blueprintData.description || '暂无说明' }}</p><dl><dt>行动目标</dt><dd>{{ blueprintData.target || '未设置' }}</dd><dt>蓝图版本</dt><dd>{{ blueprintData.version || '—' }}</dd><dt>更新时间</dt><dd>{{ formatDateTime(blueprintData.updated_at) }}</dd><dt>蓝图 ID</dt><dd>{{ blueprintData.id }}</dd></dl></div>
        <template #footer><div class="blueprint-detail-footer"><el-button v-if="selectedPreviewNode && !directoryVisible" @click="selectedPreviewNodeId = ''; directoryVisible = true">返回节点目录</el-button><el-button type="primary" @click="detailVisible = false">返回流程图</el-button></div></template>
    </MobileSheet>
</template>

<script setup>
import { ref, computed, watch, markRaw, onActivated, onDeactivated, onBeforeUnmount, nextTick, provide } from 'vue'
import { Icon } from '@iconify/vue'
import { VueFlow, useVueFlow, Handle, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import GenericNode from '@/components/action/nodes/GenericNode.vue'
import BoundaryBindingEdge from '@/components/action/edges/BoundaryBindingEdge.vue'
import { actionApi } from '@/api/action'
import { ElMessage } from 'element-plus'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'
import {
    normalizeDefaultValue,
    getDefaultData,
    formatDateTime
} from '@/utils/action'
import {
    buildBindingDisplay,
    buildBindingRelationEdges,
    collectBindingTargetKinds,
    isBoundaryConfig,
    resolveBindingTargetStates,
    validateBoundaryBindings
} from '@/utils/action/boundaryBinding'

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
const { isMobile } = useMobileViewport()
const canReadBlueprint = computed(() => hasPerm(PERM.operations.action.blueprint.read))
const canReadNodes = computed(() => hasPerm(PERM.operations.action.node.read))
const nodeConfigError = ref('')
const detailVisible = ref(false)
const directoryVisible = ref(false)
const selectedPreviewNodeId = ref('')
let requestGeneration = 0
let pageActive = true

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
const selectedPreviewNode = computed(() => blueprintData.value?.graph?.nodes?.find(node => node.id === selectedPreviewNodeId.value))
const selectedNodeEdges = computed(() => (blueprintData.value?.graph?.edges || []).filter(edge => edge.source === selectedPreviewNodeId.value || edge.target === selectedPreviewNodeId.value))

const isTemplate = computed(() => {
    return blueprintData.value?.is_template || false
})

const templateParams = computed(() => {
    return blueprintData.value?.template?.params || []
})

const templateBindings = computed(() => {
    return blueprintData.value?.template?.bindings || {}
})

provide('templateContext', {
    isTemplateMode: isTemplate,
    availableParams: templateParams,
    bindings: templateBindings,
    updateBinding: () => {
    }
})

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
const edgeTypes = {
    boundaryBinding: markRaw(BoundaryBindingEdge)
}

const fetchNodeConfigs = async (generation) => {
    if (!canReadNodes.value) return
    try {
        const response = await actionApi.getNodes()
        if (!pageActive || generation !== requestGeneration || !props.modelValue || !canReadNodes.value || !canReadBlueprint.value) return
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
        if (!pageActive || generation !== requestGeneration || !props.modelValue || !canReadNodes.value) return
        console.error('获取节点配置失败:', err)
        nodeConfigError.value = '节点定义加载失败，当前显示蓝图内保存的信息'
    }
}

const fetchBlueprint = async () => {
    if (!pageActive || !props.modelValue) return
    if (!canReadBlueprint.value) {
        error.value = '暂无蓝图读取权限'
        return
    }
    if (!props.blueprintId) {
        error.value = '蓝图ID不能为空'
        return
    }

    const id = props.blueprintId
    const generation = ++requestGeneration
    blueprintLoading.value = true
    error.value = null
    nodeConfigError.value = ''
    blueprintData.value = null
    elements.value = []
    detailVisible.value = false
    directoryVisible.value = false

    try {
        const [response] = await Promise.all([
            actionApi.getBlueprint(id),
            canReadNodes.value && !nodeTypeConfigs.value.length ? fetchNodeConfigs(generation) : Promise.resolve()
        ])
        if (!pageActive || generation !== requestGeneration || id !== props.blueprintId || !props.modelValue || !canReadBlueprint.value) return
        if (response.code === 0) {
            blueprintData.value = response.data
            loadBlueprintData()
        } else {
            error.value = response.message || '获取蓝图数据失败'
            ElMessage.error(error.value)
        }
    } catch (err) {
        if (!pageActive || generation !== requestGeneration || id !== props.blueprintId || !props.modelValue || !canReadBlueprint.value) return
        error.value = '获取蓝图数据失败'
        ElMessage.error(error.value)
        console.error('获取蓝图数据失败:', err)
    } finally {
        if (generation === requestGeneration) blueprintLoading.value = false
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

        const nodeData = getDefaultData(config)
        nodeData.interfacePortId = node.data?.interface_port_id || null
        nodeData.boundaryBinding = node.data?.boundary_binding || null
        nodeData.previewLabel = config.name || node.data?.definition_id || node.type
        const sources = [...new Set((graph.edges || []).filter(edge => edge.source === node.id).map(edge => edge.source_port_id || edge.sourceHandle || 'preview-source'))]
        const targets = [...new Set((graph.edges || []).filter(edge => edge.target === node.id).map(edge => edge.target_port_id || edge.targetHandle || 'preview-target'))]
        nodeData.previewHandles = [
            ...sources.map((id, index) => ({ id, type: 'source', offset: (index + 1) * 100 / (sources.length + 1) })),
            ...targets.map((id, index) => ({ id, type: 'target', offset: (index + 1) * 100 / (targets.length + 1) }))
        ]

        if (config.inputs && !blueprintData.value?.is_template) {
            config.inputs.forEach(input => {
                const formDataValue = node.data?.form_data?.[input.name]
                if (formDataValue !== undefined && formDataValue !== null) {
                    nodeData[input.id] = normalizeDefaultValue(input.type, formDataValue)
                }
            })
        }

        return {
            id: node.id,
            type: isMobile.value || !nodeTypeConfigs.value.length ? 'blueprintPreview' : config.id,
            position: node.position,
            data: nodeData,
            selected: false
        }
    })

    const processedEdges = (graph.edges || []).map(edge => {
        const sourceNode = processedNodes.find(n => n.id === edge.source)
        const targetNode = processedNodes.find(n => n.id === edge.target)

        let edgeColor = '#909399'
        let finalSourceHandle = edge.source_port_id || edge.sourceHandle || null
        let finalTargetHandle = edge.target_port_id || edge.targetHandle || null

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
            sourceHandle: isMobile.value || !nodeTypeConfigs.value.length ? (edge.source_port_id || edge.sourceHandle || 'preview-source') : finalSourceHandle,
            target: edge.target,
            targetHandle: isMobile.value || !nodeTypeConfigs.value.length ? (edge.target_port_id || edge.targetHandle || 'preview-target') : finalTargetHandle,
            style: {
                stroke: edgeColor,
                strokeWidth: 3
            }
        }
    })

    const bindingKindsByTarget = collectBindingTargetKinds(processedNodes)
    const bindingTargetStates = resolveBindingTargetStates(
        processedNodes,
        processedEdges
    )
    const bindingIssues = validateBoundaryBindings(
        processedNodes,
        processedEdges
    )
    processedNodes.forEach(node => {
        if (isBoundaryConfig(node.data?.config)) {
            const binding = node.data?.boundaryBinding
            const targetNode = binding?.bound_node_id
                ? processedNodes.find(item => item.id === binding.bound_node_id)
                : null
            node.data.bindingDisplay = targetNode
                ? buildBindingDisplay(
                    node,
                    targetNode,
                    (binding.port_mappings || []).map(
                        mapping => mapping.target_port_id
                    )
                )
                : null
            node.data.bindingValidationIssues = bindingIssues.filter(
                issue => issue.nodeId === node.id
            )
            return
        }
        node.data.bindingTargetKinds = bindingKindsByTarget[node.id] || []
        node.data.bindingTargetState = bindingTargetStates[node.id] || null
    })
    const bindingEdges = buildBindingRelationEdges(
        processedNodes,
        bindingTargetStates
    )
    elements.value = [
        ...processedNodes,
        ...processedEdges,
        ...bindingEdges
    ]

    handleFlowInit()
}

/** """手机按实际节点范围定位，桌面保留蓝图保存的视口。""" */
const handleFlowInit = async () => {
    const generation = requestGeneration
    await nextTick()
    if (!pageActive || generation !== requestGeneration || !props.modelValue || !blueprintData.value) return
    if (!isMobile.value && blueprintData.value?.graph?.viewport) {
        setViewport(blueprintData.value.graph.viewport)
    } else {
        fitView({ padding: 0.16, minZoom: isMobile.value ? 0.05 : 0.2, maxZoom: 1.5 })
    }
}

const handleClose = () => {
    requestGeneration++
    dialogVisible.value = false
    detailVisible.value = false
    directoryVisible.value = false
    selectedPreviewNodeId.value = ''
    blueprintLoading.value = false
    blueprintData.value = null
    elements.value = []
    error.value = null
    nodeConfigError.value = ''
}

/** """在节点详情和连线导航中复用已授权的节点显示名称。""" */
const nodeDisplayName = id => {
    const node = elements.value.find(item => item.id === id && item.position)
    return node?.data?.previewLabel || id
}
/** """节点卡片与目录共用只读详情入口，不修改图形布局。""" */
const openNodeDetails = id => {
    if (!pageActive || !canReadBlueprint.value || !blueprintData.value?.graph?.nodes?.some(node => node.id === id)) return
    selectedPreviewNodeId.value = id
    directoryVisible.value = false
    detailVisible.value = true
}
/** """把节点快照参数转为纯文本，保留结构而不启用编辑器。""" */
const formatPreviewValue = value => {
    if (value == null) return '未设置'
    return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
}

watch([() => props.modelValue, () => props.blueprintId], async ([newModelValue, newBlueprintId], [oldModelValue, oldBlueprintId]) => {
    if (newModelValue && newBlueprintId) {
        if (oldModelValue !== newModelValue || oldBlueprintId !== newBlueprintId) {
            await fetchBlueprint()
        }
    } else if (!newModelValue) {
        handleClose()
    }
}, { immediate: true })
watch(isMobile, () => { if (props.modelValue && blueprintData.value) loadBlueprintData() })
watch([canReadBlueprint, canReadNodes], ([read, nodes], [oldRead, oldNodes]) => {
    if (!read) { nodeTypeConfigs.value = []; handleClose(); return }
    if (nodes !== oldNodes) nodeTypeConfigs.value = []
    if (props.modelValue && (nodes !== oldNodes || read !== oldRead)) fetchBlueprint()
}, { flush: 'sync' })
onActivated(() => { pageActive = true })
onDeactivated(() => { pageActive = false; handleClose() })
onBeforeUnmount(() => { pageActive = false; requestGeneration++ })
</script>

<style scoped>
.blueprint-preview-node { width: 190px; border: 1px solid #93c5fd; border-radius: 12px; background: #fff; box-shadow: 0 2px 8px rgb(15 23 42 / 8%); }
.blueprint-preview-node button { display: flex; flex-direction: column; gap: 6px; text-align: left; padding: 14px 16px; width: 100%; min-height: 85px; }
.blueprint-preview-node strong { color: #0f172a; font-size: 14px; overflow-wrap: anywhere; }
.blueprint-preview-node span { color: #64748b; font-size: 11px; }
.blueprint-preview-node small { color: #2563eb; font-size: 11px; }
.mobile-flow-tools { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-shrink: 0; }
.mobile-flow-tools > span { flex: 1; text-align: center; font-size: 12px; color: #64748b; }
.mobile-flow-tools .el-button { min-height: 44px; margin: 0; padding: 10px; }
.mobile-flow-tools .el-button { flex: 1; min-width: 0; font-size: 12px; padding-inline: 6px; }
.mobile-flow-notice { font-size: 12px; line-height: 1.6; color: #64748b; padding: 8px 4px; }
.mobile-flow-footer { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.mobile-flow-footer > span { font-size: 11px; color: #64748b; text-align: left; }
.mobile-flow-footer .el-button { width: 100%; min-height: 44px; }
.blueprint-preview-detail { color: #334155; font-size: 14px; overflow-wrap: anywhere; }
.blueprint-preview-detail dl { display: grid; grid-template-columns: 65px minmax(0, 1fr); gap: 12px 10px; font-size: 13px; margin: 12px 0; }
.blueprint-preview-detail dt { color: #64748b; }.blueprint-preview-detail dd { margin: 0; }
.blueprint-preview-detail h3 { font-weight: 700; color: #0f172a; margin: 18px 0 10px; }
.blueprint-preview-detail > p { white-space: pre-wrap; line-height: 1.7; }
.blueprint-preview-detail article { margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 10px; }
.blueprint-preview-detail article strong { display: block; font-size: 13px; margin-bottom: 6px; }
.blueprint-preview-detail pre { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: 12px; line-height: 1.6; margin: 0; }
.blueprint-related-node { display: flex; justify-content: space-between; align-items: center; gap: 8px; width: 100%; padding: 12px 0; min-height: 44px; text-align: left; border-bottom: 1px solid #e2e8f0; }
.blueprint-node-directory { display: grid; gap: 8px; }.blueprint-node-directory button { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 60px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; text-align: left; }.blueprint-node-directory button > span { min-width: 0; }.blueprint-node-directory strong { display: block; font-size: 14px; overflow-wrap: anywhere; }.blueprint-node-directory small { display: block; color: #64748b; font-size: 12px; margin-top: 5px; }.blueprint-detail-footer { display: flex; gap: 8px; }.blueprint-detail-footer .el-button { margin: 0; flex: 1; min-width: 0; }
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

<style>
@media (max-width: 767px) {
    .mobile-blueprint-flow-dialog.el-dialog { width: 100% !important; max-width: 100% !important; height: var(--mobile-viewport-height, 100dvh) !important; max-height: var(--mobile-viewport-height, 100dvh) !important; margin: 0 !important; border-radius: 0; padding: 12px; display: flex; flex-direction: column; align-items: stretch !important; }
    .mobile-blueprint-flow-dialog .el-dialog__header { min-height: 44px; flex-shrink: 0; padding-right: 36px; }
    .mobile-blueprint-flow-dialog .el-dialog__title { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .mobile-blueprint-flow-dialog .el-dialog__body { padding: 0 !important; width: 100%; flex: 1; min-height: 0; overflow: hidden !important; display: flex; flex-direction: column; }
    .mobile-blueprint-flow-content { flex: 1; min-height: 0; width: 100%; }
    .mobile-blueprint-flow-dialog .el-dialog__footer { padding: 10px 0 max(10px, env(safe-area-inset-bottom)); width: 100%; flex-shrink: 0; }
    .mobile-blueprint-flow-dialog .vue-flow__controls { display: flex; flex-direction: column; align-items: stretch; box-shadow: 0 1px 6px rgb(15 23 42 / 16%); }
    .mobile-blueprint-flow-dialog .vue-flow__controls-button { width: 44px; min-width: 44px; max-width: 44px; height: 44px; min-height: 44px; max-height: 44px; padding: 0; box-sizing: border-box; display: flex; justify-content: center; align-items: center; background: #fff; border: 1px solid #e2e8f0; line-height: 1; }
    .mobile-blueprint-flow-dialog .vue-flow__controls-button svg { display: block; width: 20px; min-width: 20px; max-width: 20px; height: 20px; min-height: 20px; max-height: 20px; flex: 0 0 20px; pointer-events: none; }
}
</style>
