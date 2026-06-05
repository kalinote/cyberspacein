/**
 * @typedef {import('@/types/wiki.js').WikiInfobox} WikiInfobox
 * @typedef {Object} WikiContentNode
 * @property {string} section - 小节锚点 id（由后端生成并返回）
 * @property {string} [title]
 * @property {string} [content]
 * @property {WikiInfobox|null} [infobox]
 * @property {WikiContentNode[]} [children]
 */

/**
 * @typedef {Object} WikiTocItem
 * @property {string} id
 * @property {string} title
 * @property {number} level
 * @property {string} [number]
 * @property {WikiTocItem[]} [children]
 */

/**
 * 将 [^1] / [^a] 转为可点击上标链接（注释走 note-，参考资料走 ref-）
 * @param {string} content
 * @returns {string}
 */
export function linkifyWikiCitations(content) {
  if (!content) return ''
  return content.replace(/\[\^([^\]]+)\]/g, (_, rawId) => {
    const id = String(rawId).trim()
    const isNote = /^[a-z]$/i.test(id)
    const anchor = isNote ? `note-${id}` : `ref-${id}`
    return `<sup class="wiki-cite"><a href="#${anchor}" class="wiki-cite-link" data-wiki-target="${anchor}">[${id}]</a></sup>`
  })
}

/**
 * @param {WikiContentNode} node
 * @param {number} [depth]
 * @returns {{ id: string, title: string, level: number }[]}
 */
export function flattenWikiSectionNodes(node, depth = 0) {
  const list = []
  if (node?.section && node.section !== 'main' && node.title) {
    list.push({
      id: node.section,
      title: node.title,
      level: Math.min(depth + 2, 6),
    })
  }
  for (const child of node?.children || []) {
    list.push(...flattenWikiSectionNodes(child, depth + 1))
  }
  return list
}

/**
 * @param {WikiContentNode[]} nodes
 * @param {string} [parentNumber]
 * @param {number} [depth]
 * @returns {WikiTocItem[]}
 */
function mapContentNodesToTocItems(nodes, parentNumber = '', depth = 0) {
  const items = []
  let index = 0
  for (const node of nodes || []) {
    if (!node?.title) continue
    index += 1
    const number = parentNumber ? `${parentNumber}.${index}` : String(index)
    const childItems = mapContentNodesToTocItems(node.children || [], number, depth + 1)
    items.push({
      id: node.section,
      title: node.title,
      level: Math.min(depth + 2, 6),
      number,
      children: childItems.length ? childItems : undefined,
    })
  }
  return items
}

/**
 * @param {WikiContentNode} root
 * @returns {WikiTocItem[]}
 */
export function buildTocFromContentTree(root) {
  const groups = root?.children || []
  const topLevelCount = groups.filter((g) => g?.title).length
  const items = mapContentNodesToTocItems(groups)

  items.push(
    { id: 'notes', title: '注释', level: 2, number: String(topLevelCount + 1) },
    { id: 'references', title: '参考资料', level: 2, number: String(topLevelCount + 2) }
  )
  return items
}

/**
 * @param {string} targetId
 * @param {HTMLElement|null} [citeEl]
 */
export function scrollToWikiCitationTarget(targetId, citeEl = null) {
  document.querySelectorAll('.wiki-ref-highlight').forEach((el) => {
    el.classList.remove('wiki-ref-highlight')
  })
  document.querySelectorAll('.wiki-cite-link.is-active').forEach((el) => {
    el.classList.remove('is-active')
  })

  const target = document.getElementById(targetId)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    target.classList.add('wiki-ref-highlight')
    window.setTimeout(() => {
      target.classList.remove('wiki-ref-highlight')
    }, 2800)
  }
  if (citeEl) {
    citeEl.classList.add('is-active')
  }
}

/**
 * @param {Event} event
 */
export function handleWikiCitationClick(event) {
  const link = event.target instanceof Element ? event.target.closest('.wiki-cite-link') : null
  if (!link || !(link instanceof HTMLAnchorElement)) return false
  const targetId = link.dataset.wikiTarget
  if (!targetId) return false
  event.preventDefault()
  scrollToWikiCitationTarget(targetId, link)
  return true
}
