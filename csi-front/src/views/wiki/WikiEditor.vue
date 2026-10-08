<template>
  <div class="wiki-editor-page">
    <Header />
    <main class="wiki-editor-main">
      <header class="wiki-editor-heading">
        <div><p class="wiki-editor-eyebrow">专题维护</p><h1>{{ isCreate ? '新建专题' : wiki?.title || '编辑专题' }}</h1></div>
        <el-button :disabled="saving" @click="leaveEditor">{{ isCreate ? '返回列表' : '返回阅读' }}</el-button>
      </header>
      <div v-if="loading" class="wiki-editor-message" role="status">正在加载专题…</div>
      <div v-else-if="loadError" class="wiki-editor-message" role="alert">
        <p>{{ loadError }}</p><el-button @click="loadWiki">重新加载</el-button>
      </div>
      <template v-else-if="draft">
        <el-alert v-if="!canWrite" title="你没有维护此专题的权限，当前内容仅供查看。" type="info" :closable="false" />
        <el-alert v-if="saveError" :title="saveError" type="warning" :closable="false" show-icon />
        <el-button v-if="reloadRequired" class="mt-3" @click="reloadDraft">重新加载最新版本</el-button>
        <p v-if="!isCreate" class="wiki-editor-version">基于修订 {{ wiki.revision }}<span v-if="dirty"> · 有未保存修改</span></p>
        <el-form label-position="top" :disabled="saving || !canWrite || reloadRequired" @submit.prevent @focusin="revealEditorInput">
          <el-form-item v-if="!isCreate" label="编辑内容">
            <el-select :model-value="area" aria-label="编辑内容" @update:model-value="changeArea">
              <el-option v-for="option in areaOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <template v-if="area === 'meta'">
            <el-form-item label="标题" required><el-input v-model="draft.title" maxlength="200" aria-label="专题标题" /></el-form-item>
            <el-form-item v-if="!isCreate" label="状态"><el-select v-model="draft.status" aria-label="专题状态"><el-option label="草稿" value="draft" /><el-option label="构建中" value="building" /><el-option label="已发布" value="published" /></el-select></el-form-item>
            <el-form-item label="分类"><el-select v-model="draft.categories" multiple filterable allow-create default-first-option placeholder="输入后回车添加" aria-label="专题分类" /></el-form-item>
            <el-form-item label="来源说明"><el-input v-model="draft.sourceNote" type="textarea" :rows="3" maxlength="500" aria-label="来源说明" /></el-form-item>
          </template>
          <template v-else-if="area === 'content'">
            <el-form-item label="当前章节"><el-select :model-value="sectionId" filterable aria-label="当前章节" @update:model-value="changeSection"><el-option v-for="section in sections" :key="section.id" :label="section.label" :value="section.id" /></el-select></el-form-item>
            <el-form-item label="正文（支持 Markdown）"><el-input v-model="draft.content" type="textarea" :autosize="{ minRows: 12, maxRows: 28 }" aria-label="章节正文" placeholder="引用参考资料使用 [^1]，注释使用 [^a]" /></el-form-item>
            <details class="wiki-editor-card"><summary>正文预览</summary><WikiMarkdown :content="draft.content || '暂无正文'" /></details>
            <details class="wiki-editor-card"><summary>信息框{{ draft.infobox ? ' · 已配置' : ' · 未配置' }}</summary>
              <el-button v-if="!draft.infobox" @click="draft.infobox = createEmptyInfobox()">添加信息框</el-button>
              <template v-else>
                <el-form-item label="信息框标题" required><el-input v-model="draft.infobox.caption" aria-label="信息框标题" /></el-form-item>
                <el-form-item label="副标题"><el-input v-model="draft.infobox.series" aria-label="信息框副标题" /></el-form-item>
                <el-form-item label="图片地址"><el-input v-model="draft.infobox.image" aria-label="信息框图片地址" /></el-form-item>
                <div v-for="(row, index) in draft.infobox.rows" :key="index" class="wiki-editor-card">
                  <el-form-item :label="`字段 ${index + 1} 名称`"><el-input v-model="row.label" :aria-label="`字段 ${index + 1} 名称`" /></el-form-item>
                  <el-form-item label="字段内容"><el-input v-model="row.value" type="textarea" :rows="2" :aria-label="`字段 ${index + 1} 内容`" /></el-form-item>
                  <el-button type="danger" plain @click="draft.infobox.rows.splice(index, 1)">删除此字段</el-button>
                </div>
                <div class="wiki-editor-actions"><el-button @click="draft.infobox.rows.push({ label: '', value: '' })">添加字段</el-button><el-button type="danger" plain @click="draft.infobox = null">移除信息框</el-button></div>
              </template>
            </details>
          </template>
          <template v-else-if="area === 'toc'">
            <p class="wiki-editor-hint">调整标题、顺序和层级。保存后沿用原章节正文与信息框。</p>
            <el-form-item label="选择章节"><el-select v-model="tocSectionId" aria-label="目录章节"><el-option v-for="section in tocSections" :key="section.id" :label="section.label" :value="section.id" /></el-select></el-form-item>
            <template v-if="selectedTocNode && tocSectionId !== 'main'">
              <el-form-item label="章节标题"><el-input v-model="selectedTocNode.title" aria-label="章节标题" /></el-form-item>
              <div class="wiki-editor-actions"><el-button @click="draft = moveWikiEditorSection(draft, tocSectionId, 'up')">上移</el-button><el-button @click="draft = moveWikiEditorSection(draft, tocSectionId, 'down')">下移</el-button><el-button @click="draft = moveWikiEditorSection(draft, tocSectionId, 'indent')">降一级</el-button><el-button @click="draft = moveWikiEditorSection(draft, tocSectionId, 'outdent')">升一级</el-button></div>
              <el-button type="danger" plain class="mt-3" :disabled="!canDeleteSection" @click="removeSection">删除此章节及子章节</el-button>
            </template>
            <div class="wiki-editor-actions mt-4"><el-button :disabled="!canCreateSection" @click="addSection(false)">添加主章节</el-button><el-button :disabled="!canCreateSection" @click="addSection(true)">添加子章节</el-button></div>
            <ol class="wiki-editor-directory"><li v-for="section in tocSections.slice(1)" :key="section.id">{{ section.label }}</li></ol>
          </template>
          <template v-else>
            <p class="wiki-editor-hint">编号保持不变，调整顺序不会改变正文中的引用。{{ area === 'footnotes' ? '例如 [^a]。' : '例如 [^1]。' }}</p>
            <details v-if="area === 'references' && canSearch" class="wiki-editor-card"><summary>从系统资料检索并引用</summary>
              <div class="wiki-editor-search"><el-input v-model="searchQuery" placeholder="搜索材料标题" aria-label="检索参考资料" @keyup.enter="searchReferences(1)" /><el-button :loading="searchLoading" @click="searchReferences(1)">搜索</el-button></div>
              <p v-if="searchError" role="alert">{{ searchError }}</p>
              <p v-else-if="searchDone && !searchResults.length">未找到匹配材料</p>
              <div v-for="result in searchResults" :key="result.uuid" class="wiki-editor-search-result"><span>{{ String(result.title || '').replace(/<[^>]*>/g, '') }}</span><el-button @click="addSearchReference(result)">引用</el-button></div>
              <el-button v-if="searchPage > 1" @click="searchReferences(searchPage - 1)">上一页</el-button><el-button v-if="searchPage * 8 < searchTotal" @click="searchReferences(searchPage + 1)">下一页</el-button>
            </details>
            <div v-for="(item, index) in draft" :key="item.id" class="wiki-editor-card">
              <h2>{{ area === 'footnotes' ? '注释' : '参考资料' }} {{ item.id }}</h2>
              <el-form-item label="内容"><el-input v-model="item.text" type="textarea" :rows="3" :aria-label="`${area === 'footnotes' ? '注释' : '参考资料'} ${item.id} 内容`" /></el-form-item>
              <template v-if="area === 'references'">
                <el-form-item label="来源链接"><el-input v-model="item.url" :aria-label="`参考资料 ${item.id} 链接`" /></el-form-item>
                <p v-if="item.entityUuid" class="wiki-editor-hint">已关联 {{ item.entityType }} 材料</p>
                <el-button v-if="item.entityUuid || item.url" plain @click="item.url = ''; item.entityType = null; item.entityUuid = null">清除来源关联</el-button>
              </template>
              <div class="wiki-editor-actions mt-3"><el-button :disabled="index === 0" @click="moveCitation(index, -1)">上移</el-button><el-button :disabled="index === draft.length - 1" @click="moveCitation(index, 1)">下移</el-button><el-button type="danger" plain @click="draft.splice(index, 1)">删除</el-button></div>
            </div>
            <el-button @click="addCitation">添加{{ area === 'footnotes' ? '注释' : '参考资料' }}</el-button>
          </template>
          <el-form-item v-if="!isCreate && area !== 'toc'" label="变更说明" class="mt-5"><el-input v-model="changeSummary" type="textarea" :rows="2" maxlength="200" aria-label="变更说明" placeholder="可选，记录在版本历史中" /></el-form-item>
        </el-form>
        <div class="wiki-editor-save" :class="{ 'wiki-editor-save--keyboard': keyboardOpen }">
          <span>{{ saving ? '正在保存…' : dirty ? '修改尚未保存' : '已与当前修订同步' }}</span>
          <el-button type="primary" :disabled="!canWrite || reloadRequired || (!isCreate && !dirty)" :loading="saving" @click="saveDraft">{{ isCreate ? '创建专题' : '保存修改' }}</el-button>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import WikiMarkdown from '@/components/wiki/WikiMarkdown.vue'
