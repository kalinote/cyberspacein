<template>
  <div>
    <Header />

    <section class="relative overflow-hidden bg-linear-to-br from-white to-blue-50 pt-12 pb-16">
      <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
            <el-button plain @click="showAdvancedFilters = !showAdvancedFilters"
              :class="{ 'bg-blue-400! text-white!': hasActiveFilters }">
              <template #icon>
                <Icon :icon="showAdvancedFilters ? 'mdi:chevron-up' : 'mdi:filter'" />
              </template>
              {{ showAdvancedFilters ? '收起高级筛选' : '高级筛选' }}
            </el-button>
            <el-select v-model="sortBy" placeholder="选择排序" size="default" style="width: 140px">
              <el-option label="相关性" value="relevance" />
              <el-option label="更新时间" value="time" />
              <el-option label="发布时间" value="publish_at" />
              <el-option label="采集时间" value="crawled_at" />
            </el-select>
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

          <el-collapse-transition>
            <div v-show="showAdvancedFilters" class="pt-4 mt-4 border-t border-gray-200">
              <div class="flex items-center mb-4">
                <Icon icon="mdi:filter" class="text-xl mr-2 text-blue-500" />
                <span class="text-xl font-bold">高级<span class="text-blue-500">筛选器</span></span>
              </div>
              <div class="mb-4">
                <p class="text-gray-600">通过多维度条件精确缩小检索范围</p>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div class="flex items-center mb-4">
                    <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3">
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

                <div class="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div class="flex items-center mb-4">
                    <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3">
                      <Icon icon="mdi:tag" class="text-blue-600" />
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

                <div class="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div class="flex items-center mb-4">
                    <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3">
                      <Icon icon="mdi:source-repository" class="text-blue-600" />
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

                <div class="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div class="flex items-center mb-4">
                    <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3">
                      <Icon icon="mdi:priority-high" class="text-blue-600" />
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
              <div class="flex flex-col sm:flex-row justify-end items-start sm:items-center gap-3 pt-4 pb-4 border-t border-gray-100">
                <div class="flex flex-wrap gap-3">
                  <el-button v-if="canViewAddTemplate" plain :disabled="!canUseAddTemplate" @click="openSaveTemplateDialog">保存到模板</el-button>
                  <el-button v-if="canViewOverwriteTemplate" plain :disabled="!canUseOverwriteTemplate" @click="openOverwriteTemplateDialog">覆盖模板</el-button>
                  <el-button @click="resetFilters">重置筛选</el-button>
                  <el-button type="primary" @click="applyFilters">应用筛选</el-button>
                </div>
              </div>
            </div>
          </el-collapse-transition>

          <div v-if="filterRulesText" class="text-sm text-gray-600 pt-3 border-t border-gray-200">
            <span class="font-medium text-gray-900">当前筛选条件:</span> {{ filterRulesText }}
          </div>
        </div>
      </div>

      <div class="absolute inset-0 pointer-events-none z-0">
        <div class="absolute top-10 right-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply blur-3xl opacity-20"></div>
        <div class="absolute bottom-10 left-10 w-64 h-64 bg-cyan-200 rounded-full mix-blend-multiply blur-3xl opacity-20"></div>
      </div>
    </section>

    <section v-if="canViewTemplateList" class="py-10 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-10">
          <h2 class="text-3xl font-bold text-gray-900 mb-2">检索<span class="text-blue-500">模板</span></h2>
          <p class="text-gray-600">快速访问您常用的检索条件和查询</p>
        </div>

        <div v-loading="templateLoading" class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <template v-if="searchTemplates.length > 0">
            <div v-for="template in searchTemplates" :key="template.id"
              class="border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
              :class="{ 'opacity-60 cursor-not-allowed': !canUseApplyTemplate }"
              @click="applyTemplateFilters(template)">
              <div class="flex justify-between items-start mb-4">
                <div :class="getTemplateIconClass(template.id).bgClass"
                  class="w-12 h-12 rounded-xl flex items-center justify-center">
                  <Icon :icon="getTemplateIconClass(template.id).icon"
                    :class="getTemplateIconClass(template.id).iconClass" class="text-2xl" />
                </div>
                <div class="flex gap-1">
                  <el-button v-if="canViewEditTemplate" text :icon="'Edit'" :disabled="!canUseEditTemplate" @click.stop="handleEditTemplate(template)" />
                  <el-button v-if="canViewDeleteTemplate" text type="danger" :icon="'Delete'" :disabled="!canUseDeleteTemplate" @click.stop="handleDeleteTemplate(template)" />
                </div>
              </div>
              <h3 class="font-bold text-gray-900 text-lg mb-2">{{ template.title }}</h3>
              <p class="text-gray-600 text-sm mb-4">{{ template.description }}</p>
              <div class="text-sm text-gray-500">
                {{ Rules2Text(template.rules) || '未设置筛选条件' }}
              </div>
            </div>
          </template>
          <div v-else class="col-span-full py-12 text-center text-gray-500">
            暂无检索模板，可在高级筛选中设置条件后点击「保存到模板」快速保存。
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
            <el-button v-if="canViewResultAnalysis" type="primary">
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
            <el-select v-model="sortBy" placeholder="选择排序" size="default" style="width: 140px">
              <el-option label="相关性" value="relevance" />
              <el-option label="更新时间" value="time" />
              <el-option label="发布时间" value="publish_at" />
              <el-option label="采集时间" value="crawled_at" />
            </el-select>
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
              <h3 class="text-lg font-bold text-gray-900 mb-3 search-highlight" v-html="result.title"></h3>
              <p class="text-gray-600 mb-4 search-highlight" v-html="truncateContent(result.clean_content, 200) || '暂无分析内容'"></p>
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
                  <el-button 
                    type="primary" 
                    link
                    @click="toggleHighlight(result)"
                    :loading="result._highlightLoading"
                    :disabled="(result.is_highlighted && !hasPerm(PERM_SEARCH_RESULTS?.unhighlightUse)) || (!result.is_highlighted && !hasPerm(PERM_SEARCH_RESULTS?.highlightUse))"
                  >
                    <template #icon>
                      <Icon :icon="result.is_highlighted ? 'mdi:star' : 'mdi:star-outline'" />
                    </template>
                    {{ result.is_highlighted ? '取消重点目标' : '设置重点目标' }}
                  </el-button>
                  <router-link v-if="canViewResultDetail" :to="getDetailRoute(result.entity_type, result.uuid)" class="text-blue-600 hover:text-blue-800 flex items-center">
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

    <el-dialog v-model="saveDialogVisible" title="保存到模板" width="480px" :close-on-click-modal="false" @closed="resetSaveForm">
      <el-form :model="saveForm" label-width="80px" label-position="top">
        <el-form-item label="模板标题" required>
          <el-input v-model="saveForm.title" placeholder="输入模板标题" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="模板描述" required>
          <el-input v-model="saveForm.description" type="textarea" :rows="3" placeholder="输入模板描述" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="检索关键词" required>
          <el-input v-model="saveForm.search_query" placeholder="检索关键词" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saveSubmitLoading" @click="submitSaveTemplate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="overwriteDialogVisible" title="覆盖模板" width="440px" :close-on-click-modal="false" @closed="overwriteSelectedId = null">
      <p class="text-gray-600 text-sm mb-4">将当前检索条件和筛选规则覆盖到所选模板，模板名称与描述保持不变。</p>
      <el-select v-model="overwriteSelectedId" placeholder="请选择要覆盖的模板" filterable class="w-full">
        <el-option
          v-for="t in searchTemplates"
          :key="t.id"
          :label="t.title"
          :value="t.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="overwriteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="overwriteSubmitLoading" :disabled="!overwriteSelectedId" @click="submitOverwriteTemplate">确认覆盖</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑模板" width="480px" :close-on-click-modal="false" @closed="editingTemplate = null">
      <template v-if="editingTemplate">
        <el-form :model="editForm" label-width="80px" label-position="top">
          <el-form-item label="模板标题" required>
            <el-input v-model="editForm.title" placeholder="输入模板标题" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="模板描述" required>
            <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="输入模板描述" maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item label="检索关键词" required>
            <el-input v-model="editForm.search_query" placeholder="检索关键词" />
          </el-form-item>
          <el-form-item label="筛选条件摘要">
            <div class="text-sm text-gray-500">{{ Rules2Text(editingTemplate.rules) || '未设置筛选条件' }}</div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitLoading" @click="submitEditTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import { searchApi } from '@/api/search'
