import { getEntityCategoryLabel } from '@/utils/agentApproval'

export function entityRefKey(category, name) {
    return `${category}:${name}`
}

export function entityDisplayName(key) {
    const s = key != null ? String(key) : ''
    const idx = s.indexOf(':')
    return idx >= 0 ? s.slice(idx + 1) : s
}

export function getEntityGroups(entities) {
    if (!entities || typeof entities !== 'object' || Array.isArray(entities)) return []
    return Object.entries(entities)
        .map(([key, items]) => ({
            key,
            label: getEntityCategoryLabel(key),
            items: Array.isArray(items) ? items.map((v) => String(v)).filter(Boolean) : [],
        }))
        .filter((g) => g.items.length > 0)
}

export function hasEntities(entities) {
    return getEntityGroups(entities).length > 0
}
