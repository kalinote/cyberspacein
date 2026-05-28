<template>
  <div
    v-if="html"
    class="markdown-body wiki-markdown"
    :class="customClass"
    v-html="html"
  />
</template>

<script setup>
import { computed } from 'vue'
import { linkifyWikiCitations } from '@/utils/wikiContent'
import { renderMarkdown } from '@/utils/markdown'
import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github.css'
import '@/assets/css/markdown.css'

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
  customClass: {
    type: String,
    default: '',
  },
})

const html = computed(() =>
  renderMarkdown(linkifyWikiCitations(props.content), {
    sanitize: true,
    breaks: false,
    allowHtml: true,
  })
)
</script>
