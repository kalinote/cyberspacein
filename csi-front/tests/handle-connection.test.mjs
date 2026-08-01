import assert from 'node:assert/strict'
import test from 'node:test'

import {
  acceptsHandleDataType,
  allowsMultipleHandleInputs,
  areHandleInterfacesCompatible,
  isDuplicateHandleConnection
} from '../src/utils/action/handleConnection.js'

test('普通 Handle 仅接受自身传输类型，调试 Handle 可接受值和引用', () => {
  assert.equal(
    acceptsHandleDataType({ data_type: 'reference' }, { data_type: 'value' }),
    false
  )
  assert.equal(
    acceptsHandleDataType(
      { data_type: 'reference' },
      { data_type: 'value', accepted_data_types: ['value', 'reference'] }
    ),
    true
  )
  assert.equal(
    acceptsHandleDataType(
      { data_type: 'value' },
      { data_type: 'reference', accepted_data_types: ['value', 'reference'] }
    ),
    true
  )
})

test('多输入能力从节点编译契约或 Handle 契约读取', () => {
  assert.equal(allowsMultipleHandleInputs({}, {}), false)
  assert.equal(allowsMultipleHandleInputs({}, { allow_multiple_inputs: true }), true)
  assert.equal(
    allowsMultipleHandleInputs({
      extension: { config: { compiler: { allow_multiple_inputs: true } } }
    }),
    true
  )
})

test('通配接口可接收任意业务接口，但不会绕过传输类型校验', () => {
  const source = { id: 'article.output', data_type: 'reference' }
  const target = {
    id: 'debug.input',
    data_type: 'value',
    accepted_data_types: ['value'],
    other_compatible_interfaces: ['*']
  }
  assert.equal(areHandleInterfacesCompatible(source, target), true)
  assert.equal(acceptsHandleDataType(source, target), false)
})

test('同一对端口的完全重复边会被识别', () => {
  const connection = {
    id: 'new-edge',
    source: 'source-node',
    sourceHandle: 'output',
    target: 'debug-node',
    targetHandle: 'data_in'
  }
  assert.equal(isDuplicateHandleConnection([{
    id: 'old-edge',
    source: 'source-node',
    sourceHandle: 'output',
    target: 'debug-node',
    targetHandle: 'data_in'
  }], connection), true)
  assert.equal(isDuplicateHandleConnection([{
    id: 'other-edge',
    source: 'another-node',
    sourceHandle: 'output',
    target: 'debug-node',
    targetHandle: 'data_in'
  }], connection), false)
})
