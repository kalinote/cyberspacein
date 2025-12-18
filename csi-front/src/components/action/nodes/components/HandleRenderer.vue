<template>
    <template v-if="handleConfig">
        <Handle 
            :id="handleConfig.id" 
            :type="handleConfig.type" 
            :position="handleConfig.position"
            :style="computedHandleStyle"
        />
        <span 
            class="absolute text-xs"
            :style="computedLabelStyle"
        >
            {{ handleConfig.label }}
        </span>
    </template>
</template>

<script setup>
import { computed } from 'vue'
import { Handle } from '@vue-flow/core'

const props = defineProps({
    handleConfig: {
        type: Object,
        required: true
    },
    socketTypeConfigs: {
        type: Array,
        default: () => []
    },
    handleIndex: {
        type: Number,
        default: 0
    },
    totalHandles: {
        type: Number,
        default: 1
    }
})

const defaultHandleStyle = {
    width: '12px',
    height: '12px',
    borderRadius: '50%'
}

const defaultLabelStyle = {
    fontSize: '12px',
    fontWeight: '400'
}

const socketConfig = computed(() => {
    return props.socketTypeConfigs.find(
        config => config.socket_type === props.handleConfig.socket_type
    )
})

const handleColor = computed(() => {
    return socketConfig.value?.color || '#909399'
})

const computedHandleStyle = computed(() => {
    const socketCustomStyle = socketConfig.value?.custom_style?.handle_style || {}
    const handleCustomStyle = props.handleConfig.custom_style?.handle_style || {}
    
    const topPosition = props.totalHandles > 1 
        ? `${((props.handleIndex + 1) / (props.totalHandles + 1)) * 100}%`
        : '50%'
    
    return {
        ...defaultHandleStyle,
        backgroundColor: handleColor.value,
        top: topPosition,
        ...socketCustomStyle,
        ...handleCustomStyle
    }
})

const computedLabelStyle = computed(() => {
    const socketCustomStyle = socketConfig.value?.custom_style?.label_style || {}
    const labelCustomStyle = props.handleConfig.custom_style?.label_style || {}
    
    const topPosition = props.totalHandles > 1 
        ? `calc(${((props.handleIndex + 1) / (props.totalHandles + 1)) * 100}% - 10px)`
        : 'calc(50% - 10px)'
    
    const baseStyle = {
        ...defaultLabelStyle,
        color: handleColor.value,
        top: topPosition
    }
    
    if (props.handleConfig.position === 'left') {
        baseStyle.left = '10px'
    } else if (props.handleConfig.position === 'right') {
        baseStyle.right = '10px'
    } else if (props.handleConfig.position === 'top') {
        baseStyle.top = '10px'
        baseStyle.left = '50%'
        baseStyle.transform = 'translateX(-50%)'
    } else if (props.handleConfig.position === 'bottom') {
        baseStyle.bottom = '10px'
        baseStyle.left = '50%'
        baseStyle.transform = 'translateX(-50%)'
    }
    
    return {
        ...baseStyle,
        ...socketCustomStyle,
        ...labelCustomStyle
    }
})
</script>
