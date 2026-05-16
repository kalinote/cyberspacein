export const APPROVAL_SOURCE_MODIFY_ENTITY = 'tool:modify_entity'

const ENTITY_CATEGORY_LABELS = {
    person: '人物',
    location: '地点',
    organization: '组织',
    company: '公司',
    region: '区域',
    network_user: '网络用户',
}

const MODIFICATION_FIELD_LABELS = {
    keywords: '关键词',
    entities: '结构化实体',
}

const ENTITY_TYPE_LABELS = {
    article: '文章',
    forum: '论坛',
    platform: '平台',
}

const ACTION_LABELS = {
    set: '设置',
    append: '追加',
    remove: '移除',
}

const SOURCE_LABELS = {
    [APPROVAL_SOURCE_MODIFY_ENTITY]: '修改实体',
}

const DETAIL_ROUTE_ENTITY_TYPES = new Set(['article', 'forum', 'platform'])

function lookupLabel(map, key, fallback = '—') {
    const k = key != null ? String(key) : ''
    return map[k] || k || fallback
}

export function isApprovalAwaitingUserAction(envelope) {
    if (!envelope || typeof envelope !== 'object') return false
    if (!('resolution' in envelope)) return true
    return envelope.resolution == null
}

export function getApprovalSourceLabel(source) {
    const key = source != null ? String(source) : ''
    if (SOURCE_LABELS[key]) return SOURCE_LABELS[key]
    if (key.startsWith('tool:')) return `工具：${key.slice(5)}`
    if (key.startsWith('step:')) return `步骤：${key.slice(5)}`
    return key || '审批'
}

export function getEntityTypeLabel(entityType) {
    return lookupLabel(ENTITY_TYPE_LABELS, entityType)
}

export function getModificationFieldLabel(field) {
    return lookupLabel(MODIFICATION_FIELD_LABELS, field)
}

export function getActionLabel(action) {
    return lookupLabel(ACTION_LABELS, action)
}

export function getEntityCategoryLabel(category) {
    return lookupLabel(ENTITY_CATEGORY_LABELS, category)
}

export function getEntityDetailRoute(entityType, uuid) {
    const type = entityType != null ? String(entityType).toLowerCase() : ''
    const id = uuid != null ? String(uuid).trim() : ''
    if (!type || !id || !DETAIL_ROUTE_ENTITY_TYPES.has(type)) return null
    return `/details/${type}/${id}`
}

export function truncateUuid(uuid, head = 8, tail = 6) {
    const s = uuid != null ? String(uuid) : ''
    if (s.length <= head + tail + 3) return s
    return `${s.slice(0, head)}…${s.slice(-tail)}`
}

function parseEntitiesFieldValue(raw) {
    if (raw == null) return null
    if (typeof raw === 'object' && !Array.isArray(raw)) return raw
    const text = String(raw).trim()
    if (!text) return null
    try {
        const parsed = JSON.parse(text)
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
    } catch {
        return null
    }
}

/**
 * @param {{ field?: string, action?: string, value?: unknown }} mod
 */
export function parseModificationValue(mod) {
    const field = mod?.field != null ? String(mod.field) : ''
    const value = mod?.value

    if (field === 'keywords' && Array.isArray(value)) {
        return {
            kind: 'tags',
            tags: value.map((v) => String(v)).filter(Boolean),
        }
    }

    if (field === 'entities') {
        const groups = parseEntitiesFieldValue(value)
        if (groups) {
            const entityGroups = Object.entries(groups)
                .map(([key, items]) => ({
                    key,
                    label: getEntityCategoryLabel(key),
                    items: Array.isArray(items) ? items.map((v) => String(v)).filter(Boolean) : [],
                }))
                .filter((g) => g.items.length > 0)
            if (entityGroups.length) {
                return { kind: 'entityGroups', entityGroups }
            }
        }
    }

    if (value == null) {
        return { kind: 'primitive', primitive: '—' }
    }

    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
        return { kind: 'primitive', primitive: String(value) }
    }

    try {
        return { kind: 'json', json: JSON.stringify(value, null, 2) }
    } catch {
        return { kind: 'primitive', primitive: String(value) }
    }
}

export function getModifyEntityPayload(envelope) {
    if (!envelope || envelope.source !== APPROVAL_SOURCE_MODIFY_ENTITY) return null
    const payload = envelope.payload
    return payload && typeof payload === 'object' ? payload : null
}
