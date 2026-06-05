/**
 * @typedef {import('@/utils/wikiContent.js').WikiContentNode} WikiContentNode
 * @typedef {import('@/types/wiki.js').WikiInfobox} WikiInfobox
 */

/**
 * @param {WikiInfobox|null|undefined} infobox
 * @returns {WikiInfobox|null}
 */
export function cloneWikiInfobox(infobox) {
  if (!infobox) return null
  return {
    caption: infobox.caption ?? '',
    series: infobox.series ?? '',
    image: infobox.image ?? null,
    rows: Array.isArray(infobox.rows)
      ? infobox.rows.map((row) => ({
          label: row?.label ?? '',
          value: row?.value ?? '',
        }))
      : [],
  }
}

/**
 * @param {WikiContentNode|null|undefined} node
 * @returns {WikiContentNode|null}
 */
export function cloneWikiTree(node) {
  if (!node || typeof node !== 'object') return null
  return {
    section: node.section,
    title: node.title != null ? String(node.title) : '',
    content: node.content != null ? String(node.content) : '',
    infobox: cloneWikiInfobox(node.infobox),
    children: Array.isArray(node.children)
      ? node.children.map((child) => cloneWikiTree(child)).filter(Boolean)
      : [],
  }
}

/**
 * @param {WikiContentNode|null|undefined} root
 * @returns {Set<string>}
 */
export function collectSectionIds(root) {
  const ids = new Set()
  /** @param {WikiContentNode|null|undefined} n */
  function walk(n) {
    if (!n) return
    if (n.section) ids.add(n.section)
    for (const child of n.children || []) walk(child)
  }
  walk(root)
  return ids
}

/**
 * 根据标题生成临时章节 id（仅用于目录编辑器本地占位，保存后以接口返回的 section 为准）。
 * @param {string} title
 * @param {Set<string>|string[]} existingIds
 * @returns {string}
 */
export function generateSectionId(title, existingIds) {
  const ids = existingIds instanceof Set ? existingIds : new Set(existingIds)
  let base = String(title || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fff-]/g, '')
  if (!base) base = 'section'
  let id = base
  let n = 1
  while (ids.has(id)) {
    id = `${base}-${n}`
    n += 1
  }
  return id
}

/**
 * @param {WikiContentNode|null|undefined} root
 * @param {string} sectionId
 * @returns {WikiContentNode|null}
 */
export function findWikiNode(root, sectionId) {
  if (!root) return null
  if (root.section === sectionId) return root
  for (const child of root.children || []) {
    const found = findWikiNode(child, sectionId)
    if (found) return found
  }
  return null
}

/**
 * @param {WikiContentNode|null|undefined} root
 * @param {string} sectionId
 * @returns {WikiContentNode|null}
 */
export function findWikiParent(root, sectionId) {
  if (!root || sectionId === 'main') return null
  for (const child of root.children || []) {
    if (child.section === sectionId) return root
    const found = findWikiParent(child, sectionId)
    if (found) return found
  }
  return null
}

/**
 * @param {WikiContentNode} root
 * @param {string} sectionId
 * @param {string} content
 * @returns {WikiContentNode}
 */
export function updateNodeContent(root, sectionId, content) {
  const clone = cloneWikiTree(root)
  if (!clone) return root
  const node = findWikiNode(clone, sectionId)
  if (node) node.content = content
  return clone
}

/**
 * @param {WikiContentNode} root
 * @param {string} sectionId
 * @param {WikiInfobox|null} infobox
 * @returns {WikiContentNode}
 */
export function updateNodeInfobox(root, sectionId, infobox) {
  const clone = cloneWikiTree(root)
  if (!clone) return root
  const node = findWikiNode(clone, sectionId)
  if (node) node.infobox = infobox ? cloneWikiInfobox(infobox) : null
  return clone
}

/**
 * @param {WikiContentNode} root
 * @param {WikiContentNode[]} children
 * @returns {WikiContentNode}
 */
export function setContentTreeChildren(root, children) {
  const clone = cloneWikiTree(root)
  if (!clone) return root
  clone.children = children.map((child) => cloneWikiTree(child)).filter(Boolean)
  return clone
}

/**
 * @param {WikiContentNode} root
 * @param {string} sectionId
 * @returns {WikiContentNode}
 */
