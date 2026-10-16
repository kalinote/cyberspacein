import test from 'node:test'
import assert from 'node:assert/strict'
import { buildEvidenceApprovalSections, formatEvidenceValue } from '../src/utils/evidenceApproval.js'
import { getApprovalSourceLabel, APPROVAL_SOURCES_EVIDENCE } from '../src/utils/agentApproval.js'

test('证据链审批展示前后差异、来源及移除的子链引用', () => {
    const sections = buildEvidenceApprovalSections({
        metadata: { title: { before: '旧名称', after: '新名称' } },
        nodes: { added: [], removed: [{ id: 'ref', label: '事件溯源', kind: 'chain', chain_id: 'child' }], updated: [{ id: 'n1', label: '线索', changes: { position: { before: { x: 0, y: 0 }, after: { x: 340, y: 80 } } } }] },
        edges: { added: [{ id: 'e1', label: '支持', anchors: [{ entity: { entity_type: 'article', uuid: 'v1' }, quote: '实际原文', locator: '第三段' }] }] },
    })
    assert.equal(sections[0].rows[0].after, '新名称')
    assert.match(sections.find(section => section.title === '移除节点（1）').rows[0].before, /子链引用：child/)
    assert.equal(sections.find(section => section.title === '修改节点（1）').rows[0].after, '横向 340，纵向 80')
    assert.match(sections.find(section => section.title === '新增关系（1）').rows[0].after, /article · v1\n第三段\n实际原文/)
})

test('删除、空值和审批来源有明确显示', () => {
    assert.deepEqual(buildEvidenceApprovalSections({ deleted: true }), [])
    assert.equal(formatEvidenceValue([], 'members'), '（空）')
    assert.equal(formatEvidenceValue('pending', 'status'), '待核实')
    assert.equal(getApprovalSourceLabel('tool:evidence_save'), '保存证据链')
    assert.equal(APPROVAL_SOURCES_EVIDENCE.length, 3)
})
