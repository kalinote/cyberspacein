<template>
  <nav class="wiki-toc" aria-label="目录">
    <WikiTocItems
      :items="items"
      :active-id="activeId"
      @navigate="onNavigate"
    />
  </nav>
</template>

<script setup>
import WikiTocItems from '@/components/wiki/WikiTocItems.vue'

defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  activeId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['navigate'])

function onNavigate(id) {
  emit('navigate', id)
}
</script>