import { wikiApi } from '@/api/wiki.js'
import { searchApi } from '@/api/search.js'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { isWikiRevisionConflict } from '@/utils/wikiPersist.js'
import { collectSectionIds, createEmptyInfobox, createEmptySectionNode, findWikiNode, removeNode } from '@/utils/wikiTree.js'
import { nextFootnoteId, nextReferenceId } from '@/utils/wikiCitationIds.js'
import { referenceFromSearchResult } from '@/utils/wikiReferenceFromSearch.js'
import { buildWikiEditorPatch, createWikiEditorDraft, listWikiEditorSections, moveWikiEditorSection, persistWikiEditorToc } from '@/components/wiki/wikiEditorState.js'

defineOptions({ name: 'WikiEditor' })
const route = useRoute()
const router = useRouter()
const { keyboardOpen, viewportHeight, viewportTop } = useMobileViewport()
const isCreate = computed(() => route.name === 'wiki-create')
const canWrite = computed(() => hasPerm(PERM.operations.target.wiki[isCreate.value ? 'create' : 'update']) && (isCreate.value || hasPerm(PERM.operations.target.wiki.read)))
const canSearch = computed(() => hasPerm(PERM.operations.search.entity.execute))
const canCreateSection = computed(() => hasPerm(PERM.operations.target.wiki.create))
const canDeleteSection = computed(() => hasPerm(PERM.operations.target.wiki.delete))
const wiki = ref(null)
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const reloadRequired = ref(false)
const area = ref('meta')
const sectionId = ref('main')
const tocSectionId = ref('main')
const draft = ref(null)
const draftBaseline = ref('')
const changeSummary = ref('')
const dirty = computed(() => Boolean(draft.value) && (JSON.stringify(draft.value) !== draftBaseline.value || Boolean(changeSummary.value.trim())))
const sections = computed(() => listWikiEditorSections(wiki.value?.contentTree))
const tocSections = computed(() => area.value === 'toc' ? listWikiEditorSections(draft.value) : [])
const selectedTocNode = computed(() => area.value === 'toc' ? findWikiNode(draft.value, tocSectionId.value) : null)
const areaOptions = [{ value: 'meta', label: '基础信息' }, { value: 'content', label: '正文与信息框' }, { value: 'toc', label: '目录结构' }, { value: 'footnotes', label: '注释' }, { value: 'references', label: '参考资料' }]
const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchError = ref('')
const searchDone = ref(false)
const searchPage = ref(1)
const searchTotal = ref(0)
let loadGeneration = 0
let searchGeneration = 0

