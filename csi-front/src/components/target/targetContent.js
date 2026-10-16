import { hasAll } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'

/** """提取资料中的纯文本摘要，避免把搜索高亮标签作为标题展示。""" */
export function plainExcerpt(content, maxLength) {
  if (!content) return ''
  const element = document.createElement('template')
  element.innerHTML = String(content)
  const text = (element.content.textContent || '').trim()
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text
}

/** """仅为具有页面访问及对应正文权限的实体生成详情地址。""" */
export function entityDetailPath(entity) {
  const type = String(entity.entity_type || '').toLowerCase()
  const permission = PERM.operations.content[type]?.read
  if (!entity.uuid || !['article', 'forum'].includes(type) || !permission || !hasAll([PERM.pages.search.access, permission])) return ''
  return `/details/${type}/${encodeURIComponent(entity.uuid)}`
}
