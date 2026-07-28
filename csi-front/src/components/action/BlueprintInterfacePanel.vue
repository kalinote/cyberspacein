<template>
  <div class="border-t border-gray-200 p-4">
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
            @click="$emit('unbind', port.nodeId)"
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
defineProps({
  ports: { type: Array, default: () => [] }
})
defineEmits(['unbind'])
</script>
