import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BINDING_SOURCE_HANDLE_ID,
  BINDING_TARGET_HANDLE_ID,
  buildBindingDisplay,
  buildBindingGraphIndex,
  buildBindingRelationEdges,
  collectBindingsByTarget,
  collectBindingTargetKinds,
  getBindableHandles,
  getBoundaryExposedHandles,
  getBoundaryInitialPosition,
  isBindingProtocolHandle,
  resolveBindingTargetStates,
  validateBindingCandidate,
  validateBoundaryBindings
} from '../src/utils/action/boundaryBinding.js'

const boundaryNode = (builtinKey, compatible = ['*']) => ({
  id: builtinKey,
  position: { x: 0, y: 0 },
  dimensions: { width: 280, height: 180 },
  data: {
    config: {
      builtin_key: builtinKey,
      node_kind: 'backend_native',
      inputs: [],
      handles: [{
        id: `${builtinKey}.handle`,
        type: builtinKey === 'blueprint.input' ? 'source' : 'target',
        interface_type_id: 'builtin.value',
        compatible_interface_type_ids: compatible
      }]
    }
  }
})

const targetNode = {
  id: 'target',
  position: { x: 500, y: 300 },
  dimensions: { width: 320, height: 240 },
  data: {
    config: {
      name: '目标节点',
      handles: [
        {
          id: 'target.input',
          port_id: 'stable.input',
          type: 'target',
          interface_type_id: 'custom.input',
          relabel: '自定义输入'
        },
        {
          id: 'target.output',
          port_id: 'stable.output',
          type: 'source',
          interface_type_id: 'custom.output',
          relabel: '自定义输出'
        }
      ]
    }
  }
}

test('输入和输出边界只展示对应方向且支持通配接口的目标端口', () => {
  assert.deepEqual(
    getBindableHandles(boundaryNode('blueprint.input'), targetNode).map(handle => handle.id),
    ['target.output']
  )
  assert.deepEqual(
    getBindableHandles(boundaryNode('blueprint.output'), targetNode).map(handle => handle.id),
    ['target.input']
  )
})

test('绑定摘要明确区分替代输入和替代输出', () => {
  assert.deepEqual(
    buildBindingDisplay(
      boundaryNode('blueprint.input'),
      targetNode,
      ['stable.output']
    ),
    {
      direction: 'input',
      targetNodeName: '目标节点',
      targetPortNames: ['自定义输出'],
      portDescription: '替代输出：自定义输出'
    }
  )
})

test('可以识别同一目标上的输入和输出混合绑定', () => {
  const input = boundaryNode('blueprint.input')
  input.data.boundaryBinding = { bound_node_id: 'target' }
  const output = boundaryNode('blueprint.output')
  output.data.boundaryBinding = { bound_node_id: 'target' }

  assert.deepEqual(
    collectBindingTargetKinds([input, output, targetNode]),
    { target: ['input', 'output'] }
  )
})

test('统一绑定协议 Handle 使用保留 ID 且不属于数据端口', () => {
  assert.equal(isBindingProtocolHandle(BINDING_SOURCE_HANDLE_ID), true)
  assert.equal(isBindingProtocolHandle(BINDING_TARGET_HANDLE_ID), true)
  assert.equal(isBindingProtocolHandle('target.output'), false)
})

