<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
    <h3 class="text-lg font-bold text-gray-900 mb-4">
      内容<span class="text-blue-500">批注</span>
    </h3>
    <div class="text-sm text-gray-500 mb-4">
      共 {{ sortedAnnotations.length }} 条批注
    </div>
    
    <div class="space-y-3">
      <div v-if="sortedAnnotations.length === 0" class="text-center py-8 text-gray-400">
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
</style>
