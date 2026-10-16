import { cloneWikiTree, cloneWikiInfobox, findWikiNode, findWikiParent } from '../../utils/wikiTree.js'

/**
 * 从当前修订创建独立编辑草稿，避免输入直接改写只读页面。
 * @param {object} wiki 当前专题
 * @param {string} area 编辑区域
 * @param {string} sectionId 正文章节
 * @returns {object|Array} 区域草稿
 */
export function createWikiEditorDraft(wiki, area, sectionId = 'main') {
  if (area === 'meta') return {
    title: wiki.title || '', sourceNote: wiki.sourceNote || '',
    status: wiki.status || 'draft', categories: [...(wiki.categories || [])],
  }
  if (area === 'content') return cloneWikiTree(findWikiNode(wiki.contentTree, sectionId))
  if (area === 'toc') return cloneWikiTree(wiki.contentTree)
  return (wiki[area] || []).map(item => ({ ...item }))
}

/**
 * 仅提交当前区域，并保留引用编号、实体关联及显式清空字段。
 * @param {object} wiki 当前专题和修订
 * @param {string} area 编辑区域
 * @param {object|Array} draft 区域草稿
 * @param {string} summary 变更说明
 * @returns {object} 现有接口请求体
 */
export function buildWikiEditorPatch(wiki, area, draft, summary = '') {
  const body = { expectedRevision: wiki.revision, changeSummary: summary.trim() }
  if (area === 'meta') {
    if (!draft.title.trim()) throw new Error('请输入专题标题')
    return { ...body, title: draft.title.trim(), sourceNote: draft.sourceNote,
      status: draft.status, categories: [...draft.categories] }
  }
  if (area === 'content') {
    if (draft.infobox && !draft.infobox.caption.trim()) throw new Error('请输入信息框标题')
    return { ...body, content: draft.content, infobox: cloneWikiInfobox(draft.infobox) }
  }
  const ids = new Set()
  const items = draft.map(item => {
    const id = String(item.id).trim()
    if (!id || ids.has(id)) throw new Error('引用或注释编号不能为空或重复')
    ids.add(id)
    if (area === 'footnotes') return { id, text: String(item.text ?? '') }
    return { id, text: String(item.text ?? ''), url: item.url || null,
      entityType: item.entityType ?? null, entityUuid: item.entityUuid ?? null }
  })
  return { ...body, items }
}

/**
 * 展平目录供手机选择章节，保留完整层级路径。
 * @param {object} root 内容树
 * @param {string} prefix 上层路径
 * @returns {Array} 章节选项
 */
export function listWikiEditorSections(root, prefix = '') {
  if (!root) return []
  const label = root.section === 'main' ? '导语' : `${prefix}${root.title || '未命名章节'}`
  const nextPrefix = root.section === 'main' ? '' : `${label} / `
  return [{ id: root.section, label }, ...(root.children || []).flatMap(child => listWikiEditorSections(child, nextPrefix))]
}

/**
 * 在草稿内移动章节及其子树；缩进只能进入前一同级章节，避免形成循环。
 * @param {object} root 内容树草稿
 * @param {string} sectionId 章节标识
 * @param {'up'|'down'|'indent'|'outdent'} direction 移动方向
 * @returns {object} 新目录草稿
 */
export function moveWikiEditorSection(root, sectionId, direction) {
  const next = cloneWikiTree(root)
  const parent = findWikiParent(next, sectionId)
  if (!parent) return next
  const index = parent.children.findIndex(node => node.section === sectionId)
  const node = parent.children[index]
  if (direction === 'indent' && index > 0) {
    const previous = parent.children[index - 1]
    previous.children ||= []
    parent.children.splice(index, 1)
    previous.children.push(node)
  } else if (direction === 'outdent' && parent.section !== 'main') {
    const grandparent = findWikiParent(next, parent.section)
    const parentIndex = grandparent.children.findIndex(item => item.section === parent.section)
    parent.children.splice(index, 1)
    grandparent.children.splice(parentIndex + 1, 0, node)
  } else if (direction === 'up' || direction === 'down') {
    const target = index + (direction === 'up' ? -1 : 1)
    if (target >= 0 && target < parent.children.length) {
      parent.children.splice(index, 1)
      parent.children.splice(target, 0, node)
    }
  }
  return next
}

/**
 * 依照现有接口逐次修订目录，先移出保留节点再删除旧子树，避免丢失正文。
 * 后端未传 afterSection 时追加到末尾；按目标顺序逐个定位可得到正确最终顺序。
 * @param {object} api Wiki API
 * @param {object} wiki 保存前专题
 * @param {object} nextTree 目标目录草稿
 * @returns {Promise<object>} 最后一次接口返回的专题
 */
export async function persistWikiEditorToc(api, wiki, nextTree) {
  const desired = listWikiEditorSections(nextTree).slice(1)
  if (desired.some(item => !findWikiNode(nextTree, item.id)?.title?.trim())) throw new Error('章节标题不能为空')
  const ids = new Map()
  let current = wiki
  for (const item of desired) {
    if (findWikiNode(wiki.contentTree, item.id)) continue
    const parent = findWikiParent(nextTree, item.id)
    const created = await api.createSection(current.id, {
      expectedRevision: current.revision,
      parentSection: ids.get(parent.section) || parent.section,
      title: findWikiNode(nextTree, item.id).title,
    })
    if (!created.section || !created.detail?.id) throw new Error('章节创建结果无法确认，请重新加载后核对')
    ids.set(item.id, created.section)
    current = created.detail
  }
  for (const item of desired) {
    const section = ids.get(item.id) || item.id
    const parent = findWikiParent(nextTree, item.id)
    const parentSection = ids.get(parent.section) || parent.section
    const index = parent.children.findIndex(node => node.section === item.id)
    const previousId = index > 0 ? parent.children[index - 1].section : null
    const afterSection = ids.get(previousId) || previousId
    const actualParent = findWikiParent(current.contentTree, section)
    const actualIndex = actualParent?.children.findIndex(node => node.section === section) ?? -1
    const actualAfter = actualIndex > 0 ? actualParent.children[actualIndex - 1].section : null
    if (!actualParent) throw new Error('待保留章节缺失，请重新加载后核对')
    if (actualParent.section !== parentSection || actualAfter !== afterSection) {
      current = await api.moveSection(current.id, section, {
        expectedRevision: current.revision, parentSection,
        ...(afterSection ? { afterSection } : {}),
      })
    }
    const title = findWikiNode(nextTree, item.id).title
    if (findWikiNode(current.contentTree, section)?.title !== title) {
      current = await api.updateSection(current.id, section, { expectedRevision: current.revision, title })
    }
  }
  const retained = new Set(desired.map(item => ids.get(item.id) || item.id))
  const obsolete = listWikiEditorSections(current.contentTree).slice(1).reverse().filter(item => !retained.has(item.id))
  for (const item of obsolete) {
    if (!findWikiNode(current.contentTree, item.id)) continue
    current = await api.deleteSection(current.id, item.id, { expectedRevision: current.revision })
  }
  return current
}
