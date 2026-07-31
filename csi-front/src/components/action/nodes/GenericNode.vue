<template>
    <div 
        class="generic-node p-4 bg-white rounded-lg shadow-sm relative"
        :class="{ 
            'pl-16': hasLeftHandles, 
            'pr-16': hasRightHandles
        }"
        :style="{
            ...computedNodeStyle,
            ...bindingTargetStyle,
            border: executionStatusBorderColor
                ? `1.5px solid ${executionStatusBorderColor}`
                : bindingTargetBorder || computedNodeStyle.border || '1px solid #e5e7eb'
        }"
    >
        <BoundaryBindingAnchor
            v-if="shouldShowBindingAnchor"
            :state="bindingTargetState"
            @select="handleBindingAnchorSelect"
        />
        <template v-if="showHandle && nodeConfig">
            <HandleRenderer
                v-for="(handle, index) in leftHandles"
                :key="handle.id"
                :handle-config="handle"
                :handle-index="index"
                :total-handles="leftHandles.length"
                @handle-click="handleDataHandleClick"
            />
            
            <HandleRenderer
                v-for="(handle, index) in rightHandles"
                :key="handle.id"
                :handle-config="handle"
                :handle-index="index"
                :total-handles="rightHandles.length"
                @handle-click="handleDataHandleClick"
            />
            
            <HandleRenderer
                v-for="(handle, index) in topHandles"
                :key="handle.id"
                :handle-config="handle"
                :handle-index="index"
                :total-handles="topHandles.length"
                @handle-click="handleDataHandleClick"
            />
            
            <HandleRenderer
                v-for="(handle, index) in bottomHandles"
                :key="handle.id"
                :handle-config="handle"
                :handle-index="index"
                :total-handles="bottomHandles.length"
                @handle-click="handleDataHandleClick"
            />
        </template>
        
        <div v-if="nodeConfig" class="text-sm text-gray-600 font-medium mb-3 text-center border-b border-gray-100 pb-2">
            {{ nodeConfig.name }}
        </div>

        <div
            v-if="data.bindingDisplay || data.bindingValidationIssues?.length"
            class="mb-3 rounded-md px-2.5 py-2 text-xs"
            :class="data.bindingValidationIssues?.length
                ? 'bg-red-100/90 text-red-700'
                : data.bindingDisplay?.direction === 'input'
                    ? 'bg-blue-100/80 text-blue-700'
                    : 'bg-violet-100/80 text-violet-700'"
        >
            <div class="flex items-center gap-1 font-medium">
                <Icon icon="mdi:link-variant" class="shrink-0 text-sm" />
                <span v-if="data.bindingDisplay" class="truncate">
                    已绑定：{{ data.bindingDisplay.targetNodeName }}
                </span>
                <span v-else>绑定关系无效</span>
            </div>
            <div v-if="data.bindingDisplay" class="mt-1 truncate opacity-80">
                {{ data.bindingDisplay.portDescription }}
            </div>
            <div
                v-if="data.bindingValidationIssues?.length"
                class="mt-1 font-medium"
            >
                {{ data.bindingValidationIssues[0].message }}
            </div>
        </div>

        <div v-if="nodeConfig" class="inputs-container">
            <InputRenderer
                v-for="input in visibleInputs"
                :key="input.id"
                :input-config="input"
                :model-value="data[input.id]"
                @update:model-value="updateInputValue(input.id, $event)"
                :disabled="disabled"
                :node-id="id"
            />
        </div>
    </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { Icon } from '@iconify/vue'
import { ACTION_STATUS } from '@/utils/action'
import { useVueFlow } from '@vue-flow/core'
import HandleRenderer from './components/HandleRenderer.vue'
import InputRenderer from './components/InputRenderer.vue'
import BoundaryBindingAnchor from './components/BoundaryBindingAnchor.vue'
import { isBoundaryConfig } from '@/utils/action/boundaryBinding'

