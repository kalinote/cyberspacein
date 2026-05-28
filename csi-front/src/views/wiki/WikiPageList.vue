<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <FunctionalPageHeader
      title-prefix="专题事件"
      title-suffix="管理"
      subtitle="管理 Wiki 专题页面：搜索、新建与删除；正文请在详情页编辑。"
    />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div class="lg:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">关键词</label>
            <el-input
              v-model="filters.q"
              placeholder="搜索标题或 slug"
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

        <div v-loading="loading" element-loading-text="加载中..." class="min-h-[320px]">
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
                    :to="{ name: 'wiki-detail', params: { slug: row.slug } }"
                    class="text-blue-600 hover:underline font-medium"
                  >
                    {{ row.title }}
                  </router-link>
                </template>
              </el-table-column>
              <el-table-column prop="slug" label="Slug" min-width="140" show-overflow-tooltip />
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
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="{ row }">
                  <el-button
                    type="primary"
                    link
                    @click="router.push({ name: 'wiki-detail', params: { slug: row.slug } })"
                  >
                    查看
                  </el-button>
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

    <WikiCreateDialog v-model="createDialogVisible" @created="fetchList" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import WikiCreateDialog from '@/components/wiki/WikiCreateDialog.vue'
import { wikiApi, normalizeWikiListResponse } from '@/api/wiki.js'

defineOptions({ name: 'WikiPageList' })

const router = useRouter()
const loading = ref(false)
const createDialogVisible = ref(false)
const items = ref([])

const filters = ref({
  q: '',
  status: '',
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
  loading.value = true
  try {
    const res = await wikiApi.listPages({
      q: filters.value.q.trim() || undefined,
      status: filters.value.status || undefined,
      sortBy: filters.value.sortBy,
      sortOrder: filters.value.sortOrder,
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
    })
    const { items: list, pagination: p } = normalizeWikiListResponse(res)
    items.value = list
    pagination.value = { ...pagination.value, ...p }
  } catch {
    items.value = []
  } finally {
    loading.value = false
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
 * @param {{ id: string, title: string, slug: string }} row
 */
async function handleDelete(row) {
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
</script>
