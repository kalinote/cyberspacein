import test from 'node:test'
import assert from 'node:assert/strict'
import { makeEvidenceGraph, makeEvidenceNode, graphPayload, projectEvidenceGraph, memberPath } from '../src/utils/evidence.js'

test('模板可以独立编辑，溯源关系不自动断言因果', () => {
  const a = makeEvidenceGraph('trace'), b = makeEvidenceGraph('trace')
  assert.equal(a.nodes.length, 3)
  assert.ok(a.edges.every(edge => edge.label === '先于' && edge.status === 'pending'))
  a.nodes[0].label = '已编辑'
  assert.equal(b.nodes[0].label, '事件起点')
  assert.notEqual(a.nodes[0].id, b.nodes[0].id)
})

test('动态检索结果只影响展开视图，不物化到保存的节点', () => {
  const graph = makeEvidenceGraph()
  const node = makeEvidenceNode('versions', { id: 'versions', version_source: { entity_type: 'article', source_id: 'p', platform: '站点' } })
  graph.nodes = [node]
  const saved = JSON.stringify(graphPayload(graph))
  const first = { versions: { items: [{ entity_type: 'article', uuid: 'e1', title: '初版' }] } }
  assert.equal(projectEvidenceGraph(graph, first, new Set(['versions'])).nodes.length, 2)
  first.versions.items.push({ entity_type: 'article', uuid: 'e2', title: '修订' })
  assert.equal(projectEvidenceGraph(graph, first, new Set(['versions'])).nodes.length, 3)
  assert.equal(JSON.stringify(graphPayload(graph)), saved)
})

test('具体版本端点在收起集合后仍保留身份与关系依据', () => {
  const graph = makeEvidenceGraph()
  const entity = { entity_type: 'article', uuid: 'e2', title: '版本二' }
  graph.nodes = [makeEvidenceNode('collection', { id: 'group', members: [{ entity_type: 'article', uuid: 'e2' }] }), makeEvidenceNode('note', { id: 'claim', label: '判断' })]
  graph.edges = [{ id: 'edge', source: memberPath('group', entity), target: 'claim', label: '支持', status: 'pending', directed: true, anchors: [{ entity, quote: '摘录' }] }]
  const resolved = { group: { items: [entity] } }
  const expanded = projectEvidenceGraph(graph, resolved, new Set(['group']))
  const collapsed = projectEvidenceGraph(graph, resolved)
  assert.equal(expanded.edges.find(edge => edge.id === 'edge').source, 'group/@article:e2')
  assert.equal(collapsed.edges[0].source, 'group')
  assert.equal(collapsed.edges[0].data.folded, true)
  assert.equal(graph.edges[0].source, 'group/@article:e2')
  assert.equal(graph.edges[0].anchors[0].quote, '摘录')
})

test('同一子链可被多次引用，内部节点身份与关系归属保持独立', () => {
  const graph = makeEvidenceGraph()
  graph.nodes = [makeEvidenceNode('chain', { id: 'a1', chain_id: 'child' }), makeEvidenceNode('chain', { id: 'a2', chain_id: 'child' })]
  const child = makeEvidenceGraph('trace')
  const result = projectEvidenceGraph(graph, { a1: { chain: child }, a2: { chain: child } }, new Set(['a1', 'a2']))
  assert.equal(result.nodes.length, 8)
  assert.equal(new Set(result.nodes.map(node => node.id)).size, 8)
  assert.ok(result.nodes.filter(node => node.id.includes('/')).every(node => node.data.inherited && !node.draggable))
  assert.ok(result.edges.every(edge => edge.data.inherited))
  assert.equal(graph.edges.length, 0)
})

test('子链节点删除后保留外部关系及依据，并显示引用失效', () => {
  const graph = makeEvidenceGraph()
  graph.nodes = [makeEvidenceNode('chain', { id: 'child', chain_id: 'shared' }), makeEvidenceNode('note', { id: 'claim' })]
  graph.edges = [{ id: 'edge', source: 'child/deleted', target: 'claim', label: '支持', anchors: [{ entity: { entity_type: 'article', uuid: 'e1' }, quote: '原文依据' }] }]
  const saved = JSON.stringify(graphPayload(graph))
  const result = projectEvidenceGraph(graph, { child: { chain: makeEvidenceGraph() } })
  assert.equal(result.edges[0].source, 'child')
  assert.equal(result.edges[0].data.missing, true)
  assert.match(result.edges[0].label, /引用失效/)
  assert.equal(JSON.stringify(graphPayload(graph)), saved)
})
