<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="min(96vw, 1100px)"
    top="4vh"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <div v-loading="loading" element-loading-text="加载版本对比..." class="min-h-48 max-h-[70vh] overflow-y-auto pr-1">
      <template v-if="diff && !loading">
        <p class="text-xs text-gray-500 m-0 mb-4">
          基线修订 <span class="font-mono font-medium text-gray-700">{{ diff.fromRevision }}</span>
          → 目标修订
          <span class="font-mono font-medium text-gray-700">{{ diff.toRevision }}</span>
        </p>

        <el-alert
          v-if="showEmptyHint"
          type="info"
          :closable="false"
          show-icon
          class="mb-4!"
          title="两版本无差异"
        />

        <div v-else class="space-y-4">
          <section class="rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide m-0 mb-2">变更摘要</p>
            <div class="flex flex-wrap gap-2">
              <el-tag v-if="diff.summary.metaChanged" size="small" type="warning">元数据</el-tag>
              <el-tag v-if="diff.summary.sectionsAdded" size="small" type="success">
                章节 +{{ diff.summary.sectionsAdded }}
              </el-tag>
              <el-tag v-if="diff.summary.sectionsRemoved" size="small" type="danger">
                章节 -{{ diff.summary.sectionsRemoved }}
              </el-tag>
              <el-tag v-if="diff.summary.sectionsModified" size="small">
                章节改 {{ diff.summary.sectionsModified }}
              </el-tag>
              <el-tag v-if="diff.summary.sectionsMoved" size="small" type="info">
                章节移 {{ diff.summary.sectionsMoved }}
              </el-tag>
              <el-tag v-if="diff.summary.footnotesChanged" size="small">
                脚注 {{ diff.summary.footnotesChanged }}
              </el-tag>
              <el-tag v-if="diff.summary.referencesChanged" size="small">
                参考资料 {{ diff.summary.referencesChanged }}
              </el-tag>
            </div>
          </section>

          <el-collapse v-model="activePanels">
            <el-collapse-item v-if="diff.meta.length" name="meta" title="元数据">
              <ul class="list-none m-0 p-0 space-y-4">
                <li
                  v-for="(item, idx) in diff.meta"
                  :key="`${item.field}-${idx}`"
                  class="border-b border-gray-100 pb-4 last:border-0 last:pb-0"
                >
                  <p class="text-sm font-medium text-gray-800 m-0 mb-1">
                    {{ getMetaFieldLabel(item.field) }}
                  </p>
                  <p class="text-sm text-gray-600 m-0 mb-2">
                    <span class="text-red-700/90">{{ formatMetaValue(item.field, item.fromValue) }}</span>
                    <span class="mx-2 text-gray-400">→</span>
                    <span class="text-green-700/90">{{ formatMetaValue(item.field, item.toValue) }}</span>
                  </p>
                  <WikiTextDiffHunks v-if="item.hunks?.length" :hunks="item.hunks" />
                </li>
              </ul>
            </el-collapse-item>

            <el-collapse-item
              v-if="diff.categories && (diff.categories.added.length || diff.categories.removed.length)"
              name="categories"
              title="分类标签"
            >
              <div v-if="diff.categories.added.length" class="mb-3">
                <p class="text-xs text-gray-500 m-0 mb-1">新增</p>
                <div class="flex flex-wrap gap-1">
                  <el-tag v-for="c in diff.categories.added" :key="`a-${c}`" size="small" type="success">
                    {{ c }}
                  </el-tag>
                </div>
              </div>
              <div v-if="diff.categories.removed.length">
                <p class="text-xs text-gray-500 m-0 mb-1">移除</p>
                <div class="flex flex-wrap gap-1">
                  <el-tag v-for="c in diff.categories.removed" :key="`r-${c}`" size="small" type="danger">
                    {{ c }}
                  </el-tag>
                </div>
              </div>
            </el-collapse-item>

            <el-collapse-item v-if="diff.sections.length" name="sections" :title="`章节（${diff.sections.length}）`">
              <ul class="list-none m-0 p-0 space-y-5">
                <li
                  v-for="sec in diff.sections"
                  :key="sec.section"
                  class="rounded-lg border border-gray-200 p-3"
                >
                  <div class="flex flex-wrap items-center gap-2 mb-2">
                    <el-tag size="small" :type="sectionTagType(sec.change)">
                      {{ getSectionChangeLabel(sec.change) }}
                    </el-tag>
                    <span class="text-sm font-medium text-gray-900">
                      {{ sec.titleTo || sec.titleFrom || sec.section }}
                    </span>
                    <span class="text-xs text-gray-400 font-mono">{{ sec.section }}</span>
                  </div>
                  <p v-if="sec.change === 'moved'" class="text-sm text-gray-600 m-0 mb-2">
                    {{ formatSectionPath(sec.pathFrom) }}
                    <span class="mx-1 text-gray-400">→</span>
                    {{ formatSectionPath(sec.pathTo) }}
                  </p>
                  <p
                    v-else-if="sec.titleFrom && sec.titleTo && sec.titleFrom !== sec.titleTo"
                    class="text-sm text-gray-600 m-0 mb-2"
                  >
                    标题：{{ sec.titleFrom }} → {{ sec.titleTo }}
                  </p>
                  <p v-else-if="sec.pathTo?.length || sec.pathFrom?.length" class="text-xs text-gray-500 m-0 mb-2">
                    位置：{{ formatSectionPath(sec.pathTo || sec.pathFrom) }}
                  </p>
                  <div v-if="sec.contentHunks?.length" class="mt-2">
                    <p class="text-xs text-gray-500 m-0 mb-1">正文</p>
                    <WikiTextDiffHunks :hunks="sec.contentHunks" />
                  </div>
                  <el-collapse v-if="sec.infoboxChanged" class="mt-2 border-0">
                    <el-collapse-item title="信息框变更" name="infobox">
                      <pre class="text-xs font-mono bg-gray-50 p-2 rounded overflow-x-auto m-0">{{ infoboxSummary(sec) }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </li>
              </ul>
            </el-collapse-item>

            <el-collapse-item
              v-if="diff.footnotes.length"
              name="footnotes"
              :title="`脚注（${diff.footnotes.length}）`"
            >
              <ul class="list-none m-0 p-0 space-y-4">
                <li
                  v-for="item in diff.footnotes"
                  :key="item.id"
                  class="rounded border border-gray-100 p-3"
                >
                  <CitationDiffBlock :item="item" />
                </li>
              </ul>
            </el-collapse-item>

            <el-collapse-item
              v-if="diff.references.length"
              name="references"
              :title="`参考资料（${diff.references.length}）`"
            >
              <ul class="list-none m-0 p-0 space-y-4">
                <li
                  v-for="item in diff.references"
                  :key="item.id"
                  class="rounded border border-gray-100 p-3"
                >
                  <CitationDiffBlock :item="item" />
                </li>
              </ul>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="diff" type="primary" plain @click="emitPreview">
        查看目标版本
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import WikiTextDiffHunks from '@/components/wiki/WikiTextDiffHunks.vue'
import CitationDiffBlock from '@/components/wiki/WikiCitationDiffBlock.vue'
import { wikiApi } from '@/api/wiki.js'
import {
  formatSectionPath,
  formatScalarValue,
  getMetaFieldLabel,
  getSectionChangeLabel,
  isDiffEmpty,
} from '@/utils/wikiRevisionDiffLabels.js'

/** @typedef {import('@/types/wiki.js').WikiRevisionDiff} WikiRevisionDiff */
/** @typedef {import('@/types/wiki.js').WikiSectionDiff} WikiSectionDiff */

const STATUS_LABELS = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  wikiId: {
    type: String,
    default: '',
  },
  fromRevision: {
    type: Number,
    default: 0,
  },
  toRevision: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:modelValue', 'preview'])

const visible = ref(props.modelValue)
const loading = ref(false)
/** @type {import('vue').Ref<WikiRevisionDiff|null>} */
const diff = ref(null)
const activePanels = ref(['meta', 'categories', 'sections', 'footnotes', 'references'])

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

const dialogTitle = computed(() => {
  if (!props.fromRevision && !props.toRevision) return '版本对比'
  return `版本对比 · ${props.fromRevision} → ${props.toRevision}`
})

const showEmptyHint = computed(() => {
  if (!diff.value) return false
  if (props.fromRevision === props.toRevision) return true
  return isDiffEmpty(diff.value)
})

function onOpen() {
  loadDiff()
}

function onClosed() {
  diff.value = null
  activePanels.value = ['meta', 'categories', 'sections', 'footnotes', 'references']
}

/**
 * @param {string} change
 */
function sectionTagType(change) {
  if (change === 'added') return 'success'
  if (change === 'removed') return 'danger'
  if (change === 'moved') return 'info'
  return ''
}

/**
 * @param {string} field
 * @param {unknown} value
 */
function formatMetaValue(field, value) {
  if (field === 'status' && typeof value === 'string') {
    return STATUS_LABELS[value] || value
  }
  return formatScalarValue(value)
}

/**
 * @param {WikiSectionDiff} sec
 */
function infoboxSummary(sec) {
  const parts = []
  if (sec.infoboxFrom?.caption !== sec.infoboxTo?.caption) {
    parts.push(`标题: ${sec.infoboxFrom?.caption ?? '—'} → ${sec.infoboxTo?.caption ?? '—'}`)
  }
  const fromRows = sec.infoboxFrom?.rows?.length ?? 0
  const toRows = sec.infoboxTo?.rows?.length ?? 0
  if (fromRows !== toRows) {
    parts.push(`行数: ${fromRows} → ${toRows}`)
  }
  if (!parts.length) {
    return JSON.stringify({ from: sec.infoboxFrom, to: sec.infoboxTo }, null, 2)
  }
  return parts.join('\n')
}

function emitPreview() {
  if (diff.value?.toRevision) {
    emit('preview', diff.value.toRevision)
  }
}

async function loadDiff() {
  if (!props.wikiId || !props.fromRevision || !props.toRevision) return
  loading.value = true
  diff.value = null
  try {
    diff.value = await wikiApi.getRevisionDiff(props.wikiId, {
      from: props.fromRevision,
      to: props.toRevision,
    })
    const panels = []
    if (diff.value.meta.length) panels.push('meta')
    if (
      diff.value.categories &&
      (diff.value.categories.added.length || diff.value.categories.removed.length)
    ) {
      panels.push('categories')
    }
    if (diff.value.sections.length) panels.push('sections')
    if (diff.value.footnotes.length) panels.push('footnotes')
    if (diff.value.references.length) panels.push('references')
    activePanels.value = panels.length ? panels : []
  } catch {
    diff.value = null
    visible.value = false
  } finally {
    loading.value = false
  }
}
</script>
