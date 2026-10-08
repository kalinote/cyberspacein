import { PERM } from './permissions.js'
import { hasAllForPermissions } from './permissionPolicy.js'

const destinations = {
  'article-detail': { param: 'uuid', label: '文章阅读', permissions: [PERM.pages.search.access, PERM.operations.content.article.read] },
  'forum-detail': { param: 'uuid', label: '论坛阅读', permissions: [PERM.pages.search.access, PERM.operations.content.forum.read] },
  'wiki-detail': { param: 'id', label: '专题 Wiki', permissions: [PERM.pages.target.wiki.access, PERM.operations.target.wiki.read] },
  'evidence-editor': { param: 'id', label: '证据链', permissions: [PERM.pages.evidence.access, PERM.operations.evidence.chain.read] },
  'action-detail': { param: 'id', label: '行动任务', permissions: [PERM.pages.action.detail.access, PERM.operations.action.instance.read] },
  'agent-analysis-detail': { param: 'sessionId', label: '分析会话', permissions: [PERM.pages.agent.analysis.access, PERM.operations.agent.session.read] },
}

/**
 * 只保留已授权详情页的必要路由字段，拒绝外部地址和无效标识。
 * @param {object} route 当前路由或保存的记录。
 * @param {string[]} permissions 当前账号权限。
 * @param {string} title 可选的资源标题。
 * @returns {object|null} 可安全用于内部导航的记录。
 */
export function normalizeRecentVisit(route, permissions, title = '') {
  if (!route || typeof route.name !== 'string' || !Object.hasOwn(destinations, route.name)) return null
  const destination = destinations[route.name]
  if (!hasAllForPermissions(permissions, destination.permissions)) return null
  const id = route.params?.[destination.param]
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(id)) return null
  const query = {}
  if (route.name === 'agent-analysis-detail') {
    const agentId = route.query?.agent_id
    if (typeof agentId !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(agentId)) return null
    query.agent_id = agentId
  }
  return {
    key: `${route.name}:${id}`,
    name: route.name,
    params: { [destination.param]: id },
    query,
    label: destination.label,
    title: ((typeof title === 'string' && title.trim()) || (typeof route.title === 'string' && route.title.trim()) || `${destination.label} · ${id.slice(0, 8)}`).slice(0, 100),
  }
}
