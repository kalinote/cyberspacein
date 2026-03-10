export const formatJson = (val) => {
  if (val === null || val === undefined) return '-'
  try {
    return typeof val === 'string' ? val : JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

export const getValueType = (val) => {
  if (val === null) return 'null'
  if (Array.isArray(val)) return '数组'
  if (val instanceof Date) return '日期'
  const t = typeof val
  if (t === 'object') return '对象'
  if (t === 'string') return '字符串'
  if (t === 'number') return '数字'
  if (t === 'boolean') return '布尔'
  if (t === 'undefined') return '未定义'
  return t
}

export const isComplexValue = (val) => {
  return val !== null && typeof val === 'object'
}

export const getValuePreview = (val) => {
  if (val === null || val === undefined) return 'null'
  if (typeof val === 'string') {
    return val.length > 60 ? `${val.slice(0, 57)}...` : val
  }
  if (typeof val === 'number' || typeof val === 'boolean') {
    return String(val)
  }
  try {
    const json = JSON.stringify(val)
    return json.length > 60 ? `${json.slice(0, 57)}...` : json
  } catch {
    return String(val)
  }
}

export const filterByKeyword = (list, fields, keyword) => {
  const k = (keyword || '').trim().toLowerCase()
  if (!k) return list
  return list.filter(item =>
    fields.some(f => String(item[f] ?? '').toLowerCase().includes(k))
  )
}

