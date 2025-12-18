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
            <!-- <el-button plain>
              <template #icon><Icon icon="mdi:calendar" /></template>
              时间范围
            </el-button>
            <el-button plain>
              <template #icon><Icon icon="mdi:tag" /></template>
              分类标签
            </el-button>
            <el-button plain>
              <template #icon><Icon icon="mdi:source-repository" /></template>
              数据源
            </el-button>
            <el-button plain>
              <template #icon><Icon icon="mdi:priority-high" /></template>
              优先级
            </el-button> -->
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
            <div class="flex items-center">
              <input type="radio" id="time-0" v-model="timeRange" value="all"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label for="time-0" class="ml-2 text-gray-700">全部</label>
            </div>
            <div class="flex items-center">
              <input type="radio" id="time-1" v-model="timeRange" value="24h"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label for="time-1" class="ml-2 text-gray-700">最近24小时</label>
            </div>
            <div class="flex items-center">
              <input type="radio" id="time-2" v-model="timeRange" value="7d"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label for="time-2" class="ml-2 text-gray-700">最近7天</label>
            </div>
            <div class="flex items-center">
              <input type="radio" id="time-3" v-model="timeRange" value="30d"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label for="time-3" class="ml-2 text-gray-700">最近30天</label>
            </div>
            <div class="flex items-center">
              <input type="radio" id="time-4" v-model="timeRange" value="custom"
                class="h-4 w-4 text-blue-500 border-gray-300 focus:ring-blue-400">
              <label for="time-4" class="ml-2 text-gray-700">自定义</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:tag" class="text-green-600" />
            </div>
            <h3 class="font-bold text-gray-900">情报分类</h3>
          </div>
          <div class="space-y-3">
            <div class="flex items-center">
              <input type="checkbox" id="cat-1" v-model="categories" value="网络安全"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="cat-1" class="ml-2 text-gray-700">网络安全</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="cat-2" v-model="categories" value="市场动态"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="cat-2" class="ml-2 text-gray-700">市场动态</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="cat-3" v-model="categories" value="政策法规"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="cat-3" class="ml-2 text-gray-700">政策法规</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="cat-4" v-model="categories" value="技术发展"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="cat-4" class="ml-2 text-gray-700">技术发展</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:source-repository" class="text-purple-600" />
            </div>
            <h3 class="font-bold text-gray-900">数据源</h3>
          </div>
          <div class="space-y-3">
            <div class="flex items-center">
              <input type="checkbox" id="source-1" v-model="sources" value="公开数据源"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="source-1" class="ml-2 text-gray-700">公开数据源</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="source-2" v-model="sources" value="合作伙伴"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="source-2" class="ml-2 text-gray-700">合作伙伴</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="source-3" v-model="sources" value="内部采集"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="source-3" class="ml-2 text-gray-700">内部采集</label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="source-4" v-model="sources" value="其他来源"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="source-4" class="ml-2 text-gray-700">其他来源</label>
            </div>
          </div>
        </div>

        <div class="bg-linear-to-br from-white to-blue-50 rounded-xl p-5 shadow-sm border border-gray-100">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center mr-3">
              <Icon icon="mdi:priority-high" class="text-amber-600" />
            </div>
            <h3 class="font-bold text-gray-900">优先级</h3>
          </div>
          <div class="space-y-3">
            <div class="flex items-center">
              <input type="checkbox" id="priority-1" v-model="priorities" value="紧急"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="priority-1" class="ml-2 text-gray-700 flex items-center">
                <span class="inline-block w-3 h-3 rounded-full bg-red-500 mr-2"></span>
                紧急
              </label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="priority-2" v-model="priorities" value="高"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="priority-2" class="ml-2 text-gray-700 flex items-center">
                <span class="inline-block w-3 h-3 rounded-full bg-amber-500 mr-2"></span>
                高
              </label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="priority-3" v-model="priorities" value="中"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="priority-3" class="ml-2 text-gray-700 flex items-center">
                <span class="inline-block w-3 h-3 rounded-full bg-blue-500 mr-2"></span>
                中
              </label>
            </div>
            <div class="flex items-center">
              <input type="checkbox" id="priority-4" v-model="priorities" value="低"
                class="h-4 w-4 text-blue-500 border-gray-300 rounded focus:ring-blue-400">
              <label for="priority-4" class="ml-2 text-gray-700 flex items-center">
                <span class="inline-block w-3 h-3 rounded-full bg-gray-400 mr-2"></span>
                低
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
            <p class="text-gray-600">共 <span class="font-bold text-blue-600">{{ searchResults.length }}</span> 条相关情报</p>
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

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2 space-y-6">
            <div v-for="result in searchResults" :key="result.id"
              class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
              <div class="flex justify-between items-start mb-4">
                <div class="flex flex-wrap items-center gap-2">
                  <el-tag :type="result.categoryType" size="small">{{ result.category }}</el-tag>
                  <el-tag :type="result.priorityType" size="small">{{ result.priority }}</el-tag>
                  <el-tag v-if="result.nsfw" type="danger" size="small">NSFW</el-tag>
                </div>
                <span class="text-sm text-gray-500 shrink-0">{{ result.date }}</span>
              </div>
              <h3 class="text-lg font-bold text-gray-900 mb-3">{{ result.title }}</h3>
              <p class="text-gray-600 mb-4">{{ result.description }}</p>
              <div class="flex flex-wrap gap-2 mb-4">
                <el-tag v-for="tag in result.tags" :key="tag" size="small" type="info" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
              <div class="flex justify-between items-center text-sm text-gray-500">
                <span>来源: <router-link :to="`/platform/${result.platformId}`"
                    class="text-blue-600 hover:text-blue-800 items-center underline">
                    <span class="font-medium">{{ result.platform }}</span>
                  </router-link></span>
                <span>作者: <router-link :to="`/user/${result.authorId}`"
                    class="text-blue-600 hover:text-blue-800 items-center underline">
                    <span class="font-medium">{{ result.author }}</span>
                  </router-link></span>
                <div class="flex items-center space-x-4">
                  <span class="flex items-center">
                    <Icon icon="mdi:eye" class="mr-1" /> {{ result.views }}
                  </span>
                  <el-button type="primary" link>
                    <template #icon>
                      <Icon icon="mdi:bookmark-outline" />
                    </template>
                    收藏
                  </el-button>
                  <a :href="`/info/${result.id}`" class="text-blue-600 hover:text-blue-800 flex items-center">
                    查看详情
                    <Icon icon="mdi:arrow-right" class="ml-1" />
                  </a>
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

