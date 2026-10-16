<template>
  <div class="min-h-screen bg-gray-50 flex flex-col" :class="{ 'wiki-mobile-detail': isMobile }">
    <Header />

    <div v-if="loading" class="flex items-center justify-center h-96">
      <div class="text-center">
        <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
        <p class="text-gray-600">加载中...</p>
      </div>
    </div>

    <div v-else-if="error" class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div class="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
        <Icon icon="mdi:alert-circle" class="text-red-500 text-5xl mx-auto mb-4" />
        <h2 class="text-xl font-bold text-gray-900 mb-2">加载失败</h2>
        <p class="text-gray-600 mb-4">{{ error }}</p>
        <el-button type="primary" @click="router.back()">返回</el-button>
        <el-button @click="loadWiki">重试</el-button>
      </div>
    </div>

    <template v-else-if="wiki">
      <DetailPageHeader
        v-if="!isMobile"
        :title="wiki.title"
        :subtitle="wikiSubtitle"
        container-max-width="max-w-screen-2xl"
      >
        <template #tags>
          <el-tag v-if="wiki.status" :type="wikiStatusTagType" size="small" class="cursor-default">
            {{ wikiStatusLabel }}
          </el-tag>
          <el-tag
            v-for="cat in (wiki.categories || []).slice(0, 4)"
            :key="cat"
            type="info"
            size="small"
            class="cursor-default"
          >
            {{ cat }}
          </el-tag>
        </template>
        <template #extra>
          <AddToEvidenceButton :entity="{ entity_type: 'wiki', uuid: wiki.id, title: wiki.title }" />
          <el-button
            v-if="wiki.revision"
            type="primary"
            link
            class="text-sm! h-auto! p-0!"
            @click="revisionHistoryVisible = true"
          >
            修订 {{ wiki.revision }}
          </el-button>
          <span v-if="wiki.lastModified" class="text-sm text-gray-500">
            最后修订 {{ formattedLastModified }}
          </span>
        </template>
      </DetailPageHeader>

      <header v-if="isMobile" class="wiki-mobile-heading">
        <div class="wiki-mobile-heading-tags"><el-tag v-if="wiki.status" :type="wikiStatusTagType" size="small">{{ wikiStatusLabel }}</el-tag><span>专题资料 · 修订 {{ wiki.revision }}</span></div>
        <h1>{{ wiki.title }}</h1><p v-if="wiki.sourceNote">{{ wiki.sourceNote }}</p>
        <div class="wiki-mobile-heading-meta"><span v-if="wiki.lastModified">{{ formattedLastModified }}</span><el-button link type="primary" @click="revisionHistoryVisible = true">版本记录</el-button></div>
      </header>

      <section class="py-6 sm:py-8 wiki-reading-section">
        <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div v-if="!isMobile" class="lg:hidden mb-6">
            <WikiSidebarCard>
              <template #title>
                页面<span class="text-blue-500">目录</span>
              </template>
              <template v-if="editMode" #actions>
                <el-button
                  type="primary"
                  link
                  class="p-1!"
                  title="编辑目录"
                  @click="tocEditorVisible = true"
                >
                  <Icon icon="mdi:pencil-outline" class="text-lg" />
                </el-button>
              </template>
              <WikiToc
                :items="numberedToc"
                :active-id="activeSectionId"
                @navigate="scrollToSection"
              />
            </WikiSidebarCard>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_260px] gap-6 lg:gap-8">
            <article
              class="min-w-0"
              @click="onArticleClick"
            >
              <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 sm:p-8 wiki-reading-body">
                <WikiPageMeta
                  v-if="!isMobile"
                  v-model:edit-mode="editMode"
                  :source-note="wiki.sourceNote"
                />

                <div v-if="wiki.contentTree" class="space-y-8">
                  <WikiSectionBlock :node="wiki.contentTree" />

                  <WikiFootnotes v-if="!isMobile" :footnotes="wiki.footnotes">
                    <template v-if="editMode" #actions>
                      <div class="flex items-center gap-0.5 shrink-0">
                        <button
                          type="button"
                          class="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="编辑注释"
                          @click="footnotesEditorVisible = true"
                        >
                          <Icon icon="mdi:pencil-outline" class="text-lg" />
                        </button>
                      </div>
                    </template>
                  </WikiFootnotes>

                  <WikiReferences v-if="!isMobile" :references="wiki.references">
                    <template v-if="editMode" #actions>
                      <div class="flex items-center gap-0.5 shrink-0">
                        <button
                          type="button"
                          class="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="编辑参考资料"
                          @click="referencesEditorVisible = true"
                        >
                          <Icon icon="mdi:pencil-outline" class="text-lg" />
                        </button>
                      </div>
                    </template>
                  </WikiReferences>

                  <section class="rounded-xl border border-gray-200 bg-gray-50/60 p-4 sm:p-5">
                    <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">标签</p>
                    <div class="flex flex-wrap gap-2">
                      <el-tag
                        v-for="cat in wiki.categories"
                        :key="cat"
                        type="info"
                        size="small"
                        class="cursor-default"
                      >
                        {{ cat }}
                      </el-tag>
                    </div>
                  </section>
                </div>
              </div>
            </article>

            <aside class="hidden lg:block min-w-0 space-y-6">
              <div class="sticky top-24 space-y-6 max-h-[calc(100vh-7rem)] overflow-y-auto pr-0.5">
                <WikiSidebarCard>
                  <template #title>
                    页面<span class="text-blue-500">目录</span>
                  </template>
                  <template v-if="editMode" #actions>
                    <el-button
                      type="primary"
                      link
                      class="p-1!"
                      title="编辑目录"
                      @click="tocEditorVisible = true"
                    >
                      <Icon icon="mdi:pencil-outline" class="text-lg" />
                    </el-button>
                  </template>
                  <WikiToc
                    :items="numberedToc"
                    :active-id="activeSectionId"
                    @navigate="scrollToSection"
                  />
                </WikiSidebarCard>
              </div>
            </aside>
          </div>
        </div>
      </section>

      <MobileActionBar v-if="isMobile" aria-label="专题阅读操作">
        <el-button @click="mobilePanel = 'toc'; mobilePanelOpen = true">目录</el-button>
        <el-button @click="mobilePanel = 'sources'; mobilePanelOpen = true">引用 {{ (wiki.references?.length || 0) + (wiki.footnotes?.length || 0) }}</el-button>
        <AddToEvidenceButton :entity="{ entity_type: 'wiki', uuid: wiki.id, title: wiki.title }" />
        <el-button type="primary" :disabled="!canMobileEdit" @click="openMobileEditor">编辑</el-button>
      </MobileActionBar>
      <MobileSheet v-if="isMobile" v-model="mobilePanelOpen" :title="mobilePanel === 'toc' ? '专题目录' : '引用与注释'" destroy-on-close @opened="revealCitation">
        <WikiToc v-if="mobilePanel === 'toc'" :items="numberedToc" :active-id="activeSectionId" @navigate="scrollToSection" />
        <div v-else class="wiki-mobile-sources"><WikiReferences :references="wiki.references" /><WikiFootnotes :footnotes="wiki.footnotes" /></div>
      </MobileSheet>

      <WikiTocEditorDialog
        v-model="tocEditorVisible"
        :children="wiki.contentTree?.children ?? []"
        @apply="applyTocTree"
      />

      <WikiInfoboxEditorDialog
        v-model="infoboxEditorVisible"
        :infobox="infoboxEditorDraft"
        @save="saveInfobox"
      />

      <WikiFootnotesEditorDialog
        v-model="footnotesEditorVisible"
        :items="wiki.footnotes"
        @apply="applyFootnotes"
      />

      <WikiReferencesEditorDialog
        v-model="referencesEditorVisible"
        :items="wiki.references"
        @apply="applyReferences"
      />

      <WikiRevisionHistoryDialog
        v-model="revisionHistoryVisible"
        :wiki-id="wiki.id"
        :current-revision="wiki.revision"
        @preview="openRevisionPreview"
        @compare="openRevisionDiff"
      />

      <WikiRevisionDiffDialog
        v-model="revisionDiffVisible"
        :wiki-id="wiki.id"
        :from-revision="diffFrom"
        :to-revision="diffTo"
        @preview="openRevisionPreview"
      />

      <WikiRevisionPreviewDialog
        v-model="revisionPreviewVisible"
        :wiki-id="wiki.id"
        :revision="revisionPreviewTarget"
        :current-revision="wiki.revision"
        :allow-restore="!isMobile || canMobileRestore"
        @restore="handleRestoreRevision"
      />
    </template>
  </div>
