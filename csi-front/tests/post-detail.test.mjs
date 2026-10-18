import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from 'vue/compiler-sfc'
import { normalizePostMedia, safePostUrl } from '../src/utils/postMedia.js'
import { PERM } from '../src/utils/permissions.js'

/**
 * 执行贴文组件的真实状态与模板，保留响应式请求、路由和渲染行为。
 * @param {object} t 测试上下文。
 * @param {string} file 组件路径。
 * @param {object} options 接口、权限、屏幕和属性配置。
 * @returns {object} 页面状态、路由和虚拟节点。
 */
function harness(t, file, options = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: file })
  const code = script.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\r?\n/gm, '').replace('export default', 'return')
  const route = Vue.reactive({ params: { uuid: 'post-1' } })
  route.query = {}
  const props = Vue.reactive(options.props || {})
  const hooks = []
  const mounted = []
  const markingOptions = []
  const noop = () => {}
  const bindings = {
    ref: Vue.ref, computed: Vue.computed, watch: Vue.watch, nextTick: Vue.nextTick,
    onMounted: callback => mounted.push(callback),
    onUnmounted: callback => hooks.push(callback),
    useRoute: () => route, useRouter: () => ({ back() {}, replace() {} }),
    useMobileViewport: () => ({ isMobile: Vue.ref(Boolean(options.mobile)) }),
    useMinLg: () => ({ isLgUp: Vue.ref(!options.mobile) }),
    postApi: options.postApi || { getPostDetail: async () => ({ code: 0, data: post }) },
    articleApi: options.articleApi || { getArticleDetail: async () => ({ code: 0, data: { ...post, title: '文章标题', entity_type: 'article', safe_raw_content: '<p>原始排版</p>' } }) },
    agentApi: { getAgentsConfigList: async () => ({ data: [] }) },
    hasPerm: options.hasPerm || (() => true), PERM,
    formatDateTime: value => value, safePostUrl, normalizePostMedia,
    sanitizeHtml: value => value,
    convertRelativeLinks: value => value, revokeBlobUrl: noop,
    document: { body: { style: {} }, addEventListener: noop, removeEventListener: noop },
    window: { addEventListener: noop, removeEventListener: noop },
    ElMessage: { info: noop, error: noop },
    useAgentSessionStream: () => ({
      ...Object.fromEntries(['userPrompt', 'sseConnected', 'showApprovalDialog', 'pendingApproval', 'approvalReason', 'showRejectReason', 'approvalLoading', 'sendLoading', 'cancelLoading', 'historyLoading', 'hasMoreHistory', 'canSendMessage', 'canCancel'].map(key => [key, Vue.ref(null)])),
      timelineItems: Vue.ref([]), todos: Vue.ref([]),
      loadOlderEvents: noop, registerEventsScrollEl: noop, scrollEventsToBottom: noop, onEventsScroll: noop,
      disconnectSSE: noop, startStreamForSession: noop, sendMessage: noop, cancel: noop,
      cancelRejectFlow: noop, submitApprovalDecision: noop, onApprovalDialogClosed: noop,
    }),
    useMarkingHandler: config => {
      markingOptions.push(config)
      return {
        currentRegion: Vue.ref('rendered'), activeMarkingId: Vue.ref(null), toolbarVisible: Vue.ref(false),
        toolbarPosition: Vue.ref({}), availableStyles: Vue.ref([]), selectedStyle: Vue.ref('highlight'),
        getMarkingsByRegion: () => [], getSortedMarkingsByRegion: () => [],
        ...Object.fromEntries(['handleCleanContentMouseUp', 'handleRenderedContentMouseUp', 'handleTranslateContentMouseUp', 'handleStyleSelect', 'handleCreateMarking', 'handleUpdateMarking', 'handleDeleteMarking', 'handleMarkingHover', 'handleTabChange', 'loadMarkings', 'clearAllMarkings', 'setupEventListeners', 'cleanupEventListeners'].map(key => [key, noop])),
      }
    },
    useHighlight: () => ({ showHighlightDialog: Vue.ref(false), highlightLoading: Vue.ref(false), highlightForm: Vue.ref({ reason: '' }), isPriorityTarget: Vue.ref(false), togglePriorityTarget: noop, confirmSetHighlight: noop }),
    useKeywordHighlight: () => ({
      selectedKeywords: Vue.ref([]), keywordTagRefs: Vue.ref({}), keywordColors: Vue.ref({}),
      setKeywordRef: noop, toggleKeyword: noop, applyRenderedKeywordHighlight: noop,
      getHighlightedPlainText: getValue => String(getValue() || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
    }),
    useEntityHighlight: () => ({ selectedEntityKeys: Vue.ref([]), entityTagRefs: Vue.ref({}), entityColors: Vue.ref({}), setEntityRef: noop, toggleEntity: noop, buildEntityHighlightLayer: () => null }),
  }
  for (const name of Object.keys(script.imports)) if (!(name in bindings)) bindings[name] = { name }
  const component = new Function(...Object.keys(bindings), code)(...Object.values(bindings))
  for (const [name, definition] of Object.entries(component.props || {})) {
    if (!(name in props)) props[name] = typeof definition?.default === 'function' ? definition.default() : definition?.default
  }
  const scope = Vue.effectScope()
  const page = scope.run(() => component.setup(props, { expose() {} }))
  mounted.forEach(callback => callback())
  const render = Vue.compile(descriptor.template.content, { bindingMetadata: script.bindings })
  t.mock.method(console, 'warn', () => {})
  t.after(() => { hooks.forEach(callback => callback()); scope.stop() })
  return {
    page, route, markingOptions,
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
          for (const slot of Object.values(node.children)) if (typeof slot === 'function') stack.push(slot())
        }
      }
      return nodes
    },
  }
}

