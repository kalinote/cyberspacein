/**
 * @typedef {import('@/types/wiki.js').WikiInfobox} WikiInfobox
 * @typedef {import('@/types/wiki.js').WikiContentNode} WikiContentNode
 * @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail
 * @typedef {import('@/types/wiki.js').WikiReference} WikiReference
 * @typedef {import('@/types/wiki.js').WikiRevisionListItem} WikiRevisionListItem
 * @typedef {import('@/types/wiki.js').WikiRevisionDetail} WikiRevisionDetail
 * @typedef {import('@/types/wiki.js').WikiTextDiffHunk} WikiTextDiffHunk
 * @typedef {import('@/types/wiki.js').WikiRevisionDiff} WikiRevisionDiff
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
    title: source.title != null ? String(source.title) : '未命名条目',
    sourceNote:
      source.sourceNote != null
        ? String(source.sourceNote)
        : source.source_note != null
          ? String(source.source_note)
          : '',
    lastModified:
      source.lastModified != null
        ? String(source.lastModified)
        : source.last_modified != null
          ? String(source.last_modified)
          : '',
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
    citationHealth: (() => {
      const raw = source.citationHealth ?? source.citation_health
      if (!raw || typeof raw !== 'object') {
        return {
          missingRefs: [],
          missingFootnotes: [],
          orphanReferences: [],
          orphanFootnotes: [],
        }
      }
      return {
        missingRefs: raw.missingRefs ?? raw.missing_refs ?? [],
        missingFootnotes: raw.missingFootnotes ?? raw.missing_footnotes ?? [],
        orphanReferences: raw.orphanReferences ?? raw.orphan_references ?? [],
        orphanFootnotes: raw.orphanFootnotes ?? raw.orphan_footnotes ?? [],
      }
    })(),
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiRevisionListItem}
 */
