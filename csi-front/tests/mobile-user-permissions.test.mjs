import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript, compileTemplate, babelParse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import { findNavItemByKey } from '../src/utils/configCenterNav.js'
import { formatDateTime } from '../src/utils/action/formatters.js'

/**
 * 编译真实权限页，在隔离接口和生命周期中验证缓存、权限及写入边界。
 * @param {object} t 测试上下文。
 * @param {object} options 接口、确认与权限替身。
 * @returns {object} 响应式页面、生命周期、消息与权限。
 */
function mount(t, options = {}) {
  const file = 'views/system/UserPermissionManagement.vue'
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: file })
  const denied = Vue.ref(options.denied || [])
  const hooks = { activate: [], deactivate: [], unmount: [] }, notices = [], closes = []
  const imports = {
    vue: { ...Vue, onMounted() {}, onActivated: callback => hooks.activate.push(callback), onDeactivated: callback => hooks.deactivate.push(callback), onBeforeUnmount: callback => hooks.unmount.push(callback) },
    'element-plus': { ElMessage: { success: message => notices.push(['success', message]), warning: message => notices.push(['warning', message]), error: message => notices.push(['error', message]) }, ElMessageBox: { confirm: options.confirm || (async () => {}), close: () => closes.push(true) } },
    '@/utils/permissions': { PERM }, '@/utils/permissionKit': { hasPerm: code => typeof code === 'string' && Boolean(code) && !denied.value.includes(code) },
    '@/utils/configCenterNav': { findNavItemByKey }, '@/utils/action': { formatDateTime },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: Vue.ref(true) }) },
    '@/api/system': { systemApi: { getUsers: async () => ({ code: 0, data: { items: [], total: 0 } }), getGroups: async () => ({ code: 0, data: { items: [], total: 0 } }), getPermCodes: async () => ({ code: 0, data: [] }), ...options.api } },
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', {}]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup({}, { expose() {} }))
  const template = compileTemplate({ source: descriptor.template.content, filename: file, id: file, compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  t.after(() => { hooks.unmount.forEach(callback => callback()); scope.stop() })
  return { state, hooks, denied, notices, closes }
}

test('缓存离页关闭所有弹窗并作废迟到用户详情，返回重新读取当前模块', async t => {
  let finish, reads = 0
  const page = mount(t, { api: { getUser: () => new Promise(resolve => { finish = resolve }), getUsers: async () => { reads++; return { data: { items: [], total: 0 } } } } })
  const pending = page.state.handleViewUser({ uuid: 'user' })
  page.state.createUserDialogVisible.value = true
  page.state.dictDialogVisible.value = true
  page.hooks.deactivate.forEach(callback => callback())
  assert.equal(page.state.createUserDialogVisible.value, false)
  assert.equal(page.state.dictDialogVisible.value, false)
  finish({ data: { uuid: 'user', display_name: '迟到详情' } })
  await pending
  assert.equal(page.state.editUserDialogVisible.value, false)
  assert.equal(page.state.editingUser.value, null)
  page.hooks.activate.forEach(callback => callback())
  await Vue.nextTick()
  assert.equal(reads, 1)
})

test('模块切换及详情撤权后，详情或完整组选项迟到均不能打开用户弹窗', async t => {
  let finishOptions
  const page = mount(t, { api: { getUser: async () => ({ data: { uuid: 'user', groups: ['existing'] } }), getGroups: () => new Promise(resolve => { finishOptions = resolve }) } })
  const edit = page.state.handleEditUser({ uuid: 'user' })
  await Vue.nextTick()
  page.state.activeTab.value = 'dictionary'
  await Vue.nextTick()
  finishOptions({ data: { items: [{ uuid: 'group' }], total: 1 } })
  await edit
  assert.equal(page.state.editUserDialogVisible.value, false)
  assert.deepEqual(page.state.groupOptions.value, [])
  page.state.activeTab.value = 'users'
  await Vue.nextTick()
  const view = page.state.handleViewUser({ uuid: 'user' })
  page.denied.value.push(PERM.operations.system.users.detailRead)
  await Vue.nextTick()
  await view
  assert.equal(page.state.editUserDialogVisible.value, false)
})

test('重复用户详情请求只展示最新选择', async t => {
  const pending = []
  const page = mount(t, { api: { getUser: () => new Promise(resolve => pending.push(resolve)) } })
  const old = page.state.handleViewUser({ uuid: 'old' })
  const current = page.state.handleViewUser({ uuid: 'current' })
  pending[1]({ data: { uuid: 'current' } })
  await current
  pending[0]({ data: { uuid: 'old' } })
  await old
  assert.equal(page.state.editingUser.value.uuid, 'current')
})

test('权限码搜索乱序不能覆盖当前结果，加载失败显示错误而不是空态', async t => {
  const pending = new Map()
  const page = mount(t, { api: { getPermCodes: ({ keyword }) => keyword ? new Promise(resolve => pending.set(keyword, resolve)) : Promise.resolve({ data: [] }), getUsers: async () => { throw new Error('连接中断') } } })
  await page.state.fetchUsers()
  assert.equal(page.state.currentListError.value, '连接中断')
  assert.equal(page.state.currentListLoading.value, false)
  page.state.activeTab.value = 'dictionary'
  await Vue.nextTick()
  const old = page.state.fetchPermCodes({ keyword: 'old' })
  const current = page.state.fetchPermCodes({ keyword: 'current' })
  pending.get('current')({ data: [{ perm_key: 'current' }] })
  await current
  pending.get('old')({ data: [{ perm_key: 'old' }] })
  await old
  assert.equal(page.state.permCodeList.value[0].permKey, 'current')
})

test('用户删除确认在离页后自动收起，迟到确认不写入', async t => {
  let accept, writes = 0
  const page = mount(t, { confirm: () => new Promise(resolve => { accept = resolve }), api: { deleteUser: async () => { writes++ } } })
  const pending = page.state.handleDeleteUser({ uuid: 'user', username: 'test' })
  page.hooks.deactivate.forEach(callback => callback())
  assert.equal(page.closes.length, 1)
  accept()
  await pending
  assert.equal(writes, 0)
})

test('权限组和权限码删除确认均重新检查当前授权', async t => {
  let accept, writes = 0
  const page = mount(t, { confirm: () => new Promise(resolve => { accept = resolve }), api: { deleteGroup: async () => { writes++ }, deletePermCode: async () => { writes++ } } })
  page.state.activeTab.value = 'groups'
  await Vue.nextTick()
  const group = page.state.handleDeleteGroup({ uuid: 'group' })
  page.denied.value.push(PERM.operations.system.groups.delete)
  await Vue.nextTick()
  accept()
  await group
  page.state.activeTab.value = 'dictionary'
  await Vue.nextTick()
  const permission = page.state.handleDeleteDict({ uuid: 'permission', source: 'placeholder' })
  page.denied.value.push(PERM.operations.system.permissionCodes.delete)
  await Vue.nextTick()
  accept()
  await permission
  assert.equal(writes, 0)
})

test('创建用户在异步校验期间防重复，失败保留全部原表单字段', async t => {
  let validated
  const writes = []
  const page = mount(t, { api: { createUser: async body => { writes.push(body); throw new Error('创建冲突') } } })
  await page.state.openCreateUserDialog()
  page.state.createUserFormRef.value = { validate: () => new Promise(resolve => { validated = resolve }) }
  Object.assign(page.state.createUserForm, { username: ' test ', password: ' secret ', display_name: ' 测试 ', email: ' a@example.com ', remark: ' 备注 ', enabled: false, temporary_account: true, expired_at: '2030-01-01 00:00:00', groups: ['group', 'unknown'] })
  const saving = page.state.handleSubmitCreateUser()
  await page.state.handleSubmitCreateUser()
  validated(true)
  await saving
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0], { username: 'test', password: ' secret ', display_name: '测试', email: 'a@example.com', remark: '备注', enabled: false, temporary_account: true, expired_at: '2030-01-01 00:00:00', groups: ['group', 'unknown'] })
  assert.equal(page.state.createUserDialogVisible.value, true)
  assert.equal(page.state.createUserForm.password, ' secret ')
  assert.equal(page.state.creatingUser.value, false)
  assert.deepEqual(page.notices.at(-1), ['error', '创建冲突'])
})

