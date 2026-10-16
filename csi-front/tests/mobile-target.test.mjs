import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { babelParse, compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import { KNOWLEDGE_DESTINATIONS } from '../src/utils/knowledgeNavigation.js'
import * as formatters from '../src/utils/action/formatters.js'

/**
 * 编译真实资料组件，用模拟接口和生命周期检查用户可见行为。
 * @param {string} path 相对 src 的组件路径。
 * @param {object} options 移动断点、接口、权限及组件属性。
 * @returns {object} 组件状态、模板及生命周期回调。
 */
function loadComponent(path, { search, highlight, denied = [], mobile = true, props = {} } = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: path })
  const hooks = { mounted: [], activated: [], deactivated: [], leave: [], unmount: [] }
  const messages = []
  const permissionKit = { hasPerm: code => !denied.includes(code), hasAll: codes => codes.every(code => !denied.includes(code)) }
  const helpersSource = readFileSync(new URL('../src/components/target/targetContent.js', import.meta.url), 'utf8')
  const targetContent = new Function('hasAll', 'PERM', `${helpersSource.replace(/^import .*$/gm, '').replace(/export function /g, 'function ')}\nreturn { plainExcerpt, entityDetailPath }`)(permissionKit.hasAll, PERM)
  const imports = {
    vue: { ...Vue, onMounted: callback => hooks.mounted.push(callback), onActivated: callback => hooks.activated.push(callback), onDeactivated: callback => hooks.deactivated.push(callback), onBeforeUnmount: callback => hooks.unmount.push(callback) },
    'vue-router': { useRouter: () => ({ push() {} }), onBeforeRouteLeave: callback => hooks.leave.push(callback) },
    'element-plus': { ElMessage: { success: text => messages.push(text), error: text => messages.push(text) } },
    '@/api/search': { searchApi: { searchEntity: search || (async () => ({ code: 0, data: { items: [], total: 0 } })) } },
    '@/api/highlight': { highlightApi: { setHighlight: highlight || (async () => ({ code: 0 })) } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: Vue.ref(mobile) }) },
    '@/utils/permissions': { PERM }, '@/utils/permissionKit': permissionKit,
    '@/utils/action/formatters': formatters, '@/utils/knowledgeNavigation': { KNOWLEDGE_DESTINATIONS },
    '@/components/target/targetContent': targetContent, './targetContent': targetContent,
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', { name: specifier.local.name }]))
    const declarations = node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n')
    code = code.slice(0, node.start) + declarations + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup(props, { expose() {}, emit() {} }))
  const template = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { mode: 'function', bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  const render = new Function('Vue', template.code)({ ...Vue, resolveComponent: name => ({ name }), resolveDirective: () => ({}), withDirectives: node => node })
  return { state, hooks, messages, render: () => render({}, [], props, Vue.proxyRefs(state)), stop: () => scope.stop() }
}

/** """遍历模板及插槽中的节点，用真实模板事件验证操作。""" */
function nodes(tree, name) {
  if (Array.isArray(tree)) return tree.flatMap(node => nodes(node, name))
  if (!tree || typeof tree !== 'object') return []
  const matches = tree.type === name || tree.type?.name === name ? [tree] : []
  const children = tree.children?.default ? tree.children.default() : tree.children
  return matches.concat(nodes(children, name))
}

/** """提取模板文本，用于区分真实内容、加载和错误状态。""" */
function renderedText(tree) {
  if (typeof tree === 'string') return tree
  if (Array.isArray(tree)) return tree.map(renderedText).join('')
  if (!tree || typeof tree !== 'object' || tree.type === Vue.Comment) return ''
  return renderedText(tree.children?.default ? tree.children.default() : tree.children)
}

const listPath = 'views/target/HighlightTargetList.vue'
const hubPath = 'views/target/TargetManagement.vue'

test('手机资料入口只呈现真实重点材料，保留独立入口权限且不展示占位统计', async () => {
  const calls = []
  const page = loadComponent(hubPath, { denied: [PERM.pages.evidence.visible, PERM.pages.target.wiki.access], search: async params => {
    calls.push(params)
    return { code: 0, data: { items: [{ uuid: '真实资料', entity_type: 'article' }] } }
  } })
  await page.state.loadHighlightPreview()
  const tree = page.render()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].page_size, 6)
  assert.equal(calls[0].is_highlighted, true)
  assert.equal(nodes(tree, 'MobileHighlightCard')[0].props.entity.uuid, '真实资料')
  assert.equal(nodes(tree, 'button').length, 3)
  assert.equal(nodes(tree, 'button').find(node => renderedText(node).includes('专题 Wiki')).props.disabled, true)
  assert.doesNotMatch(renderedText(tree), /活跃目标|已完成目标|分类统计|优先级分布/)
  page.stop()
})

