<template>
  <el-dialog
    v-model="visible"
    title="修改记录"
    width="min(92vw, 1000px)"
    top="6vh"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <p v-if="currentRevision" class="text-xs text-gray-500 mb-3 m-0">
      当前修订号：<span class="font-mono font-medium text-gray-700">{{ currentRevision }}</span>
    </p>

    <div class="flex flex-wrap items-end gap-3 mb-4 p-3 rounded-lg bg-gray-50 border border-gray-200">
      <div class="flex-1 min-w-35">
        <label class="block text-xs text-gray-500 mb-1">基线版本</label>
        <el-select
          v-model="compareFrom"
          filterable
          placeholder="选择基线"
          class="w-full"
          :disabled="!revisionOptions.length"
        >
          <el-option
            v-for="opt in revisionOptions"
            :key="`from-${opt.revision}`"
            :label="revisionOptionLabel(opt)"
            :value="opt.revision"
          />
        </el-select>
      </div>
      <div class="flex-1 min-w-35">
        <label class="block text-xs text-gray-500 mb-1">目标版本</label>
        <el-select
          v-model="compareTo"
          filterable
          placeholder="选择目标"
          class="w-full"
          :disabled="!revisionOptions.length"
        >
          <el-option
            v-for="opt in revisionOptions"
            :key="`to-${opt.revision}`"
            :label="revisionOptionLabel(opt)"
            :value="opt.revision"
          />
        </el-select>
      </div>
      <el-button
        type="primary"
        :disabled="!canCompare"
        @click="handleCompare"
      >
        对比
      </el-button>
    </div>

    <div v-loading="loading" element-loading-text="加载中..." class="min-h-48">
      <el-table v-if="items.length" :data="items" stripe class="w-full" max-height="520">
        <el-table-column label="修订" width="72" align="center">
          <template #default="{ row }">
            <span class="font-mono">{{ row.revision }}</span>
            <el-tag v-if="row.revision === currentRevision" size="small" type="success" class="ml-1!">
              当前
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getWikiChangeTypeLabel(row.changeType) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatWikiRevisionSummary(row) }}
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            {{ formatTime(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="168" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="emit('preview', row.revision)">查看</el-button>
            <el-button type="primary" link @click="compareFrom = row.revision">基线</el-button>
            <el-button type="primary" link @click="compareTo = row.revision">目标</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-else-if="!loading" class="text-sm text-gray-400 text-center py-8 m-0">暂无修改记录</p>
    </div>
    <div v-if="pagination.total > 0" class="flex justify-end mt-4">
      <el-pagination
        small
        layout="total, prev, pager, next"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @current-change="onPageChange"
      />
    </div>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { wikiApi, normalizeWikiRevisionListResponse } from '@/api/wiki.js'
import { formatDateTime } from '@/utils/action'
import { formatWikiRevisionSummary, getWikiChangeTypeLabel } from '@/utils/wikiRevisionLabels.js'

/** @typedef {import('@/types/wiki.js').WikiRevisionListItem} WikiRevisionListItem */

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  wikiId: {
    type: String,
    default: '',
  },
  currentRevision: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:modelValue', 'preview', 'compare'])

const visible = ref(props.modelValue)
const loading = ref(false)
/** @type {import('vue').Ref<WikiRevisionListItem[]>} */
const items = ref([])
/** @type {import('vue').Ref<WikiRevisionListItem[]>} */
const revisionOptions = ref([])
const compareFrom = ref(null)
const compareTo = ref(null)
const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
  totalPages: 0,
})

const canCompare = computed(
  () =>
    revisionOptions.value.length > 1 &&
    compareFrom.value != null &&
    compareTo.value != null
)

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function onOpen() {
  pagination.value.page = 1
  compareFrom.value = null
  compareTo.value = null
  revisionOptions.value = []
  fetchList(1)
  fetchRevisionOptions()
}

function onClosed() {
  items.value = []
  revisionOptions.value = []
  compareFrom.value = null
  compareTo.value = null
  pagination.value = { page: 1, pageSize: 20, total: 0, totalPages: 0 }
}

/**
 * @param {WikiRevisionListItem} opt
 */
function revisionOptionLabel(opt) {
  const summary = formatWikiRevisionSummary(opt)
  return `修订 ${opt.revision} · ${summary}`
}

/**
 * @param {WikiRevisionListItem[]} list
 */
function applyDefaultCompareSelection(list) {
  if (!list.length) {
    compareFrom.value = null
    compareTo.value = null
    return
  }
  compareTo.value = list[0].revision
  compareFrom.value = list.length > 1 ? list[1].revision : list[0].revision
}

/**
 * @param {string} raw
 */
function formatTime(raw) {
  if (!raw) return '—'
  return formatDateTime(raw, { includeSecond: true }) || raw
}

async function fetchRevisionOptions() {
  if (!props.wikiId) return
  try {
    const res = await wikiApi.listRevisions(props.wikiId, { page: 1, pageSize: 100 })
    const { items: list } = normalizeWikiRevisionListResponse(res)
    revisionOptions.value = list
    applyDefaultCompareSelection(list)
  } catch {
    revisionOptions.value = []
    compareFrom.value = null
    compareTo.value = null
  }
}

/**
 * @param {number} page
 */
async function fetchList(page) {
  if (!props.wikiId) return
  loading.value = true
  try {
    const res = await wikiApi.listRevisions(props.wikiId, {
      page,
      pageSize: pagination.value.pageSize,
    })
    const { items: list, pagination: p } = normalizeWikiRevisionListResponse(res)
    items.value = list
    pagination.value = { ...pagination.value, ...p }
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

/**
 * @param {number} page
 */
function onPageChange(page) {
  fetchList(page)
}

function handleCompare() {
  if (compareFrom.value == null || compareTo.value == null) {
    ElMessage.warning('请选择基线与目标版本')
    return
  }
  emit('compare', { from: compareFrom.value, to: compareTo.value })
}
</script>