test('取消后新开表单不受旧保存响应影响，用户组提交保持原数组快照', async t => {
  let finish
  const writes = []
  const page = mount(t, { api: { getUser: async () => ({ data: { uuid: 'user', groups: ['unknown'] } }), updateUserGroups: (id, body) => { writes.push([id, body]); return new Promise(resolve => { finish = resolve }) } } })
  await page.state.handleEditUser({ uuid: 'user' })
  const pending = page.state.handleSaveEditUser()
  await page.state.handleSaveEditUser()
  page.state.editUserGroupUuids.value.push('new')
  page.state.editUserDialogVisible.value = false
  await page.state.openCreateUserDialog()
  page.state.createUserForm.username = '新草稿'
  finish({ code: 0 })
  await pending
  assert.deepEqual(writes, [['user', { groups: ['unknown'] }]])
  assert.equal(page.state.createUserDialogVisible.value, true)
  assert.equal(page.state.createUserForm.username, '新草稿')
})

test('权限组隐藏资料校验失败定位基础组，保存保留隐藏和未知权限', async t => {
  const writes = []
  const page = mount(t, { api: { createGroup: async body => { writes.push(body) } } })
  page.state.activeTab.value = 'groups'
  await Vue.nextTick()
  page.state.openCreateGroupDialog()
  await Vue.nextTick()
  page.state.createGroupFormRef.value = { validate: async () => false }
  page.state.groupSection.value = 'permissions'
  await page.state.handleSubmitCreateGroup()
  assert.equal(page.state.groupSection.value, 'profile')
  assert.equal(writes.length, 0)
  Object.assign(page.state.createGroupForm, { group_name: ' group ', display_name: ' 权限组 ', permissions: ['known', 'unknown'] })
  page.state.createGroupFormRef.value = { validate: async () => true }
  await page.state.handleSubmitCreateGroup()
  assert.deepEqual(writes[0], { group_name: 'group', display_name: '权限组', remark: undefined, enabled: true, permissions: ['known', 'unknown'] })
})

