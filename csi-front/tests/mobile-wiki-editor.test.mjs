import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, nextTick, reactive, ref } from 'vue'
import { parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import * as editorState from '../src/components/wiki/wikiEditorState.js'
import * as tree from '../src/utils/wikiTree.js'
import * as citationIds from '../src/utils/wikiCitationIds.js'

const fixture = () => ({
  id: '专题甲', title: '专题标题', revision: 7, status: 'published', sourceNote: '来源说明', categories: ['分类甲'],
  contentTree: { section: 'main', title: '', content: '导语 [^1]', infobox: null, children: [
    { section: 'a', title: '章节甲', content: '甲正文', infobox: { caption: '资料卡', series: '副标题', image: '/a.png', rows: [{ label: '名称', value: '值' }] }, children: [
      { section: 'b', title: '章节乙', content: '乙正文 [^a]', infobox: { caption: '乙资料', rows: [{ label: '保留', value: '完整字段' }] }, children: [] },
    ] },
    { section: 'c', title: '章节丙', content: '丙正文', infobox: null, children: [] },
  ] },
  references: [{ id: '1', text: '参考材料', url: '/details/article/文章甲', entityType: 'article', entityUuid: '文章甲' }],
  footnotes: [{ id: 'a', text: '注释甲' }],
})

test('编辑草稿隔离来源数据，正文保存保留信息框且不携带子树', () => {
  const wiki = fixture()
  const draft = editorState.createWikiEditorDraft(wiki, 'content', 'a')
  draft.content = ''
  draft.infobox.rows[0].value = '已修改'
  assert.equal(wiki.contentTree.children[0].content, '甲正文')
  assert.equal(wiki.contentTree.children[0].infobox.rows[0].value, '值')
  const body = editorState.buildWikiEditorPatch(wiki, 'content', draft, ' 更新正文 ')
  assert.equal(body.expectedRevision, 7)
  assert.equal(body.content, '')
  assert.equal(body.infobox.image, '/a.png')
  assert.equal(body.infobox.series, '副标题')
  assert.equal(body.infobox.rows[0].value, '已修改')
  assert.equal(body.changeSummary, '更新正文')
  assert.equal('children' in body, false)
  assert.equal('title' in body, false)
  draft.infobox = null
  assert.equal(editorState.buildWikiEditorPatch(wiki, 'content', draft).infobox, null)
})

test('元数据显式清空说明，引用重排保存原编号和关联实体', () => {
  const wiki = fixture()
  const metadata = editorState.createWikiEditorDraft(wiki, 'meta')
  metadata.sourceNote = ''
  const body = editorState.buildWikiEditorPatch(wiki, 'meta', metadata)
  assert.equal(body.sourceNote, '')
  assert.deepEqual(body.categories, ['分类甲'])
  assert.equal(body.status, 'published')
  const refs = editorState.createWikiEditorDraft(wiki, 'references')
  refs.unshift({ id: '8', text: '新参考', url: 'https://example.test/' })
  const saved = editorState.buildWikiEditorPatch(wiki, 'references', refs)
  assert.deepEqual(saved.items.map(item => item.id), ['8', '1'])
  assert.deepEqual(saved.items[1], wiki.references[0])
  assert.equal(wiki.references.length, 1)
  assert.throws(() => editorState.buildWikiEditorPatch(wiki, 'references', [refs[0], refs[0]]), /重复/)
})

/** """模拟真实后端的追加、级联删除和逐次修订校验。""" */
function memoryApi(initial) {
  let current = structuredClone(initial)
  let created = 0
  const calls = []
  const update = (kind, body, mutate) => {
    assert.equal(body.expectedRevision, current.revision, `${kind} 必须使用上一接口修订`)
    calls.push(kind)
    mutate()
    current.revision += 1
    return structuredClone(current)
  }
  return {
    calls,
    createSection: async (_id, body) => {
      const section = `服务器章节${++created}`
      const detail = update('create', body, () => {
        const parent = tree.findWikiNode(current.contentTree, body.parentSection)
        assert.ok(parent)
        parent.children.push({ section, title: body.title, content: '', infobox: null, children: [] })
      })
      return { section, detail }
    },
    moveSection: async (_id, section, body) => update('move', body, () => {
      const parent = tree.findWikiParent(current.contentTree, section)
      const index = parent.children.findIndex(node => node.section === section)
      const [node] = parent.children.splice(index, 1)
      const target = tree.findWikiNode(current.contentTree, body.parentSection)
      assert.ok(target, '不能移动到已脱离的子树中')
      if (body.afterSection) {
        const previous = target.children.findIndex(item => item.section === body.afterSection)
        assert.notEqual(previous, -1)
        target.children.splice(previous + 1, 0, node)
      } else target.children.push(node)
    }),
    updateSection: async (_id, section, body) => update('rename', body, () => { tree.findWikiNode(current.contentTree, section).title = body.title }),
    deleteSection: async (_id, section, body) => update('delete', body, () => {
      const parent = tree.findWikiParent(current.contentTree, section)
      parent.children.splice(parent.children.findIndex(node => node.section === section), 1)
    }),
  }
}

test('子章节升一级再删除原父章节，保留子章节正文和信息框', async () => {
  const wiki = fixture()
  const api = memoryApi(wiki)
  let draft = editorState.moveWikiEditorSection(wiki.contentTree, 'b', 'outdent')
  draft = tree.removeNode(draft, 'a')
  const saved = await editorState.persistWikiEditorToc(api, wiki, draft)
  assert.deepEqual(saved.contentTree.children.map(node => node.section), ['b', 'c'])
  assert.deepEqual(tree.findWikiNode(saved.contentTree, 'b'), tree.findWikiNode(wiki.contentTree, 'b'))
  assert.ok(api.calls.indexOf('move') < api.calls.indexOf('delete'))
  assert.deepEqual(saved.references, wiki.references)
})

test('目录重排及新建多级节点使用服务器标识和后端追加语义', async () => {
  const wiki = fixture()
  const api = memoryApi(wiki)
  let draft = editorState.moveWikiEditorSection(wiki.contentTree, 'c', 'up')
  draft.children.unshift({ section: '临时一', title: '新增主章', content: '', infobox: null, children: [{ section: '临时二', title: '新增子章', content: '', infobox: null, children: [] }] })
  tree.findWikiNode(draft, 'a').title = '章节甲新标题'
  const saved = await editorState.persistWikiEditorToc(api, wiki, draft)
  assert.deepEqual(saved.contentTree.children.map(node => node.title), ['新增主章', '章节丙', '章节甲新标题'])
  assert.equal(saved.contentTree.children[0].section, '服务器章节1')
  assert.equal(saved.contentTree.children[0].children[0].section, '服务器章节2')
  assert.equal(tree.findWikiNode(saved.contentTree, 'b').content, '乙正文 [^a]')
  assert.deepEqual(wiki, fixture())
})

test('升降级保留子树且首项不能降级，未改目录不产生写请求', async () => {
  const wiki = fixture()
  const draft = editorState.moveWikiEditorSection(wiki.contentTree, 'a', 'indent')
  assert.deepEqual(draft, tree.cloneWikiTree(wiki.contentTree))
  const indented = editorState.moveWikiEditorSection(wiki.contentTree, 'c', 'indent')
  assert.equal(tree.findWikiParent(indented, 'c').section, 'a')
  assert.equal(tree.findWikiNode(indented, 'b').content, '乙正文 [^a]')
  const api = memoryApi(wiki)
  await editorState.persistWikiEditorToc(api, wiki, draft)
  assert.deepEqual(api.calls, [])
})

const editorSource = readFileSync(new URL('../src/views/wiki/WikiEditor.vue', import.meta.url), 'utf8')
const editorScript = parse(editorSource).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*$/gm, '')