const props = defineProps({
    id: {
        type: String,
        required: true
    },
    data: {
        type: Object,
        default: () => ({})
    },
    showHandle: {
        type: Boolean,
        default: true
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const { updateNodeData } = useVueFlow()
const bindingController = inject('boundaryBindingController', null)

const nodeConfig = computed(() => props.data?.config || null)
const visibleInputs = computed(() => (
    (nodeConfig.value?.inputs || []).filter(input => (
        !input.custom_props?.hide_when_boundary_bound
        || !props.data?.boundaryBinding
    ))
))
const executionStatus = computed(() => props.data?.executionStatus || null)
const executionStatusBorderColor = computed(() => {
    if (!executionStatus.value) return null
    const status = executionStatus.value.status
    const colorMap = {
        // TODO: 这里的颜色可能需要进一步优化
        [ACTION_STATUS.UNKNOWN]: '#9ca3af',
        [ACTION_STATUS.UNREADY]: '#f97316',
        [ACTION_STATUS.PENDING]: '#6b7280',
        [ACTION_STATUS.READY]: '#3b82f6',
        [ACTION_STATUS.RUNNING]: '#eab308',
        [ACTION_STATUS.COMPLETED]: '#10b981',
        [ACTION_STATUS.FAILED]: '#ef4444',
        [ACTION_STATUS.CANCELLED]: '#fecaca',
        [ACTION_STATUS.TIMEOUT]: '#f59e0b',
        [ACTION_STATUS.PAUSED]: '#06b6d4'
    }
    return colorMap[status] || null
})
const bindingTargetKinds = computed(() => props.data?.bindingTargetKinds || [])
const bindingTargetState = computed(() => props.data?.bindingTargetState || null)
const shouldShowBindingAnchor = computed(() => (
    props.showHandle
    && nodeConfig.value
    && !isBoundaryConfig(nodeConfig.value)
    && bindingTargetState.value
    && (
        bindingTargetState.value.relationCount > 0
        || bindingTargetState.value.canAcceptInput
        || bindingTargetState.value.canAcceptOutput
    )
))
const bindingTargetBorder = computed(() => {
    if (bindingTargetState.value && !bindingTargetState.value.valid) {
        return '2px solid #ef4444'
    }
    if (bindingTargetKinds.value.includes('input')) return '2px solid #93c5fd'
    if (bindingTargetKinds.value.includes('output')) return '2px solid #c4b5fd'
    return null
})
const bindingTargetStyle = computed(() => {
    if (
        executionStatusBorderColor.value
        || (bindingTargetState.value && !bindingTargetState.value.valid)
        || bindingTargetKinds.value.length < 2
    ) {
        return {}
    }
    return {
        outline: '2px solid #c4b5fd',
        outlineOffset: '2px'
    }
})

const defaultNodeStyle = {
    minWidth: '250px',
    maxWidth: '400px'
}

const computedNodeStyle = computed(() => {
    if (!nodeConfig.value) return defaultNodeStyle

    const rendererStyle = (
        nodeConfig.value.extension?.config?.renderer?.node_style || {}
    )
    return {
        ...defaultNodeStyle,
        ...rendererStyle,
        ...(nodeConfig.value.node_style || {})
    }
})

const leftHandles = computed(() => {
    if (!nodeConfig.value?.handles) return []
    return nodeConfig.value.handles.filter(h => h.position === 'left')
})

const rightHandles = computed(() => {
    if (!nodeConfig.value?.handles) return []
    return nodeConfig.value.handles.filter(h => h.position === 'right')
})

const topHandles = computed(() => {
    if (!nodeConfig.value?.handles) return []
    return nodeConfig.value.handles.filter(h => h.position === 'top')
})

const bottomHandles = computed(() => {
    if (!nodeConfig.value?.handles) return []
    return nodeConfig.value.handles.filter(h => h.position === 'bottom')
})

const hasLeftHandles = computed(() => leftHandles.value.length > 0)
const hasRightHandles = computed(() => rightHandles.value.length > 0)

const updateInputValue = (inputId, value) => {
    if (!props.disabled) {
        updateNodeData(props.id, { [inputId]: value })
    }
}

const handleDataHandleClick = () => {
    if (
        isBoundaryConfig(nodeConfig.value)
        && nodeConfig.value?.builtin_key === 'blueprint.output'
    ) {
        bindingController?.startOutputBinding?.(props.id)
    }
}

const handleBindingAnchorSelect = () => {
    bindingController?.selectBindingTarget?.(props.id)
}
</script>

<style scoped>
.generic-node {
    transition: all 0.2s ease;
}

.generic-node:hover {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.inputs-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.inputs-container > :deep(.multi-line-layout:first-child) {
    margin-top: 0;
}

.inputs-container > :deep(.multi-line-layout:last-child) {
    margin-bottom: 0;
}
</style>