const post = {
  uuid: 'post-1', entity_type: 'post', source_id: 'source-1', platform: 'Twitter', platform_uuid: 'platform-1',
  author_name: '作者', clean_content: '正文 <script>不会执行</script>\n第二行',
  raw_content: '{"text":"原始内容 <img src=x onerror=alert(1)>"}', translate_content: '译文',
  media_resources: [{ source_url: 'https://source.example/photo', stored_url: 'https://stored.example/hash', content_type: 'image/jpeg', status: 'stored' }],
}

test('媒体遵守清单优先级，优先展示归档地址并识别无扩展名的类型', () => {
  const media = normalizePostMedia(post)
  assert.equal(media[0].url, 'https://stored.example/hash')
  assert.equal(media[0].type, 'image')
  assert.deepEqual(normalizePostMedia({ media_resources: [], files_urls: ['https://example.com/stale.jpg'] }), [])
  assert.equal(normalizePostMedia({ files_urls: ['https://example.com/video.mp4?signature=abc'] })[0].type, 'video')
  assert.equal(normalizePostMedia({ media_resources: null, files_urls: ['https://example.com/audio.mp3'] })[0].type, 'audio')
  assert.equal(normalizePostMedia({ media_resources: [{ source_url: 'https://example.com/hash.jpg', content_type: 'application/pdf' }] })[0].type, 'file')
})

test('视频关联封面，失败项保留来源地址，危险地址不进入展示', () => {
  const media = normalizePostMedia({ media_resources: [
    { media_id: 'v1', source_url: 'https://example.com/v.mp4', type: 'video', status: 'failed' },
    { media_id: 'v1', source_url: 'https://example.com/p.jpg', type: 'image', role: 'poster' },
    { source_url: 'https://example.com/report.pdf', content_type: 'application/pdf' },
    { source_url: 'javascript:alert(1)' }, { source_url: 'data:text/html,test' }, { source_url: '//example.com/test' },
  ] })
  assert.equal(media.length, 2)
  assert.equal(media[0].poster, 'https://example.com/p.jpg')
  assert.equal(media[0].status, 'failed')
  assert.equal(media[1].type, 'file')
  assert.equal(safePostUrl('https://user:password@example.com/file'), '')
  assert.equal(normalizePostMedia({ files_urls: ['https://example.com/stream.m3u8'] })[0].type, 'file')
})

test('媒体组件渲染图片、视频、音频和附件，播放失败后提供可用提示', t => {
  const { page, nodes } = harness(t, 'components/detail/PostMediaGallery.vue', { props: { post: { media_resources: [
    { source_url: 'https://example.com/i.jpg' }, { source_url: 'https://example.com/v.mp4' },
    { source_url: 'https://example.com/a.mp3' }, { source_url: 'https://example.com/f.pdf' },
  ] } } })
  assert.ok(nodes().some(node => node.type === 'el-image' && node.props.src.endsWith('i.jpg')))
  const video = nodes().find(node => node.type === 'video')
  assert.ok('controls' in video.props)
  assert.equal(video.props.autoplay, undefined)
  assert.ok(nodes().some(node => node.type === 'audio' && 'controls' in node.props))
  assert.ok(nodes().some(node => node.type === 'a' && node.props.href.endsWith('f.pdf')))
  video.props.onError()
  assert.ok(page.failedUrls.value.has('https://example.com/v.mp4'))
  assert.ok(!nodes().some(node => node.type === 'video'))
})

test('贴文详情直接复用文章详情组件，不再维护单独布局和样式', t => {
  const { nodes } = harness(t, 'views/details/PostDetail.vue')
  assert.ok(nodes().some(node => node.type?.name === 'ArticleDetail' && node.props['entity-type'] === 'post'))
  const { descriptor } = parse(readFileSync(new URL('../src/views/details/PostDetail.vue', import.meta.url), 'utf8'))
  assert.equal(descriptor.styles.length, 0)
})