export function normalizeWikiRevisionListItem(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const restored =
    source.restoredFromRevision ?? source.restored_from_revision
  return {
    revision: typeof source.revision === 'number' ? source.revision : Number(source.revision) || 0,
    changeType: String(source.changeType ?? source.change_type ?? ''),
    targetSection:
      source.targetSection != null
        ? String(source.targetSection)
        : source.target_section != null
          ? String(source.target_section)
          : null,
    changeSummary: String(source.changeSummary ?? source.change_summary ?? ''),
    operator: source.operator != null ? String(source.operator) : null,
    restoredFromRevision:
      restored != null && restored !== '' ? Number(restored) : null,
    createdAt: String(source.createdAt ?? source.created_at ?? ''),
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiRevisionDetail}
 */
export function normalizeWikiRevisionDetail(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const wikiId = String(source.wikiId ?? source.wiki_id ?? '')
  const revision = typeof source.revision === 'number' ? source.revision : Number(source.revision) || 0
  const snapshotRaw =
    source.snapshot && typeof source.snapshot === 'object' ? source.snapshot : {}
  const citationHealth = source.citationHealth ?? source.citation_health

  const snapshot = normalizeWikiPageDetail({
    ...snapshotRaw,
    id: wikiId,
    revision,
    citationHealth: citationHealth ?? snapshotRaw.citationHealth ?? snapshotRaw.citation_health,
  })

  const restored =
    source.restoredFromRevision ?? source.restored_from_revision

  return {
    wikiId,
    revision,
    changeType: String(source.changeType ?? source.change_type ?? ''),
    targetSection:
      source.targetSection != null
        ? String(source.targetSection)
        : source.target_section != null
          ? String(source.target_section)
          : null,
    changeSummary: String(source.changeSummary ?? source.change_summary ?? ''),
    operator: source.operator != null ? String(source.operator) : null,
    restoredFromRevision:
      restored != null && restored !== '' ? Number(restored) : null,
    createdAt: String(source.createdAt ?? source.created_at ?? ''),
    snapshot,
    citationHealth: snapshot.citationHealth,
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiTextDiffHunk}
 */
export function normalizeWikiTextDiffHunk(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const op = String(source.op ?? 'equal')
  /** @type {'equal'|'insert'|'delete'} */
  const normalizedOp =
    op === 'insert' || op === 'delete' ? op : 'equal'
  return {
    op: normalizedOp,
    text: source.text != null ? String(source.text) : '',
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiTextDiffHunk[]|null}
 */
function normalizeHunks(raw) {
  if (!Array.isArray(raw)) return null
  return raw.map((h) => normalizeWikiTextDiffHunk(h))
}

/**
 * @param {unknown} raw
 * @returns {import('@/types/wiki.js').WikiFootnote|import('@/types/wiki.js').WikiReference|null}
 */
function normalizeDiffCitationItem(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    id: raw.id != null ? String(raw.id) : '',
    text: raw.text != null ? String(raw.text) : '',
    url:
      raw.url != null && String(raw.url).trim() !== ''
        ? String(raw.url)
        : undefined,
    entityType: raw.entityType != null ? String(raw.entityType) : null,
    entityUuid: raw.entityUuid != null ? String(raw.entityUuid) : null,
  }
}

/**
 * @param {unknown} raw
 * @returns {WikiRevisionDiff}
 */
export function normalizeWikiRevisionDiff(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const summaryRaw = source.summary && typeof source.summary === 'object' ? source.summary : {}

  const categoriesRaw = source.categories
  let categories = null
  if (categoriesRaw && typeof categoriesRaw === 'object') {
    categories = {
      added: Array.isArray(categoriesRaw.added) ? categoriesRaw.added.map(String) : [],
      removed: Array.isArray(categoriesRaw.removed) ? categoriesRaw.removed.map(String) : [],
    }
  }

  return {
    wikiId: String(source.wikiId ?? source.wiki_id ?? ''),
    fromRevision:
      typeof source.fromRevision === 'number'
        ? source.fromRevision
        : Number(source.from_revision ?? source.fromRevision) || 0,
    toRevision:
      typeof source.toRevision === 'number'
        ? source.toRevision
        : Number(source.to_revision ?? source.toRevision) || 0,
    summary: {
      sectionsAdded: Number(summaryRaw.sectionsAdded ?? summaryRaw.sections_added) || 0,
      sectionsRemoved: Number(summaryRaw.sectionsRemoved ?? summaryRaw.sections_removed) || 0,
      sectionsModified: Number(summaryRaw.sectionsModified ?? summaryRaw.sections_modified) || 0,
      sectionsMoved: Number(summaryRaw.sectionsMoved ?? summaryRaw.sections_moved) || 0,
      footnotesChanged: Number(summaryRaw.footnotesChanged ?? summaryRaw.footnotes_changed) || 0,
      referencesChanged:
        Number(summaryRaw.referencesChanged ?? summaryRaw.references_changed) || 0,
      metaChanged: Boolean(summaryRaw.metaChanged ?? summaryRaw.meta_changed),
    },
    meta: Array.isArray(source.meta)
      ? source.meta.map((item) => {
          const m = item && typeof item === 'object' ? item : {}
          return {
            field: String(m.field ?? ''),
            fromValue: m.fromValue ?? m.from_value ?? null,
            toValue: m.toValue ?? m.to_value ?? null,
            hunks: normalizeHunks(m.hunks),
          }
        })
      : [],
    categories,
    sections: Array.isArray(source.sections)
      ? source.sections.map((item) => {
          const s = item && typeof item === 'object' ? item : {}
          return {
            section: String(s.section ?? ''),
            change: String(s.change ?? 'modified'),
            pathFrom: Array.isArray(s.pathFrom)
              ? s.pathFrom.map(String)
              : Array.isArray(s.path_from)
                ? s.path_from.map(String)
                : null,
            pathTo: Array.isArray(s.pathTo)
              ? s.pathTo.map(String)
              : Array.isArray(s.path_to)
                ? s.path_to.map(String)
                : null,
            titleFrom:
              s.titleFrom != null
                ? String(s.titleFrom)
                : s.title_from != null
                  ? String(s.title_from)
                  : null,
            titleTo:
              s.titleTo != null
                ? String(s.titleTo)
                : s.title_to != null
                  ? String(s.title_to)
                  : null,
            contentHunks: normalizeHunks(s.contentHunks ?? s.content_hunks),
            infoboxChanged: Boolean(s.infoboxChanged ?? s.infobox_changed),
            infoboxFrom: normalizeWikiInfobox(s.infoboxFrom ?? s.infobox_from),
            infoboxTo: normalizeWikiInfobox(s.infoboxTo ?? s.infobox_to),
          }
        })
      : [],
    footnotes: Array.isArray(source.footnotes)
      ? source.footnotes.map((item) => {
          const f = item && typeof item === 'object' ? item : {}
          return {
            id: String(f.id ?? ''),
            change: String(f.change ?? 'modified'),
            fromItem: normalizeDiffCitationItem(f.fromItem ?? f.from_item),
            toItem: normalizeDiffCitationItem(f.toItem ?? f.to_item),
            textHunks: normalizeHunks(f.textHunks ?? f.text_hunks),
          }
        })
      : [],
    references: Array.isArray(source.references)
      ? source.references.map((item) => {
          const r = item && typeof item === 'object' ? item : {}
          return {
            id: String(r.id ?? ''),
            change: String(r.change ?? 'modified'),
            fromItem: normalizeDiffCitationItem(r.fromItem ?? r.from_item),
            toItem: normalizeDiffCitationItem(r.toItem ?? r.to_item),
            textHunks: normalizeHunks(r.textHunks ?? r.text_hunks),
          }
        })
      : [],
  }
}
