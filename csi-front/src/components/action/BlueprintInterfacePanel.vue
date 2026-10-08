<template>
  <section v-if="isMobile" class="mobile-blueprint-interfaces">
    <header><h3>公开流程接口</h3><span>{{ ports.length }} 个</span></header>
    <p v-if="!ports.length" class="empty-interfaces">添加“蓝图输入”或“蓝图输出”节点后，可配置公开接口。</p>
    <article v-for="port in ports" :key="port.nodeId"><h4>{{ port.name || '未命名接口' }}</h4><div class="interface-tags"><span>{{ port.direction === 'input' ? '输入' : '输出' }}</span><span>{{ port.dataType === 'reference' ? '引用流' : '值' }}</span></div><p v-if="port.bindingDisplay">已绑定：{{ port.bindingDisplay.targetNodeName }}</p><p v-if="port.bindingDisplay">{{ port.bindingDisplay.portDescription }}</p><p v-else>独立边界节点</p><el-button v-if="port.boundNodeId" :disabled="disabled" type="danger" plain @click="!disabled && $emit('unbind', port.nodeId)">解除绑定</el-button></article>
  </section>
  <div v-else class="border-t border-gray-200 p-4">
    <div class="mb-3 flex items-center justify-between">
      <span class="text-sm font-semibold text-gray-700">公开流程接口</span>
      <el-tag size="small" type="info">{{ ports.length }} 个</el-tag>
    </div>
    <el-empty v-if="ports.length === 0" description="拖入蓝图输入或蓝图输出节点后生成" :image-size="48" />
    <div v-else class="space-y-2">
      <div
        v-for="port in ports"
        :key="port.nodeId"
        class="flex items-center justify-between rounded border border-gray-200 px-3 py-2"
      >
        <div class="min-w-0">
          <div class="truncate text-sm text-gray-700">{{ port.name || '未命名接口' }}</div>
          <div v-if="port.bindingDisplay" class="mt-0.5 text-xs text-gray-500">
            <div class="truncate">已绑定：{{ port.bindingDisplay.targetNodeName }}</div>
            <div class="truncate text-gray-400">{{ port.bindingDisplay.portDescription }}</div>
          </div>
          <div v-else class="text-xs text-gray-400">独立边界节点</div>
        </div>
        <div class="flex items-center gap-2">
          <el-tag
            size="small"
            :type="port.dataType === 'reference' ? 'warning' : 'info'"
          >
            {{ port.dataType === 'reference' ? '引用流' : '值' }}
          </el-tag>
          <el-button
            v-if="port.boundNodeId"
            link
            type="danger"
            size="small"
            :disabled="disabled"
            @click="!disabled && $emit('unbind', port.nodeId)"
          >
            解绑
          </el-button>
          <el-tag v-if="port.boundNodeId" size="small" type="warning">已绑定</el-tag>
          <el-tag size="small" :type="port.direction === 'input' ? 'primary' : 'success'">
            {{ port.direction === 'input' ? '输入' : '输出' }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMobileViewport } from '@/composables/useMobileViewport'
const { isMobile } = useMobileViewport()
defineProps({
  disabled: { type: Boolean, default: false },
  ports: { type: Array, default: () => [] }
})
defineEmits(['unbind'])
</script>

<style scoped>
.mobile-blueprint-interfaces { display: grid; gap: 12px; }.mobile-blueprint-interfaces header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }.mobile-blueprint-interfaces h3 { font-size: 16px; font-weight: 650; }.mobile-blueprint-interfaces header span { color: #64748b; font-size: 12px; }.mobile-blueprint-interfaces article { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; }.mobile-blueprint-interfaces h4 { color: #334155; font-size: 15px; font-weight: 600; overflow-wrap: anywhere; }.mobile-blueprint-interfaces p { font-size: 12px; line-height: 1.75; color: #64748b; overflow-wrap: anywhere; margin-top: 8px; }.interface-tags { display: flex; gap: 8px; margin-top: 8px; }.interface-tags span { padding: 3px 8px; border-radius: 6px; background: #eff6ff; color: #2563eb; font-size: 11px; }.mobile-blueprint-interfaces .el-button { margin-top: 12px; min-height: 44px; width: 100%; }.empty-interfaces { padding: 24px 0; text-align: center; }
</style>