export default {
  name: 'Search',
  components: {
    Header,
    Icon
  },
  data() {
    return {
      searchQuery: '',
      currentTrendRange: '7',
      currentSearchRange: '12',
      timeRange: 'all',
      categories: [],
      sources: [],
      priorities: [],
      sortBy: 'relevance',
      currentPage: 1,
      pageSize: 5,
      totalResults: 284,

      // 高级筛选器
      showAdvancedFilters: false,
      trendData: {
        '7': {
          dates: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
          values: [8320, 8740, 8920, 8670, 9150, 8410, 7890]
        },
        '30': {
          dates: ['第1周', '第2周', '第3周', '第4周'],
          values: [59800, 61200, 62500, 65400]
        },
        '90': {
          dates: ['1月', '2月', '3月'],
          values: [185000, 192000, 210000]
        }
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
            categories: ['网络安全'],
            sources: ['公开数据源'],
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
            categories: ['市场动态'],
            sources: ['公开数据源', '合作伙伴'],
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
            categories: ['政策法规'],
            sources: ['公开数据源', '内部采集'],
            priorities: ['紧急', '高']
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
            categories: ['技术发展'],
            sources: ['公开数据源', '合作伙伴', '内部采集'],
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
            categories: ['网络安全'],
            sources: ['公开数据源', '内部采集'],
            priorities: ['紧急']
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
            categories: ['网络安全', '市场动态', '政策法规', '技术发展'],
            sources: ['公开数据源', '合作伙伴', '内部采集', '其他来源'],
            priorities: ['紧急', '高', '中']
          }
        }
      ],

      stats: {
        sourceCount: 147,
        successRate: 97.8
      },

      // TODO: 这里只是临时数据
      searchResults: [],

      trendChart: null,
      sourceChart: null,
      searchTrendChart: null
    }
  },

  computed: {
    currentTrendStats() {
      const data = this.trendData[this.currentTrendRange]
      const lastValue = data.values[data.values.length - 1]
      const prevValue = data.values[data.values.length - 2]
      const change = ((lastValue - prevValue) / prevValue * 100).toFixed(1)
      const avg = Math.round(data.values.reduce((a, b) => a + b, 0) / data.values.length)

      return {
        change: parseFloat(change),
        avg: avg
      }
    },

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
    }
  },

  methods: {
    // 查询筛选模板规则转字符串
    // 筛选列表后续通过接口获取，当前只是临时数据
    Rules2Text(rule) {

      if (!rule) return ''
      const conditions = []
      const timeRangeMap = {
        'all': '全部',
        '24h': '最近24小时',
        '7d': '最近7天',
        '30d': '最近30天',
        'custom': '自定义'
      }
      // 支持 timeRange 和 timeRange 两种格式
      const timeRange = rule.timeRange
      if (rule.timeRange && rule.timeRange !== 'all') {
        conditions.push(timeRangeMap[rule.timeRange])
      }

      if (rule.categories && rule.categories.length > 0) {
        conditions.push(rule.categories.join(', '))
      }

      if (rule.sources && rule.sources.length > 0) {
        conditions.push(rule.sources.join(', '))
      }

      if (rule.priorities && rule.priorities.length > 0) {
        conditions.push(rule.priorities.join(', ') + '优先级')
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

    performSearch() {
      // console.log('执行检索:', this.searchQuery)
      this.searchResults = [
        {
          id: 1,
          category: '社区讨论',
          categoryType: 'danger',
          priority: '低',
          priorityType: 'info',
          date: '2025-12-11 12:16:38',
          title: '说一下你们看过的酒店偷拍',
          description:
            '最近喜欢看酒店和家庭偷拍、比较真实、但就是大多数图个乐呵、想问一下大佬们有没有清晰的长时间露脸、颜值高点、对话有意思的。',
          tags: ['NSFW', '偷拍', '酒店', '家庭'],
          platform: 'JAVBUS',
          platformId: 'test_nsfw_0001',
          author: 'sex_finder',
          authorId: 'test_author_0001',
          views: 2975,
          nsfw: true
        },
        {
          id: 2,
          category: '市场动态',
          categoryType: 'success',
          priority: '中',
          priorityType: '',
          date: '2023-11-19 10:23:45',
          title: '人工智能领域Q3投资报告:融资总额达45亿美元',
          description: '第三季度全球人工智能领域共发生156起投资事件,总金额达45亿美元,同比增长32%。其中,生成式AI公司最受关注...',
          tags: ['AI', '投资', '融资', '市场'],
          platform: 'TechCrunch',
          platformId: 'test_platform_0002',
          author: '张维为',
          authorId: 'test_author_0002',
          views: 892,
          nsfw: false
        },
        {
          id: 3,
          category: '政策法规',
          categoryType: '',
          priority: '中',
          priorityType: '',
          date: '2023-11-18 09:12:34',
          title: '欧盟AI法案正式通过:对高风险AI系统实施严格监管',
          description: '欧洲议会以绝对多数通过AI法案,对高风险人工智能系统提出严格要求,包括透明度、可解释性和人类监督等...',
          tags: ['欧盟', 'AI法案', '监管', '政策'],
          platform: 'EU官网',
          platformId: 'test_platform_0003',
          author: '李大钊',
          authorId: 'test_author_0003',
          views: 654,
          nsfw: false
        },
        {
          id: 4,
          category: '技术发展',
          categoryType: 'warning',
          priority: '高',
          priorityType: 'warning',
          date: '2023-11-17 14:56:23',
          title: '量子计算突破:IBM发布1000量子比特处理器',
          description: 'IBM宣布推出Condor量子处理器,拥有1121个量子比特,标志着量子计算技术进入新阶段。该处理器在错误纠正和稳定性方面取得重大进展...',
          tags: ['量子计算', 'IBM', '处理器', '技术突破'],
          platform: 'IBM Research',
          platformId: 'test_platform_0004',
          author: '王小波',
          authorId: 'test_author_0004',
          views: 2156,
          nsfw: false
        },
        {
          id: 5,
          category: '网络安全',
          categoryType: 'primary',
          priority: '紧急',
          priorityType: 'danger',
          date: '2023-11-16 12:00:00',
          title: 'APT组织Lazarus针对金融机构发起新一轮攻击活动',
          description: '安全厂商检测到Lazarus组织使用新的恶意软件变种,针对亚洲地区多家银行和金融机构发起针对性攻击。攻击手法包括鱼叉式钓鱼和供应链攻击...',
          tags: ['APT', 'Lazarus', '金融', '攻击活动'],
          platform: '威胁情报中心',
          platformId: 'test_platform_0005',
          author: '刁近乎',
          authorId: 'test_author_0005',
          views: 1834,
          nsfw: false
        }
      ]

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
    },

    switchTrendRange(range) {
      this.currentTrendRange = range
      this.updateTrendChart()
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
      console.log('应用筛选条件')
      this.showAdvancedFilters = false
    },

    applyTemplateFilters(template) {
      if (!template || !template.rules) return

      const rules = template.rules

      // 应用搜索关键词
      if (template.searchQuery) {
        this.searchQuery = template.searchQuery
      }

      // 映射时间范围：模板使用 timeRange，筛选条件使用 timeRange
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

    updateTrendChart() {
      if (!this.trendChart) return

      const data = this.trendData[this.currentTrendRange]

      this.trendChart.setOption({
        xAxis: {
          data: data.dates
        },
        series: [{
          data: data.values
        }]
      })
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
