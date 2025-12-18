<template>
    <div 
        class="generic-node p-4 bg-white rounded-lg shadow-sm border border-gray-200 relative"
        :class="{ 'pl-16': hasLeftHandles, 'pr-16': hasRightHandles }"
        :style="computedNodeStyle"
    >
        <template v-if="showHandle && nodeConfig">
            <HandleRenderer
                v-for="(handle, index) in leftHandles"
                :key="handle.id"
                :handle-config="handle"
                :socket-type-configs="socketTypeConfigs"
                :handle-index="index"
                :total-handles="leftHandles.length"
            />
            
            <HandleRenderer
                v-for="(handle, index) in rightHandles"
                :key="handle.id"
                :handle-config="handle"
                :socket-type-configs="socketTypeConfigs"
                :handle-index="index"
                :total-handles="rightHandles.length"
            />
            
            <HandleRenderer
                v-for="(handle, index) in topHandles"
                :key="handle.id"
                :handle-config="handle"
                :socket-type-configs="socketTypeConfigs"
                :handle-index="index"
                :total-handles="topHandles.length"
            />
            
            <HandleRenderer
                v-for="(handle, index) in bottomHandles"
                :key="handle.id"
                :handle-config="handle"
                :socket-type-configs="socketTypeConfigs"
                :handle-index="index"
                :total-handles="bottomHandles.length"
            />
        </template>
        
        <div v-if="nodeConfig" class="text-sm text-gray-600 font-medium mb-3 text-center border-b border-gray-100 pb-2">
            {{ nodeConfig.name }}
        </div>
        
        <div v-if="nodeConfig" class="inputs-container">
            <InputRenderer
                v-for="input in nodeConfig.inputs"
                :key="input.id"
                :input-config="input"
                :model-value="data[input.id]"
                @update:model-value="updateInputValue(input.id, $event)"
                :disabled="disabled"
            />
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import HandleRenderer from './components/HandleRenderer.vue'
import InputRenderer from './components/InputRenderer.vue'

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

const nodeConfig = computed(() => props.data?.config || null)
const socketTypeConfigs = computed(() => props.data?.socketTypeConfigs || [])

const defaultNodeStyle = {
    minWidth: '250px',
    maxWidth: '400px'
}

const computedNodeStyle = computed(() => {
    if (!nodeConfig.value) return defaultNodeStyle
    
    return {
        ...defaultNodeStyle,
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
