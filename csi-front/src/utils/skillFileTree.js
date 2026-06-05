/**
 * @typedef {Object} SkillFileItem
 * @property {string} path
 * @property {string} [file_type]
 */

/**
 * @typedef {Object} SkillFileTreeNode
 * @property {string} id
 * @property {string} label
 * @property {boolean} [isFile]
 * @property {string} [path]
 * @property {string} [file_type]
 * @property {SkillFileTreeNode[]} [children]
 */

const EXT_LANGUAGE_MAP = {
  md: 'markdown',
  markdown: 'markdown',
  py: 'python',
  json: 'json',
  js: 'javascript',
  mjs: 'javascript',
  ts: 'typescript',
  yaml: 'yaml',
  yml: 'yaml',
  sh: 'shell',
  txt: 'plaintext'
}

/**
 * @param {string} path
 */
export function getMonacoLanguageByPath(path) {
  const name = (path || '').split('/').pop() || ''
  const dot = name.lastIndexOf('.')
  if (dot < 0) return 'plaintext'
  const ext = name.slice(dot + 1).toLowerCase()
  return EXT_LANGUAGE_MAP[ext] || 'plaintext'
}

/**
 * @param {string} path
 */
export function isMarkdownPath(path) {
  const name = (path || '').split('/').pop() || ''
  const lower = name.toLowerCase()
  return lower.endsWith('.md') || lower.endsWith('.markdown')
}

/**
 * @param {SkillFileItem[]} files
 * @returns {SkillFileTreeNode[]}
 */
export function buildFileTreeFromPaths(files) {
  if (!Array.isArray(files) || files.length === 0) return []

  const sorted = [...files].sort((a, b) => {
    const pa = a.path || ''
    const pb = b.path || ''
    if (pa === 'SKILL.md') return -1
    if (pb === 'SKILL.md') return 1
    return pa.localeCompare(pb)
  })

  const root = { children: new Map() }

  for (const file of sorted) {
    const path = file.path
    if (!path) continue
    const parts = path.split('/').filter(Boolean)
    let node = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isLast = i === parts.length - 1
      if (!node.children.has(part)) {
        node.children.set(part, { children: new Map(), part, isFile: isLast })
      }
      const entry = node.children.get(part)
      if (isLast) {
        entry.isFile = true
        entry.file = file
      }
      node = entry
    }
  }

  return mapToTreeNodes(root.children, '')
}

/**
 * @param {Map<string, { children: Map, part: string, isFile?: boolean, file?: SkillFileItem }>} childrenMap
 * @param {string} prefix
 * @returns {SkillFileTreeNode[]}
 */
function mapToTreeNodes(childrenMap, prefix) {
  const nodes = []
  for (const [, entry] of childrenMap) {
    const segmentPath = prefix ? `${prefix}/${entry.part}` : entry.part
    if (entry.isFile && entry.file) {
      nodes.push({
        id: entry.file.path,
        label: entry.part,
        isFile: true,
        path: entry.file.path,
        file_type: entry.file.file_type
      })
    } else {
      const childList = mapToTreeNodes(entry.children, segmentPath)
      nodes.push({
        id: segmentPath,
        label: entry.part,
        isFile: false,
        children: childList
      })
    }
  }
  return nodes
}

/**
 * @param {SkillFileTreeNode[]} tree
 * @returns {string|null}
 */
export function findDefaultFilePath(tree) {
  let skillMd = null
  let firstFile = null

  const walk = (nodes) => {
    for (const node of nodes || []) {
      if (node.isFile && node.path) {
        if (!firstFile) firstFile = node.path
        if (node.path === 'SKILL.md') skillMd = node.path
      } else if (node.children?.length) {
        walk(node.children)
      }
    }
  }

  walk(tree)
  return skillMd || firstFile
}
