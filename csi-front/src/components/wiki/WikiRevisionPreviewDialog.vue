<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="min(96vw, 1200px)"
    top="4vh"
    destroy-on-close
    class="wiki-revision-preview-dialog"
    @open="onOpen"
    @closed="onClosed"
  >
    <div v-if="detail" class="rounded-lg border border-amber-200 bg-amber-50/80 px-4 py-3 mb-4 text-sm text-amber-900">
      <p class="m-0 font-medium">正在查看历史版本（只读）</p>
      <p class="m-0 mt-1 text-xs text-amber-800/90">
        修订 {{ detail.revision }} · {{ getWikiChangeTypeLabel(detail.changeType) }}
        · {{ formatTime(detail.createdAt) }}
        <span v-if="detail.changeSummary"> · {{ detail.changeSummary }}</span>
        <span v-if="detail.restoredFromRevision != null">
          · 自第 {{ detail.restoredFromRevision }} 版恢复
        </span>
      </p>
    </div>

    <div v-loading="loading" element-loading-text="加载历史版本..." class="min-h-60 max-h-[65vh] overflow-y-auto pr-1">
      <template v-if="detail && !loading">
        <div class="mb-6">
          <h2 class="text-2xl font-bold text-gray-900 m-0">{{ detail.snapshot.title }}</h2>
          <div class="flex flex-wrap gap-2 mt-2">
            <el-tag v-if="detail.snapshot.status" size="small" type="info">
              {{ statusLabel(detail.snapshot.status) }}
            </el-tag>
            <el-tag
              v-for="cat in (detail.snapshot.categories || []).slice(0, 6)"
              :key="cat"
              size="small"
              type="info"
            >
              {{ cat }}
            </el-tag>
          </div>
          <p v-if="detail.snapshot.sourceNote" class="text-sm text-gray-500 mt-2 m-0">
            {{ detail.snapshot.sourceNote }}
          </p>
        </div>
        <WikiSnapshotArticle :page="detail.snapshot" />
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-tooltip
        :content="isCurrentRevision ? '该版本已是当前页面内容' : ''"
        :disabled="!isCurrentRevision"
      >
        <span>
          <el-button
            type="primary"
            :disabled="!detail || isCurrentRevision || loading"
            @click="handleRestore"
          >
            恢复到此版本
          </el-button>
        </span>
      </el-tooltip>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import WikiSnapshotArticle from '@/components/wiki/WikiSnapshotArticle.vue'
import { wikiApi } from '@/api/wiki.js'
import { formatDateTime } from '@/utils/action'
import { getWikiChangeTypeLabel } from '@/utils/wikiRevisionLabels.js'

/** @typedef {import('@/types/wiki.js').WikiRevisionDetail} WikiRevisionDetail */

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  wikiId: {
    type: String,
    default: '',
  },
  revision: {
    type: Number,
    default: 0,
  },
  currentRevision: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:modelValue', 'restore'])

const visible = ref(props.modelValue)
const loading = ref(false)
/** @type {import('vue').Ref<WikiRevisionDetail|null>} */
const detail = ref(null)

/** @type {Record<string, string>} */
const STATUS_LABELS = {
  draft: '草稿',
  building: '构建中',
  published: '已发布',
}

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

watch(
  () => props.revision,
  () => {
    if (visible.value && props.revision) {
      loadRevision()
    }
  }
)

const dialogTitle = computed(() =>
  props.revision ? `历史版本 · 修订 ${props.revision}` : '历史版本'
)

const isCurrentRevision = computed(
  () => detail.value != null && detail.value.revision === props.currentRevision
)

function onOpen() {
  loadRevision()
}

function onClosed() {
  detail.value = null
}

/**
 * @param {string} [status]
 */
function statusLabel(status) {
  return (status && STATUS_LABELS[status]) || status || ''
}

/**
 * @param {string} raw
 */
function formatTime(raw) {
  if (!raw) return '—'
  return formatDateTime(raw, { includeSecond: true }) || raw
}

async function loadRevision() {
  if (!props.wikiId || !props.revision) return
  loading.value = true
  detail.value = null
  try {
    detail.value = await wikiApi.getRevision(props.wikiId, props.revision)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function handleRestore() {
  if (!detail.value || isCurrentRevision.value) return
  const rev = detail.value.revision
  try {
    await ElMessageBox.confirm(
      `确定将当前页面恢复为修订 ${rev} 的内容？此操作不可撤销，并会产生新的修订号。`,
      '恢复到此版本',
      {
        type: 'warning',
        confirmButtonText: '恢复',
        cancelButtonText: '取消',
      }
    )
  } catch {
    return
  }
  emit('restore', rev)
}
</script>