</template>

<script setup>
import AddToEvidenceButton from '@/components/evidence/AddToEvidenceButton.vue'
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import WikiPageMeta from '@/components/wiki/WikiPageMeta.vue'
import WikiFootnotes from '@/components/wiki/WikiFootnotes.vue'
import WikiFootnotesEditorDialog from '@/components/wiki/WikiFootnotesEditorDialog.vue'
import WikiReferences from '@/components/wiki/WikiReferences.vue'
import WikiReferencesEditorDialog from '@/components/wiki/WikiReferencesEditorDialog.vue'
import WikiSectionBlock from '@/components/wiki/WikiSectionBlock.vue'
import WikiSidebarCard from '@/components/wiki/WikiSidebarCard.vue'
import WikiToc from '@/components/wiki/WikiToc.vue'
import WikiTocEditorDialog from '@/components/wiki/WikiTocEditorDialog.vue'
import WikiInfoboxEditorDialog from '@/components/wiki/WikiInfoboxEditorDialog.vue'
import WikiRevisionHistoryDialog from '@/components/wiki/WikiRevisionHistoryDialog.vue'
import WikiRevisionDiffDialog from '@/components/wiki/WikiRevisionDiffDialog.vue'
import WikiRevisionPreviewDialog from '@/components/wiki/WikiRevisionPreviewDialog.vue'
import { wikiApi } from '@/api/wiki.js'
import { normalizeWikiInfobox } from '@/utils/wikiNormalize.js'
import {
  buildTocFromContentTree,
  flattenWikiSectionNodes,
  handleWikiCitationClick,
} from '@/utils/wikiContent.js'
import {
  createWikiPersistHandlers,
  isWikiRevisionConflict,
  persistWikiFootnotes,
  persistWikiReferences,
  persistWikiRestoreRevision,
  persistWikiSectionPatch,
  syncWikiTocStructure,
} from '@/utils/wikiPersist.js'
import {
  cloneWikiInfobox,
  createEmptyInfobox,
  findWikiNode,
  mergePreservedSectionContent,
} from '@/utils/wikiTree.js'

