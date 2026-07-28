import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const readSource = async relativePath => readFile(
  new URL(`../src/${relativePath}`, import.meta.url),
  'utf8'
)

test('行动资源配置提供独立封装节点子页并从普通列表排除封装节点', async () => {
  const source = await readSource('views/action/ActionResourceConfig.vue')

  assert.match(source, /activeTab === 'encapsulatedNodes'/)
  assert.match(source, /label: '封装节点'/)
  assert.match(source, /node\.node_kind !== 'encapsulated'/)
})

test('封装节点管理页包含资源族分页、引用保护和逐版本删除交互', async () => {
  const source = await readSource('components/action/EncapsulatedNodeManager.vue')

  assert.match(source, /family\.next_definition_version/)
  assert.match(source, /version\.draft_reference_count > 0/)
  assert.match(source, /getEncapsulatedNodeDetail/)
  assert.match(source, /deleteEncapsulatedNode/)
  assert.match(source, /response\?\.data\?\.items/)
  assert.match(source, /loadError/)
  assert.match(source, /fetchFamilies\(\)/)
  assert.match(source, /isFamilyExpanded\(family\.node_family_id\)/)
  assert.match(source, /rounded-xl border border-gray-200 bg-white p-6 shadow-sm/)
  assert.match(source, /版本管理/)
})

test('封装节点管理接口和独立页面权限已接入前端', async () => {
  const [apiSource, permissionSource] = await Promise.all([
    readSource('api/action.js'),
    readSource('utils/permissions.js')
  ])

  assert.match(apiSource, /\/action\/resource\/encapsulated-nodes/)
  assert.match(permissionSource, /resource:encapsulated-nodes:visible/)
  assert.match(permissionSource, /resource:encapsulated-nodes:access/)
})
