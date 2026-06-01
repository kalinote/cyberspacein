<template>
  <el-dialog
    v-model="visible"
    title="编辑参考资料"
    width="640px"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <p class="text-xs text-gray-500 mb-3">
      正文使用 <code class="text-blue-600">[^1]</code> 引用参考资料，数字与列表 ID 一致；删除条目不会自动改正文。
    </p>

    <div class="rounded-lg border border-gray-200 p-3 mb-4 bg-gray-50/60">
      <p class="text-xs font-medium text-gray-600 mb-2">从搜索结果添加</p>
      <div class="flex gap-2 mb-2">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索实体标题或内容"
          clearable
          @keyup.enter="runSearch"
        />
        <el-button type="primary" :loading="searchLoading" @click="runSearch">搜索</el-button>
      </div>
      <div v-loading="searchLoading" class="min-h-8">
        <ul v-if="searchResults.length" class="space-y-2 max-h-40 overflow-y-auto m-0 p-0 list-none">
          <li
            v-for="result in searchResults"
            :key="result.uuid"
            class="flex items-start justify-between gap-2 text-sm border border-gray-100 rounded-md p-2 bg-white"
          >
            <div class="min-w-0 flex-1">
              <p class="font-medium text-gray-900 m-0 truncate" v-html="result.title" />
              <p
                v-if="result.excerpt"
                class="text-gray-500 text-xs m-0 mt-0.5 line-clamp-2"
                v-html="result.excerpt"
              />
            </div>
            <el-button size="small" type="primary" plain @click="addFromSearch(result)">
              添加
            </el-button>
          </li>
        </ul>
        <p v-else-if="searchTried && !searchLoading" class="text-xs text-gray-400 m-0">
          无匹配结果
        </p>
        <div v-if="searchTotal > 0" class="flex justify-end mt-2">
          <el-pagination
            small
            layout="total, prev, pager, next"
            :current-page="searchPage"
            :page-size="searchPageSize"
            :total="searchTotal"
            @current-change="onSearchPageChange"
          />
        </div>
      </div>
    </div>

    <div
      v-if="draft.length"
      ref="draftListRef"
      class="flex flex-col gap-3 max-h-80 overflow-y-auto pr-1"
    >
      <div
        v-for="(item, index) in draft"
        :key="item.id"
        class="flex gap-2 items-start rounded-lg border border-gray-200 p-3 bg-gray-50/50"
      >
        <span
          class="shrink-0 text-sm font-mono font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded min-w-6 text-center"
        >
          {{ item.id }}
        </span>
        <div class="flex-1 min-w-0 space-y-2">
          <el-input
            v-model="item.text"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="参考文献条目"
          />
          <div v-if="item.url" class="flex items-center gap-2 text-xs text-gray-500">
            <Icon icon="mdi:link-variant" class="shrink-0" />
            <span class="truncate">{{ item.url }}</span>
            <el-button size="small" link type="danger" @click="clearLink(item)">清除链接</el-button>
          </div>
        </div>
        <div class="flex flex-col gap-1 shrink-0">
          <el-button
            size="small"
            :disabled="index === 0"
            title="上移"
            @click="moveItem(index, -1)"
          >
            <Icon icon="mdi:chevron-up" />
          </el-button>
          <el-button
            size="small"
            :disabled="index === draft.length - 1"
            title="下移"
            @click="moveItem(index, 1)"
          >
            <Icon icon="mdi:chevron-down" />
          </el-button>
          <el-button size="small" type="danger" plain title="删除" @click="removeItem(index)">
            <Icon icon="mdi:delete-outline" />
          </el-button>
        </div>
      </div>
    </div>
    <p v-else class="text-sm text-gray-400 text-center py-4">暂无参考资料</p>

    <el-button type="primary" plain class="w-full mt-3" @click="addEmptyItem">
      <Icon icon="mdi:plus" class="mr-1" />
      手动添加条目
    </el-button>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleApply">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { searchApi } from '@/api/search.js'
import { nextReferenceId } from '@/utils/wikiCitationIds.js'
import { referenceFromSearchResult } from '@/utils/wikiReferenceFromSearch.js'

