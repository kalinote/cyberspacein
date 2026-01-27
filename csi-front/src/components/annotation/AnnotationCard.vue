<template>
  <div
    class="annotation-card bg-white rounded-lg border border-gray-200 p-4 mb-3 shadow-sm hover:shadow-md transition-shadow"
    :class="{ 'border-blue-300 bg-blue-50': isActive }"
    :data-annotation-id="annotation.id"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <div class="flex items-start justify-between mb-2">
      <div class="flex items-center gap-2">
        <Icon :icon="getStyleIcon(annotation.style)" class="text-lg" :style="{ color: getStyleColor(annotation.style) }" />
        <span class="text-xs text-gray-500">{{ formatDate(annotation.createdAt) }}</span>
      </div>
      <button
        @click="handleDelete"
        class="p-1 rounded hover:bg-gray-200 transition-colors text-gray-400 hover:text-red-600"
        title="删除批注"
      >
        <Icon icon="mdi:delete-outline" class="text-sm" />
      </button>
    </div>
    
    <div class="mb-2">
      <div class="text-xs text-gray-600 mb-1 line-clamp-2">
        {{ getTargetText() }}
      </div>
    </div>

    <div class="annotation-content">
      <textarea
        v-if="isEditing"
        v-model="editContent"
        @blur="handleSave"
        @keydown.ctrl.enter="handleSave"
        @keydown.esc="handleCancel"
        class="w-full p-2 border border-gray-300 rounded text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        rows="3"
        placeholder="输入批注内容..."
      />
      <div
        v-else
        @click="handleEdit"
        class="p-2 border border-transparent rounded text-sm min-h-[60px] cursor-text hover:border-gray-300 transition-colors"
        :class="{ 'text-gray-400': !annotation.content }"
      >
        {{ annotation.content || '点击编辑批注...' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { getStyleColor, getStyleIcon } from '@/utils/annotationStyles'

const props = defineProps({
  annotation: {
    type: Object,
    required: true
  },
  isActive: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update', 'delete', 'hover'])

const isEditing = ref(false)
const editContent = ref('')

function handleEdit() {
  isEditing.value = true
  editContent.value = props.annotation.content || ''
  setTimeout(() => {
    const textarea = document.querySelector('.annotation-content textarea')
    if (textarea) {
      textarea.focus()
    }
  }, 0)
}

function handleSave() {
  if (editContent.value !== props.annotation.content) {
    emit('update', props.annotation.id, editContent.value)
  }
  isEditing.value = false
}

function handleCancel() {
  editContent.value = props.annotation.content || ''
  isEditing.value = false
}

function handleDelete() {
  emit('delete', props.annotation.id)
}

function handleMouseEnter() {
  emit('hover', props.annotation.id, true)
}

function handleMouseLeave() {
  emit('hover', props.annotation.id, false)
}

function formatDate(date) {
  if (!date) return ''
  const d = new Date(date)
  const now = new Date()
  const diff = now - d
  const minutes = Math.floor(diff / 60000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  return d.toLocaleDateString('zh-CN')
}

function getTargetText() {
  const { target } = props.annotation
  if (target.textOffset) {
    return target.textOffset.text || ''
  }
  if (target.spanId) {
    const element = document.getElementById(target.spanId)
    return element ? element.textContent || '' : ''
  }
  return ''
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
