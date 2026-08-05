import assert from 'node:assert/strict'
import test from 'node:test'

import {
  ACTION_STATUS,
  getActionStatusIcon,
  getStatusDotClass,
  getStatusTagType,
  getStatusText
} from '../src/utils/action/status.js'

test('部分完成使用独立状态文案与视觉样式', () => {
  assert.equal(ACTION_STATUS.PARTIALLY_COMPLETED, 'partially_completed')
  assert.equal(getStatusText(ACTION_STATUS.PARTIALLY_COMPLETED), '部分完成')
  assert.equal(getStatusTagType(ACTION_STATUS.PARTIALLY_COMPLETED), 'warning')
  assert.match(getStatusDotClass(ACTION_STATUS.PARTIALLY_COMPLETED), /violet/)
  assert.match(getActionStatusIcon(ACTION_STATUS.PARTIALLY_COMPLETED).iconClass, /violet/)
})
