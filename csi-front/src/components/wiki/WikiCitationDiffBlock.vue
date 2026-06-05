<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-2">
      <el-tag size="small" :type="citationTagType(item.change)">
        {{ getCitationChangeLabel(item.change) }}
      </el-tag>
      <span class="font-mono text-sm text-gray-700">{{ item.id }}</span>
    </div>
    <p v-if="item.change === 'added' && item.toItem" class="text-sm text-gray-700 m-0 whitespace-pre-wrap">
      {{ truncateText(item.toItem.text) }}
    </p>
    <p v-else-if="item.change === 'removed' && item.fromItem" class="text-sm text-gray-500 m-0 whitespace-pre-wrap line-through">
      {{ truncateText(item.fromItem.text) }}
    </p>
    <WikiTextDiffHunks v-else-if="item.textHunks?.length" :hunks="item.textHunks" />
    <p v-else class="text-sm text-gray-400 m-0">（无文本）</p>
  </div>
</template>

<script setup>
import WikiTextDiffHunks from '@/components/wiki/WikiTextDiffHunks.vue'
import { getCitationChangeLabel } from '@/utils/wikiRevisionDiffLabels.js'

/** @typedef {import('@/types/wiki.js').WikiCitationItemDiff} WikiCitationItemDiff */

defineProps({
  item: {
    /** @type {import('vue').PropType<WikiCitationItemDiff>} */
    type: Object,
    required: true,
  },
})

/**
 * @param {string} change
 */
function citationTagType(change) {
  if (change === 'added') return 'success'
  if (change === 'removed') return 'danger'
  return ''
}

/**
 * @param {string} [text]
 */
function truncateText(text) {
  if (!text) return '（空）'
  return text.length > 400 ? `${text.slice(0, 400)}…` : text
}
</script>
