import { request } from '@/utils/request'
import {
  normalizeWikiPageDetail,
  normalizeWikiRevisionDetail,
  normalizeWikiRevisionDiff,
  normalizeWikiRevisionListItem,
} from '@/utils/wikiNormalize.js'

/**
 * @param {unknown} res
 */
function unwrapData(res) {
  if (res && typeof res === 'object' && 'data' in res && res.data != null) {
    return res.data
  }
  return res
}

/**
 * @param {unknown} raw
 */
function normalizeWikiListItem(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  return {
    id: source.id != null ? String(source.id) : '',
    title: source.title != null ? String(source.title) : '',
    sourceNote:
      source.sourceNote != null
        ? String(source.sourceNote)
        : source.source_note != null
          ? String(source.source_note)
          : null,
    status: source.status != null ? String(source.status) : '',
    categories: Array.isArray(source.categories) ? source.categories.map(String) : [],
    lastModified:
      source.lastModified != null
        ? String(source.lastModified)
        : source.last_modified != null
          ? String(source.last_modified)
          : '',
    revision: typeof source.revision === 'number' ? source.revision : Number(source.revision) || 0,
    createdAt:
      source.createdAt != null
        ? String(source.createdAt)
        : source.created_at != null
          ? String(source.created_at)
          : '',
  }
}

/**
 * 列表 Query 使用 snake_case（sort_by、page_size 等）。
 * @param {Record<string, unknown>} [params]
 */
export function buildWikiListQuery(params = {}) {
  /** @type {Record<string, unknown>} */
  const query = {}
  if (params.q != null && String(params.q).trim() !== '') query.q = params.q
  if (params.category != null && String(params.category).trim() !== '') {
    query.category = params.category
  }
  if (params.status != null && String(params.status).trim() !== '') {
    query.status = params.status
  }
  const sortBy = params.sort_by ?? params.sortBy
  if (sortBy != null && String(sortBy).trim() !== '') query.sort_by = sortBy
  const sortOrder = params.sort_order ?? params.sortOrder
  if (sortOrder != null && String(sortOrder).trim() !== '') query.sort_order = sortOrder
  if (params.page != null) query.page = params.page
  const pageSize = params.page_size ?? params.pageSize
  if (pageSize != null) query.page_size = pageSize
  return query
}

/**
 * @param {unknown} res
 */
export function normalizeWikiListResponse(res) {
  const data = unwrapData(res) || {}
  const items = Array.isArray(data.items) ? data.items.map(normalizeWikiListItem) : []
  return {
    items,
    pagination: {
      total: data.total ?? 0,
      page: data.page ?? 1,
      pageSize: data.page_size ?? data.pageSize ?? 10,
      totalPages: data.total_pages ?? data.totalPages ?? 0,
    },
  }
}

/**
 * @param {Record<string, unknown>} [params]
 */
export function buildWikiRevisionListQuery(params = {}) {
  /** @type {Record<string, unknown>} */
  const query = {}
  if (params.page != null) query.page = params.page
  const pageSize = params.page_size ?? params.pageSize
  if (pageSize != null) query.page_size = pageSize
  return query
}

/**
 * @param {unknown} res
 */
export function normalizeWikiRevisionListResponse(res) {
  const data = unwrapData(res) || {}
  const items = Array.isArray(data.items)
    ? data.items.map(normalizeWikiRevisionListItem).sort((a, b) => b.revision - a.revision)
    : []
  return {
    items,
    pagination: {
      total: data.total ?? 0,
      page: data.page ?? 1,
      pageSize: data.page_size ?? data.pageSize ?? 20,
      totalPages: data.total_pages ?? data.totalPages ?? 0,
    },
  }
}

