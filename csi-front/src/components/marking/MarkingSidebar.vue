<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
    <h3 class="text-lg font-bold text-gray-900 mb-4">
      内容<span class="text-blue-500">标注</span>
    </h3>
    <div class="text-sm text-gray-500 mb-4">
      共 {{ sortedMarkings.length }} 条标注
    </div>
    
    <div class="space-y-3">
      <div v-if="sortedMarkings.length === 0" class="text-center py-8 text-gray-400">
        <Icon icon="mdi:comment-text-outline" class="text-4xl mb-2 mx-auto" />
        <p class="text-sm">暂无标注</p>
        <p class="text-xs mt-1">选择文本后添加标注</p>
      </div>
      
      <MarkingCard
        v-for="marking in sortedMarkings"
        :key="marking.id"
        :marking="marking"
        :is-active="activeMarkingId === marking.id"
        @update="handleUpdate"
        @delete="handleDelete"
        @hover="handleHover"
      />
    </div>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import MarkingCard from './MarkingCard.vue'

const props = defineProps({
  sortedMarkings: {
    type: Array,
    default: () => []
  },
  activeMarkingId: {
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
