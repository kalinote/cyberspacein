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

export function isSensitiveKeyword(text) {
  if (text == null || text === '') return false
  const s = String(text).toUpperCase()
  return s.includes('NSFW') || s.includes('AIGC')
}

export function getKeywordTagType(keyword, selectedKeywords) {
  if (isSensitiveKeyword(keyword)) return 'danger'
  if (Array.isArray(selectedKeywords) && selectedKeywords.includes(keyword)) return 'success'
  return 'primary'
}

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

const HIGHLIGHT_SKIP_SELECTOR = '.keyword-highlight, .entity-highlight'

function collectLayerTerms(layer) {
  if (!layer) return []
  const colors = layer.colors && typeof layer.colors === 'object' ? layer.colors : {}
  const dataAttr = layer.dataAttr || 'data-keyword'
  const highlightClass = layer.highlightClass || 'keyword-highlight'
  const terms = []

  if (Array.isArray(layer.terms)) {
    for (const t of layer.terms) {
      const matchText = t?.matchText != null ? String(t.matchText).trim() : ''
      if (!matchText) continue
      const colorKey = t.colorKey != null ? String(t.colorKey) : matchText
      const dataValue = t.dataValue != null ? String(t.dataValue) : matchText
      terms.push({
        matchText,
        dataValue,
        colorKey,
        color: colors[colorKey] || null,
        dataAttr,
        highlightClass,
      })
    }
  } else if (Array.isArray(layer.items)) {
    for (const item of layer.items) {
      const matchText = item != null ? String(item).trim() : ''
      if (!matchText) continue
      terms.push({
        matchText,
        dataValue: matchText,
        colorKey: matchText,
        color: colors[matchText] || null,
        dataAttr,
        highlightClass,
      })
    }
  }
  return terms
}

/**
 * @param {string} content
 * @param {Array<{ items?: string[], terms?: Array<{ matchText: string, dataValue?: string, colorKey?: string }>, colors?: Record<string, string>, dataAttr?: string, highlightClass?: string }>} layers
 */
export function buildHighlightedPlainTextHtmlLayers(content, layers) {
  if (content == null || typeof content !== 'string') return ''
  const safe = escapeHtml(content)
  const allTerms = (Array.isArray(layers) ? layers : []).flatMap(collectLayerTerms)
  if (!allTerms.length) return safe

  allTerms.sort((a, b) => b.matchText.length - a.matchText.length)

  const matches = []
  for (const term of allTerms) {
    const re = new RegExp(escapeRegex(term.matchText), 'gi')
    let m
    while ((m = re.exec(safe)) !== null) {
      matches.push({
        start: m.index,
        end: m.index + m[0].length,
        text: m[0],
        term,
      })
    }
  }

  if (!matches.length) return safe

  matches.sort((a, b) => a.start - b.start || b.end - b.start - (a.end - a.start))

  const filtered = []
  let lastEnd = -1
  for (const m of matches) {
    if (m.start < lastEnd) continue
    filtered.push(m)
    lastEnd = m.end
  }

  const merged = []
  for (const m of filtered) {
    const prev = merged[merged.length - 1]
    if (prev && prev.start === m.start && prev.end === m.end) {
      prev.terms.push(m.term)
    } else {
      merged.push({ start: m.start, end: m.end, text: m.text, terms: [m.term] })
    }
  }

  let result = safe
  for (let i = merged.length - 1; i >= 0; i--) {
    const { start, end, text, terms } = merged[i]
    const classes = [...new Set(terms.map((t) => t.highlightClass))].join(' ')
    const attrs = terms.map((t) => `${t.dataAttr}="${escapeAttr(t.dataValue)}"`).join(' ')
    const colorTerm = terms.find((t) => t.color)
    const style = colorTerm?.color ? ` style="background-color:${colorTerm.color}22"` : ''
    const wrap = `<span class="${classes}" ${attrs}${style}>${text}</span>`
    result = result.slice(0, start) + wrap + result.slice(end)
  }
  return result
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
  return buildHighlightedPlainTextHtmlLayers(content, [
    {
      items: keywords,
      colors: keywordColors,
      dataAttr: 'data-keyword',
      highlightClass: 'keyword-highlight',
    },
  ])
}

export function unwrapHighlightsByClass(containerEl, className) {
  if (!containerEl || !containerEl.querySelectorAll || !className) return
  const spans = containerEl.querySelectorAll(`.${className}`)
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

export function unwrapKeywordHighlights(containerEl) {
  unwrapHighlightsByClass(containerEl, 'keyword-highlight')
}

export function unwrapAllContentHighlights(containerEl) {
  unwrapHighlightsByClass(containerEl, 'keyword-highlight')
  unwrapHighlightsByClass(containerEl, 'entity-highlight')
}

function wrapTermsInRenderedElement(containerEl, terms) {
  if (!containerEl || !Array.isArray(terms) || !terms.length) return
  const sorted = [...terms].sort((a, b) => b.matchText.length - a.matchText.length)

  for (const term of sorted) {
    const { matchText, dataValue, color, dataAttr, highlightClass } = term
    const walker = document.createTreeWalker(containerEl, NodeFilter.SHOW_TEXT, null, false)
    const textNodes = []
    let node
    while ((node = walker.nextNode())) {
      if (node.parentNode?.closest?.(HIGHLIGHT_SKIP_SELECTOR)) continue
      if (node.textContent && node.textContent.toLowerCase().includes(matchText.toLowerCase())) {
        textNodes.push(node)
      }
    }
    textNodes.forEach((textNode) => {
      const text = textNode.textContent
      const re = new RegExp(escapeRegex(matchText), 'gi')
      let lastIndex = 0
      const fragment = document.createDocumentFragment()
      let match
      while ((match = re.exec(text)) !== null) {
        if (match.index > lastIndex) {
          fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
        }
        const span = document.createElement('span')
        span.className = highlightClass
        span.setAttribute(dataAttr, dataValue)
        if (color) span.style.backgroundColor = color + '22'
        span.textContent = match[0]
        fragment.appendChild(span)
        lastIndex = re.lastIndex
      }
      if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex)))
      }
      if (fragment.childNodes.length) {
        textNode.parentNode.replaceChild(fragment, textNode)
      }
    })
  }
}

/**
 * @param {HTMLElement} containerEl
 * @param {Array<{ items?: string[], terms?: Array<{ matchText: string, dataValue?: string, colorKey?: string }>, colors?: Record<string, string>, dataAttr?: string, highlightClass?: string }>} layers
 */
export function applyRenderedHighlightsMulti(containerEl, layers) {
  if (!containerEl) return
  unwrapAllContentHighlights(containerEl)
  const allTerms = (Array.isArray(layers) ? layers : []).flatMap(collectLayerTerms)
  if (!allTerms.length) return
  wrapTermsInRenderedElement(containerEl, allTerms)
}

export function wrapKeywordInRenderedElement(containerEl, keyword) {
  if (!containerEl || !keyword || typeof keyword !== 'string' || !keyword.trim()) return
  unwrapKeywordHighlights(containerEl)
  wrapKeywordInRenderedElementMulti(containerEl, [keyword.trim()])
}

export function wrapKeywordInRenderedElementMulti(containerEl, keywords, keywordColors = null) {
  if (!containerEl || !Array.isArray(keywords) || !keywords.length) return
  applyRenderedHighlightsMulti(containerEl, [
    {
      items: keywords,
      colors: keywordColors,
      dataAttr: 'data-keyword',
      highlightClass: 'keyword-highlight',
    },
  ])
}