import { WIKI_EDITOR_KEY } from '@/components/wiki/wikiEditorKey.js'
import { formatDateTime } from '@/utils/action'
import MobileActionBar from '@/components/mobile/MobileActionBar.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { scrollToWikiCitationTarget } from '@/utils/wikiContent.js'
import { rememberRecentVisit } from '@/stores/recentVisits'

defineOptions({ name: 'WikiDetail' })

/** @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail */

const route = useRoute()
const router = useRouter()
const { isMobile } = useMobileViewport()
const canMobileEdit = computed(() => hasPerm(PERM.operations.target.wiki.read) && hasPerm(PERM.operations.target.wiki.update))
const canMobileRestore = computed(() => hasPerm(PERM.operations.target.wiki.read) && hasPerm(PERM.operations.target.wiki.execute))
const mobilePanelOpen = ref(false)
const mobilePanel = ref('toc')
let pendingCitation = ''
let loadGeneration = 0

/** @type {import('vue').Ref<WikiEntry|null>} */
const wiki = ref(null)
const loading = ref(true)
const error = ref('')
const activeSectionId = ref('')

const editMode = ref(false)
const editingContentId = ref(null)
const contentDraft = ref('')
const tocEditorVisible = ref(false)
const footnotesEditorVisible = ref(false)
const referencesEditorVisible = ref(false)
const infoboxEditorVisible = ref(false)
const infoboxEditorSectionId = ref(null)
/** @type {import('vue').Ref<import('@/types/wiki.js').WikiInfobox|null>} */
const infoboxEditorDraft = ref(null)
const revisionHistoryVisible = ref(false)
const revisionDiffVisible = ref(false)
const diffFrom = ref(0)
const diffTo = ref(0)
const revisionPreviewVisible = ref(false)
const revisionPreviewTarget = ref(0)

const wikiRouteId = computed(() => String(route.params.id || ''))

const { runWrite } = createWikiPersistHandlers(
  wiki,
  () => wikiApi.getPageById(wikiRouteId.value),
  () => refreshSectionObserver()
)

/** @type {Record<string, string>} */
const WIKI_STATUS_LABELS = {
  draft: '草稿',
  building: '构建中',
  published: '已发布',
}

