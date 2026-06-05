/** @typedef {'string' | 'number' | 'array' | 'object'} TypedValueKind */

export const TYPED_VALUE_OPTIONS = [
    { value: 'string', label: '字符串' },
    { value: 'number', label: '数字' },
    { value: 'array', label: '数组' },
    { value: 'object', label: '对象' },
]

/**
 * @param {unknown} value
 * @returns {TypedValueKind}
 */
export function inferValueType(value) {
    if (value === null || value === undefined) return 'string'
    if (typeof value === 'number' && Number.isFinite(value)) return 'number'
    if (Array.isArray(value)) return 'array'
    if (typeof value === 'object') return 'object'
    return 'string'
}

/**
 * @param {unknown} value
 * @param {TypedValueKind} type
 * @returns {string}
 */
export function valueToEditString(value, type) {
    if (type === 'array' || type === 'object') {
        if (value === undefined) return ''
        try {
            return JSON.stringify(value, null, 2)
        } catch {
            return ''
        }
    }
    if (type === 'number') {
        if (value === null || value === undefined || value === '') return ''
        return String(value)
    }
    return value == null ? '' : String(value)
}

/**
 * @param {string} raw
 * @param {TypedValueKind} type
 * @returns {{ ok: true, value: unknown } | { ok: false, error: string }}
 */
export function parseTypedValue(raw, type) {
    const text = String(raw ?? '')
    if (type === 'number') {
        const trimmed = text.trim()
        if (trimmed === '') {
            return { ok: false, error: '请输入数字' }
        }
        const n = Number(trimmed)
        if (Number.isNaN(n)) {
            return { ok: false, error: '无效数字' }
        }
        return { ok: true, value: n }
    }
    if (type === 'array') {
        const trimmed = text.trim()
        if (trimmed === '') {
            return { ok: true, value: [] }
        }
        try {
            const parsed = JSON.parse(trimmed)
            if (!Array.isArray(parsed)) {
                return { ok: false, error: '必须是 JSON 数组' }
            }
            return { ok: true, value: parsed }
        } catch {
            return { ok: false, error: 'JSON 解析失败' }
        }
    }
    if (type === 'object') {
        const trimmed = text.trim()
        if (trimmed === '') {
            return { ok: true, value: {} }
        }
        try {
            const parsed = JSON.parse(trimmed)
            if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
                return { ok: false, error: '必须是 JSON 对象' }
            }
            return { ok: true, value: parsed }
        } catch {
            return { ok: false, error: 'JSON 解析失败' }
        }
    }
    return { ok: true, value: text }
}

/**
 * @param {Record<string, unknown>} obj
 * @returns {string}
 */
export function stableStringifyObject(obj) {
    try {
        return JSON.stringify(obj)
    } catch {
        return ''
    }
}
