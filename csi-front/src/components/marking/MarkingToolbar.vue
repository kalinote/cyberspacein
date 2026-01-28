<template>
  <Teleport to="body">
    <Transition name="toolbar-fade">
      <div
        v-if="visible"
        ref="toolbarRef"
        class="marking-toolbar fixed z-50 bg-white rounded-md shadow-lg border border-gray-200 px-1.5 py-1 flex items-center gap-0.5"
        :style="{
          top: `${position.top}px`,
          left: `${position.left}px`,
          transform: 'translateX(-50%)'
        }"
        @mousedown.stop
      >
      <button
        v-for="style in availableStyles"
        :key="style.value"
        @click="handleStyleSelect(style.value)"
        class="p-1 rounded transition-colors"
        :class="{ 
          'bg-blue-50 border border-blue-300 hover:bg-blue-100': selectedStyle === style.value,
          'hover:bg-gray-100': selectedStyle !== style.value
        }"
        :title="style.label"
      >
        <Icon :icon="style.icon" class="text-lg" />
      </button>
      <div class="w-px h-5 bg-gray-300 mx-0.5"></div>
      <button
        @click="handleCreate"
        class="px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-700 transition-colors text-xs font-medium"
      >
        添加批注
      </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
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

const emit = defineEmits(['style-select', 'create'])

const toolbarRef = ref(null)

function handleStyleSelect(style) {
  emit('style-select', style)
}

function handleCreate() {
  emit('create')
}

defineExpose({
  toolbarRef
})
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
