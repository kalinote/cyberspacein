import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const readSource = relativePath => readFileSync(
  new URL(`../src/${relativePath}`, import.meta.url),
  'utf8'
)

test('蓝图编辑器完整保存并回显默认调度模式', () => {
  const source = readSource('views/action/NewActionBlueprint.vue')

  assert.match(source, /default_scheduling_mode:\s*'barrier'/)
  assert.match(source, /blueprint\.default_scheduling_mode === 'streaming'/)
  assert.match(source, /default_scheduling_mode:\s*actionForm\.value\.default_scheduling_mode/)
})

test('运行控件保留主按钮、相反模式和默认模式调试入口', () => {
  const source = readSource('components/action/BlueprintRunControl.vue')

  assert.match(source, /@click="emit\('run', normalizedMode\)"/)
  assert.match(source, /command="opposite"/)
  assert.match(source, /command="debug"/)
  assert.match(source, /emit\('debug', normalizedMode\.value\)/)
})

test('模板空参数和部分完成历史状态均可操作', () => {
  const dialog = readSource('components/action/template/TemplateParamsDialog.vue')
  const history = readSource('views/action/ActionHistory.vue')

  assert.match(dialog, /inputConfigs\.value\.length === 0/)
  assert.match(dialog, /if \(!blueprintData\.value\)/)
  assert.match(dialog, /emit\('submit', \{\}\)/)
  assert.match(history, /:value="ACTION_STATUS\.PARTIALLY_COMPLETED"/)
  assert.match(history, /partiallyCompleted/)
  assert.match(history, /fetchActionsQueued/)
})

test('历史行动区分调度模式标签并为失败终态保留红黄渐变进度', () => {
  const history = readSource('views/action/ActionHistory.vue')

  assert.match(history, /barrier:\s*'border-blue-200! bg-blue-50! text-blue-600!'/)
  assert.match(history, /streaming:\s*'border-violet-200! bg-violet-50! text-violet-600!'/)
  assert.match(history, /UNSUCCESSFUL_TERMINAL_STATUSES = new Set\(\[/)
  assert.match(history, /ACTION_STATUS\.FAILED/)
  assert.match(history, /ACTION_STATUS\.TIMEOUT/)
  assert.match(history, /ACTION_STATUS\.CANCELLED/)
  assert.match(history, /ACTION_STATUS\.STOPPED/)
  assert.match(history, /ACTION_PROGRESS_STATUSES\.has\(action\.status\)/)
  assert.match(history, /ACTION_PROGRESS_STATUSES\.has\(row\.status\)/)
  assert.match(history, /UNSUCCESSFUL_TERMINAL_STATUSES\.has\(action\.status\)[\s\S]*?'bg-linear-to-r from-red-500 to-yellow-400'/)
  assert.match(history, /UNSUCCESSFUL_TERMINAL_STATUSES\.has\(row\.status\)[\s\S]*?'bg-linear-to-r from-red-500 to-yellow-400'/)
  assert.match(history, /'bg-linear-to-r from-blue-500 to-cyan-400'/)
})

test('失败、超时和已完成行动通过重放接口创建新行动', () => {
  const api = readSource('api/action.js')
  const history = readSource('views/action/ActionHistory.vue')

  assert.match(api, /retryAction\(id\)[\s\S]*?request\.post\(`\/action\/\$\{id\}\/retry`\)/)
  assert.match(history, /RETRYABLE_ACTION_STATUSES = new Set\(\[[\s\S]*?ACTION_STATUS\.FAILED,[\s\S]*?ACTION_STATUS\.TIMEOUT/)
  assert.match(history, /REPLAYABLE_ACTION_STATUSES = new Set\(\[[\s\S]*?ACTION_STATUS\.COMPLETED,[\s\S]*?ACTION_STATUS\.PARTIALLY_COMPLETED/)
  assert.match(history, /REPLAYABLE_ACTION_STATUSES\.has\(action\.status\)/)
  assert.match(history, /REPLAYABLE_ACTION_STATUSES\.has\(row\.status\)/)
  assert.match(history, /RETRYABLE_ACTION_STATUSES\.has\(action\.status\) \? '重试' : '重新执行'/)
  assert.match(history, /RETRYABLE_ACTION_STATUSES\.has\(row\.status\) \? '重试' : '重新执行'/)
  assert.match(history, /RETRYABLE_ACTION_STATUSES\.has\(action\.status\) \? 'mdi:refresh' : 'mdi:replay'/)
  assert.match(history, /RETRYABLE_ACTION_STATUSES\.has\(row\.status\) \? 'mdi:refresh' : 'mdi:replay'/)
  assert.match(history, /await actionApi\.retryAction\(action\.id\)/)
  assert.match(history, /await fetchActions\(false\)/)
  assert.doesNotMatch(history, /行动已加入执行队列/)
})
