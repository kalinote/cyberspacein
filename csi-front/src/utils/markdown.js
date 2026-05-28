/**
 * Markdown 渲染工具（markdown-it + 插件链）
 *
 * 用法：
 * ```js
 * import { renderMarkdown, createMarkdownRenderer, sanitizeHtml } from '@/utils/markdown'
 *
 * // 推荐：一行得到消毒后的 HTML
 * const html = renderMarkdown('# 标题\n\n正文')
 *
 * // 自定义渲染选项（会按选项缓存实例）
 * const html2 = renderMarkdown(src, {
 *   breaks: true,       // 单换行 -> <br>
 *   allowHtml: false,   // 是否解析内嵌 HTML，默认 false
 *   sanitize: true      // 是否 DOMPurify，默认 true
 * })
 *
 * // 单独消毒（浏览器环境）
 * const safe = sanitizeHtml(rawHtml)
 *
 * // 复用自定义 markdown-it 实例
 * const md = createMarkdownRenderer({ linkify: true })
 * const raw = md.render(src)
 * ```
 *
 * 插件：multimd-table、task-lists（只读）、footnote、deflist、abbr、sub/sup、
 * ins/mark、emoji、container(tip/warning/info/danger)、anchor、外链属性、
 * highlightjs（完整 highlight.js）、katex（$...$ / $$...$$）。
 * 删除线 ~~text~~ 由 markdown-it 14 内置支持。
 *
 * 展示请优先使用 @/components/common/MarkdownViewer.vue。
 */
import MarkdownIt from 'markdown-it'
import multimdTable from 'markdown-it-multimd-table'
import taskLists from 'markdown-it-task-lists'
import footnote from 'markdown-it-footnote'
import deflist from 'markdown-it-deflist'
import abbr from 'markdown-it-abbr'
import sub from 'markdown-it-sub'
import sup from 'markdown-it-sup'
import ins from 'markdown-it-ins'
import mark from 'markdown-it-mark'
import emoji from 'markdown-it-emoji/lib/full.mjs'
import container from 'markdown-it-container'
import anchor from 'markdown-it-anchor'
import linkAttributes from 'markdown-it-link-attributes'
import highlightjs from 'markdown-it-highlightjs'
import { katex } from '@mdit/plugin-katex'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

const CONTAINER_TYPES = ['tip', 'warning', 'info', 'danger']

/** @type {Map<string, import('markdown-it').default>} */
const rendererCache = new Map()

const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'del', 'dd', 'div', 'dl', 'dt',
    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'input', 'ins', 'kbd', 'li', 'mark', 'ol',
    'p', 'pre', 's', 'section', 'span', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
    'thead', 'tr', 'ul'
  ],
  ALLOWED_ATTR: [
    'href', 'title', 'target', 'rel', 'id', 'class', 'type', 'disabled', 'checked', 'aria-hidden',
    'colspan', 'rowspan', 'align', 'style', 'data-wiki-target'
  ],
  ALLOW_DATA_ATTR: true
}

function containerValidate(name) {
  return (params) => new RegExp(`^${name}\\s*(.*)$`).test(params.trim())
}

function containerRender(name) {
  return (tokens, idx) => {
    if (tokens[idx].nesting === 1) {
      return `<div class="markdown-container markdown-container-${name}">\n`
    }
    return '</div>\n'
  }
}

/**
 * @typedef {Object} MarkdownRendererOptions
 * @property {boolean} [html=false]
 * @property {boolean} [breaks=false]
 * @property {boolean} [linkify=true]
 * @property {boolean} [allowHtml=false]
 */

/**
 * @param {MarkdownRendererOptions} [options]
 * @returns {import('markdown-it').default}
 */
export function createMarkdownRenderer(options = {}) {
  const {
    html = false,
    breaks = false,
    linkify = true,
    allowHtml = false
  } = options

  const md = new MarkdownIt({
    html: allowHtml || html,
    linkify,
    breaks,
    typographer: true
  })

  md.use(multimdTable, {
    multiline: true,
    rowspan: true,
    headerless: true
  })
  md.use(taskLists, { enabled: false, label: true, labelAfter: false })
  md.use(footnote)
  md.use(deflist)
  md.use(abbr)
  md.use(sub)
  md.use(sup)
  md.use(ins)
  md.use(mark)
  md.use(emoji)
  for (const name of CONTAINER_TYPES) {
    md.use(container, name, {
      validate: containerValidate(name),
      render: containerRender(name)
    })
  }
  md.use(anchor, {
    permalink: false,
    tabIndex: false
  })
  md.use(linkAttributes, {
    matcher(href) {
      return /^https?:\/\//i.test(href) || href.startsWith('//')
    },
    attrs: {
      target: '_blank',
      rel: 'noopener noreferrer'
    }
  })
  md.use(highlightjs, {
    hljs,
    auto: true,
    code: true,
    inline: false,
    ignoreIllegals: true
  })
  md.use(katex, {
    delimiters: 'dollars',
    throwOnError: false
  })

  return md
}

/**
 * @param {MarkdownRendererOptions} options
 */
function getRendererKey(options) {
  return JSON.stringify({
    html: options.html ?? false,
    breaks: options.breaks ?? false,
    linkify: options.linkify ?? true,
    allowHtml: options.allowHtml ?? false
  })
}

/**
 * @param {MarkdownRendererOptions} [options]
 * @returns {import('markdown-it').default}
 */
function getRenderer(options = {}) {
  const key = getRendererKey(options)
  if (!rendererCache.has(key)) {
    rendererCache.set(key, createMarkdownRenderer(options))
  }
  return rendererCache.get(key)
}

/**
 * @param {string} html
 * @returns {string}
 */
export function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, PURIFY_CONFIG)
}

/**
 * @typedef {MarkdownRendererOptions & { sanitize?: boolean }} RenderMarkdownOptions
 */

/**
 * @param {string} src
 * @param {RenderMarkdownOptions} [options]
 * @returns {string}
 */
export function renderMarkdown(src, options = {}) {
  const { sanitize = true, ...rendererOptions } = options
  const md = getRenderer(rendererOptions)
  const html = md.render(src ?? '')
  return sanitize ? sanitizeHtml(html) : html
}