/** """键盘或输入焦点变化后，将当前字段放入实际可视区。""" */
async function revealEditorInput() {
  if (!keyboardOpen.value) return
  await nextTick()
  const field = document.activeElement
  if (!field?.matches('input, textarea')) return
  const bounds = field.getBoundingClientRect()
  const visibleTop = viewportTop.value + 64
  const visibleBottom = viewportTop.value + viewportHeight.value - 16
  if (bounds.height > visibleBottom - visibleTop) return
  if (bounds.bottom > visibleBottom) window.scrollBy({ top: bounds.bottom - visibleBottom, behavior: 'instant' })
  else if (bounds.top < visibleTop) window.scrollBy({ top: bounds.top - visibleTop, behavior: 'instant' })
}
watch([keyboardOpen, viewportHeight], revealEditorInput)

/** """从当前修订重建区域草稿。""" */
function resetDraft() {
  draft.value = createWikiEditorDraft(wiki.value, area.value, sectionId.value)
  draftBaseline.value = JSON.stringify(draft.value)
  changeSummary.value = ''
  saveError.value = ''
}

/** """提示未保存修改，返回是否允许放弃。""" */
async function allowDiscard() {
  if (saving.value) return false
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃这些修改？', '未保存修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' })
    return true
  } catch { return false }
}

