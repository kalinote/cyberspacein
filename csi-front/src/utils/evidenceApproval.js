const FIELD_LABELS = {
    title: '名称', description: '说明', purpose: '分析目的', template: '模板', status: '状态',
    tags: '标签', relation_types: '关系类型', label: '名称', kind: '节点类型',
    position: '位置', entity: '实体引用', members: '固定成员', version_source: '版本来源',
    chain_id: '子链引用', attributes: '属性', source: '起点', target: '终点',
    directed: '有向关系', anchors: '实体依据',
}
const VALUE_LABELS = {
    draft: '草稿', active: '分析中', archived: '已归档', pending: '待核实',
    confirmed: '人工确认', disputed: '存疑', blank: '自由构建', proof: '证明与反证',
    expansion: '信息扩展', trace: '事件溯源', entity: '实体引用', note: '自定义节点',
    collection: '固定集合', versions: '动态版本', chain: '子链引用',
}

export function formatEvidenceValue(value, field) {
    if (value == null) return '未设置'
    if (typeof value === 'boolean') return value ? '是' : '否'
    if (Array.isArray(value)) return value.length ? value.map(item => formatEvidenceValue(item, field)).join('\n') : '（空）'
    if (typeof value === 'object') {
        if (field === 'position') return `横向 ${value.x}，纵向 ${value.y}`
        if (field === 'version_source') return `${value.entity_type} · ${value.platform} · ${value.source_id}`
        if (value.entity_type && value.uuid) return `${value.entity_type} · ${value.uuid}`
        if (field === 'anchors') return [formatEvidenceValue(value.entity, 'entity'), value.locator, value.quote].filter(Boolean).join('\n')
        return JSON.stringify(value, null, 2)
    }
    return ['status', 'template', 'kind'].includes(field) ? (VALUE_LABELS[value] || String(value)) : (String(value) || '（空）')
}

export function buildEvidenceApprovalSections(diff) {
    if (!diff || diff.deleted) return []
    const sections = []
    const metadata = Object.entries(diff.metadata || {}).map(([key, change]) => ({
        label: FIELD_LABELS[key] || key,
        before: formatEvidenceValue(change.before, key), after: formatEvidenceValue(change.after, key),
    }))
    if (metadata.length) sections.push({ title: '基本信息', rows: metadata })
    for (const [kind, label] of [['nodes', '节点'], ['edges', '关系']]) {
        const group = diff[kind] || {}
        for (const [action, actionLabel] of [['added', '新增'], ['removed', '移除'], ['updated', '修改']]) {
            const rows = (group[action] || []).flatMap(item => {
                const name = item.label || item.id
                if (action === 'updated') return Object.entries(item.changes || {}).map(([key, change]) => ({
                    label: `${name} · ${FIELD_LABELS[key] || key}`,
                    before: formatEvidenceValue(change.before, key), after: formatEvidenceValue(change.after, key),
                }))
                const detail = Object.entries(item).filter(([key, value]) => key !== 'id' && value != null && value !== '' && (!Array.isArray(value) || value.length))
                    .map(([key, value]) => `${FIELD_LABELS[key] || key}：${formatEvidenceValue(value, key)}`).join('\n')
                return [{ label: name, [action === 'added' ? 'after' : 'before']: detail }]
            })
            if (rows.length) sections.push({ title: `${actionLabel}${label}（${(group[action] || []).length}）`, rows })
        }
    }
    return sections
}
