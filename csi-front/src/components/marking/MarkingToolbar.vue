<template>
  <Teleport to="body">
    <Transition name="toolbar-fade">
      <div
        v-if="visible"
        class="marking-toolbar fixed z-50 bg-white rounded-lg shadow-lg border border-gray-200 p-2 flex items-center gap-1"
        :style="{
          top: `${position.top}px`,
          left: `${position.left}px`,
          transform: 'translateX(-50%)'
        }"
        @click.stop
      >
      <button
        v-for="style in availableStyles"
        :key="style.value"
        @click="handleStyleSelect(style.value)"
        class="p-2 rounded transition-colors"
        :class="{ 
          'bg-blue-50 border border-blue-300 hover:bg-blue-100': selectedStyle === style.value,
          'hover:bg-gray-100': selectedStyle !== style.value
        }"
        :title="style.label"
      >
        <Icon :icon="style.icon" class="text-lg" />
      </button>
      <div class="w-px h-6 bg-gray-300 mx-1"></div>
      <button
        @click="handleCreate"
        class="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors text-sm font-medium"
      >
        添加批注
      </button>
      <button
        @click="handleCancel"
        class="p-2 rounded hover:bg-gray-100 transition-colors"
        title="取消"
      >
        <Icon icon="mdi:close" class="text-lg" />
      </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { Icon } from '@iconify/vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  position: {
    type: Object,
    default: () => ({ top: 0, left: 0 })
  },
  availableStyles: {
    type: Array,
    default: () => []
  },
  selectedStyle: {
    type: String,
    default: 'highlight'
  }
})

const emit = defineEmits(['style-select', 'create', 'cancel'])

function handleStyleSelect(style) {
  emit('style-select', style)
}

function handleCreate() {
  emit('create')
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.toolbar-fade-enter-active,
.toolbar-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.toolbar-fade-enter-from,
.toolbar-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}
</style>
