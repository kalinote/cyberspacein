import { nextReferenceId } from '@/utils/wikiCitationIds.js'

/**
 * @typedef {import('@/types/wiki.js').WikiReference} WikiReference
 */

/**
 * @param {string} entityType
 * @param {string} uuid
 */
export function getEntityDetailPath(entityType, uuid) {
  const type = String(entityType || 'article')
    .trim()
    .toLowerCase()
  const id = String(uuid || '').trim()
  if (!id) return ''
  return `/details/${type}/${id}`
}

/**
 * @param {string} html
 * @param {number} [maxLen]
 */
function stripHtml(html, maxLen = 120) {
  const text = String(html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  if (text.length <= maxLen) return text
  return `${text.slice(0, maxLen)}…`
}

/**
 * @param {Record<string, unknown>} result
 * @param {Iterable<string>} existingIds
 * @returns {WikiReference}
 */
export function referenceFromSearchResult(result, existingIds = []) {
  const entityType = String(result.entity_type ?? result.entityType ?? 'article')
    .trim()
    .toLowerCase()
  const entityUuid = String(result.uuid ?? result.entityUuid ?? '').trim()
  const text = stripHtml(result.title, 500) || '未命名条目'

  return {
    id: nextReferenceId(existingIds),
    text,
    url: getEntityDetailPath(entityType, entityUuid) || null,
    entityType: entityType || null,
    entityUuid: entityUuid || null,
  }
}