test('标准权限禁用沿用影响确认与精简载荷，退出影响读取后不再确认', async t => {
  const writes = []
  let finishImpact, confirmations = 0
  const page = mount(t, { confirm: async () => { confirmations++ }, api: { getPermCodeImpact: () => new Promise(resolve => { finishImpact = resolve }), updatePermCode: async (id, body) => writes.push([id, body]) } })
  page.state.activeTab.value = 'dictionary'
  await Vue.nextTick()
  page.state.openEditDict({ uuid: 'permission', permKey: 'code', source: 'standard', enabled: true })
  page.state.dictForm.enabled = false
  page.state.dictFormRef.value = { validate: async () => true }
  const pending = page.state.handleSaveDict()
  await new Promise(setImmediate)
  finishImpact({ data: { group_count: 2, user_count: 3 } })
  await pending
  assert.equal(confirmations, 1)
  assert.deepEqual(writes, [['permission', { enabled: false, impact_acknowledged: true }]])
  page.state.openEditDict({ uuid: 'permission', permKey: 'code', source: 'standard', enabled: true })
  page.state.dictForm.enabled = false
  const late = page.state.handleSaveDict()
  await new Promise(setImmediate)
  page.hooks.deactivate.forEach(callback => callback())
  finishImpact({ data: { group_count: 9 } })
  await late
  assert.equal(confirmations, 1)
  assert.equal(writes.length, 1)
})

