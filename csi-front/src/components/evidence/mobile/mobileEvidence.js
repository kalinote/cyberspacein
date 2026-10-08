import { evidenceId } from '../../../utils/evidence.js'

/**
 * 生成阅读顺序，优先展示有支持或反驳关系的判断，不修改图定义。
 * @param {object} projected 包含引用展开内容的图投影。
 * @returns {object} 判断、材料及真实关系列表。
 */
export function evidenceReadingSections(projected) {
  const relations = projected.edges.filter(entry => entry.data?.edge && !entry.data.containment)
  const connected = new Set(relations.filter(entry => ['支持', '反驳'].includes(entry.data.edge.label)).map(entry => `${entry.data.ownerPath || ''}${entry.data.edge.target}`))
  return {
    judgments: projected.nodes.filter(entry => entry.data.node.kind === 'note').sort((a, b) => Number(connected.has(b.id)) - Number(connected.has(a.id))),
    materials: projected.nodes.filter(entry => entry.data.node.kind !== 'note'),
    relations
  }
}

/**
 * 为端点显示名称；折叠后仍保留内部路径，不能用投影连线端点替换保存值。
 * @param {string} path 原始完整端点路径。
 * @param {Array} nodes 当前可见节点。
 * @returns {string} 含引用层次的可读名称。
 */
export function evidenceEndpointLabel(path, nodes) {
  const exact = nodes.find(entry => entry.id === path)
  if (exact) return exact.data.node.label
  const parent = nodes.filter(entry => path.startsWith(`${entry.id}/`)).sort((a, b) => b.id.length - a.id.length)[0]
  return parent ? `${parent.data.node.label} / 内部节点 ${path.slice(parent.id.length + 1)}` : `不可用节点 ${path}`
}

/**
 * 从真实关系创建独立草稿，确保取消不会改图，继承关系不能误存为本链关系。
 * @param {object|null} entry 关系投影；新增时为空。
 * @param {object} graph 当前图定义。
 * @param {string} source 新关系默认起点。
 * @returns {object|null} 可编辑关系草稿。
 */
export function createEvidenceRelationDraft(entry, graph, source = '') {
  if (entry?.data.inherited) return null
  return entry ? JSON.parse(JSON.stringify(entry.data.edge)) : {
    id: evidenceId(), source, target: '', label: graph.relation_types[0] || '关联',
    directed: true, status: 'pending', description: '', anchors: []
  }
}

/**
 * 提交移动关系草稿，允许保留折叠或已失效端点，禁止新增悬空引用。
 * @param {object} graph 可编辑图定义。
 * @param {object} draft 表单草稿。
 * @param {Array} nodes 当前可选端点。
 * @param {boolean} editable 当前编辑权限。
 * @returns {string} 校验失败原因，空字符串表示提交成功。
 */
export function commitEvidenceRelation(graph, draft, nodes, editable) {
  if (!editable) return '当前账号没有编辑权限'
  const existing = graph.edges.find(edge => edge.id === draft.id)
  if (!draft.source || !draft.target || !draft.label?.trim() || draft.label.trim().length > 100) return '请选择起点、终点，并填写 100 字以内的关系类型'
  for (const key of ['source', 'target']) {
    if (!nodes.some(node => node.id === draft[key]) && existing?.[key] !== draft[key]) return '所选端点已不可用，请重新选择'
  }
  if (draft.anchors.length > 100) return '每条关系最多保留 100 项原始依据'
  const value = JSON.parse(JSON.stringify({ ...draft, label: draft.label.trim() }))
  if (existing) Object.assign(existing, value)
  else graph.edges.push(value)
  return ''
}

/**
 * 将选定材料转换为具体版本引用；动态版本不能作为一条关系的原始依据。
 * @param {Array} nodes 材料选择器返回的节点。
 * @returns {Array} 去重后的具体实体版本。
 */
export function evidenceMaterialRefs(nodes) {
  const refs = nodes.flatMap(node => node.kind === 'entity' ? [node.entity] : node.kind === 'collection' ? node.members : [])
  return [...new Map(refs.map(entity => [`${entity.entity_type}:${entity.uuid}`, { ...entity }])).values()]
}
