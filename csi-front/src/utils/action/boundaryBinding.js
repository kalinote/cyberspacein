export const isBoundaryConfig = config => (
  config?.node_kind === 'backend_native'
  && ['blueprint.input', 'blueprint.output'].includes(config?.builtin_key)
)

export const getBoundaryDirection = boundaryNode => (
  boundaryNode?.data?.config?.builtin_key === 'blueprint.input' ? 'input' : 'output'
)

export const getBoundaryHandle = boundaryNode => {
  const expectedType = getBoundaryDirection(boundaryNode) === 'input' ? 'source' : 'target'
  return (boundaryNode?.data?.config?.handles || []).find(handle => handle.type === expectedType)
}

export const getBoundaryExposedHandles = (
  boundaryNode,
  graphNodes,
  graphEdges
) => {
  if (!boundaryNode || !isBoundaryConfig(boundaryNode.data?.config)) return []
  const direction = getBoundaryDirection(boundaryNode)
  const nodeById = new Map(graphNodes.map(node => [node.id, node]))
  const binding = boundaryNode.data?.boundaryBinding
  const entries = []
  if (binding?.bound_node_id) {
    const mappedPortIds = new Set(
      (binding.port_mappings || []).map(mapping => mapping.target_port_id)
    )
    for (const edge of graphEdges) {
      if (
        direction === 'input'
        && edge.source === binding.bound_node_id
        && mappedPortIds.has(edge.source_port_id || edge.sourceHandle)
      ) {
        entries.push({
          nodeId: edge.target,
          portId: edge.target_port_id || edge.targetHandle,
          handleType: 'target'
        })
      } else if (
        direction === 'output'
        && edge.target === binding.bound_node_id
        && mappedPortIds.has(edge.target_port_id || edge.targetHandle)
      ) {
        entries.push({
          nodeId: edge.source,
          portId: edge.source_port_id || edge.sourceHandle,
          handleType: 'source'
        })
      }
    }
  } else {
    for (const edge of graphEdges) {
      if (direction === 'input' && edge.source === boundaryNode.id) {
        entries.push({
          nodeId: edge.target,
          portId: edge.target_port_id || edge.targetHandle,
          handleType: 'target'
        })
      } else if (direction === 'output' && edge.target === boundaryNode.id) {
        entries.push({
          nodeId: edge.source,
          portId: edge.source_port_id || edge.sourceHandle,
          handleType: 'source'
        })
      }
    }
  }
  return entries
    .map(entry => {
      const node = nodeById.get(entry.nodeId)
      return (node?.data?.config?.handles || []).find(handle => (
        handle.type === entry.handleType
        && entry.portId === (handle.port_id || handle.id)
      ))
    })
    .filter(Boolean)
}

export const BINDING_SOURCE_HANDLE_ID = '__boundary_binding_source__'
export const BINDING_TARGET_HANDLE_ID = '__boundary_binding_target__'

export const isBindingProtocolHandle = handleId => (
  [BINDING_SOURCE_HANDLE_ID, BINDING_TARGET_HANDLE_ID].includes(handleId)
)

export const getBindableHandles = (boundaryNode, targetNode, context = {}) => {
  if (!boundaryNode || !targetNode || isBoundaryConfig(targetNode.data?.config)) return []
  const direction = getBoundaryDirection(boundaryNode)
  const expectedType = direction === 'input' ? 'source' : 'target'
  const occupiedPortIds = new Set(context.occupiedPortIds || [])
  const currentPortIds = new Set(
    boundaryNode.data?.boundaryBinding?.bound_node_id === targetNode.id
      ? (boundaryNode.data.boundaryBinding.port_mappings || [])
          .map(mapping => mapping.target_port_id)
      : []
  )
  const connectedPortIds = context.connectedPortIds
    ? new Set(context.connectedPortIds)
    : null

  return (targetNode.data?.config?.handles || []).filter(handle => {
    if (handle.type !== expectedType) return false
    const portId = handle.port_id || handle.id
    const occupied = occupiedPortIds.has(portId) || occupiedPortIds.has(handle.id)
    const current = currentPortIds.has(portId) || currentPortIds.has(handle.id)
    if (occupied && !current) return false
    if (
      connectedPortIds
      && !connectedPortIds.has(portId)
      && !connectedPortIds.has(handle.id)
    ) return false
    return true
  })
}

