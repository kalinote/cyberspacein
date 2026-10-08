import test from 'node:test'
import assert from 'node:assert/strict'
import { makeEvidenceGraph, makeEvidenceNode, projectEvidenceGraph } from '../src/utils/evidence.js'
import { projectMobileEvidenceGraph, evidenceRemovalImpact, moveEvidenceNodes, removeEvidenceNodes } from '../src/components/evidence/mobile/mobileEvidenceGraph.js'

/** """构造含嵌套引用端点及相似前缀的固定图定义。""" */
function fixture() {
  const graph = makeEvidenceGraph('blank', '虚构证据图')
  graph.nodes = ['claim', 'material', 'material-long', 'other'].map((id, index) => makeEvidenceNode('note', { id, label: id, position: { x: 1500 + index * 300, y: 800 + index * 200 } }))
  graph.edges = [
    { id: 'support', source: 'material', target: 'claim', label: '支持', status: 'pending', directed: true, description: '', anchors: [{ entity: { entity_type: 'article', uuid: 'sample-version' }, quote: '测试摘录', locator: '第三段' }] },
    { id: 'refute', source: 'material-long', target: 'claim', label: '反驳', status: 'confirmed', directed: true, description: '', anchors: [] },
    { id: 'second-layer', source: 'other', target: 'material', label: '关联', status: 'pending', directed: false, description: '', anchors: [] },
    { id: 'nested', source: 'material/internal/deep', target: 'claim', label: '支持', status: 'pending', directed: true, description: '', anchors: [] }
  ]
  return graph
}

test('局部一层与展开仅改变投影，筛选保留真实端点与原始依据', () => {
  const graph = fixture(), rendered = projectEvidenceGraph(graph), snapshot = JSON.stringify({ graph, rendered })
  const local = projectMobileEvidenceGraph(rendered, { focusId: 'claim', depth: 1 })
  assert.deepEqual(local.nodes.map(node => node.id).sort(), ['claim', 'material', 'material-long'])
  assert.equal(local.hiddenCount, 1)
  assert.equal(projectMobileEvidenceGraph(rendered, { focusId: 'claim', depth: 2 }).nodes.length, 4)
  const supporting = projectMobileEvidenceGraph(rendered, { focusId: 'claim', filter: 'support' })
  assert.deepEqual(supporting.edges.map(edge => edge.id).sort(), ['nested', 'support'])
  assert.equal(supporting.edges.find(edge => edge.id === 'nested').data.edge.source, 'material/internal/deep')
  const refuting = projectMobileEvidenceGraph(rendered, { focusId: 'claim', filter: 'refute' })
  assert.deepEqual(refuting.edges.map(edge => edge.id), ['refute'])
  assert.equal(projectMobileEvidenceGraph(rendered, { focusId: 'claim', filter: 'pending' }).edges.some(edge => edge.id === 'refute'), false)
  supporting.nodes[0].position.x = -999
  supporting.nodes[0].data.node.position.x = -888
  supporting.edges[0].data.edge.anchors[0].quote = '仅修改投影'
  assert.equal(JSON.stringify({ graph, rendered }), snapshot)
})

test('移动按用户增量修改原坐标，引用内部、非法位移及重复ID不会损坏位置', () => {
  const graph = fixture(), original = structuredClone(graph)
  assert.equal(moveEvidenceNodes(graph, ['material', 'material', 'material/internal'], { x: 40, y: -20 }), true)
  assert.deepEqual(graph.nodes[1].position, { x: original.nodes[1].position.x + 40, y: original.nodes[1].position.y - 20 })
  assert.deepEqual(graph.nodes[0], original.nodes[0])
  const snapshot = JSON.stringify(graph)
  assert.equal(moveEvidenceNodes(graph, ['material/internal'], { x: 40, y: 0 }), false)
  assert.equal(moveEvidenceNodes(graph, ['material'], { x: Infinity, y: 0 }), false)
  assert.equal(moveEvidenceNodes(graph, ['material'], { x: 0, y: 0 }), false)
  assert.equal(JSON.stringify(graph), snapshot)
})

test('批量移出准确计算内部端点关联，不误删相似前缀或引用原始材料', () => {
  const graph = fixture(), snapshot = structuredClone(graph)
  const impact = evidenceRemovalImpact(graph, ['material', 'material/internal'])
  assert.deepEqual(impact.nodeIds, ['material'])
  assert.deepEqual(impact.edgeIds.sort(), ['nested', 'second-layer', 'support'])
  removeEvidenceNodes(graph, ['material'])
  assert.deepEqual(graph.nodes.map(node => node.id), ['claim', 'material-long', 'other'])
  assert.deepEqual(graph.edges.map(edge => edge.id), ['refute'])
  assert.equal(snapshot.edges[0].anchors[0].entity.uuid, 'sample-version')
})

test('空图与失效焦点能安全回退，不凭空写入节点', () => {
  assert.deepEqual(projectMobileEvidenceGraph({ nodes: [], edges: [] }), { nodes: [], edges: [], focusId: '', hiddenCount: 0 })
  const rendered = projectEvidenceGraph(fixture())
  assert.equal(projectMobileEvidenceGraph(rendered, { focusId: 'removed' }).focusId, 'claim')
})

test('大量同层邻居使用最多两列纵排，避免自动布局变成超宽横条', () => {
  const graph = fixture()
  for (let index = 0; index < 8; index++) {
    graph.nodes.push(makeEvidenceNode('note', { id: `neighbor-${index}`, label: `邻居 ${index}` }))
    graph.edges.push({ ...graph.edges[0], id: `edge-${index}`, source: `neighbor-${index}`, target: 'claim' })
  }
  const local = projectMobileEvidenceGraph(projectEvidenceGraph(graph), { focusId: 'claim' })
  assert.equal(new Set(local.nodes.filter(node => node.id !== 'claim').map(node => node.position.x)).size, 2)
  assert.ok(Math.max(...local.nodes.map(node => node.position.y)) > 600)
  assert.ok(Math.max(...local.nodes.map(node => node.position.x)) - Math.min(...local.nodes.map(node => node.position.x)) <= 232)
})