test('共享详情工作台保留批注、上下分区与右侧信息分析栏，贴文媒体放在渲染内容中', async t => {
  for (const mobile of [false, true]) {
    const { page, nodes, markingOptions } = harness(t, 'views/details/ArticleDetail.vue', { mobile, props: { entityType: 'post' }, articleApi: { getArticleDetail: () => { assert.fail('贴文不能调用文章详情接口') } } })
    await page.loadArticleDetail()
    assert.equal(page.activeTab.value, 'rendered')
    const workbench = nodes().find(node => node.type?.name === 'ArticleDetailWorkbench')
    assert.ok(workbench.children['center-top'] && workbench.children['center-bottom'] && workbench.children.right)
    assert.equal(workbench.props['pane-storage-key'], 'post-detail-pane-sizes')
    assert.ok(nodes().some(node => node.type?.name === 'ArticleDetailInfoPanel'))
    assert.ok(nodes().some(node => node.type?.name === 'ArticleDetailAnalysisPanel'))
    assert.ok(nodes().some(node => node.type?.name === 'DetailRightActivityRail'))
    assert.equal(markingOptions[0].entityType, 'post')
    const rendered = nodes().find(node => node.type === 'el-tab-pane' && node.props.name === 'rendered')
    assert.equal(rendered.props.label, '渲染内容')
    assert.ok(nodes().some(node => node.type?.name === 'PostMediaGallery' && node.props.post.uuid === post.uuid))
    assert.ok(nodes().some(node => node.type === 'pre' && node.props?.innerHTML?.includes('&lt;script&gt;')))
    const raw = nodes().find(node => node.type?.name === 'MonacoEditor' && node.props['model-value'] === post.raw_content)
    assert.equal(raw.props['read-only'], true)
    assert.equal(raw.props.language, 'json')
    assert.ok(!nodes().some(node => node.type?.name === 'Timeline'))
    assert.ok(!nodes().some(node => node.type?.name === 'AddToEvidenceButton'))
    assert.equal(nodes().some(node => node.type?.name === 'MobileReadingFormat'), mobile)
  }
})

test('仅有媒体的贴文仍默认打开渲染内容，并提供相同的手机阅读选项', async t => {
  const { page, nodes } = harness(t, 'views/details/ArticleDetail.vue', {
    mobile: true, props: { entityType: 'post' },
    postApi: { getPostDetail: async () => ({ code: 0, data: { ...post, clean_content: null, raw_content: null } }) },
  })
  await page.loadArticleDetail()
  assert.equal(page.activeTab.value, 'rendered')
  assert.ok(nodes().some(node => node.type?.name === 'PostMediaGallery'))
  assert.ok(!nodes().some(node => node.type === 'el-tab-pane' && node.props.name === 'empty'))
  const format = nodes().find(node => node.type?.name === 'MobileReadingFormat')
  assert.equal(format.props['structured-content'], true)
})

test('文章默认接口、正文、时间线及操作入口保持原行为', async t => {
  let postCalls = 0
  const { page, nodes, markingOptions } = harness(t, 'views/details/ArticleDetail.vue', { postApi: { getPostDetail: () => { postCalls += 1 } } })
  await page.loadArticleDetail()
  assert.equal(postCalls, 0)
  assert.equal(page.activeTab.value, 'clean')
  assert.equal(page.detailTitle.value, '文章标题')
  assert.equal(markingOptions[0].entityType, 'article')
  assert.ok(nodes().some(node => node.type?.name === 'AddToEvidenceButton'))
  assert.ok(nodes().some(node => node.type?.name === 'Timeline'))
  assert.ok(!nodes().some(node => node.type?.name === 'PostMediaGallery'))
  const info = nodes().find(node => node.type?.name === 'ArticleDetailInfoPanel')
  assert.equal(info.props['show-analysis-action'], true)
  assert.equal(info.props['show-priority-action'], true)
})

test('切换贴文后旧请求不能覆盖新内容', async t => {
  const pending = new Map()
  const { page, route } = harness(t, 'views/details/ArticleDetail.vue', { props: { entityType: 'post' }, postApi: {
    getPostDetail: uuid => new Promise(resolve => pending.set(uuid, resolve)),
  } })
  route.params.uuid = 'post-2'
  await Vue.nextTick()
  pending.get('post-2')({ code: 0, data: { ...post, uuid: 'post-2' } })
  await Vue.nextTick()
  pending.get('post-1')({ code: 0, data: post })
  await Vue.nextTick()
  assert.equal(page.articleData.value.uuid, 'post-2')
  assert.equal(page.loading.value, false)
})

test('详情错误可重试，无贴文读取权限时不发出请求', async t => {
  let calls = 0
  const { page, nodes } = harness(t, 'views/details/ArticleDetail.vue', { props: { entityType: 'post' }, postApi: {
    getPostDetail: async () => { calls += 1; return calls === 1 ? { code: 240415, message: '贴文不存在' } : { code: 0, data: post } },
  } })
  await Vue.nextTick()
  assert.equal(page.error.value, '贴文不存在')
  assert.ok(nodes().some(node => node.children === '贴文不存在'))
  await page.loadArticleDetail()
  assert.equal(page.articleData.value.uuid, post.uuid)
  calls = 0
  const denied = harness(t, 'views/details/ArticleDetail.vue', { props: { entityType: 'post' }, hasPerm: () => false, postApi: { getPostDetail: () => { calls += 1 } } })
  assert.match(denied.page.error.value, /无权限/)
  assert.equal(calls, 0)
})
