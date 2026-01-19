<template>
  <div>
    <Header />

    <section class="relative overflow-hidden bg-linear-to-br from-white to-blue-50 pt-12 pb-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4">信息<span class="text-blue-500">检索</span></h1>
          <p class="text-xl text-gray-600 max-w-3xl mx-auto mb-8">从超过4.2亿条情报数据中快速定位关键信息,支持高级筛选与语义搜索</p>
        </div>

        <div class="max-w-4xl mx-auto bg-white rounded-2xl shadow-lg border border-gray-200 p-6 md:p-8">
          <div class="flex flex-col md:flex-row gap-4 mb-6">
            <div class="flex-1">
              <el-input v-model="searchQuery" placeholder="输入关键词、短语或自然语言描述..." @keyup.enter="performSearch" size="large"
                clearable>
                <template #prefix>
                  <Icon icon="mdi:magnify" class="text-xl" />
                </template>
              </el-input>
            </div>
            <el-button type="primary" size="large" @click="performSearch" class="px-8">
              <template #icon>
                <Icon icon="mdi:magnify" />
              </template>
              检索
            </el-button>
          </div>

          <div class="flex flex-wrap gap-3 mb-4">
            <el-button plain @click="showAdvancedFilters = true"
              :class="{ 'bg-blue-400! text-white!': hasActiveFilters }">
              <template #icon>
                <Icon icon="mdi:filter" />
              </template>
              高级筛选
            </el-button>
            <div class="flex flex-col items-center gap-0">
              <el-slider
                v-model="nsfwFilter"
                :min="0"
                :max="2"
                :step="1"
                :show-stops="true"
                :format-tooltip="formatNsfwTooltip"
                style="width: 60px"
              />
              <span class="text-xs text-gray-600 -mt-1">{{ nsfwFilterText }}</span>
            </div>
            <div class="flex flex-col items-center gap-0">
              <el-slider
                v-model="aigcFilter"
                :min="0"
                :max="2"
                :step="1"
                :show-stops="true"
                :format-tooltip="formatAigcTooltip"
                style="width: 60px"
              />
              <span class="text-xs text-gray-600 -mt-1">{{ aigcFilterText }}</span>
            </div>
          </div>

          <div v-if="filterRulesText" class="text-sm text-gray-600 pt-3 border-t border-gray-200">
            <span class="font-medium text-gray-900">当前筛选条件:</span> {{ filterRulesText }}
          </div>
        </div>
      </div>

      <div
        class="absolute top-10 right-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20">
      </div>
      <div
        class="absolute bottom-10 left-10 w-64 h-64 bg-cyan-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20">
      </div>
    </section>

    <el-dialog v-model="showAdvancedFilters" title="高级筛选器" width="90%" :before-close="handleDialogClose"
      class="filter-dialog">
      <template #header>
        <div class="flex items-center">
          <Icon icon="mdi:filter" class="text-xl mr-2 text-blue-500" />
          <span class="text-xl font-bold">高级<span class="text-blue-500">筛选器</span></span>
        </div>
      </template>

      <div class="mb-4">
        <p class="text-gray-600">通过多维度条件精确缩小检索范围</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:calendar-range" class="text-blue-600" />
            </div>
            <h3 class="font-bold text-gray-900">时间范围</h3>
          </div>
          <div class="space-y-3">
            <div v-for="(option, index) in filterOptions.timeRange" :key="index" class="flex items-center">
              <input type="radio" :id="`time-${index}`" v-model="timeRange" :value="option.value"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label :for="`time-${index}`" class="ml-2 text-gray-700">{{ option.label }}</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:tag" class="text-green-600" />
            </div>
            <h3 class="font-bold text-gray-900">实体类型</h3>
          </div>
          <div class="space-y-3">
            <div v-for="(option, index) in filterOptions.categories" :key="index" class="flex items-center">
              <input type="checkbox" :id="`cat-${index}`" v-model="categories" :value="option.value"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label :for="`cat-${index}`" class="ml-2 text-gray-700">{{ option.label }}</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:source-repository" class="text-purple-600" />
            </div>
            <h3 class="font-bold text-gray-900">网络类型</h3>
          </div>
          <div class="space-y-3">
            <div v-for="(option, index) in filterOptions.sources" :key="index" class="flex items-center">
              <input type="checkbox" :id="`source-${index}`" v-model="sources" :value="option.value"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label :for="`source-${index}`" class="ml-2 text-gray-700">{{ option.label }}</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:priority-high" class="text-amber-600" />
            </div>
            <h3 class="font-bold text-gray-900">置信度</h3>
          </div>
          <div class="space-y-3">
            <div v-for="(option, index) in filterOptions.priorities" :key="index" class="flex items-center">
              <input type="checkbox" :id="`priority-${index}`" v-model="priorities" :value="option.value"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label :for="`priority-${index}`" class="ml-2 text-gray-700 flex items-center">
                <span :class="getPriorityColorClass(option.value)" class="inline-block w-3 h-3 rounded-full mr-2"></span>
                {{ option.label }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-between items-center">
          <div class="text-sm text-gray-600">
            <span class="font-medium text-gray-900">当前筛选条件:</span> {{ filterRulesText || '未设置' }}
          </div>
          <div class="flex space-x-3">
            <el-button plain>快速保存到模板</el-button>
            <el-button @click="resetFilters">重置筛选</el-button>
            <el-button type="primary" @click="applyFilters">应用筛选</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <section class="py-10 bg-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-10">
          <h2 class="text-3xl font-bold text-gray-900 mb-2">检索<span class="text-blue-500">模板</span></h2>
          <p class="text-gray-600">快速访问您常用的检索条件和查询</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="template in searchTemplates" :key="template.id"
            class="border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
            @click="applyTemplateFilters(template)">
            <div class="flex justify-between items-start mb-4">
              <div :class="getTemplateIconClass(template.id).bgClass"
                class="w-12 h-12 rounded-xl flex items-center justify-center">
                <Icon :icon="getTemplateIconClass(template.id).icon"
                  :class="getTemplateIconClass(template.id).iconClass" class="text-2xl" />
              </div>
              <el-button text :icon="'Edit'" @click.stop="handleEditTemplate(template)" />
            </div>
            <h3 class="font-bold text-gray-900 text-lg mb-2">{{ template.title }}</h3>
            <p class="text-gray-600 text-sm mb-4">{{ template.description }}</p>
            <div class="text-sm text-gray-500">
              {{ Rules2Text(template.rules) || '未设置筛选条件' }}
            </div>
          </div>

          <div
            class="border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer">
            <div class="flex justify-between items-start mb-4">
              <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                <Icon icon="mdi:file-document" class="text-purple-600 text-2xl" />
              </div>
              <el-button type="primary" text :icon="'Plus'" />
            </div>
            <h3 class="font-bold text-gray-900 text-lg mb-2">新建检索模板</h3>
            <p class="text-gray-600 text-sm mb-4">保存当前检索条件以便快速复用</p>
            <div class="text-sm text-gray-500">
              点击"+"按钮保存当前检索
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="py-12 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-10">
          <h2 class="text-3xl font-bold text-gray-900 mb-2">检索<span class="text-blue-500">趋势分析</span></h2>
          <p class="text-gray-600">用户检索行为与系统响应趋势</p>
        </div>

        <div class="grid grid-cols-1 gap-8">
          <div class="bg-linear-to-br from-white to-blue-50 rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-xl font-bold text-gray-900">检索量与响应时间趋势</h3>
              <el-radio-group v-model="currentSearchRange" @change="switchSearchRange" size="small">
                <el-radio-button label="12">12小时</el-radio-button>
                <el-radio-button label="24">24小时</el-radio-button>
                <el-radio-button label="7">7天</el-radio-button>
              </el-radio-group>
            </div>

            <div class="h-80">
              <div id="search-trend-chart" class="w-full h-full"></div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6 pt-6 border-t border-gray-100">
              <div class="text-center">
                <p class="text-sm text-gray-500">总检索量</p>
                <p class="text-2xl font-bold text-gray-900">{{ currentSearchStats.totalSearches.toLocaleString() }}</p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">平均响应时间</p>
                <p class="text-2xl font-bold text-gray-900">{{ currentSearchStats.avgResponse }}<span
                    class="text-lg">秒</span></p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">检索成功率</p>
                <p class="text-2xl font-bold text-green-600">{{ stats.successRate }}<span class="text-lg">%</span></p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="search-results" class="py-10 bg-gray-50 scroll-mt-24" v-if="searchResults.length > 0">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-8 flex flex-col sm:flex-row sm:items-center justify-between">
          <div>
            <h2 class="text-3xl font-bold text-gray-900 mb-2">检索<span class="text-blue-500">结果</span></h2>
            <p class="text-gray-600">共 <span class="font-bold text-blue-600">{{ totalResults }}</span> 条相关情报</p>
          </div>
          <div class="flex items-center space-x-4 mt-4 sm:mt-0">
            <div class="flex items-center">
              <span class="text-gray-700 mr-2">排序:</span>
              <el-select v-model="sortBy" placeholder="选择排序" size="default" style="width: 140px">
                <el-option label="相关度" value="relevance" />
                <el-option label="时间最新" value="time" />
                <el-option label="优先级最高" value="priority" />
              </el-select>
            </div>
            <el-button type="primary">
              <template #icon>
                <Icon icon="mdi:chart-bar" />
              </template>
              结果分析
            </el-button>
          </div>
        </div>

        <div class="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="flex gap-3">
            <div class="flex-1">
              <el-input 
                v-model="searchQuery" 
                placeholder="输入关键词搜索..." 
                @keyup.enter="handleSearchFromResults"
                size="default"
                clearable>
                <template #prefix>
                  <Icon icon="mdi:magnify" class="text-lg" />
                </template>
              </el-input>
            </div>
            <div class="flex flex-col items-center gap-0">
              <el-slider
                v-model="nsfwFilter"
                :min="0"
                :max="2"
                :step="1"
                :show-stops="true"
                :format-tooltip="formatNsfwTooltip"
                style="width: 40px"
              />
              <span class="text-xs text-gray-600 -mt-1">{{ nsfwFilterText }}</span>
            </div>
            <div class="flex flex-col items-center gap-0">
              <el-slider
                v-model="aigcFilter"
                :min="0"
                :max="2"
                :step="1"
                :show-stops="true"
                :format-tooltip="formatAigcTooltip"
                style="width: 40px"
              />
              <span class="text-xs text-gray-600 -mt-1">{{ aigcFilterText }}</span>
            </div>
            <el-button type="primary" @click="handleSearchFromResults">
              <template #icon>
                <Icon icon="mdi:magnify" />
              </template>
              搜索
            </el-button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2 space-y-6" v-loading="loading">
            <div v-for="result in searchResults" :key="result.uuid"
              class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
              <div class="flex justify-between items-start mb-4">
                <div class="flex flex-wrap items-center gap-2">
                  <el-tag size="small">{{ result.section }}</el-tag>
                  <el-tag :type="getConfidenceInfo(result.confidence).type" size="small">{{ getConfidenceInfo(result.confidence).text }}</el-tag>
                  <el-tag v-if="result.nsfw" type="danger" size="small">NSFW</el-tag>
                </div>
                <span class="text-sm text-gray-500 shrink-0">{{ formatDateTime(result.update_at) }}</span>
              </div>
              <h3 class="text-lg font-bold text-gray-900 mb-3">{{ result.title }}</h3>
              <p class="text-gray-600 mb-4">{{ result.clean_content || '暂无分析内容' }}</p>
              <div class="flex flex-wrap gap-2 mb-4">
                <el-tag v-for="tag in result.keywords" :key="tag" size="small" type="info" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
              <div class="flex justify-between items-center text-sm text-gray-500">
                <span>来源: 
                  <router-link v-if="result.platform_id" :to="`/details/platform/${result.platform_id}`"
                    class="text-blue-600 hover:text-blue-800 items-center underline">
                    <span class="font-medium">{{ result.platform }}</span>
                  </router-link>
                  <span v-else class="font-medium">{{ result.platform }}</span>
                </span>
                <span>作者: 
                  <router-link v-if="result.author_uuid" :to="`/user/${result.author_uuid}`"
                    class="text-blue-600 hover:text-blue-800 items-center underline">
                    <span class="font-medium">{{ result.author_name }}</span>
                  </router-link>
                  <span v-else class="font-medium">{{ result.author_name }}</span>
                </span>
                <div class="flex items-center space-x-4">
                  <el-button type="primary" link>
                    <template #icon>
                      <Icon icon="mdi:bookmark-outline" />
                    </template>
                    收藏
                  </el-button>
                  <router-link :to="getDetailRoute(result.entity_type, result.uuid)" class="text-blue-600 hover:text-blue-800 flex items-center">
                    查看详情
                    <Icon icon="mdi:arrow-right" class="ml-1" />
                  </router-link>
                </div>
              </div>
            </div>

            <div class="flex justify-center mt-8">
              <el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="totalResults"
                layout="prev, pager, next" background />
            </div>
          </div>

          <div class="space-y-6">
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 class="text-lg font-bold text-gray-900 mb-4">检索结果分析</h3>
              <div class="space-y-3">
                <div class="flex justify-between">
                  <span class="text-sm text-gray-600">高优先级情报</span>
                  <span class="text-sm font-medium">42条 (15%)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-sm text-gray-600">24小时内新增</span>
                  <span class="text-sm font-medium">18条 (6%)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-sm text-gray-600">相关度 > 80%</span>
                  <span class="text-sm font-medium">89条 (31%)</span>
                </div>
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 class="text-lg font-bold text-gray-900 mb-4">数据源统计</h3>
              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">公开数据源</span>
                  <span class="text-sm font-medium">112条</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">合作伙伴</span>
                  <span class="text-sm font-medium">74条</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">内部采集</span>
                  <span class="text-sm font-medium">68条</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">其他来源</span>
                  <span class="text-sm font-medium">30条</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'
import Header from '@/components/Header.vue'
import { searchApi } from '@/api/search'

export default {
  name: 'Search',
  components: {
    Header,
    Icon
  },
  data() {
    return {
      searchQuery: '',
      nsfwFilter: 1,
      aigcFilter: 1,
      currentSearchRange: '12',
      timeRange: 'all',
      categories: [],
      sources: [],
      priorities: [],
      sortBy: 'relevance',
      currentPage: 1,
      pageSize: 5,
      totalResults: 0,
      loading: false,

      // 高级筛选器
      showAdvancedFilters: false,
      filterOptions: {
        timeRange: [
          { value: 'all', label: '全部' },
          { value: '24h', label: '最近24小时' },
          { value: '7d', label: '最近7天' },
          { value: '30d', label: '最近30天' },
          { value: 'custom', label: '自定义' }
        ],
        categories: [
          { value: 'Forum', label: 'Forum' },
          { value: 'Article', label: 'Article' }
        ],
        sources: [
          { value: '明网', label: '明网' },
          { value: 'Tor', label: 'Tor' }
        ],
        priorities: [
          { value: '高', label: '高' },
          { value: '中', label: '中' },
          { value: '低', label: '低' },
          { value: '零信任', label: '零信任' }
        ]
      },
      searchTrendData: {
        '12': {
          dates: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00'],
          searchVolume: [45, 38, 32, 55, 78, 92, 110],
          responseTime: [1.2, 1.1, 1.0, 1.3, 1.5, 1.6, 1.8]
        },
        '24': {
          dates: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
          searchVolume: [82, 65, 110, 156, 142, 168, 95],
          responseTime: [1.3, 1.2, 1.7, 2.0, 1.8, 1.9, 1.4]
        },
        '7': {
          dates: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
          searchVolume: [850, 920, 1050, 980, 1120, 750, 680],
          responseTime: [1.5, 1.6, 1.8, 1.7, 1.9, 1.4, 1.3]
        }
      },

      searchTemplates: [
        {
          id: 1,
          searchQuery: "近期新发现的高危漏洞",
          title: '网络安全威胁',
          description: '监控最新的网络攻击、漏洞和威胁情报',
          create_time: '2025-12-11 12:16:38',
          rules: {
            timeRange: '7d',
            categories: ['Forum'],
            sources: ['明网'],
            priorities: ['高']
          }
        },
        {
          id: 2,
          searchQuery: "市场投资动态",
          title: '市场投资动态',
          description: '追踪科技行业融资、并购和市场趋势',
          create_time: '2025-12-10 09:30:15',
          rules: {
            timeRange: '30d',
            categories: ['Article'],
            sources: ['明网', 'Tor'],
            priorities: ['中', '高']
          }
        },
        {
          id: 3,
          searchQuery: "最新政策法规更新",
          title: '政策法规更新',
          description: '关注最新的政策法规变化和合规要求',
          create_time: '2025-12-09 14:22:45',
          rules: {
            timeRange: '24h',
            categories: ['Article'],
            sources: ['明网'],
            priorities: ['高', '中']
          }
        },
        {
          id: 4,
          searchQuery: "人工智能 量子计算",
          title: '技术发展前沿',
          description: '追踪人工智能、量子计算等前沿技术突破',
          create_time: '2025-12-08 16:45:20',
          rules: {
            timeRange: '7d',
            categories: ['Article'],
            sources: ['明网', 'Tor'],
            priorities: ['高', '中']
          }
        },
        {
          id: 5,
          searchQuery: "近期发生的安全事件",
          title: '紧急安全事件',
          description: '实时监控紧急和高级别的安全威胁事件',
          create_time: '2025-12-07 11:15:30',
          rules: {
            timeRange: '24h',
            categories: ['Forum'],
            sources: ['明网', 'Tor'],
            priorities: ['高']
          }
        },
        {
          id: 6,
          searchQuery: "综合情报汇总",
          title: '综合情报汇总',
          description: '涵盖所有分类的综合性情报检索',
          create_time: '2025-12-06 10:00:00',
          rules: {
            timeRange: '7d',
            categories: ['Forum', 'Article'],
            sources: ['明网', 'Tor'],
            priorities: ['高', '中', '低']
          }
        }
      ],

      stats: {
        sourceCount: 147,
        successRate: 97.8
      },

      searchResults: [],
      searchTrendChart: null
    }
  },

  computed: {
    currentSearchStats() {
      const data = this.searchTrendData[this.currentSearchRange]
      const totalSearches = data.searchVolume.reduce((a, b) => a + b, 0)
      const avgResponse = (data.responseTime.reduce((a, b) => a + b, 0) / data.responseTime.length).toFixed(1)

      return {
        totalSearches,
        avgResponse
      }
    },

    filterRulesText() {
      const rule = {
        timeRange: this.timeRange,
        categories: this.categories,
        sources: this.sources,
        priorities: this.priorities
      }

      return this.Rules2Text(rule)
    },

    hasActiveFilters() {
      return this.filterRulesText.length > 0
    },

    nsfwFilterText() {
      return this.formatNsfwTooltip(this.nsfwFilter)
    },

    aigcFilterText() {
      return this.formatAigcTooltip(this.aigcFilter)
    }
  },

  watch: {
    currentPage() {
      if (this.searchResults.length > 0) {
        this.performSearch()
      }
    }
  },

  methods: {
    formatNsfwTooltip(value) {
      const tooltips = {
        0: '无NSFW',
        1: '包含NSFW',
        2: '仅NSFW'
      }
      return tooltips[value] || '默认'
    },

    formatAigcTooltip(value) {
      const tooltips = {
        0: '无AIGC',
        1: '包含AIGC',
        2: '仅AIGC'
      }
      return tooltips[value] || '默认'
    },

    getConfidenceInfo(confidence) {
      if (confidence === 0) {
        return { text: '零信任', type: 'danger' }
      } else if (confidence > 0 && confidence <= 0.4) {
        return { text: '低', type: 'info' }
      } else if (confidence > 0.4 && confidence <= 0.7) {
        return { text: '中', type: '' }
      } else {
        return { text: '高', type: 'warning' }
      }
    },

    getDetailRoute(entityType, uuid) {
      return `/details/${entityType}/${uuid}`
    },

    formatDateTime(dateTime) {
      if (!dateTime) return ''
      const date = new Date(dateTime)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const seconds = String(date.getSeconds()).padStart(2, '0')
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    },

    getPriorityColorClass(value) {
      const colorMap = {
        '高': 'bg-red-500',
        '中': 'bg-amber-500',
        '低': 'bg-blue-500',
        '零信任': 'bg-gray-400'
      }
      return colorMap[value] || 'bg-gray-400'
    },

    // 查询筛选模板规则转字符串
    // 筛选列表后续通过接口获取，当前只是临时数据
    Rules2Text(rule) {
      if (!rule) return ''
      const conditions = []
      
      if (rule.timeRange && rule.timeRange !== 'all') {
        const timeRangeOption = this.filterOptions.timeRange.find(opt => opt.value === rule.timeRange)
        if (timeRangeOption) {
          conditions.push(timeRangeOption.label)
        }
      }

      if (rule.categories && rule.categories.length > 0) {
        const categoryLabels = rule.categories.map(cat => {
          const option = this.filterOptions.categories.find(opt => opt.value === cat)
          return option ? option.label : cat
        })
        conditions.push(categoryLabels.join(', '))
      }

      if (rule.sources && rule.sources.length > 0) {
        const sourceLabels = rule.sources.map(src => {
          const option = this.filterOptions.sources.find(opt => opt.value === src)
          return option ? option.label : src
        })
        conditions.push(sourceLabels.join(', '))
      }

      if (rule.priorities && rule.priorities.length > 0) {
        const priorityLabels = rule.priorities.map(pri => {
          const option = this.filterOptions.priorities.find(opt => opt.value === pri)
          return option ? option.label : pri
        })
        conditions.push(priorityLabels.join(', ') + '置信度')
      }

      return conditions.length > 0 ? conditions.join(' • ') : ''
    },

    // 临时使用，用于模板图表生成
    getTemplateIconClass(templateId) {
      const iconConfigs = [
        { icon: 'mdi:shield', bgClass: 'bg-blue-100', iconClass: 'text-blue-600' },
        { icon: 'mdi:trending-up', bgClass: 'bg-green-100', iconClass: 'text-green-600' },
        { icon: 'mdi:file-document', bgClass: 'bg-purple-100', iconClass: 'text-purple-600' },
        { icon: 'mdi:chart-line', bgClass: 'bg-amber-100', iconClass: 'text-amber-600' },
        { icon: 'mdi:database', bgClass: 'bg-cyan-100', iconClass: 'text-cyan-600' }
      ]
      const index = (templateId - 1) % iconConfigs.length
      return iconConfigs[index]
    },

    async performSearch() {
      try {
        this.loading = true
        const params = {
          page: this.currentPage,
          page_size: this.pageSize,
          keywords: this.searchQuery || null,
          sort_by: this.sortBy
        }

        if (this.nsfwFilter === 0) {
          params.nsfw = false
        } else if (this.nsfwFilter === 2) {
          params.nsfw = true
        }

        if (this.aigcFilter === 0) {
          params.aigc = false
        } else if (this.aigcFilter === 2) {
          params.aigc = true
        }

        if (this.timeRange && this.timeRange !== 'all') {
          params.time_range = this.timeRange
        }

        if (this.categories && this.categories.length > 0) {
          params.categories = this.categories
        }

        if (this.sources && this.sources.length > 0) {
          params.sources = this.sources
        }

        if (this.priorities && this.priorities.length > 0) {
          params.priorities = this.priorities
        }

        const response = await searchApi.searchEntity(params)
        
        if (response.code === 0 && response.data) {
          this.searchResults = response.data.items || []
          this.totalResults = response.data.total || 0
          
          this.$nextTick(() => {
            const resultsSection = document.getElementById('search-results')
            if (resultsSection) {
              const header = document.querySelector('header')
              const headerHeight = header ? header.offsetHeight : 64
              const offsetPosition = resultsSection.getBoundingClientRect().top + window.pageYOffset - headerHeight

              window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
              })
            }
          })
        }
      } catch (error) {
        console.error('搜索失败:', error)
        this.$message.error('搜索失败，请稍后重试')
        this.searchResults = []
        this.totalResults = 0
      } finally {
        this.loading = false
      }
    },

    handleSearchFromResults() {
      this.currentPage = 1
      this.performSearch()
    },

    switchSearchRange() {
      this.updateSearchTrendChart()
    },

    resetFilters() {
      this.timeRange = 'all'
      this.categories = []
      this.sources = []
      this.priorities = []
    },

    applyFilters() {
      this.showAdvancedFilters = false
      this.performSearch()
    },

    applyTemplateFilters(template) {
      if (!template || !template.rules) return

      const rules = template.rules

      // 应用搜索关键词
      if (template.searchQuery) {
        this.searchQuery = template.searchQuery
      }

      if (rules.timeRange) {
        this.timeRange = rules.timeRange
      }

      // 应用分类
      if (rules.categories && Array.isArray(rules.categories)) {
        this.categories = [...rules.categories]
      } else {
        this.categories = []
      }

      // 应用数据源
      if (rules.sources && Array.isArray(rules.sources)) {
        this.sources = [...rules.sources]
      } else {
        this.sources = []
      }

      // 应用优先级
      if (rules.priorities && Array.isArray(rules.priorities)) {
        this.priorities = [...rules.priorities]
      } else {
        this.priorities = []
      }

      this.$message.success('已应用模板筛选条件')
    },

    handleEditTemplate(template) {
      this.$message.info('编辑模板功能开发中')
    },

    handleDialogClose(done) {
      done()
    },

    updateSearchTrendChart() {
      if (!this.searchTrendChart) return

      const data = this.searchTrendData[this.currentSearchRange]

      this.searchTrendChart.setOption({
        xAxis: {
          data: data.dates
        },
        series: [
          { data: data.searchVolume },
          { data: data.responseTime }
        ]
      })
    },

    initCharts() {
      this.$nextTick(() => {
        const searchTrendChartEl = document.getElementById('search-trend-chart')

        if (searchTrendChartEl) {
          this.searchTrendChart = echarts.init(searchTrendChartEl)
          const searchData = this.searchTrendData[this.currentSearchRange]

          this.searchTrendChart.setOption({
            grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
            xAxis: {
              type: 'category',
              data: searchData.dates,
              axisLine: { lineStyle: { color: '#e5e7eb' } },
              axisLabel: { color: '#6b7280', fontSize: 12 }
            },
            yAxis: [
              {
                type: 'value',
                name: '检索量',
                axisLine: { lineStyle: { color: '#e5e7eb' } },
                axisLabel: { color: '#6b7280' }
              },
              {
                type: 'value',
                name: '响应时间(s)',
                axisLine: { lineStyle: { color: '#e5e7eb' } },
                axisLabel: { color: '#6b7280' }
              }
            ],
            series: [
              {
                name: '检索量',
                data: searchData.searchVolume,
                type: 'bar',
                itemStyle: { color: '#3b82f6' }
              },
              {
                name: '响应时间',
                data: searchData.responseTime,
                type: 'line',
                yAxisIndex: 1,
                lineStyle: { color: '#f59e0b', width: 2 },
                itemStyle: { color: '#f59e0b' }
              }
            ],
            tooltip: { trigger: 'axis' },
            legend: { data: ['检索量', '响应时间'], top: 0 }
          })
        }

        window.addEventListener('resize', () => {
          this.searchTrendChart?.resize()
        })
      })
    }
  },

  mounted() {
    this.initCharts()
  }
}
</script>