export const buildBindingDisplay = (boundaryNode, targetNode, targetPortIds) => {
  const direction = getBoundaryDirection(boundaryNode)
  const handlesById = new Map()
  for (const handle of targetNode?.data?.config?.handles || []) {
    handlesById.set(handle.id, handle)
    if (handle.port_id) handlesById.set(handle.port_id, handle)
  }
  const portNames = targetPortIds.map(portId => {
    const handle = handlesById.get(portId)
    return handle?.relabel || handle?.label || handle?.handle_name || portId
  })
  return {
    direction,
    targetNodeName: targetNode?.data?.config?.name || targetNode?.id || '未知节点',
    targetPortNames: portNames,
    portDescription: `${direction === 'input' ? '替代输出' : '替代输入'}：${portNames.join('、')}`
  }
}

export const buildBindingGraphIndex = (graphNodes, graphEdges) => {
  const nodeById = new Map(graphNodes.map(node => [node.id, node]))
  const incomingEdgesByNode = new Map(graphNodes.map(node => [node.id, []]))
  const outgoingEdgesByNode = new Map(graphNodes.map(node => [node.id, []]))
  for (const edge of graphEdges) {
    if (incomingEdgesByNode.has(edge.target)) {
      incomingEdgesByNode.get(edge.target).push(edge)
    }
    if (outgoingEdgesByNode.has(edge.source)) {
      outgoingEdgesByNode.get(edge.source).push(edge)
    }
  }
  return {
    nodeById,
    incomingEdgesByNode,
    outgoingEdgesByNode
  }
}

export const collectBindingsByTarget = graphNodes => {
  const bindingsByTarget = {}
  for (const node of graphNodes) {
    if (!isBoundaryConfig(node.data?.config)) continue
    const targetNodeId = node.data?.boundaryBinding?.bound_node_id
    if (!targetNodeId) continue
    const entries = bindingsByTarget[targetNodeId] || []
    entries.push({
      boundaryNode: node,
      direction: getBoundaryDirection(node),
      targetPortIds: (node.data.boundaryBinding.port_mappings || [])
        .map(mapping => mapping.target_port_id)
    })
    bindingsByTarget[targetNodeId] = entries.sort(
      (left, right) => left.boundaryNode.id.localeCompare(right.boundaryNode.id)
    )
  }
  return bindingsByTarget
}