import { highlightApi } from '@/api/highlight'
import { PERM } from '@/utils/permissions'
import { hasPerm, noPerm, guardUse } from '@/utils/permissionKit'
import { formatDateTime } from '@/utils/action'

defineOptions({ name: 'Search' })

const route = useRoute()
const searchQuery = ref('')
const nsfwFilter = ref(1)
const aigcFilter = ref(1)
const timeRange = ref('all')
const categories = ref([])
const sources = ref([])
const priorities = ref([])
const sortBy = ref('crawled_at')
const currentPage = ref(1)
const pageSize = ref(5)
const totalResults = ref(0)
const loading = ref(false)
const showAdvancedFilters = ref(false)

const filterOptions = {
  timeRange: [
    { value: 'all', label: '全部' },
    { value: '24h', label: '最近24小时' },
    { value: '7d', label: '最近7天' },
    { value: '30d', label: '最近30天' },
    { value: 'custom', label: '自定义' }
  ],
  categories: [
    { value: 'forum', label: 'Forum' },
    { value: 'article', label: 'Article' }
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
}

const searchTemplates = ref([])
const templateLoading = ref(false)

const PERM_SEARCH = PERM.operations?.search
const PERM_SEARCH_TEMPLATES = PERM_SEARCH?.templateManagement?.templates
const PERM_SEARCH_RESULTS = PERM_SEARCH?.results

const canViewTemplateList = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.listView))
const canViewApplyTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.applyView))
const canUseApplyTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.applyUse))

const canViewAddTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.addView))
const canUseAddTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.addUse))

const canViewOverwriteTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.overwriteView))
const canUseOverwriteTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.overwriteUse))

const canViewEditTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.editView))
const canUseEditTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.editUse))

const canViewDeleteTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.deleteView))
const canUseDeleteTemplate = computed(() => hasPerm(PERM_SEARCH_TEMPLATES?.deleteUse))

const canViewResultDetail = computed(() => hasPerm(PERM_SEARCH_RESULTS?.detailView))
const canViewResultAnalysis = computed(() => hasPerm(PERM_SEARCH_RESULTS?.analysisView))

const saveDialogVisible = ref(false)
const saveSubmitLoading = ref(false)
const saveForm = ref({
  title: '',
  description: '',
  search_query: ''
})

const sortOptions = [
  { value: 'relevance', label: '相关性' },
  { value: 'time', label: '更新时间' },
  { value: 'publish_at', label: '发布时间' },
  { value: 'crawled_at', label: '采集时间' }
]

function getCurrentRules() {
  return {
    timeRange: timeRange.value,
    entityType: [...categories.value],
    sources: [...sources.value],
    priorities: [...priorities.value],
    nsfw: nsfwFilter.value,
    aigc: aigcFilter.value,
    sortBy: sortBy.value
  }
}

