<template>
  <div>
    <Header />

    <main v-if="isMobile" class="mobile-library">
      <header class="mobile-library__heading"><p>情报与资料</p><h1>资料库</h1><span>从检索发现线索，沉淀重点与专题</span></header>
      <nav class="mobile-library__entries" aria-label="资料入口">
        <button v-for="entry in mobileEntries" :key="entry.path" :disabled="!hasPerm(entry.permission.access)" @click="router.push(entry.path)">
          <Icon :icon="entry.icon" /><strong>{{ entry.label === '专题' ? '专题 Wiki' : entry.label === '重点' ? '重点实体' : entry.label === '证据' ? '证据链' : '情报检索' }}</strong><span>{{ entryDescriptions[entry.path] }}</span><Icon icon="mdi:arrow-top-right" class="mobile-library__entry-arrow" />
        </button>
      </nav>
      <section v-if="hasPerm(PERM.pages.target.highlights.visible)" class="mobile-library__recent" aria-labelledby="library-recent-title">
        <div class="mobile-library__section-title"><div><h2 id="library-recent-title">近期重点资料</h2><p>按原文编辑时间排序</p></div><router-link v-if="hasPerm(PERM.pages.target.highlights.access)" to="/target/highlights">查看全部<Icon icon="mdi:chevron-right" /></router-link></div>
        <div v-if="!canPreview" class="mobile-library__state" role="status">暂无查阅重点资料的权限</div>
        <div v-else-if="highlightError" class="mobile-library__state" role="alert"><Icon icon="mdi:cloud-alert-outline" /><p>{{ highlightError }}</p><el-button @click="loadHighlightPreview">重新加载</el-button></div>
        <div v-else-if="highlightLoading && !highlightItems.length" class="mobile-library__state" role="status"><el-skeleton :rows="5" animated /><p>正在加载重点资料…</p></div>
        <div v-else-if="!highlightLoading && !highlightItems.length" class="mobile-library__state" role="status"><Icon icon="mdi:star-outline" /><p>还没有重点资料</p><span>在检索结果或正文页标记重点，方便下次继续阅读。</span></div>
        <div v-else class="mobile-library__list" :aria-busy="highlightLoading"><MobileHighlightCard v-for="entity in highlightItems" :key="`${entity.entity_type}:${entity.uuid}`" :entity="entity" /></div>
      </section>
    </main>
    <template v-else>
    <!-- 英雄区域 -->
     <!-- TODO: 暂时的占位页面，内容还需要进一步调整 -->
    <section class="bg-linear-to-br from-blue-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">目标</span>管理中心</h1>
            <p class="text-gray-600 text-lg mb-6">统一管理情报收集目标，从目标设定、优先级分配到执行跟踪的全流程管理平台。</p>
            <div class="flex flex-wrap gap-4">
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:target" class="text-blue-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">活跃目标</p>
                  <p class="text-xl font-bold text-gray-900">24</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:check-circle" class="text-green-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">已完成目标</p>
                  <p class="text-xl font-bold text-gray-900">87</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:progress-clock" class="text-amber-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">进行中目标</p>
                  <p class="text-xl font-bold text-gray-900">15</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">快速创建目标</h3>
            <div class="space-y-4">
              <button class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2" @click="router.push('/platforms')">
                <Icon icon="mdi:database-search" />
                <span>目标平台管理</span>
              </button>
              <button class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2" @click="router.push('/target/wiki')">
                <Icon icon="mdi:clipboard-text-search-outline" />
                <span>专题事件管理</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2" @click="router.push('/target/highlights')">
                <Icon icon="mdi:tag-multiple" />
                <span>重点实体库</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 目标列表区域：与重点实体库同源，展示前 6 条 -->
    <section class="py-12 bg-linear-to-b from-white to-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:format-list-bulleted" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">重点</span>实体</span>
          </h2>
        </div>

        <div
          v-loading="highlightLoading"
          element-loading-text="加载中..."
          class="min-h-50"
        >
          <div
            v-if="!highlightLoading && highlightItems.length === 0"
            class="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-gray-200 bg-white/80"
          >
            <Icon icon="mdi:star-off-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">暂无重点实体</p>
            <p class="text-gray-400 text-sm text-center max-w-md">
              在检索结果或详情页中将实体标记为重点后，会在此展示。也可通过上方「重点实体库」进入完整列表。
            </p>
          </div>

          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div
              v-for="result in highlightItems"
              :key="result.uuid"
              class="bg-white rounded-xl p-4 border border-gray-200 hover:shadow-lg transition-all flex flex-col"
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
                <router-link
                  :to="getDetailRoute(result.entity_type, result.uuid)"
                  class="hover:text-blue-600 transition-colors"
                >
                  {{ result.title || '无标题' }}
                </router-link>
              </h3>
              <p class="text-gray-600 text-sm mb-3 flex-1">
                {{ truncateContent(result.clean_content, 200) || '暂无分析内容' }}
              </p>
              <div class="space-y-1.5 text-sm text-gray-500 mt-auto mb-3">
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:source-repository" class="text-blue-500 shrink-0" />
                  <router-link
                    v-if="result.platform_id"
                    :to="`/details/platform/${result.platform_id}`"
                    class="text-blue-600 hover:underline truncate"
                  >
                    {{ result.platform || '—' }}
                  </router-link>
                  <span v-else>{{ result.platform || '—' }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:calendar" class="text-purple-500 shrink-0" />
                  <span>{{ formatHighlightDate(result.update_at) }}</span>
                </div>
              </div>
              <div class="pt-3 border-t border-gray-200 flex justify-center">
                <router-link
                  :to="getDetailRoute(result.entity_type, result.uuid)"
                  class="text-blue-600 hover:text-blue-800 flex items-center text-sm font-medium"
                >
                  <Icon icon="mdi:eye" class="mr-1" />
                  查看详情
                </router-link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 目标分类统计 -->
    <section class="py-12 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:chart-bar" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">目标</span>分类统计</span>
          </h2>
          <el-radio-group v-model="statsTimeRange" size="small">
            <el-radio-button label="week">本周</el-radio-button>
            <el-radio-button label="month">本月</el-radio-button>
            <el-radio-button label="year">本年</el-radio-button>
          </el-radio-group>
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b border-gray-200 bg-gray-50">
                  <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">目标类型</th>
                  <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">数量</th>
                  <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">完成率</th>
                  <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">变化趋势</th>
                  <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">平均周期</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="stat in targetStats" 
                  :key="stat.type" 
                  class="border-b border-gray-100 hover:bg-gray-50"
                >
                  <td class="py-3 px-4">
                    <div class="flex items-center">
                      <div :class="['w-2 h-2 rounded-full mr-2', stat.colorClass]"></div>
                      <span class="font-medium">{{ stat.type }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4">{{ stat.count }}</td>
                  <td class="py-3 px-4">
                    <div class="flex items-center">
                      <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden mr-2" style="max-width: 100px">
                        <div 
                          class="h-full bg-blue-500 rounded-full"
                          :style="{ width: stat.completionRate }"
                        ></div>
                      </div>
                      <span class="text-sm">{{ stat.completionRate }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4">
                    <div :class="['flex items-center', stat.trendClass]">
                      <Icon :icon="stat.trendIcon" />
                      <span class="ml-1">{{ stat.trend }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4">{{ stat.avgCycle }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 目标优先级分布 -->
    <section class="py-12 bg-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:priority-high" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">优先级</span>分布</span>
          </h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-linear-to-br from-red-50 to-white rounded-2xl p-6 border border-red-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-red-500 to-pink-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:alert-octagon" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">高优先级</h3>
                  <p class="text-sm text-gray-500">紧急重要目标</p>
                </div>
              </div>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">目标数量</span>
                  <span class="font-medium">8 个</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-red-500 rounded-full" style="width: 33%"></div>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 pt-3">
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">进行中</p>
                  <p class="text-lg font-bold text-gray-900">5</p>
                </div>
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">待启动</p>
                  <p class="text-lg font-bold text-gray-900">3</p>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-linear-to-br from-amber-50 to-white rounded-2xl p-6 border border-amber-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-amber-500 to-orange-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:alert" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">中优先级</h3>
                  <p class="text-sm text-gray-500">重要常规目标</p>
                </div>
              </div>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">目标数量</span>
                  <span class="font-medium">11 个</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-amber-500 rounded-full" style="width: 46%"></div>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 pt-3">
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">进行中</p>
                  <p class="text-lg font-bold text-gray-900">7</p>
                </div>
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">待启动</p>
                  <p class="text-lg font-bold text-gray-900">4</p>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 border border-blue-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:information" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">低优先级</h3>
                  <p class="text-sm text-gray-500">常规监控目标</p>
                </div>
              </div>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">目标数量</span>
                  <span class="font-medium">5 个</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-blue-500 rounded-full" style="width: 21%"></div>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 pt-3">
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">进行中</p>
                  <p class="text-lg font-bold text-gray-900">3</p>
                </div>
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">待启动</p>
                  <p class="text-lg font-bold text-gray-900">2</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Header from '@/components/Header.vue'
import { Icon } from '@iconify/vue'
import { searchApi } from '@/api/search'
import { formatDateTime as formatDateTimeUtil } from '@/utils/action/formatters'
import MobileHighlightCard from '@/components/target/MobileHighlightCard.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm, hasAll } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { KNOWLEDGE_DESTINATIONS } from '@/utils/knowledgeNavigation'

defineOptions({ name: 'TargetManagement' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const mobileEntries = computed(() => KNOWLEDGE_DESTINATIONS.filter(entry => hasPerm(entry.permission.visible)))
const entryDescriptions = { '/search': '搜索全部情报材料', '/target/highlights': '继续阅读重要线索', '/target/wiki': '查阅专题与引用', '/evidence/chains': '追溯材料之间的关联' }
const canPreview = computed(() => hasAll([PERM.pages.target.access, PERM.pages.target.highlights.visible, PERM.pages.target.highlights.access, PERM.operations.search.entity.execute]))
const statsTimeRange = ref('week')
const highlightLoading = ref(false)
const highlightItems = ref([])
const highlightError = ref('')
let previewSequence = 0
let active = true

function formatHighlightDate(val) {
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

function getDetailRoute(entityType, uuid) {
  return `/details/${entityType}/${uuid}`
}

/**
 * 获取真实重点材料预览，返回资料入口时刷新且忽略过期响应。
 * @returns {Promise<void>} 更新当前预览或显示可重试的错误状态。
 */
async function loadHighlightPreview() {
  if (!active) return
  const sequence = ++previewSequence
  if (!canPreview.value) {
    highlightItems.value = []
    highlightLoading.value = false
    return
  }
  try {
    highlightLoading.value = true
    highlightError.value = ''
    const params = {
      page: 1,
      page_size: 6,
      is_highlighted: true,
      search_mode: 'keyword',
      sort_by: 'time',
      sort_order: 'desc'
    }
    const response = await searchApi.searchEntity(params)
    if (!active || sequence !== previewSequence) return
    if (response?.code !== 0 || !response.data) throw new Error('重点资料加载失败')
    highlightItems.value = response.data.items || []
  } catch (err) {
    if (!active || sequence !== previewSequence) return
    console.error('加载重点实体预览失败:', err)
    highlightError.value = '重点资料加载失败，请重试'
    if (!isMobile.value) ElMessage.error('重点实体加载失败，请稍后重试')
    highlightItems.value = []
  } finally {
    if (sequence === previewSequence) highlightLoading.value = false
  }
}

onMounted(loadHighlightPreview)
onActivated(() => { if (!active) { active = true; return loadHighlightPreview() } })
onDeactivated(() => { active = false; previewSequence++; highlightLoading.value = false })
onBeforeUnmount(() => { active = false; previewSequence++ })
watch(canPreview, () => { if (active) loadHighlightPreview() })
const targetStats = ref([
        {
          type: '网络安全',
          count: '42',
          completionRate: '78%',
          trend: '+5.2%',
          avgCycle: '7天',
          colorClass: 'bg-blue-500',
          trendClass: 'text-green-600',
          trendIcon: 'mdi:trending-up'
        },
        {
          type: '市场情报',
          count: '35',
          completionRate: '65%',
          trend: '+3.8%',
          avgCycle: '10天',
          colorClass: 'bg-green-500',
          trendClass: 'text-green-600',
          trendIcon: 'mdi:trending-up'
        },
        {
          type: '技术研发',
          count: '28',
          completionRate: '82%',
          trend: '-2.1%',
          avgCycle: '14天',
          colorClass: 'bg-purple-500',
          trendClass: 'text-red-600',
          trendIcon: 'mdi:trending-down'
        },
        {
          type: '政策法规',
          count: '18',
          completionRate: '92%',
          trend: '+1.5%',
          avgCycle: '5天',
          colorClass: 'bg-amber-500',
          trendClass: 'text-green-600',
          trendIcon: 'mdi:trending-up'
        }
      ])
</script>

<style scoped>
.mobile-library { max-width: 767px; margin: auto; padding: 24px 16px 16px; }
.mobile-library__heading { margin-bottom: 24px; }
.mobile-library__heading > p { margin: 0 0 8px; color: #2563eb; font-size: 12px; font-weight: 600; }
.mobile-library__heading h1 { margin: 0 0 8px; font-size: 28px; line-height: 1.3; color: #0f172a; font-weight: 750; }
.mobile-library__heading > span { font-size: 13px; color: #64748b; }
.mobile-library__entries { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.mobile-library__entries button { position: relative; display: flex; flex-direction: column; align-items: flex-start; min-width: 0; padding: 16px 12px; text-align: left; background: white; border: 1px solid #e2e8f0; border-radius: 16px; }
.mobile-library__entries button > svg:first-child { color: #2563eb; font-size: 24px; margin-bottom: 12px; }
.mobile-library__entries strong { font-size: 15px; color: #0f172a; margin-bottom: 5px; }
.mobile-library__entries span { font-size: 11px; line-height: 1.6; color: #64748b; overflow-wrap: anywhere; }
.mobile-library__entry-arrow { position: absolute; right: 12px; top: 17px; color: #94a3b8; font-size: 16px; }
.mobile-library__entries button:disabled { opacity: .45; }
.mobile-library__entries button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.mobile-library__recent { margin-top: 28px; }
.mobile-library__section-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 16px; }
.mobile-library__section-title h2 { color: #0f172a; font-size: 17px; font-weight: 700; margin: 0; }
.mobile-library__section-title p { margin: 5px 0 0; color: #94a3b8; font-size: 12px; }
.mobile-library__section-title a { display: flex; align-items: center; min-height: 44px; color: #2563eb; font-size: 12px; white-space: nowrap; }
.mobile-library__state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 28px 16px; color: #64748b; font-size: 14px; text-align: center; border: 1px solid #e2e8f0; border-radius: 16px; background: white; }
.mobile-library__state > svg { color: #94a3b8; font-size: 34px; }
.mobile-library__state span { font-size: 12px; line-height: 1.7; }
.mobile-library__list { display: grid; gap: 12px; }
.mobile-library__list[aria-busy=true] { opacity: .6; }
</style>