export const validateBoundaryBindings = (graphNodes, graphEdges) => {
  const issues = []
  const graphIndex = buildBindingGraphIndex(graphNodes, graphEdges)
  const bindingsByTarget = collectBindingsByTarget(graphNodes)

  for (const node of graphNodes) {
    if (!isBoundaryConfig(node.data?.config) || !node.data?.boundaryBinding) continue
    const incidentEdges = [
      ...(graphIndex.incomingEdgesByNode.get(node.id) || []),
      ...(graphIndex.outgoingEdgesByNode.get(node.id) || [])
    ]
    if (incidentEdges.length > 0) {
      issues.push({
        code: 'binding_boundary_has_data_edge',
        message: `已绑定 IO 节点“${node.data?.config?.name || node.id}”不能保留普通数据边`,
        nodeId: node.id,
        targetNodeId: node.data.boundaryBinding.bound_node_id,
        edgeIds: [...new Set(incidentEdges.map(edge => edge.id))]
      })
    }
  }

  for (const node of graphNodes) {
    if (!isBoundaryConfig(node.data?.config)) continue
    const exposedHandles = getBoundaryExposedHandles(node, graphNodes, graphEdges)
    const signatures = new Set(exposedHandles.map(handle => [
      handle.handle_config_id || handle.id,
      handle.interface_type_id || handle.id,
      handle.data_type || 'value'
    ].join(':')))
    if (signatures.size > 1) {
      issues.push({
        code: 'boundary_exposed_handle_mismatch',
        message: `IO 节点“${node.data?.config?.name || node.id}”对应了不同类型的相邻接口，请拆分为多个 IO 节点`,
        nodeId: node.id,
        targetNodeId: node.data?.boundaryBinding?.bound_node_id || null
      })
    }
  }

  for (const [targetNodeId, bindings] of Object.entries(bindingsByTarget)) {
    const targetNode = graphIndex.nodeById.get(targetNodeId)
    if (!targetNode || isBoundaryConfig(targetNode.data?.config)) {
      for (const binding of bindings) {
        issues.push({
          code: targetNode ? 'binding_target_is_boundary' : 'binding_target_not_found',
          message: targetNode
            ? '输入输出 IO 节点不能绑定另一个 IO 节点'
            : `绑定目标节点不存在：${targetNodeId}`,
          nodeId: binding.boundaryNode.id,
          targetNodeId
        })
      }
      continue
    }

    const directions = [...new Set(bindings.map(binding => binding.direction))]
    if (directions.length > 1) {
      issues.push({
        code: 'binding_mixed_direction',
        message: `节点“${targetNode.data?.config?.name || targetNode.id}”不能同时绑定蓝图输入和蓝图输出`,
        nodeId: bindings[0].boundaryNode.id,
        targetNodeId,
        relatedBoundaryNodeIds: bindings.map(binding => binding.boundaryNode.id)
      })
    }

    const handleByAlias = new Map()
    for (const handle of targetNode.data?.config?.handles || []) {
      const portId = handle.port_id || handle.id
      handleByAlias.set(handle.id, { handle, portId })
      if (handle.port_id) handleByAlias.set(handle.port_id, { handle, portId })
    }

    for (const binding of bindings) {
      const boundaryNode = binding.boundaryNode
      const expectedType = binding.direction === 'input' ? 'source' : 'target'
      const mappings = boundaryNode.data?.boundaryBinding?.port_mappings || []
      if (mappings.length === 0) {
        issues.push({
          code: 'binding_empty_mapping',
          message: `IO 节点“${boundaryNode.data?.config?.name || boundaryNode.id}”必须至少映射一个目标端口`,
          nodeId: boundaryNode.id,
          targetNodeId
        })
      }
      for (const mapping of mappings) {
        if (mapping.interface_port_id !== boundaryNode.data?.interfacePortId) {
          issues.push({
            code: 'binding_interface_invalid',
            message: '绑定映射引用了其他公开接口端口',
            nodeId: boundaryNode.id,
            targetNodeId,
            targetPortId: mapping.target_port_id
          })
        }
        const targetEntry = handleByAlias.get(mapping.target_port_id)
        if (!targetEntry || targetEntry.handle.type !== expectedType) {
          issues.push({
            code: 'binding_port_direction_invalid',
            message: `目标端口 ${mapping.target_port_id} 不存在或方向错误`,
            nodeId: boundaryNode.id,
            targetNodeId,
            targetPortId: mapping.target_port_id
          })
          continue
        }
      }
    }

    for (const direction of directions) {
      const directionBindings = bindings.filter(binding => binding.direction === direction)
      const occupiedPortOwners = new Map()
      for (const binding of directionBindings) {
        for (const rawPortId of binding.targetPortIds) {
          const portId = handleByAlias.get(rawPortId)?.portId || rawPortId
          if (occupiedPortOwners.has(portId)) {
            issues.push({
              code: 'binding_duplicate_target_port',
              message: `目标端口 ${portId} 被多个同方向 IO 重复替换`,
              nodeId: binding.boundaryNode.id,
              targetNodeId,
              targetPortId: portId
            })
          } else {
            occupiedPortOwners.set(portId, binding.boundaryNode.id)
          }
        }
      }

      const incomingEdges = graphIndex.incomingEdgesByNode.get(targetNodeId) || []
      const outgoingEdges = graphIndex.outgoingEdgesByNode.get(targetNodeId) || []
      if (direction === 'input' && incomingEdges.length > 0) {
        issues.push({
          code: 'binding_target_not_start',
          message: `输入绑定目标“${targetNode.data?.config?.name || targetNode.id}”必须是起始节点`,
          nodeId: directionBindings[0].boundaryNode.id,
          targetNodeId
        })
      }
      if (direction === 'output' && outgoingEdges.length > 0) {
        issues.push({
          code: 'binding_target_not_end',
          message: `输出绑定目标“${targetNode.data?.config?.name || targetNode.id}”必须是结束节点`,
          nodeId: directionBindings[0].boundaryNode.id,
          targetNodeId
        })
      }

      const relevantEdges = direction === 'input' ? outgoingEdges : incomingEdges
      const connectedPortIds = new Set(relevantEdges.map(edge => {
        const rawPortId = direction === 'input'
          ? edge.source_port_id || edge.sourceHandle
          : edge.target_port_id || edge.targetHandle
        return handleByAlias.get(rawPortId)?.portId || rawPortId
      }))
      const mappedPortIds = new Set(occupiedPortOwners.keys())
      for (const portId of mappedPortIds) {
        if (connectedPortIds.has(portId)) continue
        issues.push({
          code: 'binding_port_not_connected',
          message: `目标端口 ${portId} 没有可替换的普通数据边`,
          nodeId: occupiedPortOwners.get(portId),
          targetNodeId,
          targetPortId: portId
        })
      }
      const missingPortIds = [...connectedPortIds]
        .filter(portId => !mappedPortIds.has(portId))
        .sort()
      if (missingPortIds.length > 0) {
        issues.push({
          code: 'binding_port_coverage_incomplete',
          message: `目标节点“${targetNode.data?.config?.name || targetNode.id}”的已连接端口未被完整映射`,
          nodeId: directionBindings[0].boundaryNode.id,
          targetNodeId,
          targetPortIds: missingPortIds
        })
      }
    }
  }

  return issues
}