const wikiStatusLabel = computed(() => {
  const status = wiki.value?.status
  return (status && WIKI_STATUS_LABELS[status]) || status || ''
})

const wikiStatusTagType = computed(() => {
  const status = wiki.value?.status
  if (status === 'published') return 'success'
  if (status === 'building') return 'warning'
  return 'info'
})

const formattedLastModified = computed(() => {
  const raw = wiki.value?.lastModified
  if (!raw) return ''
  return formatDateTime(raw, { includeSecond: true }) || raw
})

const wikiSubtitle = computed(() => {
  const note = wiki.value?.sourceNote?.trim()
  if (note) return note
  return wiki.value?.id || ''
})

const numberedToc = computed(() =>
  wiki.value?.contentTree ? buildTocFromContentTree(wiki.value.contentTree) : []
)

const sectionIds = computed(() => {
  if (!wiki.value?.contentTree) return ['notes', 'references']
  const ids = flattenWikiSectionNodes(wiki.value.contentTree)
    .map((s) => s.id)
    .filter((id) => id !== 'main')
  return [...ids, 'notes', 'references']
})

function clearContentEdit() {
  editingContentId.value = null
  contentDraft.value = ''
}

function clearInfoboxEditor() {
  infoboxEditorVisible.value = false
  infoboxEditorSectionId.value = null
  infoboxEditorDraft.value = null
}

async function refreshSectionObserver() {
  if (!wiki.value?.contentTree) return
  await nextTick()
  setupSectionObserver()
}

function startEditContent(sectionId) {
  if (!wiki.value?.contentTree || !editMode.value) return
  clearInfoboxEditor()
  const node = findWikiNode(wiki.value.contentTree, sectionId)
  if (!node) return
  editingContentId.value = sectionId
  contentDraft.value = node.content || ''
}

async function saveContent() {
  if (!wiki.value?.contentTree || !editingContentId.value) return
  const sectionId = editingContentId.value
  const content = contentDraft.value
  try {
    await runWrite(() => persistWikiSectionPatch(wiki.value, sectionId, { content }))
    clearContentEdit()
    ElMessage.success('章节内容已保存')
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重新编辑后保存')
    }
  }
}

function cancelContent() {
  clearContentEdit()
}

function openInfoboxEditor(sectionId) {
  if (!wiki.value?.contentTree || !editMode.value) return
  clearContentEdit()
  const node = findWikiNode(wiki.value.contentTree, sectionId)
  infoboxEditorSectionId.value = sectionId
  infoboxEditorDraft.value = node?.infobox
    ? cloneWikiInfobox(node.infobox)
    : createEmptyInfobox()
  infoboxEditorVisible.value = true
}

async function addInfobox(sectionId) {
  if (!wiki.value?.contentTree || !editMode.value) return
  clearContentEdit()
  const empty = normalizeWikiInfobox(createEmptyInfobox())
  if (!empty) return
  try {
    await runWrite(() => persistWikiSectionPatch(wiki.value, sectionId, { infobox: empty }))
    openInfoboxEditor(sectionId)
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重试')
    }
  }
}

async function removeInfobox(sectionId) {
  if (!wiki.value?.contentTree) return
  try {
    await ElMessageBox.confirm('确定删除该章节的信息框？', '删除信息框', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await runWrite(() => persistWikiSectionPatch(wiki.value, sectionId, { infobox: null }))
    ElMessage.success('信息框已删除')
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重试')
    }
  }
}

async function saveInfobox(payload) {
  if (!wiki.value?.contentTree || !infoboxEditorSectionId.value) return
  const normalized = normalizeWikiInfobox(payload)
  if (!normalized) {
    ElMessage.warning('请填写信息框标题')
    return
  }
  const sectionId = infoboxEditorSectionId.value
  try {
    await runWrite(() => persistWikiSectionPatch(wiki.value, sectionId, { infobox: normalized }))
    clearInfoboxEditor()
    ElMessage.success('信息框已保存')
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重新编辑后保存')
    }
  }
}

async function applyTocTree(children) {
  if (!wiki.value?.contentTree) return
  const prevChildren = wiki.value.contentTree.children || []
  const merged = mergePreservedSectionContent(children, prevChildren)
  try {
    await runWrite(() => syncWikiTocStructure(wiki.value, prevChildren, merged))
    ElMessage.success('目录结构已更新')
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重新编辑目录')
    }
  }
}

