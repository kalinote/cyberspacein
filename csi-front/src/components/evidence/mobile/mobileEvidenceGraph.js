/**
 * 生成手机局部视图，筛选、展开和临时排版均不修改持久化图定义。
 * @param {object} rendered 包含引用内部内容的完整投影。
 * @param {object} options 焦点、邻接层数和关系筛选。
 * @returns {object} 独立节点、关系与局部图统计。
 */
export function projectMobileEvidenceGraph(rendered, { focusId = '', depth = 1, filter = 'all' } = {}) {
  const nodes = rendered.nodes || [], nodeIds = new Set(nodes.map(node => node.id))
  const focus = nodeIds.has(focusId) ? focusId : (nodes.find(node => node.data.node.kind === 'note') || nodes[0])?.id || ''
  const edges = (rendered.edges || []).filter(edge => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return false
    if (edge.data?.containment || filter === 'all') return true
    const relation = edge.data?.edge
    return filter === 'pending' ? relation?.status === 'pending' : relation?.label === (filter === 'support' ? '支持' : '反驳')
  })
  const levels = new Map(focus ? [[focus, 0]] : []), adjacency = new Map()
  for (const edge of edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set())
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set())
    adjacency.get(edge.source).add(edge.target)
    adjacency.get(edge.target).add(edge.source)
  }
  const queue = focus ? [focus] : []
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const id = queue[cursor], level = levels.get(id)
    if (level >= Math.max(1, depth)) continue
    for (const next of adjacency.get(id) || []) {
      if (levels.has(next)) continue
      levels.set(next, level + 1)
      queue.push(next)
    }
  }
  const rows = new Map()
  for (const id of queue) {
    const level = levels.get(id)
    if (!rows.has(level)) rows.set(level, [])
    rows.get(level).push(id)
  }
  const rowOffsets = new Map()
  let offset = 0
  for (const [level, row] of rows) { rowOffsets.set(level, offset); offset += Math.ceil(row.length / 2) * 170 }
  return {
    focusId: focus,
    hiddenCount: nodes.length - levels.size,
    nodes: nodes.filter(node => levels.has(node.id)).map(node => {
      const level = levels.get(node.id), row = rows.get(level)
      const index = row.indexOf(node.id), columns = Math.min(2, row.length)
      return { ...JSON.parse(JSON.stringify(node)), position: { x: (index % 2 - (columns - 1) / 2) * 232, y: rowOffsets.get(level) + Math.floor(index / 2) * 170 } }
    }),
    edges: edges.filter(edge => levels.has(edge.source) && levels.has(edge.target)).map(edge => JSON.parse(JSON.stringify(edge)))
  }
}

/**
 * 计算移出本链节点造成的真实关系删除范围，引用子节点不参与修改。
 * @param {object} graph 原始图定义。
 * @param {Array<string>} ids 目录或画布选中的节点。
 * @returns {{nodeIds:Array<string>,edgeIds:Array<string>}} 本链影响范围。
 */
export function evidenceRemovalImpact(graph, ids) {
  const requested = new Set(ids), nodeIds = graph.nodes.filter(node => requested.has(node.id)).map(node => node.id)
  return { nodeIds, edgeIds: graph.edges.filter(edge => [edge.source, edge.target].some(endpoint => nodeIds.some(id => endpoint === id || endpoint.startsWith(`${id}/`)))).map(edge => edge.id) }
}

/**
 * 将明确的移动增量应用到本链原坐标，不写入手机局部图的临时坐标。
 * @param {object} graph 原始图定义。
 * @param {Array<string>} ids 本链节点标识。
 * @param {{x:number,y:number}} delta 用户拖动或按钮微调的位移。
 * @returns {boolean} 是否改变图定义。
 */
export function moveEvidenceNodes(graph, ids, delta) {
  if (!Number.isFinite(delta?.x) || !Number.isFinite(delta?.y) || (!delta.x && !delta.y)) return false
  const requested = new Set(ids)
  let changed = false
  for (const node of graph.nodes) {
    if (!requested.has(node.id)) continue
    const x = node.position.x + delta.x, y = node.position.y + delta.y
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    node.position = { x, y }
    changed = true
  }
  return changed
}

/**
 * 移出本链选中节点和关联关系，原始实体及引用子链不受影响。
 * @param {object} graph 当前图定义。
 * @param {Array<string>} ids 本链节点标识。
 * @returns {object} 实际移除范围。
 */
export function removeEvidenceNodes(graph, ids) {
  const impact = evidenceRemovalImpact(graph, ids), nodes = new Set(impact.nodeIds), edges = new Set(impact.edgeIds)
  graph.nodes = graph.nodes.filter(node => !nodes.has(node.id))
  graph.edges = graph.edges.filter(edge => !edges.has(edge.id))
  return impact
}
