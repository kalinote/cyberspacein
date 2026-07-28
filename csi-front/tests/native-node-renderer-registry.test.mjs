import assert from 'node:assert/strict'
import test from 'node:test'

import {
  registerNativeNodeRenderer,
  resolveNativeNodeRenderer
} from '../src/components/action/nodes/nativeNodeRendererRegistryCore.js'

test('渲染器按 renderer_key 和 contract_version 选择，不依赖 Handler', () => {
  const component = { name: '测试 Schema 渲染器' }
  registerNativeNodeRenderer('test.schema', 7, component)

  assert.equal(
    resolveNativeNodeRenderer({
      execution: { handler: '任意.handler' },
      extension: {
        renderer_key: 'test.schema',
        contract_version: 7
      }
    }),
    component
  )
  assert.equal(
    resolveNativeNodeRenderer({
      execution: { handler: 'test.schema' },
      extension: {
        renderer_key: 'test.schema',
        contract_version: 8
      }
    }),
    null
  )
})

test('重复注册不同组件和未知契约版本都会明确失败', () => {
  const component = { name: '原组件' }
  registerNativeNodeRenderer('test.conflict', 1, component)
  registerNativeNodeRenderer('test.conflict', 1, component)

  assert.throws(
    () => registerNativeNodeRenderer('test.conflict', 1, { name: '新组件' }),
    /重复注册/
  )
  assert.equal(
    resolveNativeNodeRenderer({
      extension: {
        renderer_key: 'missing',
        contract_version: 1
      }
    }),
    null
  )
})
