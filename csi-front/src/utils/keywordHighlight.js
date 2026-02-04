export function escapeHtml(str) {
  if (str == null || typeof str !== 'string') return ''
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function escapeRegex(str) {
  if (str == null || typeof str !== 'string') return ''
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export const KEYWORD_COLOR_PALETTE = ['#e53935', '#d81b60', '#8e24aa', '#5e35b1', '#3949ab', '#1e88e5', '#00acc1', '#00897b', '#43a047', '#7cb342', '#c0ca33', '#fdd835', '#ffb300', '#fb8c00', '#f4511e', '#6d4c41']

export function getRandomKeywordColor() {
  return KEYWORD_COLOR_PALETTE[Math.floor(Math.random() * KEYWORD_COLOR_PALETTE.length)]
}

function escapeAttr(str) {
  if (str == null || typeof str !== 'string') return ''
  return str
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function buildHighlightedPlainTextHtml(content, keyword) {
  if (content == null || typeof content !== 'string') return ''
  const safe = escapeHtml(content)
  if (!keyword || typeof keyword !== 'string' || !keyword.trim()) return safe
  const escaped = escapeRegex(keyword.trim())
  const attr = escapeAttr(keyword.trim())
  const re = new RegExp(escaped, 'gi')
  return safe.replace(re, `<span class="keyword-highlight" data-keyword="${attr}">$&</span>`)
}

export function buildHighlightedPlainTextHtmlMulti(content, keywords, keywordColors = null) {
  if (content == null || typeof content !== 'string') return ''
  const safe = escapeHtml(content)
  const list = Array.isArray(keywords) ? keywords.filter((k) => k && typeof k === 'string' && k.trim()) : []
  if (!list.length) return safe
  const sorted = [...list].map((k) => k.trim()).sort((a, b) => b.length - a.length)
  const pattern = sorted.map((k) => escapeRegex(k)).join('|')
  const re = new RegExp(pattern, 'gi')
  const colors = keywordColors && typeof keywordColors === 'object' ? keywordColors : {}
  return safe.replace(re, (match) => {
    const kw = sorted.find((k) => k.toLowerCase() === match.toLowerCase())
    const attr = escapeAttr(kw || match)
    const color = kw ? colors[kw] : null
    const style = color ? ` style="background-color:${color}22"` : ''
    return `<span class="keyword-highlight" data-keyword="${attr}"${style}>${match}</span>`
  })
}

export function unwrapKeywordHighlights(containerEl) {
  if (!containerEl || !containerEl.querySelectorAll) return
  const spans = containerEl.querySelectorAll('.keyword-highlight')
  spans.forEach((span) => {
    const parent = span.parentNode
    if (!parent) return
    while (span.firstChild) {
      parent.insertBefore(span.firstChild, span)
    }
    parent.removeChild(span)
    if (parent.normalize) parent.normalize()
  })
}

export function wrapKeywordInRenderedElement(containerEl, keyword) {
  if (!containerEl || !keyword || typeof keyword !== 'string' || !keyword.trim()) return
  unwrapKeywordHighlights(containerEl)
  wrapKeywordInRenderedElementMulti(containerEl, [keyword.trim()])
}

export function wrapKeywordInRenderedElementMulti(containerEl, keywords, keywordColors = null) {
  if (!containerEl || !Array.isArray(keywords) || !keywords.length) return
  unwrapKeywordHighlights(containerEl)
  const list = keywords.map((k) => (typeof k === 'string' && k.trim()) || null).filter(Boolean)
  if (!list.length) return
  const sorted = [...list].sort((a, b) => b.length - a.length)
  const colors = keywordColors && typeof keywordColors === 'object' ? keywordColors : {}
  for (const kw of sorted) {
    const lineColor = colors[kw]
    const walker = document.createTreeWalker(containerEl, NodeFilter.SHOW_TEXT, null, false)
    const textNodes = []
    let node
    while ((node = walker.nextNode())) {
      if (node.parentNode?.closest?.('.keyword-highlight')) continue
      if (node.textContent && node.textContent.toLowerCase().includes(kw.toLowerCase())) textNodes.push(node)
    }
    textNodes.forEach((textNode) => {
      const text = textNode.textContent
      const re = new RegExp(escapeRegex(kw), 'gi')
      let lastIndex = 0
      const fragment = document.createDocumentFragment()
      let match
      while ((match = re.exec(text)) !== null) {
        if (match.index > lastIndex) {
          fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
        }
        const span = document.createElement('span')
        span.className = 'keyword-highlight'
        span.setAttribute('data-keyword', kw)
        if (lineColor) span.style.backgroundColor = lineColor + '22'
        span.textContent = match[0]
        fragment.appendChild(span)
        lastIndex = re.lastIndex
      }
      if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex)))
      }
      textNode.parentNode.replaceChild(fragment, textNode)
    })
  }
}
