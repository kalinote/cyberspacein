<template>
  <section id="notes" class="scroll-mt-24">
    <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2 mb-4">
      <h2 class="text-xl font-bold text-gray-900 flex items-center gap-2 m-0">
        <Icon icon="mdi:note-text-outline" class="text-blue-500" />
        注释
      </h2>
      <slot name="actions" />
    </div>
    <ol v-if="footnotes.length" class="wiki-notes-list">
      <li
        v-for="note in footnotes"
        :key="note.id"
        :id="`note-${note.id}`"
        class="wiki-note-item"
      >
        <span class="wiki-ref-index">{{ note.id }}.</span>
        {{ note.text }}
      </li>
    </ol>
    <p v-else class="text-sm text-gray-400 m-0">暂无注释</p>
  </section>
</template>

<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  footnotes: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.wiki-notes-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.wiki-note-item {
  display: flex;
  align-items: flex-start;
  gap: 0.25rem;
  font-size: 0.875rem;
  line-height: 1.5;
  color: #374151;
  scroll-margin-top: 6rem;
  padding: 0.25rem 0.375rem;
  border-radius: 0.375rem;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.wiki-note-item.wiki-ref-highlight {
  background-color: #eff6ff;
  box-shadow: inset 0 0 0 1px #bfdbfe;
}

.wiki-ref-index {
  flex-shrink: 0;
  font-weight: 500;
  color: #6b7280;
  min-width: 1.25rem;
}
</style>
