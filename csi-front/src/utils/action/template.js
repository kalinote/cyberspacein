// 验证参数名称是否合法（只允许字母、数字、下划线，且不能以数字开头）
export const validateParamName = (name) => {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)
}

// 生成唯一的参数ID
export const generateParamId = () => {
  return `param_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// 检查参数名是否已存在（可忽略指定id）
export const isParamNameExists = (name, params, excludeId = null) => {
  return params.some(p => p.id !== excludeId && p.name === name)
}

// 获取参数在所有绑定中的引用次数
export const getParamReferenceCount = (paramName, bindings) => {
  let count = 0
  Object.values(bindings).forEach(nodeBindings => {
    Object.values(nodeBindings).forEach(boundParamName => {
      if (boundParamName === paramName) {
        count++
      }
    })
  })
  return count
}

// 删除指定参数在所有绑定中的引用
export const removeParamBindings = (paramName, bindings) => {
  Object.keys(bindings).forEach(nodeId => {
    Object.keys(bindings[nodeId]).forEach(fieldName => {
      if (bindings[nodeId][fieldName] === paramName) {
        delete bindings[nodeId][fieldName]
      }
    })
    if (Object.keys(bindings[nodeId]).length === 0) {
      delete bindings[nodeId]
    }
  })
}

// 更新所有已绑定的参数名（重命名）
export const updateParamBindingsName = (oldName, newName, bindings) => {
  Object.keys(bindings).forEach(nodeId => {
    Object.keys(bindings[nodeId]).forEach(fieldName => {
      if (bindings[nodeId][fieldName] === oldName) {
        bindings[nodeId][fieldName] = newName
      }
    })
  })
}