/** """确认草稿后切换编辑区域。""" */
async function changeArea(value) {
  if (!await allowDiscard()) return
  area.value = value
  resetDraft()
}

/** """确认草稿后切换正文章节。""" */
async function changeSection(value) {
  if (!await allowDiscard()) return
  sectionId.value = value
  resetDraft()
}

/** """读取指定专题并丢弃已经离开的请求响应。""" */
async function loadWiki() {
  const generation = ++loadGeneration
  loading.value = true
  loadError.value = ''
  reloadRequired.value = false
  try {
    if (!isCreate.value && !hasPerm(PERM.operations.target.wiki.read)) throw new Error('没有读取专题的权限')
    const detail = isCreate.value ? { title: '', sourceNote: '', status: 'draft', categories: [] } : await wikiApi.getPageById(String(route.params.id))
    if (generation !== loadGeneration) return
    if (!isCreate.value && (!detail.id || detail.id !== String(route.params.id))) throw new Error('专题数据无效，请重试')
    wiki.value = detail
    if (area.value === 'content' && !findWikiNode(detail.contentTree, sectionId.value)) sectionId.value = 'main'
    resetDraft()
  } catch (error) {
    if (generation === loadGeneration) loadError.value = error?.message || '专题加载失败，请重试'
  } finally { if (generation === loadGeneration) loading.value = false }
}

/** """显式放弃冲突草稿，再读取最新版本。""" */
async function reloadDraft() {
  if (await allowDiscard()) await loadWiki()
}

/**
 * 使用当前修订保存单一区域；冲突和目录部分失败后保留草稿，要求显式重新加载。
 * @returns {Promise<void>}
 */
