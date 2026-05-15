<template>
  <div
    v-if="html"
    class="markdown-body"
    :class="customClass"
    v-html="html"
  />
</template>

<script setup>
/**
 * Markdown 只读展示组件（基于 markdown-it + 插件，见 @/utils/markdown.js）
 *
 * 用法（在任意 Vue 页面）：
 *   import MarkdownViewer from '@/components/common/MarkdownViewer.vue'
 *   const text = '# 标题\n\n正文 **粗体**'
 *
 *   基础：        <MarkdownViewer :content="text" />
 *   附加样式：    <MarkdownViewer :content="text" custom-class="rounded-lg border p-4" />
 *   软换行：      <MarkdownViewer :content="text" :breaks="true" />
 *   允许 HTML：   <MarkdownViewer :content="text" :allow-html="true" />
 *   跳过消毒：    <MarkdownViewer :content="text" :sanitize="false" />  （仅信任内容）
 *
 * 不经过组件、直接得到 HTML：
 *   import { renderMarkdown, sanitizeHtml } from '@/utils/markdown'
 *   const html = renderMarkdown('# Hello')
 *
 * 支持：标准 MD、GFM 表格/任务列表、删除线、高亮、下划线、脚注、定义列表、缩写、
 * 上下标、Emoji、标题锚点、::: tip/warning/info/danger、代码高亮、KaTeX、外链新窗口、XSS 过滤。
 *
 * @typedef {Object} MarkdownViewerProps
 * @property {string} [content] Markdown 源文本
 * @property {boolean} [sanitize] 是否经 DOMPurify 消毒，默认 true
 * @property {boolean} [breaks] 单换行是否转为 br，默认 false
 * @property {boolean} [allowHtml] 是否允许内嵌原始 HTML，默认 false
 * @property {string} [customClass] 根节点附加 class
 */
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github.css'
import '@/assets/css/markdown.css'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  sanitize: {
    type: Boolean,
    default: true
  },
  breaks: {
    type: Boolean,
    default: false
  },
  allowHtml: {
    type: Boolean,
    default: false
  },
  customClass: {
    type: String,
    default: ''
  }
})

const html = computed(() =>
  renderMarkdown(props.content, {
    sanitize: props.sanitize,
    breaks: props.breaks,
    allowHtml: props.allowHtml
  })
)
</script>
