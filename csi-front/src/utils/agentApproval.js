export const APPROVAL_SOURCE_MODIFY_ENTITY = 'tool:modify_entity'
export const APPROVAL_SOURCE_WIKI_CREATE = 'tool:wiki_create'
export const APPROVAL_SOURCE_WIKI_EDIT = 'tool:wiki_edit'

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

const WIKI_STATUS_LABELS = {
    draft: '草稿',
    building: '构建中',
    published: '已发布',
}

const WIKI_EDIT_OPERATION_LABELS = {
    patch_meta: '修改元数据',
    patch_main: '修改导语',
    add_section: '添加章节',
    patch_section: '编辑章节',
    move_section: '移动章节',
    put_footnotes: '更新脚注',
    put_references: '更新参考文献',
}

const SOURCE_LABELS = {
    [APPROVAL_SOURCE_MODIFY_ENTITY]: '修改实体',
    [APPROVAL_SOURCE_WIKI_CREATE]: '创建 Wiki 页面',
    [APPROVAL_SOURCE_WIKI_EDIT]: '编辑 Wiki 页面',
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

export function getWikiStatusLabel(status) {
    return lookupLabel(WIKI_STATUS_LABELS, status)
}

export function getWikiEditOperationLabel(operation) {
    return lookupLabel(WIKI_EDIT_OPERATION_LABELS, operation)
}

export function getWikiDetailRoute(wikiId) {
    const id = wikiId != null ? String(wikiId).trim() : ''
    if (!id) return null
    return `/details/wiki/${id}`
}

export function getWikiCreatePayload(envelope) {
    if (!envelope || envelope.source !== APPROVAL_SOURCE_WIKI_CREATE) return null
    const payload = envelope.payload
    return payload && typeof payload === 'object' ? payload : null
}

export function getWikiEditPayload(envelope) {
    if (!envelope || envelope.source !== APPROVAL_SOURCE_WIKI_EDIT) return null
    const payload = envelope.payload
    return payload && typeof payload === 'object' ? payload : null
}

/**
 * @param {string} operation
 * @param {Record<string, unknown>|null|undefined} params
 * @returns {Array<{ label: string, kind: 'text'|'tags'|'items'|'pre', text?: string, tags?: string[], items?: Array<{ primary: string, secondary?: string }> }>}
 */
export function buildWikiEditParamRows(operation, params) {
    const p = params && typeof params === 'object' ? params : {}
    const op = operation != null ? String(operation) : ''
    const rows = []

    function pushText(label, value) {
        if (value == null || value === '') return
        rows.push({ label, kind: 'text', text: String(value) })
    }

    function pushPre(label, value) {
        if (value == null || value === '') return
        rows.push({ label, kind: 'pre', text: String(value) })
    }

    function pushTags(label, value) {
        const tags = Array.isArray(value) ? value.map((v) => String(v)).filter(Boolean) : []
        if (!tags.length) return
        rows.push({ label, kind: 'tags', tags })
    }

    function pushItems(label, value) {
        const list = Array.isArray(value) ? value : []
        const items = list
            .map((item) => {
                if (!item || typeof item !== 'object') return null
                const id = item.id != null ? String(item.id) : ''
                const text = item.text != null ? String(item.text) : ''
                const url = item.url != null ? String(item.url) : ''
                const primary = [id, text].filter(Boolean).join(' · ') || '—'
                return { primary, secondary: url || undefined }
            })
            .filter(Boolean)
        if (!items.length) {
            rows.push({ label, kind: 'text', text: '（空）' })
            return
        }
        rows.push({ label, kind: 'items', items })
    }

    if (op === 'patch_meta') {
        if (p.status != null) {
            pushText('状态', `${getWikiStatusLabel(p.status)} (${p.status})`)
        }
        pushTags('分类', p.categories)
    } else if (op === 'patch_main') {
        pushPre('导语内容', p.content)
        if (p.infobox_set != null) {
            pushText('信息框', p.infobox_set ? '已设置' : '未设置')
        }
    } else if (op === 'add_section' || op === 'patch_section') {
        pushText('章节 ID', p.section_id)
        pushText('章节标题', p.title)
        pushText('父章节', p.parent_section)
        pushPre('章节内容', p.content)
    } else if (op === 'move_section') {
        pushText('章节 ID', p.section_id)
        pushText('父章节', p.parent_section)
        pushText('置于章节之后', p.after_section)
    } else if (op === 'put_footnotes') {
        pushItems('脚注', p.items)
    } else if (op === 'put_references') {
        pushItems('参考文献', p.items)
    } else if (Object.keys(p).length) {
        try {
            rows.push({ label: '参数', kind: 'pre', text: JSON.stringify(p, null, 2) })
        } catch {
            rows.push({ label: '参数', kind: 'text', text: String(p) })
        }
    }

    return rows
}