test('手机用户表单加载完整权限组选项，页码和后端字段保持原语义', async t => {
  const calls = []
  const page = mount(t, { api: { getGroups: async params => { calls.push(params); return { data: { total: 101, items: params.page === 1 ? Array.from({ length: 100 }, (_, i) => ({ uuid: String(i) })) : [{ uuid: 'last' }] } } } } })
  await page.state.openCreateUserDialog()
  assert.deepEqual(calls, [{ page: 1, page_size: 100 }, { page: 2, page_size: 100 }])
  assert.equal(page.state.groupOptions.value.length, 101)
  assert.equal(page.state.groupChoices.value.at(-1).uuid, 'last')
})

test('权限目录加载失败保留组草稿并阻止空目录误保存，重试成功后按原字段更新', async t => {
  let fail = true
  const writes = []
  const page = mount(t, { api: { getPermCodes: async () => { if (fail) throw new Error('目录不可用'); return { data: [] } }, updateGroup: async (id, body) => writes.push([id, body]) } })
  page.state.activeTab.value = 'groups'
  await Vue.nextTick()
  page.state.handleEditGroup({ uuid: 'group', group_name: 'identity', display_name: '权限组', remark: '说明', enabled: true, permissions: ['known', 'unknown'] })
  await Vue.nextTick()
  page.state.editGroupFormRef.value = { validate: async () => true }
  await page.state.handleSaveEditGroup()
  assert.equal(writes.length, 0)
  assert.equal(page.state.permCodeCatalogError.value, '目录不可用')
  assert.equal(page.state.editGroupDialogVisible.value, true)
  fail = false
  await page.state.fetchPermCodeCatalog()
  await page.state.handleSaveEditGroup()
  assert.deepEqual(writes, [['group', { display_name: '权限组', remark: '说明', enabled: true, permissions: ['known', 'unknown'] }]])
})

test('批量权限码沿用规范化载荷，后端失败保留每项草稿并指出错误项', async t => {
  const writes = []
  const page = mount(t, { api: { createPermCodesBatch: async body => { writes.push(body); throw new Error('权限码已存在: operation:custom:item:read') } } })
  page.state.activeTab.value = 'dictionary'
  await Vue.nextTick()
  page.state.openCreateDict()
  page.state.dictCreateTab.value = 'batch'
  Object.assign(page.state.dictBatchRows.value[0], { permKey: ' operation:custom:item:read ', name: ' 读取 ', category: ' 自定义 ', desc: ' 说明 ', tags: [' 标签 ', ''], enabled: false })
  await page.state.handleSaveDict()
  assert.deepEqual(writes, [{ items: [{ perm_key: 'operation:custom:item:read', name: '读取', category: '自定义', desc: '说明', tags: ['标签'], enabled: false }] }])
  assert.equal(page.state.dictDialogVisible.value, true)
  assert.equal(page.state.dictBatchRows.value[0].errorFields.permKey, true)
  assert.equal(page.state.dictSaving.value, false)
  assert.match(page.state.dictBatchErrorSummary.value, /第 1 行失败/)
})

test('异步表单校验期间离页，校验迟到通过也不会提交用户或权限组', async t => {
  let validated, writes = 0
  const page = mount(t, { api: { createUser: async () => { writes++ }, createGroup: async () => { writes++ } } })
  await page.state.openCreateUserDialog()
  page.state.createUserFormRef.value = { validate: () => new Promise(resolve => { validated = resolve }) }
  const user = page.state.handleSubmitCreateUser()
  page.hooks.deactivate.forEach(callback => callback())
  validated(true)
  await user
  page.hooks.activate.forEach(callback => callback())
  page.state.activeTab.value = 'groups'
  await Vue.nextTick()
  page.state.openCreateGroupDialog()
  await Vue.nextTick()
  page.state.createGroupFormRef.value = { validate: () => new Promise(resolve => { validated = resolve }) }
  const group = page.state.handleSubmitCreateGroup()
  page.hooks.deactivate.forEach(callback => callback())
  validated(true)
  await group
  assert.equal(writes, 0)
})
