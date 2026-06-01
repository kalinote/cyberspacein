/** @typedef {import('@/types/wiki.js').WikiRevisionDiff} WikiRevisionDiff */

/** @type {Record<string, string>} */
export const SECTION_CHANGE_LABELS = {
  added: '新增',
  removed: '删除',
  modified: '修改',
  moved: '移动',
}

/** @type {Record<string, string>} */
export const CITATION_CHANGE_LABELS = {
  added: '新增',
  removed: '删除',
  modified: '修改',
}

/** @type {Record<string, string>} */
export const META_FIELD_LABELS = {
  title: '标题',
  sourceNote: '来源说明',
  status: '状态',
}

/**
 * @param {string} change
 */
export function getSectionChangeLabel(change) {
  return SECTION_CHANGE_LABELS[change] || change || '—'
}

/**
 * @param {string} change
 */
export function getCitationChangeLabel(change) {
  return CITATION_CHANGE_LABELS[change] || change || '—'
}

/**
 * @param {string} field
 */
export function getMetaFieldLabel(field) {
  return META_FIELD_LABELS[field] || field || '—'
}

/**
 * @param {string[]|null|undefined} path
 */
export function formatSectionPath(path) {
  if (!path?.length) return '（根级）'
  return path.join(' › ')
}

/**
 * @param {unknown} value
 */
export function formatScalarValue(value) {
  if (value == null || value === '') return '（空）'
  return String(value)
}

/**
 * @param {WikiRevisionDiff|null|undefined} diff
 */
export function isDiffEmpty(diff) {
  if (!diff) return true
  const s = diff.summary
  const noSummary =
    !s.metaChanged &&
    s.sectionsAdded === 0 &&
    s.sectionsRemoved === 0 &&
    s.sectionsModified === 0 &&
    s.sectionsMoved === 0 &&
    s.footnotesChanged === 0 &&
    s.referencesChanged === 0
  const noLists =
    diff.meta.length === 0 &&
    !diff.categories &&
    diff.sections.length === 0 &&
    diff.footnotes.length === 0 &&
    diff.references.length === 0
  return noSummary && noLists
}