/** """执行真实页面脚本，以内存路由/API 验证草稿与异步行为。""" */
function editorHarness(api = {}, options = {}) {
  const route = reactive({ name: 'wiki-editor', params: { id: '专题甲' } })
  const permissions = reactive(new Set(Object.values(PERM.operations.target.wiki)))
  const hooks = {}, events = [], navigation = []
  const scrolls = []
  const viewport = { keyboardOpen: ref(false), viewportHeight: ref(400), viewportTop: ref(0) }
  const document = { activeElement: null }
  const dependencies = {
    computed, nextTick, ref, watch: () => {}, defineOptions: () => {}, document,
    useRoute: () => route,
    useRouter: () => ({ push: value => navigation.push(value), replace: value => navigation.push(value) }),
    onBeforeRouteLeave: fn => { hooks.leave = fn }, onBeforeRouteUpdate: fn => { hooks.update = fn }, onBeforeUnmount: fn => { hooks.unmount = fn },
    window: { addEventListener: (name, fn) => { hooks[name] = fn }, removeEventListener: () => {}, scrollBy: value => scrolls.push(value) },
    useMobileViewport: () => viewport,
    ElMessage: { success: message => events.push(message), warning: message => events.push(message) },
    ElMessageBox: { confirm: options.confirm || (async () => {}) },
    wikiApi: { getPageById: async () => fixture(), ...api }, searchApi: {},
    hasPerm: value => permissions.has(value), PERM,
    isWikiRevisionConflict: error => error?.code === 241003,
    referenceFromSearchResult: () => {},
    ...tree, ...citationIds, ...editorState,
  }
  const state = new Function(...Object.keys(dependencies), `${editorScript}\nreturn { loadWiki, saveDraft, draft, wiki, dirty, area, changeArea, changeSection, sectionId, saving, saveError, reloadRequired, loadError, canWrite, addSection, removeSection, searchQuery, searchReferences, revealEditorInput };`)(...Object.values(dependencies))
  return { ...state, route, permissions, hooks, events, navigation, viewport, document, scrolls }
}

