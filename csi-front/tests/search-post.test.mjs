import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'

/**
 * 执行真实页面状态与模板，隔离网络、生命周期和浏览器滚动。
 * @param {object} t 测试上下文。
 * @param {string} file 相对 src 的组件路径。
 * @param {object} options 接口、移动断点及组件属性。
 * @returns {object} 页面状态、虚拟节点遍历及消息记录。
 */
function pageHarness(t, file, options = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: file })
  const code = script.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\r?\n/gm, '').replace('export default', 'return')
  const messages = []
  const hooks = []
  const events = []
  const props = Vue.reactive(options.props || {})
  const bindings = {
    ref: Vue.ref, computed: Vue.computed, watch: Vue.watch,
    nextTick: Vue.nextTick, markRaw: Vue.markRaw, PERM,
    useRoute: () => Vue.reactive({ query: {}, params: { id: 'twitter-id' } }),
    useRouter: () => ({ push: path => events.push(path) }),
    useMobileViewport: () => ({ isMobile: Vue.ref(Boolean(options.mobile)) }),
    onMounted() {}, onBeforeRouteLeave() {}, onBeforeUnmount: fn => hooks.push(fn),
    hasPerm: () => true, hasAny: () => true, guardPermission: () => true,
    formatDate: value => value, formatDateTime: value => value,
    sanitizeHtml: value => String(value || ''), getCosUrl: value => value,
    platformApi: options.platformApi || {}, searchApi: options.searchApi || {}, highlightApi: {},
    ElMessage: Object.assign(value => messages.push(value), { error: value => messages.push(value) }),
    ElNotification: value => messages.push(value),
    document: { getElementById: () => null }, window: { removeEventListener() {} },
    console: { error() {} },
  }
  for (const name of Object.keys(script.imports)) {
    if (!(name in bindings)) bindings[name] = { name }
  }
  const component = new Function(...Object.keys(bindings), code)(...Object.values(bindings))
  for (const [name, definition] of Object.entries(component.props || {})) {
    if (!(name in props)) props[name] = typeof definition?.default === 'function' ? definition.default() : definition?.default
  }
  const scope = Vue.effectScope()
  const page = scope.run(() => component.setup(props, { expose() {}, emit() {} }))
  const render = Vue.compile(descriptor.template.content, { bindingMetadata: script.bindings })
  t.mock.method(console, 'warn', () => {})
  t.after(() => { hooks.forEach(fn => fn()); scope.stop() })
  return {
    page, messages, events,
    nodes() {
      const state = Vue.proxyRefs({ ...props, ...page })
      const stack = [render(state, [], props, state, {}, {})]
      const nodes = []
      while (stack.length) {
        const node = stack.pop()
        if (Array.isArray(node)) { stack.push(...node); continue }
        if (!node || typeof node !== 'object') continue
        nodes.push(node)
        if (Array.isArray(node.children)) stack.push(...node.children)
        else if (node.children && typeof node.children === 'object') {
          for (const slot of Object.values(node.children)) {
            if (typeof slot === 'function') stack.push(slot())
          }
        }
      }
      return nodes
    },
  }
}

const results = ['post', 'article', 'forum'].map(entity_type => ({
  uuid: `${entity_type}-1`, entity_type, title: '情报标题', clean_content: '',
  platform: 'twitter', platform_id: 'twitter-id', keywords: [], confidence: 1,
}))

test('桌面和手机搜索提交贴文筛选，保留文章论坛详情并隐藏贴文详情', async t => {
  const calls = []
  const { page, nodes } = pageHarness(t, 'views/Search.vue', {
    mobile: true,
    searchApi: { searchEntity: async params => { calls.push(params); return { code: 0, data: { items: results, total: 3 } } } },
  })
  page.categories.value = ['post']
  await page.performSearch()
  await Vue.nextTick()
  assert.deepEqual(calls[0].entity_type, ['post'])
  assert.match(page.mobileFilterSummary.value, /贴文/)
  assert.equal(page.getDetailRoute('post', 'post-1'), '')
  assert.ok(page.filterOptions.categories.some(item => item.value === 'post'))
  page.mobileSelectedResult.value = results[0]
  page.mobileResultActionsVisible.value = true
  for (const mobile of [true, false]) {
    page.isMobile.value = mobile
    const links = nodes().filter(node => node.type === 'router-link').map(node => node.props.to)
    assert.ok(links.includes('/details/article/article-1'))
    assert.ok(links.includes('/details/forum/forum-1'))
    assert.ok(!links.some(path => String(path).startsWith('/details/post/')))
  }
})

test('平台关联情报按当前平台分页请求，桌面只保留已实现的详情入口', async t => {
  const calls = []
  const { page, nodes } = pageHarness(t, 'views/details/PlatformDetail.vue', {
    platformApi: { getPlatformDetail: async () => ({ code: 0, data: { id: 'twitter-id', name: 'twitter' } }) },
    searchApi: { searchEntity: async params => { calls.push(params); return { code: 0, data: { items: results, total: 3 } } } },
  })
  await page.loadPlatformDetail()
  await Vue.nextTick()
  assert.equal(calls[0].platform, 'twitter')
  assert.equal(calls[0].page_size, 5)
  assert.equal(page.intelligenceTotalResults.value, 3)
  const links = nodes().filter(node => node.type === 'router-link').map(node => node.props.to)
  assert.ok(links.includes('/details/article/article-1'))
  assert.ok(links.includes('/details/forum/forum-1'))
  assert.ok(!links.some(path => String(path).startsWith('/details/post/')))
})

test('手机平台关联情报隐藏贴文查看按钮，文章论坛按钮仍可跳转', t => {
  const { page, nodes, events } = pageHarness(t, 'components/platform/MobilePlatformDetail.vue', {
    props: { platform: { uuid: 'twitter-id', type: 'post' }, buckets: [], intelligence: results },
  })
  page.plainText = value => String(value || '')
  const buttons = nodes().filter(node => node.type === 'el-button'
    && (Array.isArray(node.children) ? node.children : node.children?.default?.() || [])
      .some(child => child.children === '查看情报'))
  assert.equal(buttons.length, 2)
  buttons.forEach(button => button.props.onClick())
  assert.deepEqual(events.sort(), ['/details/article/article-1', '/details/forum/forum-1'])
})

test('平台关联情报接口报错时显示重试状态，不伪装为暂无数据', async t => {
  const { page, nodes } = pageHarness(t, 'views/details/PlatformDetail.vue', {
    searchApi: { searchEntity: async () => ({ code: 250002, message: '检索暂时不可用' }) },
  })
  page.platformDetail.value.name = 'twitter'
  await page.loadRelatedIntelligence()
  assert.equal(page.intelligenceError.value, '关联情报加载失败，请重试')
  assert.ok(nodes().some(node => node.props?.role === 'alert'))
})
