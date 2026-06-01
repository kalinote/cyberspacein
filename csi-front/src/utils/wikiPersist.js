import { wikiApi } from '@/api/wiki.js'
import { normalizeWikiPageDetail } from '@/utils/wikiNormalize.js'
import { collectSectionIds } from '@/utils/wikiTree.js'

/**
 * @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail
 * @typedef {import('@/types/wiki.js').WikiContentNode} WikiContentNode
 * @typedef {import('@/types/wiki.js').WikiFootnote} WikiFootnote
 * @typedef {import('@/types/wiki.js').WikiReference} WikiReference
 */

const WIKI_REVISION_CONFLICT_CODE = 241003

/**
 * @param {unknown} error
 */
export function isWikiRevisionConflict(error) {
  if (error && typeof error === 'object' && 'code' in error) {
    return Number(error.code) === WIKI_REVISION_CONFLICT_CODE
  }
  const msg = error instanceof Error ? error.message : String(error ?? '')
  return msg.includes('241003') || msg.includes('revision')
}

/**
 * @param {WikiContentNode[]} nodes
 * @param {string} [parentSection]
 * @param {string|null} [afterSection]
 * @returns {{ section: string, title: string, parentSection: string, afterSection: string|null, depth: number, node: WikiContentNode }[]}
 */
function flattenSectionPlacements(nodes, parentSection = 'main', afterSection = null, depth = 0) {
  /** @type {{ section: string, title: string, parentSection: string, afterSection: string|null, depth: number, node: WikiContentNode }[]} */
  const list = []
  let prev = afterSection
  for (const node of nodes || []) {
    const section = node.section
    list.push({
      section,
      title: node.title ?? '',
      parentSection,
      afterSection: prev,
      depth,
      node,
    })
    prev = section
    if (node.children?.length) {
      list.push(...flattenSectionPlacements(node.children, section, null, depth + 1))
    }
  }
  return list
}

/**
 * @param {string} section
 * @param {Map<string, string>} idMap
 */
function resolveSectionId(section, idMap) {
  return idMap.get(section) ?? section
}

/**
 * @param {WikiContentNode[]} nodes
 * @param {Map<string, string>} idMap
 * @returns {WikiContentNode[]}
 */
function remapTreeSectionIds(nodes, idMap) {
  return (nodes || []).map((node) => ({
    ...node,
    section: resolveSectionId(node.section, idMap),
    children: remapTreeSectionIds(node.children || [], idMap),
  }))
}

/**
 * @param {WikiPageDetail} wiki
 * @param {string} sectionId
 * @param {Record<string, unknown>} patch
 */
export async function persistWikiSectionPatch(wiki, sectionId, patch) {
  const body = {
    expectedRevision: wiki.revision,
    changeSummary: '',
    ...patch,
  }
  if (sectionId === 'main') {
    return wikiApi.updateMain(wiki.id, body)
  }
  return wikiApi.updateSection(wiki.id, sectionId, body)
}

/**
 * @param {WikiPageDetail} wiki
 * @param {WikiFootnote[]} items
 */
export async function persistWikiFootnotes(wiki, items) {
  return wikiApi.putFootnotes(wiki.id, {
    expectedRevision: wiki.revision,
    changeSummary: '',
    items: items.map((item) => ({
      id: String(item.id),
      text: String(item.text ?? ''),
    })),
  })
}

/**
 * @param {WikiPageDetail} wiki
 * @param {WikiReference[]} items
 */
export async function persistWikiReferences(wiki, items) {
  return wikiApi.putReferences(wiki.id, {
    expectedRevision: wiki.revision,
    changeSummary: '',
    items: items.map((item) => ({
      id: String(item.id),
      text: String(item.text ?? ''),
      url: item.url && String(item.url).trim() !== '' ? String(item.url) : null,
      entityType: item.entityType ?? null,
      entityUuid: item.entityUuid ?? null,
    })),
  })
}

/**
 * @param {WikiPageDetail} wiki
 * @param {number} targetRevision
 * @param {string} [changeSummary]
 */
export async function persistWikiRestoreRevision(wiki, targetRevision, changeSummary) {
  return wikiApi.restoreRevision(wiki.id, targetRevision, {
    expectedRevision: wiki.revision,
    changeSummary: changeSummary?.trim() || `恢复到第 ${targetRevision} 版`,
  })
}

