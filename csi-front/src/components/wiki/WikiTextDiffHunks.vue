<template>
  <span v-if="hunks?.length" class="wiki-text-diff-hunks whitespace-pre-wrap font-mono text-sm leading-relaxed">
    <span
      v-for="(hunk, index) in hunks"
      :key="index"
      :class="hunkClass(hunk.op)"
    >{{ hunk.text }}</span>
  </span>
  <span v-else class="text-gray-400 text-sm">（无文本差异）</span>
</template>

<script setup>
/** @typedef {import('@/types/wiki.js').WikiTextDiffHunk} WikiTextDiffHunk */

defineProps({
  hunks: {
    /** @type {import('vue').PropType<WikiTextDiffHunk[]|null|undefined>} */
    type: Array,
    default: null,
  },
})

/**
 * @param {string} op
 */
function hunkClass(op) {
  if (op === 'insert') {
    return 'bg-green-100 text-green-900 rounded-sm px-0.5'
  }
  if (op === 'delete') {
    return 'bg-red-100 text-red-800 line-through rounded-sm px-0.5'
  }
  return 'text-gray-800'
}
</script>
