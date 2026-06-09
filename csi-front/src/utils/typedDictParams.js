/**
 * 类型化字典参数工具 (typedDictParams)
 *
 * 为 TypedDictParamsEditor 及分析引擎 injection_param 等场景提供参数行与对象的互转、校验能力。
 * 编辑交互参考 /action/task-configs 的配置参数 (config) 区块。
 *
 * 使用场景：
 * - AgentStartDialog 提交前将 ParamRow[] 转为 injection_param 对象
 * - 详情页打开弹窗时将 { entity_uuid, entity_type } 转为预填参数行
 * - 校验参数名是否重复
 *
 * 使用示例：
 * import {
 *   objectToParamRows,
 *   buildObjectFromParamRows,
 *   validateParamRows,
 * } from '@/utils/typedDictParams'
 *
 * const rows = objectToParamRows({ entity_uuid: 'xxx', entity_type: 'article' })
 * const injectionParam = buildObjectFromParamRows(rows)
 * const error = validateParamRows(rows) // null 表示通过
 *
 * @typedef {'string'|'number'|'boolean'|'null'|'array'|'object'} ParamValueType
 */

/**
 * @typedef {Object} ParamRow
 * @property {string} key
 * @property {ParamValueType} valueType
 * @property {*} value
 */

/**
 * @param {*} val
 * @returns {ParamValueType}
 */
export function detectValueType(val) {
  if (val === null) return 'null'
  if (Array.isArray(val)) return 'array'
  if (val !== null && typeof val === 'object') return 'object'
  if (typeof val === 'boolean') return 'boolean'
  if (typeof val === 'number') return 'number'
  return 'string'
}

/**
 * @param {*} val
 * @returns {string}
 */
export function summarizeValue(val) {
  if (val === null) return 'null'
  const t = typeof val
  if (t === 'string') return val.length > 80 ? JSON.stringify(val.slice(0, 80) + '...') : JSON.stringify(val)
  if (t === 'number' || t === 'boolean') return String(val)
  if (Array.isArray(val)) return `数组(${val.length})：` + (val.length ? summarizeValue(val[0]) : '空')
  if (t === 'object') {
    const keys = Object.keys(val || {})
    return `对象(${keys.length})：` + (keys.length ? `${keys[0]}=${summarizeValue(val[keys[0]])}` : '空')
  }
  return String(val)
}

/**
 * @param {*} val
 * @param {*} [fallback]
 * @returns {*}
 */
export function deepCloneJsonLike(val, fallback = null) {
  if (val === null || val === undefined) return val ?? fallback
  if (typeof val !== 'object') return val
  try {
    return JSON.parse(JSON.stringify(val))
  } catch {
    return fallback
  }
}

/**
 * @param {*} str
 * @returns {object|array|null}
 */
export function tryParseJsonStringToValue(str) {
  if (typeof str !== 'string') return null
  const trimmed = str.trim()
  if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return null
  try {
    const parsed = JSON.parse(trimmed)
    if (parsed !== null && typeof parsed === 'object') return parsed
    return null
  } catch {
    return null
  }
}

/**
 * @param {object} [obj]
 * @returns {ParamRow[]}
 */
export function objectToParamRows(obj = {}) {
  return Object.entries(obj).map(([key, val]) => {
    const parsedMaybe = tryParseJsonStringToValue(val)
    const normalizedVal = parsedMaybe ?? val
    const vt = detectValueType(normalizedVal)
    return {
      key,
      valueType: vt,
      value: (vt === 'array' || vt === 'object')
        ? deepCloneJsonLike(normalizedVal, vt === 'array' ? [] : {})
        : normalizedVal,
    }
  })
}

/**
 * @param {ParamRow[]} rows
 * @returns {Record<string, *>}
 */
export function buildObjectFromParamRows(rows) {
  const result = {}
  rows.forEach((row) => {
    if (!row.key) return
    let val = row.value
    if (row.valueType === 'number') val = typeof val === 'number' ? val : Number(val) || 0
    else if (row.valueType === 'boolean') val = !!val
    else if (row.valueType === 'null') val = null
    else if (row.valueType === 'array') val = Array.isArray(val) ? val : []
    else if (row.valueType === 'object') {
      val = (val !== null && typeof val === 'object' && !Array.isArray(val)) ? val : {}
    }
    result[row.key] = val
  })
  return result
}

/**
 * @param {ParamRow} row
 */
export function resetParamRowValueByType(row) {
  if (row.valueType === 'number') row.value = 0
  else if (row.valueType === 'boolean') row.value = false
  else if (row.valueType === 'null') row.value = null
  else if (row.valueType === 'array') row.value = []
  else if (row.valueType === 'object') row.value = {}
  else row.value = ''
}

/**
 * @returns {ParamRow}
 */
export function createEmptyParamRow() {
  return { key: '', valueType: 'string', value: '' }
}

/**
 * @param {ParamRow[]} rows
 * @returns {string|null}
 */
export function validateParamRows(rows) {
  const keys = new Set()
  for (const row of rows) {
    const key = row.key?.trim()
    if (!key) continue
    if (keys.has(key)) return `参数名「${key}」重复`
    keys.add(key)
  }
  return null
}
