/**
 * @typedef {import('@/types/wiki.js').WikiInfobox} WikiInfobox
 * @typedef {import('@/types/wiki.js').WikiContentNode} WikiContentNode
 * @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail
 * @typedef {import('@/types/wiki.js').WikiReference} WikiReference
 */

/**
 * @param {unknown} raw
 * @returns {WikiInfobox|null}
 */
export function normalizeWikiInfobox(raw) {
  if (!raw || typeof raw !== 'object') return null
  const caption = raw.caption != null ? String(raw.caption).trim() : ''
  if (!caption) return null

  const rows = Array.isArray(raw.rows)
    ? raw.rows
        .map((row) => ({
          label: row?.label != null ? String(row.label).trim() : '',
          value: row?.value != null ? String(row.value).trim() : '',
        }))
        .filter((row) => row.label || row.value)
    : []

  const image = raw.image != null && String(raw.image).trim() !== '' ? String(raw.image) : null

  return {
    caption,
    series: raw.series != null ? String(raw.series) : '',
    image,
    rows,
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiContentNode|null}
 */
function normalizeContentNode(raw) {
  if (!raw || typeof raw !== 'object') return null
  const section = raw.section != null ? String(raw.section) : ''
  if (!section) return null

  return {
    section,
    title: raw.title != null ? String(raw.title) : '',
    content: raw.content != null ? String(raw.content) : '',
    infobox: normalizeWikiInfobox(raw.infobox),
    children: Array.isArray(raw.children)
      ? raw.children.map((child) => normalizeContentNode(child)).filter(Boolean)
      : [],
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiReference[]}
 */
function normalizeReferences(raw) {
  if (!Array.isArray(raw)) return []
  return raw.map((ref) => ({
    id: ref?.id != null ? String(ref.id) : '',
    text: ref?.text != null ? String(ref.text) : '',
    url:
      ref?.url != null && String(ref.url).trim() !== ''
        ? String(ref.url)
        : ref?.detailPath != null && String(ref.detailPath).trim() !== ''
          ? String(ref.detailPath)
          : '',
    entityType: ref?.entityType != null ? String(ref.entityType) : null,
    entityUuid: ref?.entityUuid != null ? String(ref.entityUuid) : null,
  }))
}

/**
 * @param {unknown} raw
 * @returns {WikiPageDetail}
 */
export function normalizeWikiPageDetail(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const contentTree = normalizeContentNode(source.contentTree) || {
    section: 'main',
    title: '',
    content: '',
    infobox: null,
    children: [],
  }

  return {
    id: source.id != null ? String(source.id) : '',
    slug: source.slug != null ? String(source.slug) : '',
    title: source.title != null ? String(source.title) : '未命名条目',
    sourceNote: source.sourceNote != null ? String(source.sourceNote) : '',
    lastModified: source.lastModified != null ? String(source.lastModified) : '',
    revision: typeof source.revision === 'number' ? source.revision : Number(source.revision) || 1,
    status: source.status != null ? String(source.status) : 'draft',
    contentTree,
    footnotes: Array.isArray(source.footnotes)
      ? source.footnotes.map((n) => ({
          id: n?.id != null ? String(n.id) : '',
          text: n?.text != null ? String(n.text) : '',
        }))
      : [],
    references: normalizeReferences(source.references),
    categories: Array.isArray(source.categories) ? source.categories.map(String) : [],
    citationHealth:
      source.citationHealth && typeof source.citationHealth === 'object'
        ? source.citationHealth
        : {
            missingRefs: [],
            missingFootnotes: [],
            orphanReferences: [],
            orphanFootnotes: [],
          },
  }
}