async function saveDraft() {
  if (saving.value || !canWrite.value || reloadRequired.value || !draft.value) return
  saving.value = true
  saveError.value = ''
  const generation = loadGeneration
  try {
    let detail
    if (isCreate.value) {
      const body = buildWikiEditorPatch(wiki.value, 'meta', draft.value)
      detail = await wikiApi.createPage({ title: body.title, sourceNote: body.sourceNote, categories: body.categories })
    } else if (area.value === 'toc') {
      const before = collectSectionIds(wiki.value.contentTree)
      const after = collectSectionIds(draft.value)
      if ([...after].some(id => !before.has(id)) && !canCreateSection.value) throw new Error('没有创建章节的权限')
      if ([...before].some(id => !after.has(id)) && !canDeleteSection.value) throw new Error('没有删除章节的权限')
      detail = await persistWikiEditorToc(wikiApi, wiki.value, draft.value)
    } else {
      const body = buildWikiEditorPatch(wiki.value, area.value, draft.value, changeSummary.value)
      if (area.value === 'meta') detail = await wikiApi.updateMeta(wiki.value.id, body)
      else if (area.value === 'content') detail = await (sectionId.value === 'main' ? wikiApi.updateMain(wiki.value.id, body) : wikiApi.updateSection(wiki.value.id, sectionId.value, body))
      else if (area.value === 'footnotes') detail = await wikiApi.putFootnotes(wiki.value.id, body)
      else detail = await wikiApi.putReferences(wiki.value.id, body)
    }
    if (generation !== loadGeneration) return
    if (!detail?.id) throw new Error('保存结果无法确认，请重新加载专题核对')
    wiki.value = detail
    tocSectionId.value = 'main'
    resetDraft()
    ElMessage.success(isCreate.value ? '专题已创建' : '修改已保存')
    const missing = [...(detail.citationHealth?.missingRefs || []), ...(detail.citationHealth?.missingFootnotes || [])]
    if (missing.length) ElMessage.warning(`正文仍有未定义的引用：${missing.map(id => `[^${id}]`).join('、')}`)
    if (isCreate.value) {
      saving.value = false
      await router.replace({ name: 'wiki-editor', params: { id: detail.id } })
    }
  } catch (error) {
    if (generation !== loadGeneration) return
    reloadRequired.value = isWikiRevisionConflict(error) || area.value === 'toc'
    saveError.value = isWikiRevisionConflict(error) ? '专题已被他人修改。当前草稿已保留，请核对后重新加载最新版本。' : error?.message || '保存失败，修改已保留，请重试'
  } finally { if (generation === loadGeneration) saving.value = false }
}

/** """在选中节点或根节点添加本地空章节。""" */
function addSection(asChild) {
  if (!canWrite.value || !canCreateSection.value || saving.value) return
  const parent = asChild ? selectedTocNode.value : draft.value
  if (!parent) return
  const node = createEmptySectionNode('新章节', collectSectionIds(draft.value))
  parent.children ||= []
  parent.children.push(node)
  tocSectionId.value = node.section
}