test('专题软键盘使用实际可视高度定位字段，已可见输入和非输入焦点不触发滚动', async () => {
  const state = editorHarness()
  state.document.activeElement = { matches: () => true, getBoundingClientRect: () => ({ top: 348, bottom: 430, height: 82 }) }
  await state.revealEditorInput()
  assert.equal(state.scrolls.length, 0)
  state.viewport.keyboardOpen.value = true
  await state.revealEditorInput()
  assert.deepEqual(state.scrolls, [{ top: 46, behavior: 'instant' }])
  state.document.activeElement.getBoundingClientRect = () => ({ top: 100, bottom: 182, height: 82 })
  await state.revealEditorInput()
  assert.equal(state.scrolls.length, 1)
  state.document.activeElement.matches = () => false
  await state.revealEditorInput()
  assert.equal(state.scrolls.length, 1)
})

test('保存正文使用指定章节与旧修订，成功后同步新修订并清除脏状态', async () => {
  const calls = []
  const state = editorHarness({ updateSection: async (...args) => { calls.push(args); const next = fixture(); next.revision = 8; next.contentTree.children[0].content = '新正文'; return next } })
  await state.loadWiki()
  await state.changeArea('content')
  await state.changeSection('a')
  state.draft.value.content = '新正文'
  assert.equal(state.dirty.value, true)
  await state.saveDraft()
  assert.equal(calls[0][0], '专题甲')
  assert.equal(calls[0][1], 'a')
  assert.equal(calls[0][2].expectedRevision, 7)
  assert.equal(calls[0][2].infobox.image, '/a.png')
  assert.equal(state.wiki.value.revision, 8)
  assert.equal(state.dirty.value, false)
})

test('修订冲突保留草稿且阻止再次提交旧稿，不自动覆盖最新修订', async () => {
  let saves = 0
  const state = editorHarness({ updateMeta: async () => { saves++; throw { code: 241003 } } })
  await state.loadWiki()
  state.draft.value.title = '本地标题'
  await state.saveDraft()
  assert.equal(state.draft.value.title, '本地标题')
  assert.equal(state.wiki.value.revision, 7)
  assert.equal(state.reloadRequired.value, true)
  assert.match(state.saveError.value, /已被他人修改/)
  await state.saveDraft()
  assert.equal(saves, 1)
})

