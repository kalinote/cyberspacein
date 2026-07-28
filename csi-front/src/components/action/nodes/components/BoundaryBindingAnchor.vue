<template>
    <el-tooltip :content="tooltipContent" placement="top" :show-after="250">
        <div
            class="boundary-binding-anchor nodrag"
            :class="anchorClass"
            :aria-label="tooltipContent"
            @click.stop="emit('select')"
        >
            <Icon icon="mdi:link-variant" class="pointer-events-none text-[10px]" />
            <span
                v-if="state.relationCount"
                class="binding-count pointer-events-none"
            >
                {{ state.relationCount }}
            </span>
            <Handle
                v-if="state.canAcceptInput || state.directions?.includes('input')"
                :id="BINDING_TARGET_HANDLE_ID"
                type="target"
                :position="Position.Top"
                class="binding-protocol-handle"
            />
            <Handle
                v-if="state.canAcceptOutput || state.directions?.includes('output')"
                :id="BINDING_SOURCE_HANDLE_ID"
                type="source"
                :position="Position.Top"
                class="binding-protocol-handle"
            />
        </div>
    </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Handle, Position } from '@vue-flow/core'
import {
    BINDING_SOURCE_HANDLE_ID,
    BINDING_TARGET_HANDLE_ID
} from '@/utils/action/boundaryBinding'

const emit = defineEmits(['select'])

const props = defineProps({
    state: {
        type: Object,
        required: true
    }
})

const anchorClass = computed(() => ({
    'is-entry': props.state.role === 'entry',
    'is-exit': props.state.role === 'exit',
    'is-invalid': !props.state.valid,
    'is-unbound': !props.state.role
}))

const tooltipContent = computed(() => {
    if (!props.state.valid) {
        return props.state.issues?.[0]?.message || '当前绑定关系无效'
    }
    if (props.state.role === 'entry') {
        return `入口替代：已绑定 ${props.state.relationCount} 个蓝图输入`
    }
    if (props.state.role === 'exit') {
        return `出口替代：已绑定 ${props.state.relationCount} 个蓝图输出`
    }
    if (props.state.canAcceptInput) {
        return '绑定：用蓝图输入替代该起始节点'
    }
    if (props.state.canAcceptOutput) {
        return '绑定：用蓝图输出替代该结束节点'
    }
    return '当前节点不能建立 IO 替换绑定'
})
</script>

<style scoped>
.boundary-binding-anchor {
    position: absolute;
    top: -7px;
    left: 50%;
    z-index: 12;
    display: flex;
    width: 14px;
    height: 14px;
    transform: translateX(-50%);
    align-items: center;
    justify-content: center;
    border: 2px solid white;
    border-radius: 9999px;
    background: #9ca3af;
    color: white;
    box-shadow: 0 1px 4px rgb(15 23 42 / 25%);
    cursor: crosshair;
}

.boundary-binding-anchor.is-entry {
    background: #60a5fa;
}

.boundary-binding-anchor.is-exit {
    background: #a78bfa;
}

.boundary-binding-anchor.is-invalid {
    background: #ef4444;
    cursor: not-allowed;
}

.binding-count {
    position: absolute;
    top: -9px;
    right: -9px;
    display: flex;
    min-width: 14px;
    height: 14px;
    align-items: center;
    justify-content: center;
    border: 1px solid white;
    border-radius: 9999px;
    background: #334155;
    padding: 0 3px;
    color: white;
    font-size: 9px;
    line-height: 1;
}

.binding-protocol-handle {
    position: absolute;
    inset: -4px;
    width: 22px;
    height: 22px;
    transform: none;
    border: 0;
    background: transparent;
    opacity: 0;
}
</style>
