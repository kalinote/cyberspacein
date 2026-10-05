<template>
  <div class="evidence-node" :class="{ selected, inherited: data.inherited }" :style="{ '--node-color': info.color }">
    <Handle type="target" :position="Position.Left" :is-connectable="connectable" />
    <div class="node-type"><Icon :icon="info.icon" /><span>{{ info.label }}</span><span v-if="data.inherited" class="ml-auto">引用内</span></div>
    <div class="node-label">{{ data.node.label }}</div>
    <div v-if="data.node.description" class="node-description">{{ data.node.description }}</div>
    <div class="node-footer"><span v-if="data.node.kind === 'versions'">全部版本 · 动态查询</span><span v-else-if="data.node.kind === 'collection'">{{ data.node.members.length }} 个固定成员</span><span v-else-if="data.node.kind === 'chain'">{{ data.resolved?.chain?.nodes.length ?? '—' }} 个节点 · 实时引用</span><span v-else-if="data.node.kind === 'entity'">{{ data.node.entity.entity_type }} · {{ data.resolved?.items?.[0]?.missing ? '源数据缺失' : '确定版本' }}</span><span v-else>人工定义</span><span v-if="data.expanded">已展开</span></div>
    <Handle type="source" :position="Position.Right" :is-connectable="connectable" />
  </div>
</template>
<script setup>
import { computed } from 'vue';
import { Handle, Position } from '@vue-flow/core';
import { Icon } from '@iconify/vue';
import { NODE_KINDS } from '@/utils/evidence';
const props = defineProps({
  data: {
    type: Object,
    required: true
  },
  selected: Boolean,
  connectable: {
    type: Boolean,
    default: true
  }
});
const info = computed(() => NODE_KINDS[props.data.node.kind] || NODE_KINDS.note);
</script>
<style scoped>
.evidence-node{width:248px;min-height:108px;background:#fff;border:1px solid #e2e8f0;border-top:3px solid var(--node-color);border-radius:12px;box-shadow:0 3px 12px #1e293b08;padding:13px 15px;cursor:pointer}.evidence-node.selected{outline:2px solid var(--node-color);outline-offset:3px}.evidence-node.inherited{background:#f8fafc;border-style:dashed}.node-type{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--node-color);margin-bottom:8px}.node-label{font-size:14px;font-weight:600;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}.node-description{color:#64748b;font-size:11px;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.node-footer{display:flex;justify-content:space-between;gap:6px;margin-top:12px;font-size:10px;color:#94a3b8}:deep(.vue-flow__handle){width:10px;height:10px;background:var(--node-color);border:2px solid white}
</style>