test('起始、中间和结束节点只接受对应方向的 IO 绑定', () => {
  const source = {
    ...structuredClone(targetNode),
    id: 'source',
    data: {
      config: {
        name: '起始节点',
        handles: [{
          id: 'source.output',
          port_id: 'source.output',
          type: 'source',
          interface_type_id: 'custom.output'
        }]
      }
    }
  }
  const middle = {
    ...structuredClone(targetNode),
    id: 'middle',
    data: {
      config: {
        name: '中间节点',
        handles: [
          {
            id: 'middle.input',
            port_id: 'middle.input',
            type: 'target',
            interface_type_id: 'custom.output'
          },
          {
            id: 'middle.output',
            port_id: 'middle.output',
            type: 'source',
            interface_type_id: 'custom.output'
          }
        ]
      }
    }
  }
  const sink = {
    ...structuredClone(targetNode),
    id: 'sink',
    data: {
      config: {
        name: '结束节点',
        handles: [{
          id: 'sink.input',
          port_id: 'sink.input',
          type: 'target',
          interface_type_id: 'custom.output'
        }]
      }
    }
  }
  const edges = [
    {
      id: 'e1',
      source: 'source',
      sourceHandle: 'source.output',
      target: 'middle',
      targetHandle: 'middle.input'
    },
    {
      id: 'e2',
      source: 'middle',
      sourceHandle: 'middle.output',
      target: 'sink',
      targetHandle: 'sink.input'
    }
  ]

  const graphIndex = buildBindingGraphIndex([source, middle, sink], edges)
  const states = resolveBindingTargetStates([source, middle, sink], edges)

  assert.equal(graphIndex.incomingEdgesByNode.get('middle').length, 1)
  assert.deepEqual(
    {
      input: states.source.canAcceptInput,
      output: states.source.canAcceptOutput
    },
    { input: true, output: false }
  )
  assert.deepEqual(
    {
      input: states.middle.canAcceptInput,
      output: states.middle.canAcceptOutput
    },
    { input: false, output: false }
  )
  assert.deepEqual(
    {
      input: states.sink.canAcceptInput,
      output: states.sink.canAcceptOutput
    },
    { input: false, output: true }
  )
})

test('同一目标混合方向后锁定统一绑定 Handle 并产生结构化问题', () => {
  const input = boundaryNode('blueprint.input')
  input.data.boundaryBinding = {
    bound_node_id: 'target',
    port_mappings: [{
      interface_port_id: 'public.in',
      target_port_id: 'stable.output'
    }]
  }
  const output = boundaryNode('blueprint.output')
  output.data.boundaryBinding = {
    bound_node_id: 'target',
    port_mappings: [{
      interface_port_id: 'public.out',
      target_port_id: 'stable.input'
    }]
  }
  const nodes = [input, output, targetNode]
  const issues = validateBoundaryBindings(nodes, [])
  const state = resolveBindingTargetStates(nodes, []).target

  assert.equal(
    issues.some(issue => issue.code === 'binding_mixed_direction'),
    true
  )
  assert.equal(state.valid, false)
  assert.equal(state.canAcceptInput, false)
  assert.equal(state.canAcceptOutput, false)
  assert.deepEqual(
    collectBindingsByTarget(nodes).target.map(binding => binding.direction),
    ['input', 'output']
  )
})

test('统一绑定 Handle 可接收多个同方向 IO 并过滤已占用端口', () => {
  const source = {
    id: 'source',
    data: {
      config: {
        name: '双输出源',
        handles: [
          {
            id: 'source.left',
            port_id: 'stable.left',
            type: 'source',
            interface_type_id: 'builtin.value'
          },
          {
            id: 'source.right',
            port_id: 'stable.right',
            type: 'source',
            interface_type_id: 'builtin.value'
          }
        ]
      }
    }
  }
  const leftTarget = {
    id: 'left-target',
    data: {
      config: {
        name: '左目标',
        handles: [{
          id: 'left-target.input',
          type: 'target',
          interface_type_id: 'builtin.value'
        }]
      }
    }
  }
  const rightTarget = {
    id: 'right-target',
    data: {
      config: {
        name: '右目标',
        handles: [{
          id: 'right-target.input',
          type: 'target',
          interface_type_id: 'builtin.value'
        }]
      }
    }
  }
  const firstInput = boundaryNode('blueprint.input')
  firstInput.id = 'first-input'
  firstInput.data.boundaryBinding = {
    bound_node_id: 'source',
    port_mappings: [{
      interface_port_id: 'public.left',
      target_port_id: 'stable.left'
    }]
  }
  const secondInput = boundaryNode('blueprint.input')
  secondInput.id = 'second-input'
  const nodes = [firstInput, secondInput, source, leftTarget, rightTarget]
  const edges = [
    {
      id: 'left',
      source: 'source',
      sourceHandle: 'source.left',
      source_port_id: 'stable.left',
      target: 'left-target',
      targetHandle: 'left-target.input'
    },
    {
      id: 'right',
      source: 'source',
      sourceHandle: 'source.right',
      source_port_id: 'stable.right',
      target: 'right-target',
      targetHandle: 'right-target.input'
    }
  ]

  const result = validateBindingCandidate(secondInput, source, nodes, edges)

  assert.equal(result.valid, true)
  assert.deepEqual(
    result.bindableHandles.map(handle => handle.port_id),
    ['stable.right']
  )
})

