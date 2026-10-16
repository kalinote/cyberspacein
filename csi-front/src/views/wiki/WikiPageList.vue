<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <section v-if="isMobile" class="wiki-mobile-list">
      <MobileKnowledgeNav />
      <header class="wiki-mobile-list-heading"><div><h1>专题资料</h1><p>沿目录阅读，随时维护专题</p></div><el-button type="primary" :disabled="!canCreate" @click="openMobileCreate">新建</el-button></header>
      <form class="wiki-mobile-search" @submit.prevent="applySearch"><el-input v-model="filters.q" clearable placeholder="搜索专题标题" aria-label="搜索专题标题" /><el-button native-type="submit" type="primary">搜索</el-button></form>
      <div class="wiki-mobile-list-toolbar"><span>{{ pagination.total }} 个专题<span v-if="filters.status"> · {{ statusLabel(filters.status) }}</span></span><el-button @click="mobileFiltersOpen = true">筛选与排序</el-button></div>
      <div v-if="listError" class="wiki-mobile-error" role="alert"><p>{{ listError }}</p><p v-if="items.length">下方保留上次成功加载的资料。</p><el-button :loading="loading" @click="fetchList">重试</el-button></div>
      <p v-if="loading" class="wiki-mobile-empty" role="status">正在加载专题…</p>
      <p v-else-if="!listError && !items.length" class="wiki-mobile-empty">{{ filters.q || filters.status || filters.category ? '没有符合条件的专题，请调整筛选。' : '暂无专题资料' }}</p>
      <div class="wiki-mobile-cards" :aria-busy="loading">
        <article v-for="item in items" :key="item.id" class="wiki-mobile-card">
          <router-link :to="{ name: 'wiki-detail', params: { id: item.id } }" class="wiki-mobile-card-title">{{ item.title }}</router-link>
          <p v-if="item.sourceNote" class="wiki-mobile-card-note">{{ item.sourceNote }}</p>
          <div class="wiki-mobile-card-tags"><el-tag size="small" :type="statusTagType(item.status)">{{ statusLabel(item.status) }}</el-tag><el-tag v-for="category in item.categories.slice(0, 3)" :key="category" size="small" type="info">{{ category }}</el-tag></div>
          <p class="wiki-mobile-card-date">修订 {{ item.revision }} · {{ item.lastModified ? formatDateTime(item.lastModified) : '暂无更新时间' }}</p>
          <div class="wiki-mobile-card-actions"><el-button :disabled="!canUpdate" @click="openMobileEdit(item)">维护专题</el-button><el-button type="danger" plain :disabled="!canDelete" @click="handleDelete(item)">删除</el-button></div>
        </article>
      </div>
      <div v-if="pagination.total > 0" class="wiki-mobile-pagination"><el-pagination v-model:current-page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" :pager-count="5" layout="prev, pager, next" :disabled="loading" @current-change="fetchList" /></div>
      <MobileSheet v-model="mobileFiltersOpen" title="筛选专题">
        <el-form label-position="top"><el-form-item label="状态"><el-select v-model="filters.status" aria-label="专题状态筛选"><el-option label="全部" value="" /><el-option label="草稿" value="draft" /><el-option label="构建中" value="building" /><el-option label="已发布" value="published" /></el-select></el-form-item><el-form-item label="分类"><el-input v-model="filters.category" clearable placeholder="分类名称" aria-label="专题分类筛选" /></el-form-item><el-form-item label="排序字段"><el-select v-model="filters.sortBy" aria-label="专题排序字段"><el-option label="更新时间" value="updated_at" /><el-option label="创建时间" value="created_at" /><el-option label="标题" value="title" /></el-select></el-form-item><el-form-item label="顺序"><el-select v-model="filters.sortOrder" aria-label="专题排序顺序"><el-option label="降序" value="desc" /><el-option label="升序" value="asc" /></el-select></el-form-item></el-form>
        <template #footer><el-button @click="filters.status = ''; filters.category = ''; filters.sortBy = 'updated_at'; filters.sortOrder = 'desc'">重置筛选</el-button><el-button type="primary" @click="mobileFiltersOpen = false; applySearch()">应用筛选</el-button></template>
      </MobileSheet>
    </section>

    <FunctionalPageHeader
      v-if="!isMobile"
      title-prefix="专题事件"
      title-suffix="管理"
      subtitle="管理 Wiki 专题页面：搜索、新建与删除；正文请在详情页编辑。"
    />

    <div v-if="!isMobile" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div class="lg:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">关键词</label>
            <el-input
              v-model="filters.q"
              placeholder="搜索标题"
              clearable
              @keyup.enter="applySearch"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">状态</label>
            <el-select v-model="filters.status" placeholder="全部" clearable class="w-full">
              <el-option label="全部" value="" />
              <el-option label="草稿" value="draft" />
              <el-option label="构建中" value="building" />
              <el-option label="已发布" value="published" />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">排序</label>
            <el-select v-model="filters.sortBy" class="w-full">
              <el-option label="更新时间" value="updated_at" />
              <el-option label="创建时间" value="created_at" />
              <el-option label="标题" value="title" />
            </el-select>
          </div>
          <div class="flex gap-2">
            <el-select v-model="filters.sortOrder" style="width: 100px">
              <el-option label="降序" value="desc" />
              <el-option label="升序" value="asc" />
            </el-select>
            <el-button type="primary" class="flex-1" @click="applySearch">
              <template #icon><Icon icon="mdi:magnify" /></template>
              搜索
            </el-button>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between flex-wrap gap-3">
          <h2 class="text-lg font-bold text-gray-900">专题事件列表</h2>
          <el-button type="primary" @click="createDialogVisible = true">
            <template #icon><Icon icon="mdi:plus" /></template>
            新建专题事件
          </el-button>
        </div>

        <div v-loading="loading" element-loading-text="加载中..." class="min-h-80">
          <div
            v-if="!loading && items.length === 0"
            class="flex flex-col items-center justify-center py-16"
          >
            <Icon icon="mdi:book-open-page-variant-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">暂无专题事件</p>
            <p class="text-gray-400 text-sm">点击右上角新建，创建后可进入详情页编辑正文。</p>
          </div>

          <div v-else class="p-4 sm:p-6 overflow-x-auto">
            <el-table :data="items" stripe class="w-full">
              <el-table-column label="标题" min-width="200">
                <template #default="{ row }">
                  <router-link
                    :to="{ name: 'wiki-detail', params: { id: row.id } }"
                    class="text-blue-600 hover:underline font-medium"
                  >
                    {{ row.title }}
                  </router-link>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="分类" min-width="160">
                <template #default="{ row }">
                  <div v-if="row.categories?.length" class="flex flex-wrap gap-1">
                    <el-tag
                      v-for="cat in row.categories.slice(0, 3)"
                      :key="cat"
                      size="small"
                      type="info"
                    >
                      {{ cat }}
                    </el-tag>
                    <el-tag v-if="row.categories.length > 3" size="small" type="info">
                      +{{ row.categories.length - 3 }}
                    </el-tag>
                  </div>
                  <span v-else class="text-gray-400 text-sm">—</span>
                </template>
              </el-table-column>
              <el-table-column prop="lastModified" label="最后修改" width="170" />
              <el-table-column prop="revision" label="修订" width="72" align="center" />
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <el-button
                    type="primary"
                    link
                    @click="router.push({ name: 'wiki-detail', params: { id: row.id } })"
                  >
                    查看
                  </el-button>
                  <el-button type="primary" link @click="openEditMeta(row)">编辑</el-button>
                  <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="pagination.total > 0" class="px-6 pb-6 flex justify-end">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.pageSize"
              :total="pagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              @current-change="fetchList"
              @size-change="onPageSizeChange"
            />
          </div>
        </div>
      </div>
    </div>

    <WikiCreateDialog v-if="!isMobile" v-model="createDialogVisible" @created="fetchList" />
    <WikiEditMetaDialog
      v-if="!isMobile"
      v-model="editDialogVisible"
      :row="editRow"
      @updated="fetchList"
    />
  </div>
