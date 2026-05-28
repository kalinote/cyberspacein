<template>
  <ul :class="depth === 0 ? 'space-y-0.5 text-sm' : 'mt-0.5 ml-1 border-l border-gray-100'">
    <li v-for="item in items" :key="item.id">
      <a
        :href="`#${item.id}`"
        class="block py-1.5 rounded-lg transition-colors"
        :class="[
          depth === 0 ? 'px-2.5' : 'pr-2.5',
          linkClass(item.id, depth > 0),
        ]"
        :style="depth > 0 ? { paddingLeft: `${1 + depth * 0.75}rem` } : undefined"
        @click.prevent="emit('navigate', item.id)"
      >
        {{ item.number ? `${item.number} ` : '' }}{{ item.title }}
      </a>
      <WikiTocItems
        v-if="item.children?.length"
        :items="item.children"
        :active-id="activeId"
        :depth="depth + 1"
        @navigate="emit('navigate', $event)"
      />
    </li>
  </ul>
</template>

<script setup>
import WikiTocItems from '@/components/wiki/WikiTocItems.vue'

defineOptions({ name: 'WikiTocItems' })

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  activeId: {
    type: String,
    default: '',
  },
  depth: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['navigate'])

function linkClass(id, isNested) {
  if (props.activeId === id) {
    return 'bg-blue-50 text-blue-600 font-medium border border-blue-200 shadow-sm'
  }
  return isNested
    ? 'text-gray-600 hover:bg-gray-50 hover:text-blue-600'
    : 'text-gray-800 font-medium hover:bg-gray-50 hover:text-blue-600'
}
</script>
