import { acceptsHandleDataType, allowsMultipleHandleInputs, areHandleInterfacesCompatible, isDuplicateHandleConnection } from './handleConnection.js'
import { isBindingProtocolHandle, validateBoundaryBindings } from './boundaryBinding.js'

/**
 * 为手机生成紧凑的浏览投影，原节点位置、字段及边均不被修改。
 * @param {object[]} elements 原始节点和关系。
 * @param {object} positions 用户本次浏览明确调整过的显示位置。
 * @returns {object[]} 可交给独立画布的深拷贝元素。
 */
export function projectMobileBlueprint(elements, positions = {}) {
  const nodes = elements.filter(item => !item.source)
  const edges = elements.filter(item => item.source)
  const levels = new Map()
  const incoming = new Set(edges.map(edge => edge.target))
  const queue = nodes.filter(node => !incoming.has(node.id)).map(node => [node.id, 0])
  if (!queue.length && nodes.length) queue.push([nodes[0].id, 0])
  while (queue.length) {
    const [id, level] = queue.shift()
    if (levels.has(id)) continue
    levels.set(id, level)
    for (const edge of edges.filter(item => item.source === id)) if (!levels.has(edge.target)) queue.push([edge.target, level + 1])
  }
  let disconnectedLevel = Math.max(-1, ...levels.values()) + 1
  const columns = new Map()
  return elements.map(item => {
    if (item.source) return JSON.parse(JSON.stringify(item))
    const level = levels.has(item.id) ? levels.get(item.id) : disconnectedLevel++
    const column = columns.get(level) || 0
    columns.set(level, column + 1)
    return {
      id: item.id, type: item.type,
      position: { ...(positions[item.id] || { x: column * 220, y: level * 140 }) },
      data: JSON.parse(JSON.stringify(item.data)),
    }
  })
}

/** """只截取可持久化草稿，排除选择、测量与派生绑定边。""" */
export function captureBlueprintDraft({ elements, form, template, params, bindings, resource, resourceEnabled }) {
  return JSON.parse(JSON.stringify({
    elements: elements.filter(item => item.data?.relationKind !== 'boundary-binding').map(item => item.source
      ? { id: item.id, source: item.source, target: item.target, sourceHandle: item.sourceHandle, targetHandle: item.targetHandle, style: item.style }
      : { id: item.id, type: item.type, position: { x: item.position.x, y: item.position.y }, data: {
        config: item.data.config,
        ...Object.fromEntries((item.data.config?.inputs || []).map(input => [input.id, item.data[input.id]])),
        interfacePortId: item.data.interfacePortId || null, boundaryBinding: item.data.boundaryBinding || null,
      } }),
    form, template, params, bindings, resource, resourceEnabled,
  }))
}

/**
 * 返回普通数据边的拒绝原因，兼容性与桌面采用同一端口契约。
 * @param {object[]} nodes 原始图节点。
 * @param {object[]} edges 普通数据边。
 * @param {object} connection 拟连接的两端节点和端口。
 * @returns {string} 空字符串表示可连接。
 */
export function blueprintConnectionIssue(nodes, edges, connection) {
  const source = nodes.find(node => node.id === connection.source)
  const target = nodes.find(node => node.id === connection.target)
  if (!source || !target) return '节点已不存在，请重新选择'
  if (isBindingProtocolHandle(connection.sourceHandle) || isBindingProtocolHandle(connection.targetHandle)) return '公开 IO 绑定请使用独立绑定向导'
  if (source.data?.boundaryBinding || target.data?.boundaryBinding) return '已绑定 IO 不能创建普通数据边，请先解绑'
  const output = source.data?.config?.handles?.find(handle => handle.id === connection.sourceHandle)
  const input = target.data?.config?.handles?.find(handle => handle.id === connection.targetHandle)
  if (output?.type !== 'source' || input?.type !== 'target') return '请选择输出端口和输入端口'
  if (isDuplicateHandleConnection(edges, connection)) return '这两个端口已经连接'
  if (!allowsMultipleHandleInputs(target.data.config, input) && edges.some(edge => edge.id !== connection.id && edge.target === target.id && edge.targetHandle === input.id)) return '该输入端口已有上游连接'
  if (!acceptsHandleDataType(output, input)) return '传输类型不兼容（值或引用）'
  if (!areHandleInterfacesCompatible(output, input)) return '业务接口类型不兼容'
  return ''
}

/** """收集可定位的图问题，不把有分支的图转化为线性流程。""" */
export function collectBlueprintGraphIssues(nodes, edges, ports) {
  const issues = validateBoundaryBindings(nodes, edges).map(issue => ({ ...issue }))
  if (!nodes.length) issues.push({ message: '请至少添加一个节点' })
  for (const node of nodes) {
    if (node.data?.config?.rendererUnsupported) issues.push({ nodeId: node.id, message: '当前前端不支持该节点版本' })
  }
  for (const edge of edges) {
    const message = blueprintConnectionIssue(nodes, edges, edge)
    if (message) issues.push({ nodeId: edge.target, edgeId: edge.id, message })
  }
  for (const port of ports) {
    if (!port.name?.trim()) issues.push({ nodeId: port.nodeId, message: '公开接口名称不能为空' })
    if (!port.handleConfigId || !port.interfaceTypeId) issues.push({ nodeId: port.nodeId, message: '公开接口需要绑定、数据连线或明确的接口类型' })
    if (port.name?.trim() && ports.some(other => other.nodeId !== port.nodeId && other.direction === port.direction && other.name?.trim() === port.name.trim())) issues.push({ nodeId: port.nodeId, message: '同方向公开接口名称不能重复' })
  }
  return issues
}

/** """列出删除影响；绑定目标与模板引用需同时处理，不能留下悬空引用。""" */
export function blueprintRemovalImpact(elements, nodeIds, edgeIds = [], bindings = {}) {
  const nodes = new Set(nodeIds)
  const edges = elements.filter(item => item.source && item.data?.relationKind !== 'boundary-binding' && (nodes.has(item.source) || nodes.has(item.target) || edgeIds.includes(item.id)))
  const boundaries = elements.filter(item => !item.source && !nodes.has(item.id) && nodes.has(item.data?.boundaryBinding?.bound_node_id))
  return { edgeIds: edges.map(edge => edge.id), boundaryIds: boundaries.map(node => node.id), templateCount: nodeIds.reduce((count, id) => count + Object.keys(bindings[id] || {}).length, 0) }
}

/**
 * 创建有限的草稿撤销历史；外部只在有效操作或字段编辑完成后提交。
 * @param {number} limit 最大快照数。
 * @returns {object} 重置、提交、撤销、重做和状态方法。
 */
export function createBlueprintHistory(limit = 60) {
  let frames = [], index = -1
  return {
    reset(snapshot) { frames = [JSON.stringify(snapshot)]; index = 0 },
    commit(snapshot) {
      const value = JSON.stringify(snapshot)
      if (frames[index] === value) return false
      frames = frames.slice(0, index + 1)
      frames.push(value)
      if (frames.length > limit) frames.shift()
      index = frames.length - 1
      return true
    },
    undo() { return index > 0 ? JSON.parse(frames[--index]) : null },
    redo() { return index < frames.length - 1 ? JSON.parse(frames[++index]) : null },
    get canUndo() { return index > 0 },
    get canRedo() { return index >= 0 && index < frames.length - 1 },
  }
}