export const resolveBindingTargetStates = (graphNodes, graphEdges) => {
  const graphIndex = buildBindingGraphIndex(graphNodes, graphEdges)
  const bindingsByTarget = collectBindingsByTarget(graphNodes)
  const issues = validateBoundaryBindings(graphNodes, graphEdges)
  const states = {}

  for (const targetNode of graphNodes) {
    if (isBoundaryConfig(targetNode.data?.config)) continue
    const bindings = bindingsByTarget[targetNode.id] || []
    const directions = [...new Set(bindings.map(binding => binding.direction))]
    const targetIssues = issues.filter(issue => issue.targetNodeId === targetNode.id)
    const role = directions.length === 1
      ? directions[0] === 'input' ? 'entry' : 'exit'
      : null
    const handles = targetNode.data?.config?.handles || []
    const incomingEdges = graphIndex.incomingEdgesByNode.get(targetNode.id) || []
    const outgoingEdges = graphIndex.outgoingEdgesByNode.get(targetNode.id) || []
    states[targetNode.id] = {
      role,
      directions,
      boundaryNodeIds: bindings.map(binding => binding.boundaryNode.id),
      relationCount: bindings.length,
      canAcceptInput: (
        incomingEdges.length === 0
        && outgoingEdges.length > 0
        && handles.some(handle => handle.type === 'source')
        && (directions.length === 0 || role === 'entry')
      ),
      canAcceptOutput: (
        outgoingEdges.length === 0
        && incomingEdges.length > 0
        && handles.some(handle => handle.type === 'target')
        && (directions.length === 0 || role === 'exit')
      ),
      valid: targetIssues.length === 0,
      issues: targetIssues
    }
  }
  return states
}

