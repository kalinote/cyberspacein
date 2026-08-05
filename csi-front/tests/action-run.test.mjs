import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildActionRunRequest,
  getOppositeActionSchedulingMode,
  normalizeActionSchedulingMode
} from '../src/utils/action/run.js'

test('普通运行显式发送 debug=false', () => {
  assert.deepEqual(buildActionRunRequest('blueprint-1', null), {
    blueprint_id: 'blueprint-1',
    debug: false,
    scheduling_mode: 'barrier'
  })
})

test('模板调试运行同时保留参数和运行模式', () => {
  assert.deepEqual(
    buildActionRunRequest('blueprint-2', { keyword: '测试' }, true, 'streaming'),
    {
      blueprint_id: 'blueprint-2',
      debug: true,
      scheduling_mode: 'streaming',
      params: { keyword: '测试' }
    }
  )
})

test('运行控件规范化默认模式并提供相反模式', () => {
  assert.equal(normalizeActionSchedulingMode('streaming'), 'streaming')
  assert.equal(normalizeActionSchedulingMode('unknown'), 'barrier')
  assert.equal(getOppositeActionSchedulingMode('barrier'), 'streaming')
  assert.equal(getOppositeActionSchedulingMode('streaming'), 'barrier')
})

test('无参数模板仍显式提交本次运行模式', () => {
  assert.deepEqual(buildActionRunRequest('blueprint-3', {}, false, 'streaming'), {
    blueprint_id: 'blueprint-3',
    debug: false,
    scheduling_mode: 'streaming',
    params: {}
  })
})
