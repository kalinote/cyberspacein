import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { babelParse, compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

/**
 * 编译真实组件，并替换网络请求和生命周期以验证状态与模板事件。
 * @param {string} path 相对于 src 的组件路径。
 * @param {object} options 模拟接口、组件属性和更新权限。
 * @returns {object} 组件状态、生命周期、事件记录和模板渲染入口。
 */
function loadComponent(path, { api = {}, props = {}, canUpdate = true } = {}) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: path })
  const activated = []
  const mounted = []
  const events = []
  const messages = []
  const imports = {
    vue: { ...Vue, onActivated: callback => activated.push(callback), onMounted: callback => mounted.push(callback) },
    'vue-router': { useRouter: () => ({ push() {} }) },
    'element-plus': {
      ElMessage: { success: message => messages.push(message), error: message => messages.push(message) }
    },
    '@/api/action': { actionApi: api },
    '@/utils/permissions': { PERM: { operations: { action: { blueprint: {}, node: {} } } } },
    '@/utils/permissionKit': { hasPerm: () => canUpdate, hasAll: () => canUpdate }
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [
      specifier.imported?.name || 'default', { name: specifier.local.name }
    ]))
    const declarations = node.specifiers.map(specifier => (
      `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`
    )).join('\n')
    code = code.slice(0, node.start) + declarations + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const state = component.setup(props, { expose() {}, emit: (...args) => events.push(args) })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename: path,
    id: path,
    compilerOptions: { mode: 'function', bindingMetadata: script.bindings }
  })
  assert.deepEqual(template.errors, [])
  const render = new Function('Vue', template.code)({
    ...Vue, resolveComponent: name => ({ name }), resolveDirective: () => ({}), withDirectives: node => node
  })
  return { state, activated, mounted, events, messages, render: () => render({}, [], props, Vue.proxyRefs(state)) }
}

/** 查找组件渲染树中的目标节点，供事件和展示数量断言复用。 */
function findNodes(tree, name) {
  if (Array.isArray(tree)) return tree.flatMap(node => findNodes(node, name))
  if (!tree || typeof tree !== 'object') return []
  const matches = tree.type === name || tree.type?.name === name ? [tree] : []
  return matches.concat(Array.isArray(tree.children) ? findNodes(tree.children, name) : [])
}

for (const count of [0, 7, 205]) {
  test(`主页完整展示 ${count} 项置顶蓝图，跨页请求始终限定置顶`, async () => {
    const calls = []
    const items = Array.from({ length: count }, (_, id) => ({ id, name: `蓝图${id}`, is_pinned: true }))
    const page = loadComponent('views/action/ActionMonitor.vue', {
      api: { getBlueprintsBaseInfo: async params => {
        calls.push(params)
        return { items: items.slice((params.page - 1) * 100, params.page * 100), total_pages: Math.ceil(count / 100) }
      } }
    })

    await page.state.fetchCommonBlueprints()

    assert.equal(page.state.loadingBlueprints.value, false)
    assert.deepEqual(page.state.commonBlueprints.value.map(item => item.id), items.map(item => item.id))
    assert.ok(page.state.commonBlueprints.value.every(item => item.isPinned))
    assert.equal(findNodes(page.render(), 'ActionBlueprintCard').length, count)
    assert.deepEqual(calls, Array.from({ length: Math.max(1, Math.ceil(count / 100)) }, (_, index) => ({
      page: index + 1, page_size: 100, is_pinned: true
    })))
  })
}

test('后续分页失败时不展示部分结果，并结束加载状态', async () => {
  const page = loadComponent('views/action/ActionMonitor.vue', {
    api: { getBlueprintsBaseInfo: async ({ page }) => {
      if (page === 2) throw new Error('模拟后续分页失败')
      return { items: [{ id: '部分结果', is_pinned: true }], total_pages: 2 }
    } }
  })
  page.state.commonBlueprints.value = [{ id: '旧蓝图', isPinned: true }]

  await page.state.fetchCommonBlueprints()

  assert.deepEqual(page.state.commonBlueprints.value, [])
  assert.equal(page.state.loadingBlueprints.value, false)
  assert.deepEqual(page.messages, ['获取行动蓝图失败'])
})

test('缓存主页每次激活都会刷新置顶结果', async () => {
  let requests = 0
  const page = loadComponent('views/action/ActionMonitor.vue', {
    api: { getBlueprintsBaseInfo: async () => ({
      items: [{ id: ++requests, is_pinned: true }], total_pages: 1
    }) }
  })

  assert.equal(page.activated.length, 1)
  await page.activated[0]()
  assert.equal(page.state.commonBlueprints.value[0].id, 1)
  await page.activated[0]()
  assert.equal(page.state.commonBlueprints.value[0].id, 2)
})

test('置顶请求进行中阻止重复提交，成功后才通知父组件', async () => {
  const calls = []
  let complete
  const blueprint = { id: '置顶测试', isPinned: false }
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint },
    api: { updateBlueprintPin: (...args) => {
      calls.push(args)
      return new Promise(resolve => { complete = resolve })
    } }
  })

  const pending = button.state.togglePin()
  await button.state.togglePin()
  assert.equal(button.state.saving.value, true)
  assert.deepEqual(calls, [['置顶测试', true]])
  assert.deepEqual(button.events, [])
  assert.equal(blueprint.isPinned, false)
  complete({ data: { is_pinned: true } })
  await pending

  assert.equal(button.state.saving.value, false)
  assert.deepEqual(button.events, [['change', true]])
  assert.deepEqual(button.messages, ['已置顶到主页（全局生效）'])
})

test('置顶保存失败保持原状态，并允许再次点击重试', async () => {
  let requests = 0
  const blueprint = { id: '失败测试', isPinned: true }
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint },
    api: { updateBlueprintPin: async (_id, pinned) => {
      assert.equal(pinned, false)
      if (++requests === 1) throw new Error('模拟保存失败')
      return { data: { is_pinned: false } }
    } }
  })

  await button.state.togglePin()
  assert.equal(button.state.saving.value, false)
  assert.equal(blueprint.isPinned, true)
  assert.deepEqual(button.events, [])
  assert.deepEqual(button.messages, [])
  await button.state.togglePin()
  assert.deepEqual(button.events, [['change', false]])
})

test('没有更新权限时不提交置顶请求', async () => {
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint: { id: '无权限', isPinned: false } }, canUpdate: false,
    api: { updateBlueprintPin() { assert.fail('无权限时不应调用接口') } }
  })

  await button.state.togglePin()

  assert.equal(button.state.saving.value, false)
  assert.deepEqual(button.events, [])
  assert.equal(button.render().type, Vue.Comment)
})

test('卡片传递取消置顶事件后，主页立即移除对应蓝图并保留其他蓝图', () => {
  const page = loadComponent('views/action/ActionMonitor.vue')
  page.state.commonBlueprints.value = [{ id: '取消', isPinned: true }, { id: '保留', isPinned: true }]
  const cards = findNodes(page.render(), 'ActionBlueprintCard')
  const card = loadComponent('components/action/ActionBlueprintCard.vue', { props: { blueprint: cards[0].props.blueprint } })
  const pin = findNodes(card.render(), 'BlueprintPinButton')[0]

  pin.props.onChange(false)
  assert.deepEqual(card.events, [['pin-change', false]])
  cards[0].props.onPinChange(card.events[0][1])

  assert.deepEqual(page.state.commonBlueprints.value.map(item => item.id), ['保留'])
  assert.equal(findNodes(page.render(), 'ActionBlueprintCard').length, 1)
})