/** """确认移除目录子树，仅在保存时写入服务器。""" */
async function removeSection() {
  if (!canWrite.value || !canDeleteSection.value || saving.value) return
  try { await ElMessageBox.confirm('保存后将删除此章节、子章节及其正文，是否从草稿中移除？', '删除章节', { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  if (!canWrite.value || !canDeleteSection.value || saving.value) return
  draft.value = removeNode(draft.value, tocSectionId.value)
  tocSectionId.value = 'main'
}

/** """新增未占用编号，避免影响正文中的既有引用。""" */
function addCitation() {
  const ids = draft.value.map(item => item.id)
  draft.value.push(area.value === 'footnotes' ? { id: nextFootnoteId(ids), text: '' } : { id: nextReferenceId(ids), text: '', url: '', entityType: null, entityUuid: null })
}

/** """移动引用显示顺序并保留编号及全部字段。""" */
function moveCitation(index, delta) {
  const target = index + delta
  if (target < 0 || target >= draft.value.length) return
  const [item] = draft.value.splice(index, 1)
  draft.value.splice(target, 0, item)
}

/** """从已有检索接口读取材料，失败状态与无结果分开。""" */
async function searchReferences(page) {
  if (!canSearch.value || !searchQuery.value.trim()) return
  const generation = ++searchGeneration
  searchLoading.value = true
  searchError.value = ''
  try {
    const response = await searchApi.searchEntity({ keywords: searchQuery.value.trim(), search_mode: 'keyword', sort_by: 'time', sort_order: 'desc', page, page_size: 8 })
    if (generation !== searchGeneration) return
    const data = response?.data || response
    if (!Array.isArray(data?.items)) throw new Error('检索结果无效，请重试')
    searchResults.value = data.items
    searchTotal.value = Number(data.total || 0)
    searchPage.value = page
    searchDone.value = true
  } catch (error) { if (generation === searchGeneration) searchError.value = error?.message || '检索失败，请重试' }
  finally { if (generation === searchGeneration) searchLoading.value = false }
}

/** """保留检索材料的实体关系并添加到引用草稿。""" */
function addSearchReference(result) {
  draft.value.push(referenceFromSearchResult(result, draft.value.map(item => item.id)))
  ElMessage.success('已添加到引用草稿，保存后生效')
}

/** """通过路由守卫确认修改后返回阅读或列表。""" */
function leaveEditor() {
  router.push(isCreate.value ? { name: 'wiki-page-list' } : { name: 'wiki-detail', params: { id: route.params.id } })
}

/** """在浏览器刷新或关闭时保护尚未保存的输入。""" */
function protectDraft(event) {
  if (!dirty.value && !saving.value) return
  event.preventDefault()
  event.returnValue = ''
}
onBeforeRouteLeave(allowDiscard)
onBeforeRouteUpdate(allowDiscard)
window.addEventListener('beforeunload', protectDraft)
watch(() => [route.name, route.params.id], () => { area.value = 'meta'; sectionId.value = 'main'; loadWiki() }, { immediate: true })
onBeforeUnmount(() => { loadGeneration += 1; searchGeneration += 1; window.removeEventListener('beforeunload', protectDraft) })
</script>

<style scoped>
.wiki-editor-page{min-height:100vh;background:#f8fafc;color:#0f172a}.wiki-editor-main{max-width:780px;margin:0 auto;padding:28px 24px 110px}.wiki-editor-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}.wiki-editor-heading h1{font-size:24px;font-weight:700;overflow-wrap:anywhere;margin:0}.wiki-editor-eyebrow{font-size:12px;color:#64748b;margin:0 0 6px}.wiki-editor-version,.wiki-editor-hint{font-size:13px;line-height:1.6;color:#64748b;margin:14px 0}.wiki-editor-message{text-align:center;padding:60px 12px}.wiki-editor-main :deep(.el-select){width:100%}.wiki-editor-card{border:1px solid #e2e8f0;border-radius:12px;background:white;padding:16px;margin:16px 0;min-width:0}.wiki-editor-card summary{font-weight:600;cursor:pointer;min-height:36px}.wiki-editor-card h2{font-size:16px;font-weight:600;margin:0 0 16px}.wiki-editor-actions{display:flex;gap:8px;flex-wrap:wrap}.wiki-editor-actions :deep(.el-button){margin:0;min-height:40px}.wiki-editor-directory{font-size:14px;line-height:2;padding-left:22px;overflow-wrap:anywhere}.wiki-editor-save{position:sticky;bottom:0;display:flex;align-items:center;justify-content:space-between;gap:12px;background:white;border-top:1px solid #e2e8f0;padding:16px;margin-top:24px;z-index:20}.wiki-editor-save span{font-size:12px;color:#64748b}.wiki-editor-search{display:flex;gap:8px}.wiki-editor-search-result{display:flex;gap:12px;align-items:center;justify-content:space-between;border-bottom:1px solid #e2e8f0;padding:12px 0}.wiki-editor-search-result span{overflow-wrap:anywhere;min-width:0;font-size:14px}
@media(max-width:767px){.wiki-editor-main{padding:20px 16px 100px}.wiki-editor-heading{align-items:flex-start}.wiki-editor-heading h1{font-size:21px}.wiki-editor-heading :deep(.el-button){flex-shrink:0;min-height:44px}.wiki-editor-main :deep(.el-input__inner),.wiki-editor-main :deep(.el-textarea__inner){font-size:16px}.wiki-editor-main :deep(.el-input__wrapper),.wiki-editor-main :deep(.el-select__wrapper){min-height:44px}.wiki-editor-save{position:fixed;left:0;right:0;bottom:var(--mobile-nav-height,64px);margin:0;padding:12px 16px;min-height:68px}.wiki-editor-save :deep(.el-button){min-height:44px}.wiki-editor-save--keyboard{position:static;margin-top:24px}.wiki-editor-card{padding:12px}.wiki-editor-main :deep(.el-select__selected-item){overflow-wrap:anywhere}}
</style>

<style scoped>
@media (max-width: 767px) {
  .wiki-editor-main { padding-bottom: calc(100px + var(--mobile-keyboard-offset, 0px)); }
  .mobile-keyboard-open .wiki-editor-main :deep(.el-textarea__inner) {
    min-height: 82px !important;
    max-height: max(100px, calc(var(--mobile-viewport-height, 100dvh) - 180px));
    overflow-y: auto;
  }
}
</style>