test('缺少检索操作或重点页面访问权限时不请求资料接口', async () => {
  for (const path of [hubPath, listPath]) {
    for (const permission of [PERM.operations.search.entity.execute, PERM.pages.target.highlights.access]) {
      let calls = 0
      const page = loadComponent(path, { denied: [permission], search: async () => { calls++; return {} } })
      await Promise.all(page.hooks.mounted.map(callback => callback()))
      assert.equal(calls, 0)
      assert.match(renderedText(page.render()), /暂无查阅重点资料的权限/)
      page.stop()
    }
  }
})

test('提交筛选从后续页回第一页只发一次请求，分页沿用已提交关键词', async () => {
  const calls = []
  const page = loadComponent(listPath, { search: async params => {
    calls.push(params)
    return { code: 0, data: { items: [{ uuid: '资料' }], total: 30 } }
  } })
  page.state.currentPage.value = 3
  await Vue.nextTick()
  calls.length = 0
  page.state.keywords.value = ' 已提交 '
  page.state.entityTypes.value = ['article']
  page.state.timeRange.value = '7d'
  await page.state.applyFilters()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].page, 1)
  assert.equal(calls[0].keywords, '已提交')
  assert.deepEqual(calls[0].entity_type, ['article'])
  assert.ok(calls[0].start_at && calls[0].end_at)
  page.state.keywords.value = '尚未提交'
  page.state.currentPage.value = 2
  await Vue.nextTick()
  assert.equal(calls.at(-1).keywords, '已提交')
  assert.equal(calls.at(-1).page, 2)
  page.stop()
})

test('筛选草稿关闭不生效，应用按钮才提交；离页关闭抽屉且正常返回保留结果与分页', async () => {
  let calls = 0
  const page = loadComponent(listPath, { search: async () => {
    calls++
    return { code: 0, data: { items: [{ uuid: '保留材料' }], total: 30 } }
  } })
  await page.state.loadData()
  page.state.currentPage.value = 2
  await Vue.nextTick()
  page.state.openMobileFilters()
  page.state.mobileDraft.value.timeRange = '30d'
  page.state.mobileFiltersVisible.value = false
  assert.equal(page.state.activeFilters.value.timeRange, 'all')
  page.state.openMobileFilters()
  assert.equal(page.state.mobileDraft.value.timeRange, 'all')
  page.state.mobileDraft.value.timeRange = '7d'
  const sheet = nodes(page.render(), 'MobileSheet')[0]
  const apply = nodes(sheet.children.footer(), 'el-button').find(node => renderedText(node) === '应用筛选')
  apply.props.onClick()
  await Vue.nextTick()
  assert.equal(page.state.activeFilters.value.timeRange, '7d')
  assert.equal(page.state.mobileFiltersVisible.value, false)
  page.state.currentPage.value = 2
  await Vue.nextTick()
  page.state.mobileFiltersVisible.value = true
  const beforeReturn = calls
  page.hooks.deactivated.forEach(callback => callback())
  assert.equal(page.state.mobileFiltersVisible.value, false)
  await Promise.all(page.hooks.activated.map(callback => callback()))
  assert.equal(calls, beforeReturn)
  assert.equal(page.state.currentPage.value, 2)
  assert.equal(page.state.items.value[0].uuid, '保留材料')
  page.stop()
})

test('重点请求乱序到达时不覆盖最新结果，离页未完成请求不会污染缓存', async () => {
  const pending = []
  const page = loadComponent(listPath, { search: () => new Promise(resolve => pending.push(resolve)) })
  const old = page.state.loadData()
  page.state.keywords.value = '新的搜索'
  const current = page.state.applyFilters()
  pending[1]({ code: 0, data: { items: [{ uuid: '新结果' }], total: 1 } })
  await current
  pending[0]({ code: 500, message: '旧请求失败' })
  await old
  assert.equal(page.state.items.value[0].uuid, '新结果')
  assert.equal(page.state.loadError.value, '')
  const leaving = page.state.loadData()
  page.hooks.deactivated.forEach(callback => callback())
  pending[2]({ code: 0, data: { items: [{ uuid: '离页后的旧结果' }], total: 1 } })
  await leaving
  assert.equal(page.state.items.value[0].uuid, '新结果')
  const returning = Promise.all(page.hooks.activated.map(callback => callback()))
  assert.equal(pending.length, 4)
  pending[3]({ code: 0, data: { items: [{ uuid: '返回后补载' }], total: 1 } })
  await returning
  assert.equal(page.state.items.value[0].uuid, '返回后补载')
  page.stop()
})