/**
 * @param {import('@/types/wiki.js').WikiCitationHealth} health
 */
async function warnCitationIssues(health) {
  const missing = [
    ...(health.missingRefs || []).map((id) => `[^${id}]`),
    ...(health.missingFootnotes || []).map((id) => `[^${id}]`),
  ]
  if (missing.length > 0) {
    ElMessage.warning(`正文中仍有未定义的引用：${missing.join('、')}`)
  }
}

/** @typedef {import('@/types/wiki.js').WikiFootnote} WikiFootnote */

/**
 * @param {WikiFootnote[]} items
 */
async function applyFootnotes(items) {
  if (!wiki.value) return
  try {
    await runWrite(() => persistWikiFootnotes(wiki.value, items))
    ElMessage.success('注释已保存')
    try {
      const health = await wikiApi.validateCitations(wiki.value.id)
      await warnCitationIssues(health)
    } catch {
      /* ignore validate failure */
    }
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重新编辑注释')
    }
  }
}

/** @typedef {import('@/types/wiki.js').WikiReference} WikiReference */

/**
 * @param {WikiReference[]} items
 */
async function applyReferences(items) {
  if (!wiki.value) return
  try {
    await runWrite(() => persistWikiReferences(wiki.value, items))
    ElMessage.success('参考资料已保存')
    try {
      const health = await wikiApi.validateCitations(wiki.value.id)
      await warnCitationIssues(health)
    } catch {
      /* ignore validate failure */
    }
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被修改，请重新编辑参考资料')
    }
  }
}

/**
 * @param {number} revision
 */
function openRevisionPreview(revision) {
  revisionPreviewTarget.value = revision
  revisionPreviewVisible.value = true
}

/**
 * @param {{ from: number, to: number }} payload
 */
function openRevisionDiff(payload) {
  diffFrom.value = payload.from
  diffTo.value = payload.to
  revisionDiffVisible.value = true
}

/**
 * @param {number} targetRevision
 */
async function handleRestoreRevision(targetRevision) {
  if (isMobile.value && !canMobileRestore.value) return
  if (!wiki.value) return
  try {
    await runWrite(() => persistWikiRestoreRevision(wiki.value, targetRevision))
    revisionPreviewVisible.value = false
    revisionHistoryVisible.value = false
    ElMessage.success(`已恢复到修订 ${targetRevision}，当前修订号为 ${wiki.value?.revision}`)
    await refreshSectionObserver()
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被他人修改，请关闭预览后重试')
    }
  }
}

provide(WIKI_EDITOR_KEY, {
  editMode,
  editingContentId,
  contentDraft,
  startEditContent,
  saveContent,
  cancelContent,
  openInfoboxEditor,
  addInfobox,
  removeInfobox,
})

watch(editMode, (enabled) => {
  if (!enabled) {
    clearContentEdit()
    clearInfoboxEditor()
    tocEditorVisible.value = false
    footnotesEditorVisible.value = false
    referencesEditorVisible.value = false
    revisionHistoryVisible.value = false
    revisionDiffVisible.value = false
    revisionPreviewVisible.value = false
  }
})

/** """手机先展开引用面板，再定位正文引用对应的来源。""" */
function onArticleClick(event) {
  const link = event.target instanceof Element ? event.target.closest('.wiki-cite-link') : null
  if (isMobile.value && link?.dataset.wikiTarget) {
    event.preventDefault()
    const rawTarget = link.dataset.wikiTarget
    const citationId = rawTarget.replace(/^(note|ref)-/, '')
    pendingCitation = wiki.value.footnotes?.some(note => note.id === citationId) ? `note-${citationId}` : rawTarget
    mobilePanel.value = 'sources'
    mobilePanelOpen.value = true
    nextTick(revealCitation)
    return
  }
  handleWikiCitationClick(event)
}

/** """面板完成进入后高亮目标，避免抽屉延迟挂载导致定位丢失。""" */
function revealCitation() {
  if (pendingCitation && document.getElementById(pendingCitation)) {
    scrollToWikiCitationTarget(pendingCitation)
    pendingCitation = ''
  }
}