/** @typedef {import('@/types/wiki.js').WikiReference} WikiReference */

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  /** @type {import('vue').PropType<WikiReference[]>} */
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue', 'apply'])

const visible = ref(props.modelValue)
/** @type {import('vue').Ref<WikiReference[]>} */
const draft = ref([])
const searchKeyword = ref('')
const searchLoading = ref(false)
const searchTried = ref(false)
/** @type {import('vue').Ref<{ uuid: string, title: string, excerpt: string, raw: Record<string, unknown> }[]>} */
const searchResults = ref([])
const searchPage = ref(1)
const searchPageSize = 8
const searchTotal = ref(0)
const draftListRef = ref(null)

async function scrollDraftListToBottom() {
  await nextTick()
  await nextTick()
  requestAnimationFrame(() => {
    const el = draftListRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
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

function cloneItems(items) {
  return (items || []).map((item) => ({
    id: String(item.id),
    text: String(item.text ?? ''),
    url: item.url ? String(item.url) : '',
    entityType: item.entityType ?? null,
    entityUuid: item.entityUuid ?? null,
  }))
}

function onOpen() {
  draft.value = cloneItems(props.items)
  searchKeyword.value = ''
  searchResults.value = []
  searchTried.value = false
  searchPage.value = 1
  searchTotal.value = 0
}

function onClosed() {
  draft.value = []
  searchResults.value = []
  searchTotal.value = 0
}

function stripHtml(html, maxLen = 100) {
  const text = String(html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  if (text.length <= maxLen) return text
  return `${text.slice(0, maxLen)}…`
}

function mapSearchItems(items) {
  return items.map((item) => ({
    uuid: String(item.uuid ?? ''),
    title: item.title ?? '未命名',
    excerpt: stripHtml(item.clean_content),
    raw: item,
  }))
}

/**
 * @param {number} page
 */
async function fetchSearchPage(page) {
  const keywords = searchKeyword.value.trim()
  if (!keywords) return

  searchLoading.value = true
  searchTried.value = true
  try {
    const response = await searchApi.searchEntity({
      page,
      page_size: searchPageSize,
      keywords,
      search_mode: 'keyword',
      sort_by: 'time',
      sort_order: 'desc',
    })
    if (response?.code === 0 && response.data) {
      searchPage.value = page
      searchTotal.value = response.data.total ?? 0
      searchResults.value = mapSearchItems(response.data.items || [])
    } else {
      searchResults.value = []
      searchTotal.value = 0
    }
  } catch {
    searchResults.value = []
    searchTotal.value = 0
  } finally {
    searchLoading.value = false
  }
}

async function runSearch() {
  const keywords = searchKeyword.value.trim()
  if (!keywords) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  searchPage.value = 1
  await fetchSearchPage(1)
}

/**
 * @param {number} page
 */
function onSearchPageChange(page) {
  fetchSearchPage(page)
}

/**
 * @param {{ raw: Record<string, unknown> }} result
 */
async function addFromSearch(result) {
  const ref = referenceFromSearchResult(
    result.raw,
    draft.value.map((item) => item.id)
  )
  draft.value.push(ref)
  ElMessage.success(`已添加参考资料 ${ref.id}`)
  await scrollDraftListToBottom()
}

async function addEmptyItem() {
  const id = nextReferenceId(draft.value.map((item) => item.id))
  draft.value.push({
    id,
    text: '',
    url: '',
    entityType: null,
    entityUuid: null,
  })
  await scrollDraftListToBottom()
}

/**
 * @param {WikiReference} item
 */
function clearLink(item) {
  item.url = ''
  item.entityType = null
  item.entityUuid = null
}

/**
 * @param {number} index
 */
function removeItem(index) {
  draft.value.splice(index, 1)
}

/**
 * @param {number} index
 * @param {number} delta
 */
function moveItem(index, delta) {
  const next = index + delta
  if (next < 0 || next >= draft.value.length) return
  const list = [...draft.value]
  const [item] = list.splice(index, 1)
  list.splice(next, 0, item)
  draft.value = list
}

function handleApply() {
  emit('apply', cloneItems(draft.value))
  visible.value = false
}
</script>