test('已绑定 IO 保留普通数据边时会被本地校验拒绝', () => {
  const input = boundaryNode('blueprint.input')
  input.id = 'input'
  input.data.boundaryBinding = {
    bound_node_id: 'target',
    port_mappings: [{
      interface_port_id: 'public.in',
      target_port_id: 'stable.output'
    }]
  }
  const issues = validateBoundaryBindings(
    [input, targetNode],
    [{
      id: 'data-edge',
      source: 'input',
      sourceHandle: 'blueprint.input.handle',
      target: 'target',
      targetHandle: 'target.input'
    }]
  )

  assert.equal(
    issues.some(issue => issue.code === 'binding_boundary_has_data_edge'),
    true
  )
})

test('绑定 IO 的公开接口继承重连后的相邻 Handle 类型', () => {
  const input = boundaryNode('blueprint.input', [])
  input.id = 'input'
  input.data.interfacePortId = 'public.in'
  input.data.boundaryBinding = {
    bound_node_id: 'target',
    port_mappings: [{
      interface_port_id: 'public.in',
      target_port_id: 'stable.output'
    }]
  }
  const downstream = {
    id: 'downstream',
    data: {
      config: {
        name: '下游',
        handles: [{
          id: 'downstream.input',
          type: 'target',
          interface_type_id: 'custom.output'
        }]
      }
    }
  }
  const issues = validateBoundaryBindings(
    [input, targetNode, downstream],
    [{
      id: 'data-edge',
      source: 'target',
      sourceHandle: 'target.output',
      source_port_id: 'stable.output',
      target: 'downstream',
      targetHandle: 'downstream.input'
    }]
  )
  const [exposedHandle] = getBoundaryExposedHandles(
    input,
    [input, targetNode, downstream],
    [{
      id: 'data-edge',
      source: 'target',
      sourceHandle: 'target.output',
      source_port_id: 'stable.output',
      target: 'downstream',
      targetHandle: 'downstream.input'
    }]
  )

  assert.equal(exposedHandle.id, 'downstream.input')
  assert.equal(
    issues.some(issue => issue.code === 'binding_port_type_incompatible'),
    false
  )
})

test('绑定关系线由 boundaryBinding 派生且与普通数据边区分', () => {
  const input = boundaryNode('blueprint.input')
  input.id = 'input'
  input.data.boundaryBinding = {
    bound_node_id: 'target',
    port_mappings: [{
      interface_port_id: 'public.in',
      target_port_id: 'stable.output'
    }]
  }
  const [relation] = buildBindingRelationEdges([input, targetNode], {
    target: { valid: true }
  })

  assert.deepEqual(
    {
      source: relation.source,
      sourceHandle: relation.sourceHandle,
      target: relation.target,
      targetHandle: relation.targetHandle,
      relationKind: relation.data.relationKind,
      deletable: relation.deletable
    },
    {
      source: 'input',
      sourceHandle: 'blueprint.input.handle',
      target: 'target',
      targetHandle: BINDING_TARGET_HANDLE_ID,
      relationKind: 'boundary-binding',
      deletable: false
    }
  )
})

test('边界节点绑定时按输入在左上、输出在右上的规则设置初始位置', () => {
  assert.deepEqual(
    getBoundaryInitialPosition(boundaryNode('blueprint.input'), targetNode),
    { x: 172, y: 72 }
  )
  assert.deepEqual(
    getBoundaryInitialPosition(boundaryNode('blueprint.output'), targetNode),
    { x: 868, y: 72 }
  )
})
