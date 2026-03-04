<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

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
                  <router-link :to="getDetailRoute(result.entity_type, result.uuid)" class="hover:text-blue-600 transition-colors">
                    {{ result.title || '无标题' }}
                  </router-link>
                </h3>
                <p class="text-gray-600 text-sm mb-3 flex-1">{{ truncateContent(result.clean_content, 200) || '暂无分析内容' }}</p>
                <div class="space-y-1.5 text-sm text-gray-500 mt-auto mb-3">
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:source-repository" class="text-blue-500 shrink-0" />
                    <router-link v-if="result.platform_id" :to="`/details/platform/${result.platform_id}`" class="text-blue-600 hover:underline truncate">
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
                  <router-link :to="getDetailRoute(result.entity_type, result.uuid)" class="text-blue-600 hover:text-blue-800 flex items-center text-sm font-medium">
                    <Icon icon="mdi:eye" class="mr-1" />
                    查看详情
                  </router-link>
                  <el-button
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
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { searchApi } from '@/api/search'
import { highlightApi } from '@/api/highlight'
import { formatDateTime as formatDateTimeUtil } from '@/utils/action/formatters'

export default {
  name: 'HighlightTargetList',
  components: {
    Header,
    FunctionalPageHeader,
    Icon
  },
  data() {
    return {
      keywords: '',
      timeRange: 'all',
      entityTypes: [],
      sortBy: 'time',
      categoryOptions: [
        { value: 'Forum', label: 'Forum' },
        { value: 'Article', label: 'Article' }
      ],
      loading: false,
      items: [],
      total: 0,
      currentPage: 1,
      pageSize: 10
    }
  },
  mounted() {
    this.loadData()
  },
  watch: {
    currentPage() {
      if (this.items.length > 0 || this.total > 0) {
        this.loadData()
      }
    }
  },
  methods: {
    formatDateTime(val) {
      return formatDateTimeUtil(val) || '—'
    },
    truncateContent(content, maxLength) {
      if (!content) return ''
      const tempDiv = document.createElement('div')
      tempDiv.innerHTML = content
      const text = (tempDiv.textContent || tempDiv.innerText || '').trim()
      if (text.length <= maxLength) return text
      return text.slice(0, maxLength) + '...'
    },
    getConfidenceInfo(confidence) {
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
    },
    getDetailRoute(entityType, uuid) {
      return `/details/${entityType}/${uuid}`
    },
    getTimeRangeBounds() {
      if (!this.timeRange || this.timeRange === 'all') {
        return { start_at: null, end_at: null }
      }
      const end = new Date()
      const start = new Date()
      if (this.timeRange === '24h') {
        start.setHours(start.getHours() - 24)
      } else if (this.timeRange === '7d') {
        start.setDate(start.getDate() - 7)
      } else if (this.timeRange === '30d') {
        start.setDate(start.getDate() - 30)
      } else {
        return { start_at: null, end_at: null }
      }
      return {
        start_at: start.toISOString(),
        end_at: end.toISOString()
      }
    },
    applyFilters() {
      this.currentPage = 1
      this.loadData()
    },
    async loadData() {
      try {
        this.loading = true
        const { start_at, end_at } = this.getTimeRangeBounds()
        const params = {
          page: this.currentPage,
          page_size: this.pageSize,
          is_highlighted: true,
          search_mode: 'keyword',
          sort_by: this.sortBy,
          sort_order: 'desc'
        }
        if (this.keywords && this.keywords.trim()) {
          params.keywords = this.keywords.trim()
        }
        if (start_at) params.start_at = start_at
        if (end_at) params.end_at = end_at
        if (this.entityTypes && this.entityTypes.length > 0) {
          params.entity_type = [...this.entityTypes]
        }
        const response = await searchApi.searchEntity(params)
        if (response.code === 0 && response.data) {
          this.items = response.data.items || []
          this.total = response.data.total || 0
        } else {
          this.items = []
          this.total = 0
        }
      } catch (err) {
        console.error('加载重点实体失败:', err)
        this.$message.error('加载失败，请稍后重试')
        this.items = []
        this.total = 0
      } finally {
        this.loading = false
      }
    },
    async cancelHighlight(result) {
      const entityType = result.entity_type
      if (!entityType || !result.uuid) return
      result._highlightLoading = true
      try {
        const res = await highlightApi.setHighlight(entityType, result.uuid, { is_highlighted: false })
        if (res && res.code === 0) {
          this.$message.success('已取消重点目标')
          const idx = this.items.findIndex((i) => i.uuid === result.uuid)
          if (idx !== -1) this.items.splice(idx, 1)
          this.total = Math.max(0, (this.total || 1) - 1)
        } else {
          this.$message.error(res?.message || '操作失败')
        }
      } catch (err) {
        console.error('取消重点失败:', err)
        this.$message.error('操作失败，请稍后重试')
      } finally {
        result._highlightLoading = false
      }
    }
  }
}
</script>
