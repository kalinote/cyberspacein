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