/** """关闭目录后定位正文，参考资料与注释在面板中读取。""" */
async function scrollToSection(id) {
  if (isMobile.value) {
    if (id === 'notes' || id === 'references') {
      mobilePanel.value = 'sources'
      pendingCitation = id
      await nextTick()
      revealCitation()
      return
    }
    mobilePanelOpen.value = false
    await nextTick()
  }
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    activeSectionId.value = id
  }
}

let observer = null

function teardownSectionObserver() {
  observer?.disconnect()
  observer = null
}

function setupSectionObserver() {
  teardownSectionObserver()
  const options = { root: null, rootMargin: '-96px 0px -60% 0px', threshold: 0 }
  observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
    if (visible.length > 0) {
      activeSectionId.value = visible[0].target.id
    }
  }, options)

  sectionIds.value.forEach((id) => {
    const el = document.getElementById(id)
    if (el) observer.observe(el)
  })
}

async function loadWiki() {
  const generation = ++loadGeneration
  const id = wikiRouteId.value
  loading.value = true
  error.value = ''
  clearContentEdit()
  clearInfoboxEditor()
  tocEditorVisible.value = false
  footnotesEditorVisible.value = false
  referencesEditorVisible.value = false
  revisionHistoryVisible.value = false
  revisionDiffVisible.value = false
  revisionPreviewVisible.value = false
  mobilePanelOpen.value = false
  pendingCitation = ''
  try {
    if (isMobile.value && !hasPerm(PERM.operations.target.wiki.read)) throw new Error('没有读取专题的权限')
    const detail = await wikiApi.getPageById(id)
    if (generation !== loadGeneration) return
    if (!detail.id || detail.id !== id) throw new Error('专题数据无效，请重试')
    wiki.value = detail
    rememberRecentVisit(route, detail.title)
    loading.value = false
    await nextTick()
    if (generation !== loadGeneration) return
    setupSectionObserver()
  } catch (e) {
    if (generation !== loadGeneration) return
    wiki.value = null
    error.value = e?.message || '加载维基条目失败'
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

watch(wikiRouteId, () => {
  loadWiki()
})

onMounted(() => {
  loadWiki()
})

onUnmounted(() => {
  loadGeneration += 1
  teardownSectionObserver()
})

/** """验证权限后进入独立专题编辑页面。""" */
function openMobileEditor() {
  if (!canMobileEdit.value || !wiki.value) return
  router.push({ name: 'wiki-editor', params: { id: wiki.value.id } })
}

watch(isMobile, (mobile) => {
  mobilePanelOpen.value = false
  if (mobile) editMode.value = false
  refreshSectionObserver()
})
</script>

<style scoped>
.wiki-mobile-heading{padding:22px 20px 16px;background:white;border-bottom:1px solid #e2e8f0}.wiki-mobile-heading-tags{display:flex;gap:8px;align-items:center;color:#64748b;font-size:12px}.wiki-mobile-heading h1{font-size:26px;line-height:1.4;font-weight:700;margin:14px 0;overflow-wrap:anywhere}.wiki-mobile-heading>p{font-size:14px;line-height:1.7;color:#64748b;margin:0 0 12px;overflow-wrap:anywhere}.wiki-mobile-heading-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px;color:#64748b}.wiki-mobile-heading-meta :deep(.el-button){min-height:40px}.wiki-mobile-sources{display:grid;gap:28px;overflow-wrap:anywhere}.wiki-mobile-sources :deep(.wiki-ref-go){min-width:36px;min-height:36px}.wiki-mobile-detail .wiki-reading-section{padding:16px 0}.wiki-mobile-detail .wiki-reading-section>div{padding:0 12px}.wiki-mobile-detail .wiki-reading-body{padding:20px 16px;border-radius:12px}.wiki-mobile-detail :deep(.wiki-markdown){font-size:16px;line-height:1.85;overflow-wrap:anywhere;min-width:0}.wiki-mobile-detail :deep(.wiki-markdown pre){max-width:100%;overflow-x:auto}.wiki-mobile-detail :deep(.wiki-markdown table){display:block;max-width:100%;overflow-x:auto}.wiki-mobile-detail :deep(.wiki-cite-link){display:inline-block;min-width:24px;line-height:24px;text-align:center}.wiki-mobile-detail :deep(.mobile-action-bar .el-button){font-size:13px;padding:10px 8px;min-width:0;margin:0}
</style>

