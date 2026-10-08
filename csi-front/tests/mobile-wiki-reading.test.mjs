import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref } from 'vue'
import { PERM } from '../src/utils/permissions.js'

const listSource = readFileSync(new URL('../src/views/wiki/WikiPageList.vue', import.meta.url), 'utf8')
const fetchCode = listSource.slice(listSource.indexOf('async function fetchList()'), listSource.indexOf('function applySearch()'))
const lifecycleCode = listSource.slice(listSource.indexOf('onDeactivated(() =>'), listSource.indexOf('onBeforeUnmount(() =>'))

/** """执行列表实际请求与缓存钩子，验证筛选和迟到响应。""" */
function listHarness(listPages) {
  return new Function('wikiApi', 'ref', 'PERM', `
    const hooks = {}, isMobile = ref(true), loading = ref(false), listError = ref('');
    const onDeactivated = fn => { hooks.deactivate = fn }, onActivated = fn => { hooks.activate = fn };
    const hasPerm = () => true;
    const filters = ref({q:'测试',status:'published',category:'专题',sortBy:'updated_at',sortOrder:'desc'});
    const pagination = ref({page:2,pageSize:10,total:30});
    const items = ref([{id:'之前的专题'}]);
    const mobileFiltersOpen = ref(true), createDialogVisible = ref(true), editDialogVisible = ref(true);
    let listGeneration = 0, wasDeactivated = false;
    const normalizeWikiListResponse = res => {const data=res.data||res;return {items:data.items,pagination:{page:data.page||1,total:data.total||0}}};
    ${fetchCode}
    ${lifecycleCode}
    return {fetchList,hooks,filters,pagination,items,loading,listError,mobileFiltersOpen,createDialogVisible,editDialogVisible};
  `)({ listPages }, ref, PERM)
}

test('专题列表失败保留旧资料并明确报错，有效空结果才显示空列表', async () => {
  let result = new Error('网络中断')
  const state = listHarness(async () => { if (result instanceof Error) throw result; return result })
  await state.fetchList()
  assert.match(state.listError.value, /网络中断/)
  assert.deepEqual(state.items.value, [{ id: '之前的专题' }])
  result = { code: 0, data: null }
  await state.fetchList()
  assert.match(state.listError.value, /数据无效/)
  result = { items: [], total: 0, page: 1 }
  await state.fetchList()
  assert.equal(state.listError.value, '')
  assert.deepEqual(state.items.value, [])
})

test('返回列表保留关键词分类页码，离开时关闭弹层并拒绝旧请求', async () => {
  const pending = []
  const state = listHarness(params => new Promise(resolve => pending.push({ params, resolve })))
  const oldFetch = state.fetchList()
  state.hooks.deactivate()
  assert.equal(state.mobileFiltersOpen.value, false)
  assert.equal(state.createDialogVisible.value, false)
  assert.equal(state.editDialogVisible.value, false)
  pending[0].resolve({ items: [{ id: '旧响应' }], total: 1 })
  await oldFetch
  assert.deepEqual(state.items.value, [{ id: '之前的专题' }])
  state.hooks.activate()
  assert.deepEqual(pending[1].params, { q: '测试', status: 'published', category: '专题', sortBy: 'updated_at', sortOrder: 'desc', page: 2, pageSize: 10 })
  pending[1].resolve({ items: [{ id: '最新专题' }], total: 30, page: 2 })
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(state.items.value[0].id, '最新专题')
  assert.equal(state.pagination.value.page, 2)
})

const detailSource = readFileSync(new URL('../src/views/details/WikiDetail.vue', import.meta.url), 'utf8')
const citationCode = detailSource.slice(detailSource.indexOf('function onArticleClick(event)'), detailSource.indexOf('let observer = null'))

/** """用最小 DOM 替身验证实际引用面板导航。""" */
function citationHarness() {
  class Element {
    constructor(target) { this.dataset = { wikiTarget: target } }
    closest() { return this }
  }
  const highlighted = [], scrolls = []
  const state = new Function('ref', 'Element', 'highlighted', 'scrolls', `
    const isMobile=ref(true), wiki=ref({footnotes:[{id:'aa',text:'第27条注释'}]});
    const mobilePanel=ref('toc'),mobilePanelOpen=ref(false),activeSectionId=ref('');
    let pendingCitation='';
    const document={getElementById:id=>({scrollIntoView:()=>scrolls.push(id)})};
    const nextTick=async callback=>callback?.();
    const scrollToWikiCitationTarget=id=>highlighted.push(id);
    const handleWikiCitationClick=()=>{};
    ${citationCode}
    return {onArticleClick,scrollToSection,mobilePanel,mobilePanelOpen,activeSectionId};
  `)(ref, Element, highlighted, scrolls)
  return { ...state, Element, highlighted, scrolls }
}

test('正文参考链接展开来源并高亮，多字母脚注定位正确', async () => {
  const state = citationHarness()
  let prevented = false
  state.onArticleClick({ target: new state.Element('ref-1'), preventDefault: () => { prevented = true } })
  assert.equal(prevented, true)
  assert.equal(state.mobilePanelOpen.value, true)
  assert.equal(state.mobilePanel.value, 'sources')
  assert.deepEqual(state.highlighted, ['ref-1'])
  state.onArticleClick({ target: new state.Element('ref-aa'), preventDefault() {} })
  assert.deepEqual(state.highlighted, ['ref-1', 'note-aa'])
})

test('目录正文跳转关闭面板，目录注释跳转保留阅读面板', async () => {
  const state = citationHarness()
  state.mobilePanelOpen.value = true
  await state.scrollToSection('正文甲')
  assert.equal(state.mobilePanelOpen.value, false)
  assert.equal(state.activeSectionId.value, '正文甲')
  assert.deepEqual(state.scrolls, ['正文甲'])
  state.mobilePanelOpen.value = true
  await state.scrollToSection('notes')
  assert.equal(state.mobilePanel.value, 'sources')
  assert.equal(state.mobilePanelOpen.value, true)
  assert.deepEqual(state.highlighted, ['notes'])
})
