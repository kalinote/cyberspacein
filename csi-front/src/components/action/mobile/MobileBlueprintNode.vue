<template>
  <div class="blueprint-compact-node" :class="{ selected }">
    <Handle v-for="(handle, index) in inputs" :key="handle.id" :id="handle.id" type="target" :position="Position.Left" :connectable="false" :style="{ top: `${(index + 1) * 100 / (inputs.length + 1)}%` }" />
    <span>{{ data.config?.type || '节点' }}</span>
    <strong>{{ data.config?.name || id }}</strong>
    <small :title="id">节点 · {{ id?.length > 12 ? `…${id.slice(-12)}` : id }}</small>
    <small>{{ inputs.length }} 输入 · {{ outputs.length }} 输出<span v-if="data.boundaryBinding"> · IO 已绑定</span></small>
    <Handle v-for="(handle, index) in outputs" :key="handle.id" :id="handle.id" type="source" :position="Position.Right" :connectable="false" :style="{ top: `${(index + 1) * 100 / (outputs.length + 1)}%` }" />
    <Handle id="__boundary_binding_target__" type="target" :position="Position.Top" :connectable="false" class="binding-handle" />
    <Handle id="__boundary_binding_source__" type="source" :position="Position.Bottom" :connectable="false" class="binding-handle" />
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps({ id: String, data: Object, selected: Boolean })
const inputs = computed(() => (props.data?.config?.handles || []).filter(handle => handle.type === 'target'))
const outputs = computed(() => (props.data?.config?.handles || []).filter(handle => handle.type === 'source'))
</script>
<style scoped>
.blueprint-compact-node { width: 172px; min-height: 76px; box-sizing: border-box; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 14px; background: white; box-shadow: 0 3px 12px #0f172a0c; }
.blueprint-compact-node.selected { border-color: #2563eb; box-shadow: 0 0 0 3px #2563eb20; }
strong,small,.blueprint-compact-node>span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
strong { font-size: 13px; color: #0f172a; margin: 4px 0; } small,.blueprint-compact-node>span { font-size: 10px; color: #64748b; }
.binding-handle { opacity: 0; }
</style>
