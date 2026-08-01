const getCompilerConfig = (nodeConfig) => (
  nodeConfig?.extension?.config?.compiler
  || nodeConfig?.extension?.compiler
  || {}
)

export const allowsMultipleHandleInputs = (nodeConfig, handleConfig) => (
  Boolean(handleConfig?.allow_multiple_inputs)
  || Boolean(getCompilerConfig(nodeConfig).allow_multiple_inputs)
)

export const acceptsHandleDataType = (sourceHandle, targetHandle) => {
  const sourceDataType = sourceHandle?.data_type || 'value'
  const acceptedDataTypes = (
    Array.isArray(targetHandle?.accepted_data_types)
    && targetHandle.accepted_data_types.length > 0
  )
    ? targetHandle.accepted_data_types
    : [targetHandle?.data_type || 'value']
  return acceptedDataTypes.includes(sourceDataType)
}

export const areHandleInterfacesCompatible = (sourceHandle, targetHandle) => {
  const sourceHandleId = sourceHandle?.interface_type_id || sourceHandle?.id
  const targetHandleId = targetHandle?.interface_type_id || targetHandle?.id
  if (!sourceHandleId || !targetHandleId) return false
  if (sourceHandleId === targetHandleId) return true

  const sourceCompatibleInterfaces = [
    ...(sourceHandle?.compatible_interface_type_ids || []),
    ...(sourceHandle?.other_compatible_interfaces || [])
  ]
  const targetCompatibleInterfaces = [
    ...(targetHandle?.compatible_interface_type_ids || []),
    ...(targetHandle?.other_compatible_interfaces || [])
  ]
  return sourceCompatibleInterfaces.includes('*')
    || targetCompatibleInterfaces.includes('*')
    || sourceCompatibleInterfaces.includes(targetHandleId)
    || sourceCompatibleInterfaces.includes(targetHandle?.id)
    || targetCompatibleInterfaces.includes(sourceHandleId)
    || targetCompatibleInterfaces.includes(sourceHandle?.id)
}

export const isDuplicateHandleConnection = (edges, connection) => (
  edges.some(edge => (
    edge.id !== connection.id
    && edge.source === connection.source
    && edge.sourceHandle === connection.sourceHandle
    && edge.target === connection.target
    && edge.targetHandle === connection.targetHandle
  ))
)
