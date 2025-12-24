import { INPUT_TYPE_DEFAULTS } from './constants'

// 规范化输入默认值
export const normalizeDefaultValue = (type, value) => {
  if (value === undefined || value === null) {
    return INPUT_TYPE_DEFAULTS[type] ?? null
  }
  
  switch (type) {
    case 'int':
      const numValue = Number(value)
      return isNaN(numValue) ? null : numValue
      
    case 'boolean':
    case 'checkbox':
      return Boolean(value)
      
    case 'tags':
    case 'checkbox-group':
    case 'conditions':
      return Array.isArray(value) ? value : []
      
    case 'string':
    case 'textarea':
    case 'select':
    case 'radio-group':
    case 'datetime':
      return value
      
    default:
      return value
  }
}

// 获取节点默认数据
export const getDefaultData = (config, socketTypeConfigs) => {
  const data = {
    config: config,
    socketTypeConfigs: socketTypeConfigs
  }
  
  if (config.inputs) {
    config.inputs.forEach(input => {
      data[input.id] = normalizeDefaultValue(input.type, input.default)
    })
  }
  
  return data
}

// 根据节点配置获取节点颜色
export const getNodeColor = (config, socketTypeConfigs) => {
  if (config.handles && config.handles.length > 0) {
    const firstHandle = config.handles[0]
    const socketConfig = socketTypeConfigs.find(
      s => s.socket_type === firstHandle.socket_type
    )
    return socketConfig?.color || '#909399'
  }
  return '#909399'
}

// 根据 socket_type 获取连接线颜色
export const getEdgeColor = (socketType, socketTypeConfigs) => {
  const socketConfig = socketTypeConfigs.find(
    s => s.socket_type === socketType
  )
  return socketConfig?.color || '#909399'
}