</template>

<script setup>
import { computed, onActivated, onDeactivated, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import WikiCreateDialog from '@/components/wiki/WikiCreateDialog.vue'
import WikiEditMetaDialog from '@/components/wiki/WikiEditMetaDialog.vue'
import { wikiApi, normalizeWikiListResponse } from '@/api/wiki.js'
import MobileKnowledgeNav from '@/components/mobile/MobileKnowledgeNav.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { formatDateTime } from '@/utils/action'

defineOptions({ name: 'WikiPageList' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const canCreate = computed(() => hasPerm(PERM.operations.target.wiki.create))
const canUpdate = computed(() => hasPerm(PERM.operations.target.wiki.update) && hasPerm(PERM.operations.target.wiki.read))
const canDelete = computed(() => hasPerm(PERM.operations.target.wiki.delete))
const mobileFiltersOpen = ref(false)
const listError = ref('')
let listGeneration = 0
let wasDeactivated = false
const loading = ref(false)
const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
/** @type {import('vue').Ref<import('@/types/wiki.js').WikiPageListItem|null>} */
const editRow = ref(null)
const items = ref([])

const filters = ref({
  q: '',
  status: '',
  category: '',
  sortBy: 'updated_at',
  sortOrder: 'desc',
})

const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0,
})

/** @type {Record<string, string>} */
const STATUS_LABELS = {
  draft: '草稿',
  building: '构建中',
  published: '已发布',
}

/**
 * @param {string} [status]
 */
function statusLabel(status) {
  return STATUS_LABELS[status] || status || '—'
}

/**
 * @param {string} [status]
 */
function statusTagType(status) {
  if (status === 'published') return 'success'
  if (status === 'building') return 'warning'
  return 'info'
}

async function fetchList() {
  const generation = ++listGeneration
  loading.value = true
  listError.value = ''
  try {
    if (isMobile.value && !hasPerm(PERM.operations.target.wiki.read)) throw new Error('没有读取专题的权限')
    const res = await wikiApi.listPages({
      q: filters.value.q.trim() || undefined,
      status: filters.value.status || undefined,
      category: filters.value.category.trim() || undefined,
      sortBy: filters.value.sortBy,
      sortOrder: filters.value.sortOrder,
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
    })
    if (generation !== listGeneration) return
    if (!Array.isArray((res?.data || res)?.items)) throw new Error('专题列表数据无效，请重试')
    const { items: list, pagination: p } = normalizeWikiListResponse(res)
    items.value = list
    pagination.value = { ...pagination.value, ...p }
  } catch (error) {
    if (generation !== listGeneration) return
    listError.value = error?.message || '专题加载失败，请重试'
    if (!isMobile.value) items.value = []
  } finally {
    if (generation === listGeneration) loading.value = false
  }
}

function applySearch() {
  pagination.value.page = 1
  fetchList()
}

function onPageSizeChange() {
  pagination.value.page = 1
  fetchList()
}

/**
 * @param {import('@/types/wiki.js').WikiPageListItem} row
 */
function openEditMeta(row) {
  editRow.value = row
  editDialogVisible.value = true
}

/**
 * @param {{ id: string, title: string }} row
 */
async function handleDelete(row) {
  if (isMobile.value && !canDelete.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.title}」？此操作不可恢复。`,
      '删除专题事件',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      }
    )
  } catch {
    return
  }

  try {
    if (isMobile.value && !canDelete.value) return
    await wikiApi.deletePage(row.id)
    ElMessage.success('已删除')
    if (items.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }
    await fetchList()
  } catch {
    /* 错误由拦截器处理 */
  }
}

onMounted(() => {
  fetchList()
})

/** """验证维护权限后进入独立专题编辑页。""" */
function openMobileEdit(row) {
  if (!canUpdate.value) return
  router.push({ name: 'wiki-editor', params: { id: row.id } })
}

/** """验证创建权限后进入独立专题创建页。""" */
function openMobileCreate() {
  if (!canCreate.value) return
  router.push({ name: 'wiki-create' })
}

onDeactivated(() => {
  wasDeactivated = true
  listGeneration += 1
  loading.value = false
  mobileFiltersOpen.value = false
  createDialogVisible.value = false
  editDialogVisible.value = false
})
onActivated(() => { if (wasDeactivated) { wasDeactivated = false; fetchList() } })
onBeforeUnmount(() => { listGeneration += 1 })
watch(isMobile, () => { mobileFiltersOpen.value = false; createDialogVisible.value = false; editDialogVisible.value = false })
</script>

<style scoped>
.wiki-mobile-list{padding:16px;max-width:767px;margin:auto}.wiki-mobile-list-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:20px 0}.wiki-mobile-list-heading h1{font-size:24px;font-weight:700;margin:0}.wiki-mobile-list-heading p{font-size:13px;color:#64748b;margin:6px 0 0}.wiki-mobile-search{display:flex;gap:8px}.wiki-mobile-list :deep(.el-button){min-height:44px;margin:0}.wiki-mobile-list :deep(.el-input__wrapper){min-height:44px}.wiki-mobile-list :deep(.el-input__inner){font-size:16px}.wiki-mobile-list-toolbar{display:flex;justify-content:space-between;align-items:center;margin:12px 0;color:#64748b;font-size:13px;gap:8px}.wiki-mobile-cards{display:grid;gap:12px}.wiki-mobile-card{border:1px solid #e2e8f0;border-radius:14px;padding:16px;background:white;min-width:0}.wiki-mobile-card-title{display:block;font-size:18px;font-weight:650;line-height:1.55;overflow-wrap:anywhere;color:#0f172a;padding-bottom:8px}.wiki-mobile-card-note{font-size:14px;line-height:1.6;color:#64748b;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0 0 12px}.wiki-mobile-card-tags{display:flex;flex-wrap:wrap;gap:6px}.wiki-mobile-card-date{font-size:12px;color:#64748b;overflow-wrap:anywhere;margin:12px 0}.wiki-mobile-card-actions{display:flex;justify-content:space-between;gap:8px}.wiki-mobile-error{padding:14px;background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;font-size:14px;margin-bottom:12px}.wiki-mobile-empty{text-align:center;padding:40px 12px;color:#64748b;font-size:14px}.wiki-mobile-pagination{display:flex;justify-content:center;padding:24px 0}
</style>
