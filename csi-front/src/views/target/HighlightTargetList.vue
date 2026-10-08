<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <main v-if="isMobile" class="mobile-highlights">
      <MobileKnowledgeNav />
      <div class="mobile-highlights__heading"><div><h1>重点实体</h1><p>查阅已标记的重要资料</p></div><Icon icon="mdi:star-outline" /></div>
      <form class="mobile-highlights__search" @submit.prevent="applyFilters">
        <el-input v-model="keywords" placeholder="搜索重点资料" aria-label="搜索重点资料" clearable :disabled="!canSearch"><template #prefix><Icon icon="mdi:magnify" /></template></el-input>
        <el-button native-type="submit" type="primary" :disabled="!canSearch">搜索</el-button>
      </form>
      <div class="mobile-highlights__controls">
        <div class="mobile-highlights__types" aria-label="资料类型">
          <button v-for="option in mobileCategories" :key="option.value" :aria-pressed="activeCategory === option.value" :class="{ active: activeCategory === option.value }" :disabled="!canSearch" @click="entityTypes = option.value ? [option.value] : []; applyFilters()">{{ option.label }}</button>
        </div>
        <button class="mobile-highlights__filter" :disabled="!canSearch" @click="openMobileFilters"><Icon icon="mdi:tune-variant" />筛选<span v-if="activeFilters.timeRange !== 'all'" class="mobile-highlights__dot" /></button>
      </div>
      <div class="mobile-highlights__summary"><span>{{ loading ? '正在查找重点资料…' : `共 ${total} 条重点资料` }}</span><button :disabled="loading || !canSearch" @click="loadData">刷新</button></div>
      <div v-if="!canSearch" class="mobile-highlights__state" role="status">暂无查阅重点资料的权限</div>
      <div v-else-if="loadError" class="mobile-highlights__state" role="alert"><Icon icon="mdi:cloud-alert-outline" /><p>{{ loadError }}</p><el-button @click="loadData">重新加载</el-button></div>
      <div v-else-if="loading && !items.length" class="mobile-highlights__state" role="status"><el-skeleton :rows="5" animated /><p>正在加载重点资料…</p></div>
      <div v-else-if="!loading && !items.length" class="mobile-highlights__state" role="status"><Icon icon="mdi:star-off-outline" /><p>{{ hasActiveFilters ? '没有符合条件的重点资料' : '暂无重点资料' }}</p><span>{{ hasActiveFilters ? '试试其他关键词或筛选条件。' : '在检索结果或正文页标记重点后，即可在这里查阅。' }}</span></div>
      <div v-else class="mobile-highlights__list" :aria-busy="loading">
        <MobileHighlightCard v-for="result in items" :key="`${result.entity_type}:${result.uuid}`" :entity="result" manageable @cancel="cancelHighlight" />
      </div>
      <nav v-if="total > pageSize && !loadError" class="mobile-highlights__pagination" aria-label="重点资料分页">
        <el-button :disabled="currentPage <= 1 || loading" @click="currentPage--">上一页</el-button><span>{{ currentPage }} / {{ totalPages }}</span><el-button :disabled="currentPage >= totalPages || loading" @click="currentPage++">下一页</el-button>
      </nav>
      <MobileSheet v-model="mobileFiltersVisible" title="筛选重点资料">
        <div class="mobile-highlights__filter-form">
          <label for="highlight-time-range">原文编辑时间</label>
          <el-select id="highlight-time-range" v-model="mobileDraft.timeRange" aria-label="原文编辑时间范围"><el-option v-for="option in timeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select>
          <label for="highlight-sort-order">排序方式</label>
          <el-select id="highlight-sort-order" v-model="mobileDraft.sortBy" aria-label="排序方式"><el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select>
        </div>
        <template #footer><div class="mobile-highlights__sheet-actions"><el-button @click="mobileDraft = { timeRange: 'all', sortBy: 'time' }">重置</el-button><el-button type="primary" @click="timeRange = mobileDraft.timeRange; sortBy = mobileDraft.sortBy; mobileFiltersVisible = false; applyFilters()">应用筛选</el-button></div></template>
      </MobileSheet>
    </main>
    <template v-else>
    <FunctionalPageHeader
      title-prefix="重点"
      title-suffix="实体库"
      subtitle="查看和管理已标记为重点的情报实体，支持条件筛选与取消重点。"
    />

    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="flex flex-col sm:flex-row flex-wrap gap-4 items-end">
          <div class="flex-1 min-w-[200px]">
            <el-input
              v-model="keywords"
              placeholder="关键词筛选"
              clearable
              @keyup.enter="applyFilters"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <el-select v-model="timeRange" placeholder="时间范围" style="width: 140px">
            <el-option label="全部" value="all" />
            <el-option label="最近24小时" value="24h" />
            <el-option label="最近7天" value="7d" />
            <el-option label="最近30天" value="30d" />
          </el-select>
          <el-select v-model="entityTypes" placeholder="实体类型" multiple collapse-tags style="width: 180px">
            <el-option v-for="opt in categoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-select v-model="sortBy" placeholder="排序" style="width: 140px">
            <el-option label="更新时间" value="time" />
            <el-option label="发布时间" value="publish_at" />
            <el-option label="采集时间" value="crawled_at" />
            <el-option label="相关性" value="relevance" />
          </el-select>
          <el-button type="primary" @click="applyFilters">
            <template #icon><Icon icon="mdi:magnify" /></template>
            筛选
          </el-button>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="p-6 border-b border-gray-200">
          <h2 class="text-lg font-bold text-gray-900">重点实体列表</h2>
        </div>

        <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[400px]">
          <div v-if="!loading && items.length === 0" class="flex flex-col items-center justify-center py-16">
            <Icon icon="mdi:star-off-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">暂无重点实体</p>
            <p class="text-gray-400 text-sm">在检索结果或详情页中将实体标记为重点后，会在此展示。</p>
          </div>

          <div v-else class="p-6">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
              <div
                v-for="result in items"
                :key="result.uuid"
                class="bg-gray-50 rounded-xl p-4 border border-gray-200 hover:shadow-lg transition-all flex flex-col"
              >
                <div class="flex flex-wrap items-center gap-1.5 mb-2">
                  <el-tag size="small">{{ result.section }}</el-tag>
                  <el-tag :type="getConfidenceInfo(result.confidence).type" size="small">
                    {{ getConfidenceInfo(result.confidence).text }}
                  </el-tag>
                  <el-tag v-if="result.nsfw" type="danger" size="small">NSFW</el-tag>
                  <el-tag v-if="result.aigc" type="warning" size="small">AIGC</el-tag>
                </div>
                <h3 class="text-base font-bold text-gray-900 mb-1.5 line-clamp-2">
                  <router-link v-if="entityDetailPath(result)" :to="entityDetailPath(result)" class="hover:text-blue-600 transition-colors">
                    {{ result.title || '无标题' }}
                  </router-link>
                  <span v-else>{{ result.title || '无标题' }}</span>
                </h3>
                <p class="text-gray-600 text-sm mb-3 flex-1">{{ truncateContent(result.clean_content, 200) || '暂无分析内容' }}</p>
                <div class="space-y-1.5 text-sm text-gray-500 mt-auto mb-3">
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:source-repository" class="text-blue-500 shrink-0" />
                    <router-link v-if="result.platform_id && hasAll([PERM.pages.search.access, PERM.operations.content.platform.read])" :to="`/details/platform/${result.platform_id}`" class="text-blue-600 hover:underline truncate">
                      {{ result.platform || '—' }}
                    </router-link>
                    <span v-else>{{ result.platform || '—' }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:calendar" class="text-purple-500 shrink-0" />
                    <span>{{ formatDateTime(result.update_at) }}</span>
                  </div>
                </div>
                <div class="pt-3 border-t border-gray-200 flex items-center justify-between gap-2">
                  <AddToEvidenceButton :entity="result" />
                  <router-link v-if="entityDetailPath(result)" :to="entityDetailPath(result)" class="text-blue-600 hover:text-blue-800 flex items-center text-sm font-medium">
                    <Icon icon="mdi:eye" class="mr-1" />
                    查看详情
                  </router-link>
                  <el-button
                    v-if="hasPerm(PERM.operations.target.highlight.update)"
                    type="danger"
                    link
                    size="small"
                    :loading="result._highlightLoading"
                    @click="cancelHighlight(result)"
                  >
                    <template #icon>
                      <Icon icon="mdi:star-off-outline" />
                    </template>
                    取消重点目标
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="total > 0" class="p-6 border-t border-gray-200 flex justify-center">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            background
          />
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import AddToEvidenceButton from '@/components/evidence/AddToEvidenceButton.vue'
import { computed, ref, watch, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { searchApi } from '@/api/search'
import { highlightApi } from '@/api/highlight'
import { formatDateTime as formatDateTimeUtil } from '@/utils/action/formatters'
import MobileHighlightCard from '@/components/target/MobileHighlightCard.vue'
import { entityDetailPath } from '@/components/target/targetContent'
import MobileKnowledgeNav from '@/components/mobile/MobileKnowledgeNav.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm, hasAll } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'

defineOptions({ name: 'HighlightTargetList' })

const keywords = ref('')
const timeRange = ref('all')
const entityTypes = ref([])
const sortBy = ref('time')
const categoryOptions = [
  { value: 'forum', label: '论坛' },
  { value: 'article', label: '文章' }
]
const mobileCategories = [{ value: '', label: '全部' }, ...categoryOptions]
const timeOptions = [{ value: 'all', label: '全部时间' }, { value: '24h', label: '最近24小时' }, { value: '7d', label: '最近7天' }, { value: '30d', label: '最近30天' }]
const sortOptions = [{ value: 'time', label: '原文编辑时间' }, { value: 'publish_at', label: '发布时间' }, { value: 'crawled_at', label: '采集时间' }, { value: 'relevance', label: '相关性' }]
const { isMobile } = useMobileViewport()
const canSearch = computed(() => hasAll([PERM.pages.target.highlights.access, PERM.operations.search.entity.execute]))
const mobileFiltersVisible = ref(false)
const mobileDraft = ref({ timeRange: 'all', sortBy: 'time' })
const activeFilters = ref({ keywords: '', timeRange: 'all', sortBy: 'time', entityTypes: [] })
const activeCategory = computed(() => activeFilters.value.entityTypes.length === 1 ? activeFilters.value.entityTypes[0] : '')
const hasActiveFilters = computed(() => Boolean(activeFilters.value.keywords || activeFilters.value.entityTypes.length || activeFilters.value.timeRange !== 'all'))
const loading = ref(false)
const loadError = ref('')
const items = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
let requestSequence = 0
let active = true
let needsReload = true

function formatDateTime(val) {
  return formatDateTimeUtil(val) || '—'
}

function truncateContent(content, maxLength) {
  if (!content) return ''
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = content
  const text = (tempDiv.textContent || tempDiv.innerText || '').trim()
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

function getConfidenceInfo(confidence) {
  if (confidence === 0) {
    return { text: '零信任', type: 'danger' }
  }
  if (confidence > 0 && confidence <= 0.4) {
    return { text: '低', type: 'info' }
  }
  if (confidence > 0.4 && confidence <= 0.7) {
    return { text: '中', type: '' }
  }
  return { text: '高', type: 'warning' }
}

/** """将已提交的时间范围转为后端原文编辑时间过滤条件。""" */
function getTimeRangeBounds(range) {
  if (!range || range === 'all') {
    return { start_at: null, end_at: null }
  }
  const end = new Date()
  const start = new Date()
  if (range === '24h') {
    start.setHours(start.getHours() - 24)
  } else if (range === '7d') {
    start.setDate(start.getDate() - 7)
  } else if (range === '30d') {
    start.setDate(start.getDate() - 30)
  } else {
    return { start_at: null, end_at: null }
  }
  return {
    start_at: start.toISOString(),
    end_at: end.toISOString()
  }
}

/** """编辑移动筛选草稿，关闭面板时不改变已应用条件。""" */
function openMobileFilters() {
  mobileDraft.value = { timeRange: activeFilters.value.timeRange, sortBy: activeFilters.value.sortBy }
  mobileFiltersVisible.value = true
}

/** """提交搜索条件并回到第一页，仅发起一次请求。""" */
function applyFilters() {
  activeFilters.value = { keywords: keywords.value.trim(), timeRange: timeRange.value, sortBy: sortBy.value, entityTypes: [...entityTypes.value] }
  if (currentPage.value === 1) return loadData()
  currentPage.value = 1
}

/**
 * 加载当前已提交条件的重点资料，忽略离页和过期请求。
 * @returns {Promise<void>} 当前请求完成后更新列表或明确错误状态。
 */
async function loadData() {
  if (!active) return
  const sequence = ++requestSequence
  if (!canSearch.value) {
    items.value = []
    total.value = 0
    loading.value = false
    return
  }
  const filters = activeFilters.value
  try {
    loading.value = true
    loadError.value = ''
    needsReload = false
    const { start_at, end_at } = getTimeRangeBounds(filters.timeRange)
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      is_highlighted: true,
      search_mode: 'keyword',
      sort_by: filters.sortBy,
      sort_order: 'desc'
    }
    if (filters.keywords) params.keywords = filters.keywords
    if (start_at) params.start_at = start_at
    if (end_at) params.end_at = end_at
    if (filters.entityTypes.length) params.entity_type = [...filters.entityTypes]
    const response = await searchApi.searchEntity(params)
    if (!active || sequence !== requestSequence) return
    if (response?.code !== 0 || !response.data) throw new Error('重点资料加载失败')
    items.value = response.data.items || []
    total.value = response.data.total || 0
  } catch (err) {
    if (!active || sequence !== requestSequence) return
    console.error('加载重点实体失败:', err)
    loadError.value = '重点资料加载失败，请重试'
    if (!isMobile.value) ElMessage.error('加载失败，请稍后重试')
    items.value = []
    total.value = 0
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

/**
 * 沿用直接取消重点的操作，并在成功后修正分页。
 * @param {object} result 待取消重点的材料。
 * @returns {Promise<void>} 更新成功后的列表，失败时保留原材料。
 */
async function cancelHighlight(result) {
  const entityType = String(result.entity_type || '').toLowerCase()
  if (!active || result._highlightLoading || !['article', 'forum'].includes(entityType) || !result.uuid || !hasAll([PERM.pages.target.highlights.access, PERM.operations.target.highlight.update])) return
  result._highlightLoading = true
  try {
    const res = await highlightApi.setHighlight(entityType, result.uuid, { is_highlighted: false })
    if (!active) { needsReload = true; return }
    if (res && res.code === 0) {
      ElMessage.success('已取消重点目标')
      const idx = items.value.findIndex((i) => i.uuid === result.uuid && String(i.entity_type || '').toLowerCase() === entityType)
      if (idx !== -1) items.value.splice(idx, 1)
      if (idx !== -1) total.value = Math.max(0, total.value - 1)
      if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
    } else {
      ElMessage.error(res?.message || '操作失败')
    }
  } catch (err) {
    if (!active) { needsReload = true; return }
    console.error('取消重点失败:', err)
    ElMessage.error('操作失败，请稍后重试')
  } finally {
    result._highlightLoading = false
  }
}

watch(currentPage, loadData, { flush: 'sync' })
watch(canSearch, () => { if (active) loadData() })
onMounted(loadData)
onActivated(() => { active = true; if (needsReload && !loading.value) return loadData() })
onBeforeRouteLeave(() => { mobileFiltersVisible.value = false })
onDeactivated(() => {
  mobileFiltersVisible.value = false
  active = false
  needsReload = needsReload || loading.value
  requestSequence++
  loading.value = false
})
onBeforeUnmount(() => { active = false; requestSequence++ })
</script>

<style scoped>
.mobile-highlights { padding: 16px; max-width: 767px; margin: auto; }
.mobile-highlights__heading { display: flex; align-items: center; justify-content: space-between; margin: 20px 0; }
.mobile-highlights__heading h1 { margin: 0; font-size: 23px; font-weight: 700; color: #0f172a; }
.mobile-highlights__heading p { margin: 5px 0 0; color: #64748b; font-size: 13px; }
.mobile-highlights__heading > svg { padding: 10px; width: 46px; height: 46px; color: #d97706; background: #fff7ed; border-radius: 14px; }
.mobile-highlights__search { display: flex; gap: 8px; }
.mobile-highlights__search .el-input { min-width: 0; }
.mobile-highlights__search :deep(.el-input__wrapper), .mobile-highlights__search .el-button { min-height: 44px; }
.mobile-highlights__controls { display: flex; align-items: center; gap: 8px; margin-top: 14px; }
.mobile-highlights__types { flex: 1; min-width: 0; display: flex; gap: 4px; }
.mobile-highlights__types button { flex: 1; min-height: 44px; padding: 0 8px; border-radius: 9px; color: #64748b; font-size: 13px; }
.mobile-highlights__types button.active { background: #e8f0ff; color: #2563eb; font-weight: 600; }
.mobile-highlights__filter { display: flex; align-items: center; justify-content: center; gap: 5px; min-height: 44px; padding: 0 9px; color: #475569; font-size: 13px; }
.mobile-highlights__dot { width: 5px; height: 5px; border-radius: 50%; background: #2563eb; }
.mobile-highlights__summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 8px 0; color: #64748b; font-size: 12px; }
.mobile-highlights__summary button { min-height: 44px; padding: 0 8px; color: #2563eb; }
.mobile-highlights button:disabled { opacity: .45; }
.mobile-highlights button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.mobile-highlights__state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 32px 18px; background: white; border: 1px solid #e2e8f0; border-radius: 15px; color: #64748b; font-size: 14px; text-align: center; }
.mobile-highlights__state > svg { font-size: 36px; color: #94a3b8; }
.mobile-highlights__state span { font-size: 12px; line-height: 1.7; }
.mobile-highlights__list { display: grid; gap: 12px; }
.mobile-highlights__list[aria-busy=true] { opacity: .55; }
.mobile-highlights__pagination { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 18px 0 6px; font-size: 13px; color: #64748b; }
.mobile-highlights__pagination .el-button { min-height: 44px; }
.mobile-highlights__filter-form { display: grid; gap: 10px; font-size: 14px; color: #475569; }
.mobile-highlights__filter-form label:not(:first-child) { margin-top: 8px; }
.mobile-highlights__filter-form :deep(.el-select__wrapper) { min-height: 44px; }
.mobile-highlights__sheet-actions { display: flex; gap: 10px; }
.mobile-highlights__sheet-actions .el-button { flex: 1; margin: 0; }
</style>
