import assert from 'node:assert/strict'
import test from 'node:test'

import { buildActionRunRequest } from '../src/utils/action/run.js'

test('普通运行显式发送 debug=false', () => {
  assert.deepEqual(buildActionRunRequest('blueprint-1', null), {
    blueprint_id: 'blueprint-1',
    debug: false
  })
})

test('模板调试运行同时保留参数和运行模式', () => {
  assert.deepEqual(
    buildActionRunRequest('blueprint-2', { keyword: '测试' }, true),
    {
      blueprint_id: 'blueprint-2',
      debug: true,
      params: { keyword: '测试' }
    }
  )
})