export const wikiApi = {
  /**
   * @param {Record<string, unknown>} [params]
   */
  listPages(params) {
    return request.get('/wiki/pages', buildWikiListQuery(params))
  },

  /**
   * @param {string} wikiId
   */
  async getPageById(wikiId) {
    const res = await request.get(`/wiki/pages/${encodeURIComponent(wikiId)}`)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {{ title: string, sourceNote?: string, categories?: string[] }} body
   */
  async createPage(body) {
    const res = await request.post('/wiki/pages', body)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   */
  deletePage(pageId) {
    return request.delete(`/wiki/pages/${encodeURIComponent(pageId)}`)
  },

  /**
   * @param {string} pageId
   * @param {Record<string, unknown>} body
   */
  async updateMain(pageId, body) {
    const res = await request.patch(`/wiki/pages/${encodeURIComponent(pageId)}/main`, body)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   * @param {string} sectionId
   * @param {Record<string, unknown>} body
   */
  async updateSection(pageId, sectionId, body) {
    const res = await request.patch(
      `/wiki/pages/${encodeURIComponent(pageId)}/sections/${encodeURIComponent(sectionId)}`,
      body
    )
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   * @param {Record<string, unknown>} body
   */
  async createSection(pageId, body) {
    const res = await request.post(`/wiki/pages/${encodeURIComponent(pageId)}/sections`, body)
    const data = unwrapData(res) || {}
    return {
      section: data.section != null ? String(data.section) : '',
      detail: normalizeWikiPageDetail(data.detail),
    }
  },

  /**
   * @param {string} pageId
   * @param {string} sectionId
   * @param {Record<string, unknown>} body
   */
  async moveSection(pageId, sectionId, body) {
    const res = await request.patch(
      `/wiki/pages/${encodeURIComponent(pageId)}/sections/${encodeURIComponent(sectionId)}/move`,
      body
    )
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   * @param {string} sectionId
   * @param {{ expectedRevision: number, changeSummary?: string }} query
   */
  async deleteSection(pageId, sectionId, query) {
    const res = await request.delete(
      `/wiki/pages/${encodeURIComponent(pageId)}/sections/${encodeURIComponent(sectionId)}`,
      { params: query }
    )
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   * @param {{ expectedRevision: number, changeSummary?: string, items: { id: string, text: string }[] }} body
   */
  async putFootnotes(pageId, body) {
    const res = await request.put(`/wiki/pages/${encodeURIComponent(pageId)}/footnotes`, body)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   * @param {{ expectedRevision: number, changeSummary?: string, items: import('@/types/wiki.js').WikiReference[] }} body
   */
  async putReferences(pageId, body) {
    const res = await request.put(`/wiki/pages/${encodeURIComponent(pageId)}/references`, body)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   */
  async validateCitations(pageId) {
    const res = await request.get(
      `/wiki/pages/${encodeURIComponent(pageId)}/citations/validate`
    )
    const data = unwrapData(res) || {}
    return {
      missingRefs: data.missingRefs ?? data.missing_refs ?? [],
      missingFootnotes: data.missingFootnotes ?? data.missing_footnotes ?? [],
      orphanReferences: data.orphanReferences ?? data.orphan_references ?? [],
      orphanFootnotes: data.orphanFootnotes ?? data.orphan_footnotes ?? [],
    }
  },

  /**
   * @param {string} wikiId
   * @param {Record<string, unknown>} [params]
   */
  listRevisions(wikiId, params) {
    return request.get(
      `/wiki/pages/${encodeURIComponent(wikiId)}/revisions`,
      buildWikiRevisionListQuery(params)
    )
  },

  /**
   * @param {string} wikiId
   * @param {number} revision
   */
  async getRevision(wikiId, revision) {
    const res = await request.get(
      `/wiki/pages/${encodeURIComponent(wikiId)}/revisions/${revision}`
    )
    return normalizeWikiRevisionDetail(unwrapData(res))
  },

  /**
   * @param {string} wikiId
   * @param {number} targetRevision
   * @param {{ expectedRevision: number, changeSummary?: string }} body
   */
  async restoreRevision(wikiId, targetRevision, body) {
    const res = await request.post(
      `/wiki/pages/${encodeURIComponent(wikiId)}/revisions/${targetRevision}/restore`,
      body
    )
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} wikiId
   * @param {{ from: number, to: number }} params
   */
  async getRevisionDiff(wikiId, params) {
    const res = await request.get(
      `/wiki/pages/${encodeURIComponent(wikiId)}/revisions/diff`,
      { from: params.from, to: params.to }
    )
    return normalizeWikiRevisionDiff(unwrapData(res))
  },
}