export function removeNode(root, sectionId) {
  if (sectionId === 'main') return root
  const clone = cloneWikiTree(root)
  if (!clone) return root

  /** @param {WikiContentNode} parent */
  function removeFrom(parent) {
    if (!Array.isArray(parent.children)) return false
    const idx = parent.children.findIndex((c) => c.section === sectionId)
    if (idx >= 0) {
      parent.children.splice(idx, 1)
      return true
    }
    for (const child of parent.children) {
      if (removeFrom(child)) return true
    }
    return false
  }

  removeFrom(clone)
  return clone
}

/**
 * 新建章节节点（临时 section，保存目录后由后端分配正式 section）。
 * @param {string} [title]
 * @param {Set<string>|string[]} existingIds
 * @returns {WikiContentNode}
 */
export function createEmptySectionNode(title = '新章节', existingIds = new Set()) {
  const ids = existingIds instanceof Set ? existingIds : new Set(existingIds)
  const sectionTitle = String(title).trim() || '新章节'
  return {
    section: generateSectionId(sectionTitle, ids),
    title: sectionTitle,
    content: '',
    infobox: null,
    children: [],
  }
}

/**
 * 应用目录结构时保留已有章节的正文与信息框（新建节点无 content）。
 * @param {WikiContentNode[]} nextChildren
 * @param {WikiContentNode[]} prevChildren
 * @returns {WikiContentNode[]}
 */
export function mergePreservedSectionContent(nextChildren, prevChildren) {
  /** @type {Map<string, WikiContentNode>} */
  const prevBySection = new Map()
  /** @param {WikiContentNode[]} nodes */
  function index(nodes) {
    for (const n of nodes || []) {
      if (n.section) prevBySection.set(n.section, n)
      index(n.children)
    }
  }
  index(prevChildren)

  /** @param {WikiContentNode[]} nodes */
  function merge(nodes) {
    return (nodes || []).map((node) => {
      const prev = prevBySection.get(node.section)
      const hasContent = String(node.content ?? '').trim() !== ''
      const hasInfobox = Boolean(node.infobox)
      return {
        section: node.section,
        title: node.title ?? '',
        content: hasContent ? String(node.content) : String(prev?.content ?? ''),
        infobox: hasInfobox ? cloneWikiInfobox(node.infobox) : cloneWikiInfobox(prev?.infobox),
        children: merge(node.children || []),
      }
    })
  }

  return merge(nextChildren)
}

/**
 * @returns {WikiInfobox}
 */
export function createEmptyInfobox() {
  return {
    caption: '新信息框',
    series: '',
    image: null,
    rows: [{ label: '', value: '' }],
  }
}

/**
 * @typedef {Object} WikiTocTreeNode
 * @property {string} id
 * @property {string} label
 * @property {string} section
 * @property {string} title
 * @property {string} content
 * @property {WikiInfobox|null} infobox
 * @property {string} [number]
 * @property {WikiTocTreeNode[]} [children]
 */

/**
 * 与 WikiSectionBlock / buildTocFromContentTree 一致：按树顺序生成 1、1.1、1.2…
 * @param {WikiTocTreeNode[]} nodes
 * @param {string} [parentNumber]
 */
export function syncWikiTocTreeNumbers(nodes, parentNumber = '') {
  ;(nodes || []).forEach((node, index) => {
    const childIndex = index + 1
    node.number = parentNumber ? `${parentNumber}.${childIndex}` : String(childIndex)
    if (node.children?.length) {
      syncWikiTocTreeNumbers(node.children, node.number)
    }
  })
}

/**
 * @param {WikiContentNode[]} children
 * @returns {WikiTocTreeNode[]}
 */
export function contentChildrenToTreeNodes(children) {
  return (children || []).map((node) => ({
    id: node.section,
    label: node.title || node.section,
    section: node.section,
    title: node.title || '',
    content: node.content || '',
    infobox: cloneWikiInfobox(node.infobox),
    children:
      node.children?.length > 0 ? contentChildrenToTreeNodes(node.children) : undefined,
  }))
}

/**
 * @param {WikiTocTreeNode[]} nodes
 * @returns {WikiContentNode[]}
 */
export function treeNodesToContentChildren(nodes) {
  return (nodes || []).map((node) => ({
    section: node.section || node.id,
    title: node.title || node.label || '',
    content: node.content != null ? String(node.content) : '',
    infobox: cloneWikiInfobox(node.infobox),
    children: treeNodesToContentChildren(node.children || []),
  }))
}