function openSaveTemplateDialog() {
  if (!canViewAddTemplate.value) return
  if (!canUseAddTemplate.value) return void noPerm()
  const rule = getCurrentRules()
  const descText = Rules2Text({
    timeRange: rule.timeRange,
    categories: rule.entityType,
    sources: rule.sources,
    priorities: rule.priorities,
    nsfw: rule.nsfw,
    aigc: rule.aigc,
    sortBy: rule.sortBy
  })
  saveForm.value = {
    title: (searchQuery.value || '未命名模板').slice(0, 20) || '未命名模板',
    description: descText || '当前筛选条件',
    search_query: searchQuery.value || ''
  }
  saveDialogVisible.value = true
}

function resetSaveForm() {
  saveForm.value = { title: '', description: '', search_query: '' }
}

async function submitSaveTemplate() {
  if (!guardUse(PERM_SEARCH_TEMPLATES?.addUse)) return
  const { title, description, search_query } = saveForm.value
  if (!title?.trim()) {
    ElMessage.warning('请输入模板标题')
    return
  }
  if (!description?.trim()) {
    ElMessage.warning('请输入模板描述')
    return
  }
  if (!search_query?.trim()) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  saveSubmitLoading.value = true
  try {
    await searchApi.createTemplate({
      title: title.trim(),
      description: description.trim(),
      search_query: search_query.trim(),
      rules: getCurrentRules()
    })
    saveDialogVisible.value = false
    loadSearchTemplates()
    ElMessage.success('模板已保存')
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    saveSubmitLoading.value = false
  }
}

async function loadSearchTemplates() {
  templateLoading.value = true
  try {
    const res = await searchApi.getTemplateList({ page: 1, page_size: 20 })
    const data = Array.isArray(res?.items) && typeof res?.total === 'number' ? res : (res?.data ?? {})
    searchTemplates.value = data.items ?? []
  } catch {
    searchTemplates.value = []
  } finally {
    templateLoading.value = false
  }
}

const editDialogVisible = ref(false)
const editingTemplate = ref(null)
const editSubmitLoading = ref(false)
const editForm = ref({ title: '', description: '', search_query: '' })

function handleEditTemplate(template) {
  if (!guardUse(PERM_SEARCH_TEMPLATES?.editUse)) return
  editingTemplate.value = template
  editForm.value = {
    title: template.title ?? '',
    description: template.description ?? '',
    search_query: template.search_query ?? template.searchQuery ?? ''
  }
  editDialogVisible.value = true
}

async function submitEditTemplate() {
  if (!guardUse(PERM_SEARCH_TEMPLATES?.editUse)) return
  if (!editingTemplate.value) return
  const { title, description, search_query } = editForm.value
  if (!title?.trim()) {
    ElMessage.warning('请输入模板标题')
    return
  }
  if (!description?.trim()) {
    ElMessage.warning('请输入模板描述')
    return
  }
  if (!search_query?.trim()) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  editSubmitLoading.value = true
  try {
    await searchApi.updateTemplate(editingTemplate.value.id, {
      title: title.trim(),
      description: description.trim(),
      search_query: search_query.trim()
    })
    editDialogVisible.value = false
    loadSearchTemplates()
    ElMessage.success('模板已更新')
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    editSubmitLoading.value = false
  }
}