test('资料入口与重点列表初次失败均显示错误重试，成功重试后恢复真实空态', async () => {
  for (const path of [hubPath, listPath]) {
    let fail = true
    const page = loadComponent(path, { search: async () => fail ? { code: 500 } : { code: 0, data: { items: [], total: 0 } } })
    const load = page.state.loadData || page.state.loadHighlightPreview
    await load()
    assert.match(renderedText(page.render()), /重点资料加载失败，请重试/)
    assert.doesNotMatch(renderedText(page.render()), /还没有重点资料|暂无重点资料/)
    fail = false
    await load()
    assert.match(renderedText(page.render()), /还没有重点资料|暂无重点资料/)
    page.stop()
  }
})

test('取消重点保留原业务语义，拒绝无权限与重复操作，失败不移除资料', async () => {
  let writes = 0
  const deniedPage = loadComponent(listPath, { denied: [PERM.operations.target.highlight.update], highlight: async () => { writes++; return { code: 0 } } })
  await deniedPage.state.cancelHighlight({ entity_type: 'article', uuid: '保留' })
  assert.equal(writes, 0)
  deniedPage.stop()
  let resolveWrite
  const page = loadComponent(listPath, { highlight: () => { writes++; return new Promise(resolve => { resolveWrite = resolve }) } })
  page.state.items.value = [{ entity_type: 'article', uuid: '保留' }]
  page.state.total.value = 1
  const record = page.state.items.value[0]
  const pending = page.state.cancelHighlight(record)
  await page.state.cancelHighlight(record)
  assert.equal(writes, 1)
  resolveWrite({ code: 500, message: '无法取消' })
  await pending
  assert.equal(page.state.items.value[0].uuid, '保留')
  assert.equal(page.state.total.value, 1)
  assert.equal(record._highlightLoading, false)
  assert.deepEqual(page.messages, ['无法取消'])
  page.stop()
})

test('取消最后一页唯一资料后回到有效页，使用对应小写实体接口', async () => {
  const requests = []
  const writes = []
  const page = loadComponent(listPath, { search: async params => {
    requests.push(params)
    return { code: 0, data: { items: [{ uuid: '另一条' }], total: requests.length === 1 ? 11 : 10 } }
  }, highlight: async (...params) => { writes.push(params); return { code: 0 } } })
  page.state.currentPage.value = 2
  await Vue.nextTick()
  page.state.items.value = [{ entity_type: 'Article', uuid: '最后一条' }]
  await page.state.cancelHighlight(page.state.items.value[0])
  await Vue.nextTick()
  assert.deepEqual(writes, [['article', '最后一条', { is_highlighted: false }]])
  assert.equal(page.state.currentPage.value, 1)
  assert.equal(requests.length, 2)
  assert.equal(requests.at(-1).page, 1)
  page.stop()
})

test('取消成功立即移除当前材料，不被索引尚未刷新的重复查询重新加回', async () => {
  let reads = 0
  const page = loadComponent(listPath, { search: async () => {
    reads++
    return { code: 0, data: { items: [{ entity_type: 'article', uuid: '待取消' }], total: 1 } }
  } })
  await page.state.loadData()
  await page.state.cancelHighlight(page.state.items.value[0])
  assert.equal(reads, 1)
  assert.equal(page.state.items.value.length, 0)
  assert.equal(page.state.total.value, 0)
  page.stop()
})

test('正文卡片按实体类型检查阅读权限，页面可见不能代替正文权限', () => {
  for (const type of ['article', 'forum']) {
    const props = { entity: { entity_type: type, uuid: '资料/一' }, manageable: true }
    const deniedPage = loadComponent('components/target/MobileHighlightCard.vue', { props, denied: [PERM.operations.content[type].read] })
    assert.equal(deniedPage.state.detailPath.value, '')
    deniedPage.stop()
    const allowedPage = loadComponent('components/target/MobileHighlightCard.vue', { props })
    assert.equal(allowedPage.state.detailPath.value, `/details/${type}/${encodeURIComponent('资料/一')}`)
    allowedPage.stop()
  }
})