test('取消离页和切换保留输入，保存中不允许离页；刷新触发浏览器保护', async () => {
  const state = editorHarness({}, { confirm: async () => { throw new Error('取消') } })
  await state.loadWiki()
  state.draft.value.title = '未保存'
  assert.equal(await state.hooks.leave(), false)
  assert.equal(await state.hooks.update(), false)
  await state.changeArea('references')
  assert.equal(state.area.value, 'meta')
  assert.equal(state.draft.value.title, '未保存')
  let prevented = false
  state.hooks.beforeunload({ preventDefault: () => { prevented = true } })
  assert.equal(prevented, true)
  state.saving.value = true
  assert.equal(await state.hooks.leave(), false)
})

test('卸载后迟到保存响应不会导航、提示或改写页面', async () => {
  let finish
  const state = editorHarness({ updateMeta: () => new Promise(resolve => { finish = resolve }) })
  await state.loadWiki()
  state.draft.value.title = '等待保存'
  const pending = state.saveDraft()
  state.hooks.unmount()
  finish({ ...fixture(), title: '迟到结果', revision: 8 })
  await pending
  assert.equal(state.wiki.value.revision, 7)
  assert.deepEqual(state.events, [])
  assert.deepEqual(state.navigation, [])
})

test('路由切换忽略旧详情响应，无更新权限不产生保存请求', async () => {
  const pending = []
  let saves = 0
  const state = editorHarness({ getPageById: id => new Promise(resolve => pending.push({ id, resolve })), updateMeta: async () => { saves++ } })
  const oldLoad = state.loadWiki()
  state.route.params.id = '专题乙'
  const newLoad = state.loadWiki()
  pending[1].resolve({ ...fixture(), id: '专题乙', title: '新专题' })
  await newLoad
  pending[0].resolve(fixture())
  await oldLoad
  assert.equal(state.wiki.value.id, '专题乙')
  state.permissions.delete(PERM.operations.target.wiki.update)
  state.draft.value.title = '无权限修改'
  await state.saveDraft()
  assert.equal(saves, 0)
})

test('创建与删除章节的独立权限在入口及保存前均受约束', async () => {
  let creates = 0, deletes = 0
  const state = editorHarness({ createSection: async () => { creates++ }, deleteSection: async () => { deletes++ } })
  await state.loadWiki()
  await state.changeArea('toc')
  state.permissions.delete(PERM.operations.target.wiki.create)
  const originalCount = state.draft.value.children.length
  state.addSection(false)
  assert.equal(state.draft.value.children.length, originalCount)
  state.draft.value.children.push(tree.createEmptySectionNode('草稿新章节', tree.collectSectionIds(state.draft.value)))
  await state.saveDraft()
  assert.equal(creates, 0)
  assert.match(state.saveError.value, /创建章节的权限/)
  await state.loadWiki()
  state.permissions.delete(PERM.operations.target.wiki.delete)
  state.draft.value = tree.removeNode(state.draft.value, 'a')
  await state.saveDraft()
  assert.equal(deletes, 0)
  assert.match(state.saveError.value, /删除章节的权限/)
})

test('目录中途失败立即停止，保留草稿并要求重载已提交的修订', async () => {
  const api = memoryApi(fixture())
  api.deleteSection = async () => { throw new Error('删除请求失败') }
  const state = editorHarness(api)
  await state.loadWiki()
  await state.changeArea('toc')
  state.draft.value = tree.removeNode(editorState.moveWikiEditorSection(state.draft.value, 'b', 'outdent'), 'a')
  await state.saveDraft()
  assert.equal(state.reloadRequired.value, true)
  assert.equal(tree.findWikiNode(state.draft.value, 'b').content, '乙正文 [^a]')
  assert.equal(state.wiki.value.revision, 7)
  assert.match(state.saveError.value, /删除请求失败/)
})
