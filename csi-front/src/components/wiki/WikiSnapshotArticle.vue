<template>
  <div class="wiki-snapshot-article" @click="onArticleClick">
    <div v-if="page?.contentTree" class="space-y-8">
      <WikiSectionBlock :node="page.contentTree" />
      <WikiFootnotes :footnotes="page.footnotes ?? []" />
      <WikiReferences :references="page.references ?? []" />
      <section
        v-if="page.categories?.length"
        class="rounded-xl border border-gray-200 bg-gray-50/60 p-4 sm:p-5"
      >
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">标签</p>
        <div class="flex flex-wrap gap-2">
          <el-tag
            v-for="cat in page.categories"
            :key="cat"
            type="info"
            size="small"
            class="cursor-default"
          >
            {{ cat }}
          </el-tag>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import WikiFootnotes from '@/components/wiki/WikiFootnotes.vue'
import WikiReferences from '@/components/wiki/WikiReferences.vue'
import WikiSectionBlock from '@/components/wiki/WikiSectionBlock.vue'
import { provideWikiReadonlyEditor } from '@/components/wiki/wikiReadonlyEditorProvider.js'
import { handleWikiCitationClick } from '@/utils/wikiContent.js'

/** @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail */

defineProps({
  /** @type {import('vue').PropType<WikiPageDetail|null>} */
  page: {
    type: Object,
    default: null,
  },
})

provideWikiReadonlyEditor()

/**
 * @param {Event} event
 */
function onArticleClick(event) {
  handleWikiCitationClick(event)
}
</script>