/**
 * @param {WikiPageDetail} wiki
 * @param {WikiContentNode[]} prevChildren
 * @param {WikiContentNode[]} nextChildren
 * @returns {Promise<WikiPageDetail>}
 */
export async function syncWikiTocStructure(wiki, prevChildren, nextChildren) {
  const prevIds = collectSectionIds({ section: 'main', children: prevChildren })
  prevIds.delete('main')

  const prevPlacements = flattenSectionPlacements(prevChildren)
  const depthBySection = new Map(prevPlacements.map((p) => [p.section, p.depth]))

  const nextPlacements = flattenSectionPlacements(nextChildren)
  const nextIdSet = new Set(nextPlacements.map((p) => p.section))

  /** @type {string[]} */
  const toDelete = [...prevIds].filter((id) => !nextIdSet.has(id))
  toDelete.sort((a, b) => (depthBySection.get(b) ?? 0) - (depthBySection.get(a) ?? 0))

  /** @type {Map<string, string>} */
  const idMap = new Map()
  let current = { ...wiki }

  for (const sectionId of toDelete) {
    current = await wikiApi.deleteSection(current.id, sectionId, {
      expectedRevision: current.revision,
    })
  }

  const prevPlacementBySection = new Map(prevPlacements.map((p) => [p.section, p]))

  for (const placement of nextPlacements) {
    if (prevIds.has(placement.section)) continue

    const parentSection = resolveSectionId(placement.parentSection, idMap)
    const afterSection = placement.afterSection
      ? resolveSectionId(placement.afterSection, idMap)
      : undefined

    const created = await wikiApi.createSection(current.id, {
      expectedRevision: current.revision,
      parentSection,
      title: placement.title || '新章节',
      ...(afterSection ? { afterSection } : {}),
    })
    current = created.detail
    if (created.section) {
      idMap.set(placement.section, created.section)
    }
  }

  const remappedNext = remapTreeSectionIds(nextChildren, idMap)
  const remappedPlacements = flattenSectionPlacements(remappedNext)

  for (const placement of remappedPlacements) {
    const prev = prevPlacementBySection.get(placement.section)
    if (!prev) continue
    const prevTitle = prev.title ?? ''
    if (prevTitle !== placement.title) {
      current = await wikiApi.updateSection(current.id, placement.section, {
        expectedRevision: current.revision,
        title: placement.title,
      })
    }
  }

  const serverPlacements = flattenSectionPlacements(current.contentTree?.children ?? [])

  for (const placement of remappedPlacements) {
    const server = serverPlacements.find((p) => p.section === placement.section)
    if (!server) continue

    const parentChanged = server.parentSection !== placement.parentSection
    const afterChanged = (server.afterSection ?? null) !== (placement.afterSection ?? null)
    if (!parentChanged && !afterChanged) continue

    current = await wikiApi.moveSection(current.id, placement.section, {
      expectedRevision: current.revision,
      parentSection: placement.parentSection,
      ...(placement.afterSection ? { afterSection: placement.afterSection } : {}),
    })
    const updatedPlacements = flattenSectionPlacements(current.contentTree?.children ?? [])
    serverPlacements.length = 0
    serverPlacements.push(...updatedPlacements)
  }

  return current
}

/**
 * @param {import('vue').Ref<WikiPageDetail|null>} wikiRef
 * @param {() => Promise<WikiPageDetail>} reloadFn
 * @param {(detail: WikiPageDetail) => Promise<void>|void} [onUpdated]
 */
export function createWikiPersistHandlers(wikiRef, reloadFn, onUpdated) {
  /**
   * @param {() => Promise<WikiPageDetail>} apiCall
   */
  async function runWrite(apiCall) {
    if (!wikiRef.value?.id) {
      throw new Error('页面未加载')
    }
    try {
      const detail = await apiCall()
      wikiRef.value = normalizeWikiPageDetail(detail)
      await onUpdated?.(wikiRef.value)
      return wikiRef.value
    } catch (error) {
      if (isWikiRevisionConflict(error)) {
        try {
          wikiRef.value = await reloadFn()
        } catch {
          /* ignore reload failure */
        }
      }
      throw error
    }
  }

  return { runWrite }
}
