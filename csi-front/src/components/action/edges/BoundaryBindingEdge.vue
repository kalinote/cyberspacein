<template>
    <BaseEdge :id="id" :path="edgePath" :style="style" />
    <EdgeLabelRenderer>
        <el-tooltip :content="data?.tooltip || 'IO 绑定关系'" placement="top">
            <div
                class="boundary-binding-edge-label nodrag nopan"
                :class="data?.direction"
                :style="{
                    transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`
                }"
            >
                <Icon icon="mdi:link-variant" />
            </div>
        </el-tooltip>
    </EdgeLabelRenderer>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
    BaseEdge,
    EdgeLabelRenderer,
    getBezierPath
} from '@vue-flow/core'

const props = defineProps({
    id: { type: String, required: true },
    sourceX: { type: Number, required: true },
    sourceY: { type: Number, required: true },
    targetX: { type: Number, required: true },
    targetY: { type: Number, required: true },
    sourcePosition: { type: String, required: true },
    targetPosition: { type: String, required: true },
    style: { type: Object, default: () => ({}) },
    data: { type: Object, default: () => ({}) }
})

const path = computed(() => getBezierPath(props))
const edgePath = computed(() => path.value[0])
const labelX = computed(() => path.value[1])
const labelY = computed(() => path.value[2])
</script>

<style scoped>
.boundary-binding-edge-label {
    position: absolute;
    z-index: 10;
    display: flex;
    width: 18px;
    height: 18px;
    align-items: center;
    justify-content: center;
    border: 1px solid white;
    border-radius: 9999px;
    background: #60a5fa;
    color: white;
    font-size: 11px;
    box-shadow: 0 1px 4px rgb(15 23 42 / 20%);
    pointer-events: all;
}

.boundary-binding-edge-label.output {
    background: #a78bfa;
}
</style>
