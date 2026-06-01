<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
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
      </div>
    </div>

    <template v-else-if="wiki">
      <DetailPageHeader
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

      <section class="py-6 sm:py-8">
        <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="lg:hidden mb-6">
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
              <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 sm:p-8">
                <WikiPageMeta
                  v-model:edit-mode="editMode"
                  :source-note="wiki.sourceNote"
                />

                <div v-if="wiki.contentTree" class="space-y-8">
                  <WikiSectionBlock :node="wiki.contentTree" />

                  <WikiFootnotes :footnotes="wiki.footnotes">
                    <template v-if="editMode" #actions>
                      <el-button type="primary" link class="p-1!" @click="footnotesEditorVisible = true">
                        <Icon icon="mdi:pencil-outline" class="text-lg" />
                        编辑
                      </el-button>
                    </template>
                  </WikiFootnotes>

                  <WikiReferences :references="wiki.references">
                    <template v-if="editMode" #actions>
                      <el-button type="primary" link class="p-1!" @click="referencesEditorVisible = true">
                        <Icon icon="mdi:pencil-outline" class="text-lg" />
                        编辑
                      </el-button>
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
        @restore="handleRestoreRevision"
      />
    </template>
  </div>
</template>

<script setup>
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

defineOptions({ name: 'WikiDetail' })

/** @typedef {import('@/types/wiki.js').WikiPageDetail} WikiPageDetail */

const route = useRoute()
const router = useRouter()

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

function onArticleClick(event) {
  handleWikiCitationClick(event)
}

function scrollToSection(id) {
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
  try {
    wiki.value = await wikiApi.getPageById(wikiRouteId.value)
    await nextTick()
    setupSectionObserver()
  } catch (e) {
    wiki.value = null
    error.value = e?.message || '加载维基条目失败'
  } finally {
    loading.value = false
  }
}

watch(wikiRouteId, () => {
  loadWiki()
})

onMounted(() => {
  loadWiki()
})

onUnmounted(() => {
  teardownSectionObserver()
})
</script>