export const validateBindingCandidate = (
  boundaryNode,
  targetNode,
  graphNodes,
  graphEdges
) => {
  if (!boundaryNode || !targetNode || isBoundaryConfig(targetNode.data?.config)) {
    return {
      valid: false,
      bindableHandles: [],
      issues: [{ code: 'binding_target_invalid', message: '请选择非 IO 目标节点' }]
    }
  }
  const graphIndex = buildBindingGraphIndex(graphNodes, graphEdges)
  if (
    (graphIndex.incomingEdgesByNode.get(boundaryNode.id) || []).length > 0
    || (graphIndex.outgoingEdgesByNode.get(boundaryNode.id) || []).length > 0
  ) {
    return {
      valid: false,
      bindableHandles: [],
      issues: [{
        code: 'binding_boundary_has_data_edge',
        message: 'IO 节点已有普通数据连线，请先删除连线再建立绑定'
      }]
    }
  }
  const direction = getBoundaryDirection(boundaryNode)
  const state = resolveBindingTargetStates(graphNodes, graphEdges)[targetNode.id]
  const roleAllowed = direction === 'input'
    ? state?.canAcceptInput
    : state?.canAcceptOutput
  if (!roleAllowed) {
    return {
      valid: false,
      bindableHandles: [],
      issues: [{
        code: direction === 'input'
          ? 'binding_target_not_start'
          : 'binding_target_not_end',
        message: direction === 'input'
          ? '蓝图输入只能绑定起始节点'
          : '蓝图输出只能绑定结束节点'
      }]
    }
  }

  const bindings = collectBindingsByTarget(graphNodes)[targetNode.id] || []
  const occupiedPortIds = bindings
    .filter(binding => (
      binding.direction === direction
      && binding.boundaryNode.id !== boundaryNode.id
    ))
    .flatMap(binding => binding.targetPortIds)
  const relevantEdges = direction === 'input'
    ? graphIndex.outgoingEdgesByNode.get(targetNode.id) || []
    : graphIndex.incomingEdgesByNode.get(targetNode.id) || []
  const connectedPortIds = relevantEdges.map(edge => (
    direction === 'input'
      ? edge.source_port_id || edge.sourceHandle
      : edge.target_port_id || edge.targetHandle
  ))
  const bindableHandles = getBindableHandles(boundaryNode, targetNode, {
    occupiedPortIds,
    connectedPortIds
  })
  return {
    valid: bindableHandles.length > 0,
    bindableHandles,
    issues: bindableHandles.length > 0
      ? []
      : [{ code: 'binding_port_unavailable', message: '没有可用的已连接兼容端口' }]
  }
}

export const buildBindingRelationEdges = (graphNodes, targetStates = {}) => {
  const nodeIds = new Set(graphNodes.map(node => node.id))
  return graphNodes
    .filter(node => (
      isBoundaryConfig(node.data?.config)
      && node.data?.boundaryBinding?.bound_node_id
      && nodeIds.has(node.data.boundaryBinding.bound_node_id)
    ))
    .map(boundaryNode => {
      const direction = getBoundaryDirection(boundaryNode)
      const targetNodeId = boundaryNode.data.boundaryBinding.bound_node_id
      const targetNode = graphNodes.find(node => node.id === targetNodeId)
      const boundaryHandle = getBoundaryHandle(boundaryNode)
      const input = direction === 'input'
      const invalid = targetStates[targetNodeId]?.valid === false
      const display = buildBindingDisplay(
        boundaryNode,
        targetNode,
        boundaryNode.data.boundaryBinding.port_mappings
          .map(mapping => mapping.target_port_id)
      )
      return {
        id: `binding:${boundaryNode.id}:${targetNodeId}`,
        type: 'boundaryBinding',
        source: input ? boundaryNode.id : targetNodeId,
        sourceHandle: input
          ? boundaryHandle?.id
          : BINDING_SOURCE_HANDLE_ID,
        target: input ? targetNodeId : boundaryNode.id,
        targetHandle: input
          ? BINDING_TARGET_HANDLE_ID
          : boundaryHandle?.id,
        selectable: false,
        deletable: false,
        focusable: false,
        data: {
          relationKind: 'boundary-binding',
          boundaryNodeId: boundaryNode.id,
          targetNodeId,
          direction,
          tooltip: `${
            input ? '入口替代' : '出口替代'
          }：${display.targetNodeName}；${display.portDescription}`
        },
        style: {
          stroke: invalid ? '#ef4444' : input ? '#60a5fa' : '#a78bfa',
          strokeWidth: 2,
          strokeDasharray: '6 5'
        }
      }
    })
}

export const collectBindingTargetKinds = graphNodes => {
  return Object.fromEntries(
    Object.entries(collectBindingsByTarget(graphNodes)).map(
      ([targetNodeId, bindings]) => [
        targetNodeId,
        [...new Set(bindings.map(binding => binding.direction))].sort()
      ]
    )
  )
}

export const getBoundaryInitialPosition = (boundaryNode, targetNode, gap = 48) => {
  const boundaryWidth = boundaryNode?.dimensions?.width || 300
  const boundaryHeight = boundaryNode?.dimensions?.height || 220
  const targetWidth = targetNode?.dimensions?.width || 300
  const targetPosition = targetNode?.position || { x: 0, y: 0 }
  return {
    x: getBoundaryDirection(boundaryNode) === 'input'
      ? targetPosition.x - boundaryWidth - gap
      : targetPosition.x + targetWidth + gap,
    y: targetPosition.y - boundaryHeight - gap
  }
}
