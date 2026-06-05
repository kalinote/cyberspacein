/** @typedef {import('@/types/wiki.js').WikiRevisionListItem} WikiRevisionListItem */

/** @type {Record<string, string>} */
export const WIKI_CHANGE_TYPE_LABELS = {
  create: '创建',
  meta: '元数据',
  main: '导语',
  section: '章节',
  structure: '目录结构',
  footnotes: '注释',
  references: '参考资料',
  restore: '恢复版本',
}

/**
 * @param {string} [changeType]
 */
export function getWikiChangeTypeLabel(changeType) {
  if (!changeType) return '—'
  return WIKI_CHANGE_TYPE_LABELS[changeType] || changeType
}

/**
 * @param {WikiRevisionListItem|{ changeSummary?: string, targetSection?: string|null, restoredFromRevision?: number|null, changeType?: string }} item
 */
export function formatWikiRevisionSummary(item) {
  const parts = []
  const summary = item.changeSummary?.trim()
  if (summary) parts.push(summary)
  if (item.targetSection) parts.push(`章节 ${item.targetSection}`)
  if (item.changeType === 'restore' && item.restoredFromRevision != null) {
    parts.push(`自第 ${item.restoredFromRevision} 版恢复`)
  }
  return parts.length ? parts.join(' · ') : '—'
}
