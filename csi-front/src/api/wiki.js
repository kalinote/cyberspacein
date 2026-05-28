import { request } from '@/utils/request'
import { normalizeWikiPageDetail } from '@/utils/wikiNormalize.js'

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
 * @param {unknown} res
 */
export function normalizeWikiListResponse(res) {
  const data = unwrapData(res) || {}
  return {
    items: Array.isArray(data.items) ? data.items : [],
    pagination: {
      total: data.total ?? 0,
      page: data.page ?? 1,
      pageSize: data.pageSize ?? 10,
      totalPages: data.totalPages ?? 0,
    },
  }
}

export const wikiApi = {
  /**
   * @param {Record<string, unknown>} [params]
   */
  listPages(params) {
    return request.get('/wiki/pages', params)
  },

  /**
   * @param {string} slug
   */
  async getPageBySlug(slug) {
    const res = await request.get(`/wiki/pages/by-slug/${encodeURIComponent(slug)}`)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {string} pageId
   */
  async getPageById(pageId) {
    const res = await request.get(`/wiki/pages/${encodeURIComponent(pageId)}`)
    return normalizeWikiPageDetail(unwrapData(res))
  },

  /**
   * @param {{ slug: string, title: string, sourceNote?: string, categories?: string[] }} body
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
}