async function handleDeleteTemplate(template) {
  if (!guardUse(PERM_SEARCH_TEMPLATES?.deleteUse)) return
  try {
    await ElMessageBox.confirm('确定要删除该检索模板吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await searchApi.deleteTemplate(template.id)
    loadSearchTemplates()
    ElMessage.success('模板已删除')
  } catch {
    // 错误已由 request 拦截器提示
  }
}

const overwriteDialogVisible = ref(false)
const overwriteSelectedId = ref(null)
const overwriteSubmitLoading = ref(false)

function openOverwriteTemplateDialog() {
  if (!canViewOverwriteTemplate.value) return
  if (!canUseOverwriteTemplate.value) return void noPerm()
  if (searchTemplates.value.length === 0) {
    ElMessage.warning('暂无模板可覆盖，请先保存一个模板')
    return
  }
  overwriteSelectedId.value = null
  overwriteDialogVisible.value = true
}

async function submitOverwriteTemplate() {
  if (!guardUse(PERM_SEARCH_TEMPLATES?.overwriteUse)) return
  if (!overwriteSelectedId.value) return
  overwriteSubmitLoading.value = true
  try {
    await searchApi.updateTemplate(overwriteSelectedId.value, {
      search_query: searchQuery.value?.trim() || '',
      rules: getCurrentRules()
    })
    overwriteDialogVisible.value = false
    loadSearchTemplates()
    ElMessage.success('模板已覆盖')
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    overwriteSubmitLoading.value = false
  }
}

const searchResults = ref([])

const filterRulesText = computed(() => {
  const rule = {
    timeRange: timeRange.value,
    categories: categories.value,
    sources: sources.value,
    priorities: priorities.value,
    nsfw: nsfwFilter.value,
    aigc: aigcFilter.value,
    sortBy: sortBy.value
  }
  return Rules2Text(rule)
})

const hasActiveFilters = computed(() => filterRulesText.value.length > 0)

const nsfwFilterText = computed(() => formatNsfwTooltip(nsfwFilter.value))

const aigcFilterText = computed(() => formatAigcTooltip(aigcFilter.value))

watch(currentPage, () => {
  if (searchResults.value.length > 0) {
    performSearch()
  }
})

watch(() => route.query.q, () => {
  initSearchFromQuery()
})
function truncateContent(content, maxLength) {
      if (!content) return ''
      const tempDiv = document.createElement('div')
      tempDiv.innerHTML = content
      const textContent = tempDiv.textContent || tempDiv.innerText || ''
      if (textContent.length <= maxLength) return content
      let truncated = ''
      let currentLength = 0
      const walk = (node) => {
        if (currentLength >= maxLength) return
        if (node.nodeType === Node.TEXT_NODE) {
          const remaining = maxLength - currentLength
          if (node.textContent.length <= remaining) {
            truncated += node.textContent
            currentLength += node.textContent.length
          } else {
            truncated += node.textContent.substring(0, remaining) + '...'
            currentLength = maxLength
          }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          truncated += `<${node.tagName.toLowerCase()}>`
          for (const child of node.childNodes) {
            walk(child)
          }
          truncated += `</${node.tagName.toLowerCase()}>`
        }
      }
      for (const child of tempDiv.childNodes) {
        walk(child)
      }
      return truncated
    }

    function formatNsfwTooltip(value) {
      const tooltips = {
        0: '无NSFW',
        1: '包含NSFW',
        2: '仅NSFW'
      }
      return tooltips[value] || '默认'
    }

    function formatAigcTooltip(value) {
      const tooltips = {
        0: '无AIGC',
        1: '包含AIGC',
        2: '仅AIGC'
      }
      return tooltips[value] || '默认'
    }

    function getConfidenceInfo(confidence) {
      if (confidence === 0) {
        return { text: '零信任', type: 'danger' }
      } else if (confidence > 0 && confidence <= 0.4) {
        return { text: '低', type: 'info' }
      } else if (confidence > 0.4 && confidence <= 0.7) {
        return { text: '中', type: '' }
      } else {
        return { text: '高', type: 'warning' }
      }
    }

    function getDetailRoute(entityType, uuid) {
      return `/details/${entityType}/${uuid}`
    }

    function getPriorityColorClass(value) {
      const colorMap = {
        '高': 'bg-red-500',
        '中': 'bg-amber-500',
        '低': 'bg-blue-500',
        '零信任': 'bg-gray-400'
      }
      return colorMap[value] || 'bg-gray-400'
    }

    function Rules2Text(rule) {
      if (!rule) return ''
      const conditions = []

      const timeVal = rule.timeRange ?? rule.time_range
      if (timeVal && timeVal !== 'all') {
        const timeRangeOption = filterOptions.timeRange.find(opt => opt.value === timeVal)
        if (timeRangeOption) {
          conditions.push(timeRangeOption.label)
        }
      }

      const cats = rule.entityType ?? rule.entity_type ?? rule.categories
      if (cats && cats.length > 0) {
        const categoryLabels = cats.map(cat => {
          const option = filterOptions.categories.find(opt => opt.value === cat)
          return option ? option.label : cat
        })
        conditions.push(categoryLabels.join(', '))
      }

      if (rule.sources && rule.sources.length > 0) {
        const sourceLabels = rule.sources.map(src => {
          const option = filterOptions.sources.find(opt => opt.value === src)
          return option ? option.label : src
        })
        conditions.push(sourceLabels.join(', '))
      }

      if (rule.priorities && rule.priorities.length > 0) {
        const priorityLabels = rule.priorities.map(pri => {
          const option = filterOptions.priorities.find(opt => opt.value === pri)
          return option ? option.label : pri
        })
        conditions.push(priorityLabels.join(', ') + '置信度')
      }

      if (rule.nsfw !== undefined && rule.nsfw !== null) {
        conditions.push(formatNsfwTooltip(rule.nsfw))
      }

      if (rule.aigc !== undefined && rule.aigc !== null) {
        conditions.push(formatAigcTooltip(rule.aigc))
      }

      const sortVal = rule.sortBy ?? rule.sort_by
      if (sortVal) {
        const sortOption = sortOptions.find(opt => opt.value === sortVal)
        if (sortOption) conditions.push('排序: ' + sortOption.label)
      }

      return conditions.length > 0 ? conditions.join(' • ') : ''
    }

    function getTemplateIconClass(templateId) {
      const iconConfigs = [
        { icon: 'mdi:shield', bgClass: 'bg-blue-100', iconClass: 'text-blue-600' },
        { icon: 'mdi:trending-up', bgClass: 'bg-green-100', iconClass: 'text-green-600' },
        { icon: 'mdi:file-document', bgClass: 'bg-purple-100', iconClass: 'text-purple-600' },
        { icon: 'mdi:chart-line', bgClass: 'bg-amber-100', iconClass: 'text-amber-600' },
        { icon: 'mdi:database', bgClass: 'bg-cyan-100', iconClass: 'text-cyan-600' }
      ]
      const idStr = String(templateId)
      const hash = idStr.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
      const index = Math.abs(hash) % iconConfigs.length
      return iconConfigs[index]
    }

    function getTimeRangeBounds() {
      if (!timeRange.value || timeRange.value === 'all') {
        return { start_at: null, end_at: null }
      }
      const end = new Date()
      let start = new Date()
      if (timeRange.value === '24h') {
        start.setHours(start.getHours() - 24)
      } else if (timeRange.value === '7d') {
        start.setDate(start.getDate() - 7)
      } else if (timeRange.value === '30d') {
        start.setDate(start.getDate() - 30)
      } else if (timeRange.value === 'custom') {
        return { start_at: null, end_at: null }
      } else {
        return { start_at: null, end_at: null }
      }
      return {
        start_at: start.toISOString(),
        end_at: end.toISOString()
      }
    }

    async function performSearch() {
      try {
        loading.value = true
        const { start_at, end_at } = getTimeRangeBounds()
        const params = {
          page: currentPage.value,
          page_size: pageSize.value,
          keywords: searchQuery.value || undefined,
          search_mode: 'keyword',
          sort_by: sortBy.value,
          sort_order: 'desc'
        }

        if (nsfwFilter.value === 0) {
          params.nsfw = false
        } else if (nsfwFilter.value === 2) {
          params.nsfw = true
        }

        if (aigcFilter.value === 0) {
          params.aigc = false
        } else if (aigcFilter.value === 2) {
          params.aigc = true
        }

        if (start_at) params.start_at = start_at
        if (end_at) params.end_at = end_at

        if (categories.value && categories.value.length > 0) {
          params.entity_type = [...categories.value]
        }

        const response = await searchApi.searchEntity(params)

        if (response.code === 0 && response.data) {
          searchResults.value = response.data.items || []
          totalResults.value = response.data.total || 0
          if (searchResults.value.length === 0) {
            ElMessage({
              message: '没有找到相关内容',
              type: 'error',
              duration: 4000
            })
          }
          nextTick(() => {
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
        ElMessage.error('搜索失败，请稍后重试')
        searchResults.value = []
        totalResults.value = 0
      } finally {
        loading.value = false
      }
    }

    function handleSearchFromResults() {
      currentPage.value = 1
      performSearch()
    }

    function initSearchFromQuery() {
      if (route.query.q) {
        searchQuery.value = route.query.q
        currentPage.value = 1
        performSearch()
      }
    }

    function resetFilters() {
      timeRange.value = 'all'
      categories.value = []
      sources.value = []
      priorities.value = []
    }

    function applyFilters() {
      showAdvancedFilters.value = false
      performSearch()
    }

    function applyTemplateFilters(template) {
  if (!canViewApplyTemplate.value) return
  if (!canUseApplyTemplate.value) return void noPerm()
      const rules = template?.rules
      if (!template) return

      const q = template.search_query ?? template.searchQuery
      if (q) {
        searchQuery.value = q
      }

      if (rules) {
        const timeVal = rules.timeRange ?? rules.time_range
        if (timeVal) timeRange.value = timeVal

        const entityTypes = rules.entityType ?? rules.entity_type ?? rules.categories
        if (entityTypes && Array.isArray(entityTypes)) {
          categories.value = [...entityTypes]
        } else {
          categories.value = []
        }

        if (rules.sources && Array.isArray(rules.sources)) {
          sources.value = [...rules.sources]
        } else {
          sources.value = []
        }

        if (rules.priorities && Array.isArray(rules.priorities)) {
          priorities.value = [...rules.priorities]
        } else {
          priorities.value = []
        }

        if (rules.nsfw !== undefined && rules.nsfw !== null) {
          nsfwFilter.value = rules.nsfw
        }

        if (rules.aigc !== undefined && rules.aigc !== null) {
          aigcFilter.value = rules.aigc
        }

        const sortVal = rules.sortBy ?? rules.sort_by
        if (sortVal) sortBy.value = sortVal
      }

      currentPage.value = 1
      performSearch()
      ElMessage.success('已应用模板并开始检索')
    }

    async function toggleHighlight(result) {
      if (!result || !result.uuid) return

      result._highlightLoading = true

      try {
        const isHighlighted = result.is_highlighted
    if (isHighlighted) {
      if (!guardUse(PERM_SEARCH_RESULTS?.unhighlightUse)) return
    } else {
      if (!guardUse(PERM_SEARCH_RESULTS?.highlightUse)) return
    }
        const entityType = result.entity_type?.toLowerCase() || 'article'
        const requestData = isHighlighted
          ? { is_highlighted: false }
          : { is_highlighted: true, highlight_reason: '用户在搜索结果页标记' }

        const response = await highlightApi.setHighlight(entityType, result.uuid, requestData)

        if (response.code === 0) {
          result.is_highlighted = !isHighlighted
          ElMessage.success(isHighlighted ? '已取消重点目标' : '已设置为重点目标')
        } else {
          ElMessage.error(response.message || (isHighlighted ? '取消重点目标失败' : '设置重点目标失败'))
        }
      } catch (err) {
        ElMessage.error('操作失败，请稍后重试')
      } finally {
        result._highlightLoading = false
      }
    }

onMounted(() => {
  initSearchFromQuery()
  loadSearchTemplates()
})
</script>

<style scoped>
.search-highlight :deep(em) {
  font-style: normal;
  color: #dc2626;
  font-weight: 700;
}
</style>
