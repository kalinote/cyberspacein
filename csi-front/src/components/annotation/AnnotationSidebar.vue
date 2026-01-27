<template>
  <div class="annotation-sidebar bg-white border-r border-gray-200 flex flex-col h-full">
    <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
      <h3 class="text-base font-semibold text-gray-800 text-center">
        批注<span class="text-blue-500">栏</span>
      </h3>
      <div class="mt-2 text-xs text-gray-500 text-center">
        共 {{ sortedAnnotations.length }} 条批注
      </div>
    </div>
    
    <div class="flex-1 overflow-y-auto p-4 min-h-0">
      <div v-if="sortedAnnotations.length === 0" class="text-center py-12 text-gray-400">
        <Icon icon="mdi:comment-text-outline" class="text-4xl mb-2 mx-auto" />
        <p class="text-sm">暂无批注</p>
        <p class="text-xs mt-1">选择文本后添加批注</p>
      </div>
      
      <AnnotationCard
        v-for="annotation in sortedAnnotations"
        :key="annotation.id"
        :annotation="annotation"
        :is-active="activeAnnotationId === annotation.id"
        @update="handleUpdate"
        @delete="handleDelete"
        @hover="handleHover"
      />
    </div>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import AnnotationCard from './AnnotationCard.vue'

const props = defineProps({
  sortedAnnotations: {
    type: Array,
    default: () => []
  },
  activeAnnotationId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update', 'delete', 'hover'])

function handleUpdate(id, content) {
  emit('update', id, content)
}

function handleDelete(id) {
  emit('delete', id)
}

function handleHover(id, isHovering) {
  emit('hover', id, isHovering)
}
</script>

<style scoped>
.annotation-sidebar {
  width: 320px;
}
</style>
