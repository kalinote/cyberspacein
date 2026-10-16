<template>
  <main class="mobile-platform-detail">
    <router-link to="/platforms" class="platform-back"><Icon icon="mdi:chevron-left" />平台列表</router-link>
    <div v-if="!hasPerm(PERM.operations.content.platform.read)" class="platform-state">暂无平台读取权限</div>
    <div v-else-if="error" class="platform-state" role="alert"><p>{{ error }}</p><el-button @click="$emit('retry')">重新加载</el-button></div>
    <div v-else-if="loading" class="platform-state" aria-live="polite">正在加载平台资料…</div>
    <template v-else>
      <header class="platform-identity">
        <img v-if="platform.logo" :src="getCosUrl(platform.logo)" alt="" /><Icon v-else icon="mdi:web" class="platform-logo" />
        <div><h1>{{ platform.name || '平台详情' }}</h1><p>{{ [platform.category, platform.subCategory].filter(Boolean).join(' · ') || '未分类' }}</p></div>
      </header>
      <div class="platform-tags"><el-tag :type="platform.status === '活跃' ? 'success' : 'info'">{{ platform.status || '状态未设置' }}</el-tag><el-tag type="info">{{ platform.type === 'forum' ? '论坛' : platform.type === 'article' ? '文章' : platform.type }}</el-tag><el-tag type="info">{{ platform.netType || '网络未设置' }}</el-tag></div>
      <nav class="platform-tabs" aria-label="平台详情分区"><button :class="{ active: tab === 'overview' }" :aria-pressed="tab === 'overview'" @click="tab = 'overview'">平台概览</button><button :class="{ active: tab === 'intelligence' }" :aria-pressed="tab === 'intelligence'" @click="tab = 'intelligence'">关联情报</button></nav>
      <div v-show="tab === 'overview'">
        <section class="platform-section"><h2>平台资料</h2><p class="platform-description">{{ platform.description || '暂无平台描述' }}</p><a v-if="externalUrl" :href="externalUrl" target="_blank" rel="noopener noreferrer" class="platform-external"><Icon icon="mdi:open-in-new" />访问平台<span>{{ platform.url }}</span></a><p v-else-if="platform.url" class="platform-description">{{ platform.url }}</p>
          <details class="platform-details"><summary>分类、标签与采集信息</summary><dl><dt>子分类</dt><dd>{{ platform.subCategory || '未设置' }}</dd><dt>信任度</dt><dd>{{ platform.confidence == null ? '未设置' : platform.confidence }}</dd><dt>爬虫名称</dt><dd>{{ platform.spiderName || '未设置' }}</dd><dt>创建时间</dt><dd>{{ platform.createdAt || '—' }}</dd><dt>更新时间</dt><dd>{{ platform.updatedAt || '—' }}</dd><dt>平台 ID</dt><dd>{{ platform.uuid || '—' }}</dd></dl><h3>标签</h3><div class="platform-tags"><el-tag v-for="tag in platform.tags" :key="tag" type="info" effect="plain">{{ tag }}</el-tag><span v-if="!platform.tags?.length">暂无标签</span></div><h3>板块</h3><div class="platform-tags"><el-tag v-for="section in platform.sections" :key="section" type="info" effect="plain">{{ section }}</el-tag><span v-if="!platform.sections?.length">暂无板块</span></div></details>
        </section>
        <section class="platform-section"><div class="platform-section-heading"><h2>新增数据趋势</h2><el-select :model-value="range" aria-label="趋势统计范围" class="platform-range" @update:model-value="$emit('range-change', $event)"><el-option label="近 30 天" value="trend30d" /><el-option label="近 90 天" value="trend90d" /><el-option label="近 12 月" value="trend1y" /></el-select></div>
          <div v-if="trendLoading" class="platform-state">正在加载趋势…</div><div v-else-if="trendError" class="platform-state" role="alert"><p>{{ trendError }}</p><el-button @click="$emit('retry-trend')">重新加载</el-button></div>
          <template v-else><div class="platform-metrics"><div><strong>{{ trendTotal.toLocaleString() }}</strong><span>所选范围新增</span></div><div><strong>{{ daily }}</strong><span>日均新增</span></div><div><strong>{{ change }}</strong><span>趋势变化率</span></div></div><svg v-if="buckets.length" viewBox="0 0 280 88" role="img" aria-label="所选范围新增数量趋势" class="platform-spark"><line x1="0" y1="80" x2="280" y2="80" stroke="#e2e8f0" /><polyline :points="sparkPoints" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" /></svg><el-empty v-else description="暂无趋势数据" :image-size="45" /><button v-if="buckets.length" class="platform-text-button" @click="trendSheet = true">查看各期新增数量 <Icon icon="mdi:chevron-right" /></button></template>
        </section>
      </div>
      <section v-show="tab === 'intelligence'" class="platform-section platform-intelligence">
        <div class="platform-section-heading"><h2>关联情报 <span v-if="hasPerm(PERM.operations.search.entity.execute)">{{ total }}</span></h2><el-button :disabled="!hasPerm(PERM.operations.search.entity.execute)" @click="sortSheet = true"><Icon icon="mdi:sort" />排序</el-button></div>
        <div v-if="!hasPerm(PERM.operations.search.entity.execute)" class="platform-state">暂无情报搜索权限</div><div v-else-if="intelligenceError" class="platform-state" role="alert"><p>{{ intelligenceError }}</p><el-button @click="$emit('retry-intelligence')">重新加载</el-button></div><div v-else v-loading="intelligenceLoading" class="platform-intelligence-list"><el-empty v-if="!intelligenceLoading && !intelligence.length" description="暂无关联情报" :image-size="54" />
          <article v-for="item in intelligence" :key="item.uuid" class="platform-intelligence-card"><div class="platform-tags"><el-tag v-if="item.section" size="small">{{ item.section }}</el-tag><el-tag v-if="item.nsfw" size="small" type="danger">NSFW</el-tag><span>{{ formatDateTime(item.update_at) }}</span></div><h3>{{ plainText(item.title) || '未命名情报' }}</h3><p>{{ plainText(item.clean_content).slice(0, 160) || '暂无分析内容' }}</p><div class="platform-intelligence-actions"><el-button :disabled="!hasPerm(PERM.operations.target.highlight.update)" :loading="item._highlightLoading" @click="$emit('highlight', item)"><Icon :icon="item.is_highlighted ? 'mdi:star' : 'mdi:star-outline'" />{{ item.is_highlighted ? '取消重点' : '设为重点' }}</el-button><el-button type="primary" plain :disabled="!canReadEntity(item)" @click="router.push(`/details/${String(item.entity_type).toLowerCase()}/${item.uuid}`)">查看情报</el-button></div></article>
        </div><div v-if="!intelligenceError && total > pageSize" class="platform-pagination"><el-pagination :current-page="page" :page-size="pageSize" :total="total" :pager-count="5" layout="prev, pager, next" @current-change="$emit('page-change', $event)" /></div>
      </section>
    </template>
    <MobileSheet v-model="sortSheet" title="情报排序"><div class="platform-sort-options"><el-button v-for="option in [{ value: 'relevance', label: '相关性优先' }, { value: 'time', label: '时间最新' }, { value: 'priority', label: '优先级最高' }]" :key="option.value" :type="sort === option.value ? 'primary' : ''" @click="$emit('sort-change', option.value); sortSheet = false">{{ option.label }}</el-button></div></MobileSheet>
    <MobileSheet v-model="trendSheet" title="各期新增数量"><div v-for="bucket in buckets" :key="bucket.label" class="platform-trend-row"><span>{{ bucket.label }}</span><strong>{{ bucket.value.toLocaleString() }} 条</strong></div></MobileSheet>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { getCosUrl } from '@/utils/cos'
import { formatDateTime } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

const props = defineProps({ platform: { type: Object, required: true }, loading: Boolean, error: String, range: String, buckets: { type: Array, default: () => [] }, trendLoading: Boolean, trendError: String, daily: String, change: String, intelligence: { type: Array, default: () => [] }, intelligenceLoading: Boolean, intelligenceError: String, sort: String, page: Number, pageSize: Number, total: Number })
defineEmits(['retry', 'range-change', 'retry-trend', 'retry-intelligence', 'sort-change', 'page-change', 'highlight'])
const router = useRouter()
const tab = ref('overview')
const sortSheet = ref(false)
const trendSheet = ref(false)
const trendTotal = computed(() => props.buckets.reduce((total, bucket) => total + bucket.value, 0))
const sparkPoints = computed(() => {
  const max = Math.max(1, ...props.buckets.map(bucket => bucket.value))
  return props.buckets.map((bucket, index) => `${props.buckets.length === 1 ? 140 : index * 280 / (props.buckets.length - 1)},${80 - bucket.value * 70 / max}`).join(' ')
})
const externalUrl = computed(() => {
  try { const url = new URL(props.platform.url); return ['http:', 'https:'].includes(url.protocol) ? url.href : '' } catch { return '' }
})
watch(() => props.platform.uuid, () => { tab.value = 'overview'; sortSheet.value = false; trendSheet.value = false })

/** """去除检索高亮标签，以纯文本显示移动情报摘要。""" */
function plainText(value) {
  const document = new DOMParser().parseFromString(String(value || ''), 'text/html')
  return document.body.textContent || ''
}
/** """只为可读取的已知实体类型开放情报详情入口。""" */
function canReadEntity(item) {
  const type = String(item.entity_type || '').toLowerCase()
  return Boolean(item.uuid && ['article', 'forum'].includes(type) && hasPerm(PERM.pages.search.access) && hasPerm(PERM.operations.content[type].read))
}
</script>

<style scoped>
.mobile-platform-detail { padding: 12px 12px 24px; background: #f8fafc; min-height: 80vh; color: #0f172a; overflow-wrap: anywhere; }
.platform-back { display: inline-flex; align-items: center; min-height: 44px; gap: 4px; color: #475569; font-size: 14px; }
.platform-identity { display: flex; align-items: center; gap: 12px; margin: 10px 0 14px; }
.platform-identity img, .platform-logo { width: 48px; height: 48px; object-fit: contain; flex-shrink: 0; color: #2563eb; }
.platform-identity div { min-width: 0; }.platform-identity h1 { margin: 0; font-size: 22px; font-weight: 750; }.platform-identity p { margin: 5px 0 0; color: #64748b; font-size: 13px; }
.platform-tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; color: #64748b; }.platform-tags :deep(.el-tag) { max-width: 100%; white-space: normal; height: auto; min-height: 24px; }
.platform-tabs { display: flex; padding: 4px; background: #e2e8f0; border-radius: 12px; margin: 20px 0 14px; }.platform-tabs button { flex: 1; min-height: 44px; color: #475569; border-radius: 9px; }.platform-tabs button.active { background: white; color: #1d4ed8; font-weight: 650; }
.platform-section { padding: 16px; background: white; border: 1px solid #e2e8f0; border-radius: 16px; margin-bottom: 14px; min-width: 0; }.platform-section h2 { font-size: 16px; font-weight: 700; margin: 0; }.platform-section h3 { font-size: 14px; font-weight: 650; margin: 14px 0 8px; }.platform-section-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }.platform-section-heading h2 span { color: #64748b; font-size: 13px; font-weight: normal; }
.platform-description { white-space: pre-wrap; line-height: 1.7; font-size: 14px; color: #475569; margin: 12px 0; }.platform-external { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: #2563eb; font-size: 14px; padding: 8px 0; min-height: 44px; }.platform-external span { flex-basis: 100%; font-size: 12px; color: #64748b; }.platform-details summary { padding: 14px 0; font-size: 14px; cursor: pointer; border-top: 1px solid #f1f5f9; margin-top: 12px; }.platform-details dl { display: grid; grid-template-columns: 68px minmax(0, 1fr); gap: 12px 8px; font-size: 13px; }.platform-details dt { color: #64748b; }.platform-details dd { margin: 0; }
.platform-range { width: 116px; flex-shrink: 0; }.platform-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin: 20px 0 8px; }.platform-metrics strong, .platform-metrics span { display: block; }.platform-metrics strong { font-size: 17px; }.platform-metrics span { font-size: 11px; color: #64748b; margin-top: 5px; }.platform-spark { width: 100%; height: auto; margin-top: 8px; }.platform-text-button { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 44px; font-size: 13px; color: #2563eb; }.platform-state { padding: 25px 8px; text-align: center; color: #64748b; font-size: 14px; }.platform-state p { margin-bottom: 14px; }
.platform-intelligence-list { min-height: 120px; }.platform-intelligence-card { padding: 18px 0; border-bottom: 1px solid #e2e8f0; }.platform-intelligence-card h3 { font-size: 16px; margin: 10px 0; }.platform-intelligence-card > p { color: #64748b; font-size: 13px; line-height: 1.7; }.platform-intelligence-actions { display: flex; gap: 8px; margin-top: 12px; }.platform-intelligence-actions .el-button { flex: 1; margin: 0; min-width: 0; }.platform-pagination { display: flex; justify-content: center; margin-top: 18px; }
.mobile-platform-detail :deep(.el-button), .mobile-platform-detail :deep(.el-select__wrapper) { min-height: 44px; }.platform-sort-options { display: grid; gap: 10px; }.platform-sort-options .el-button { margin: 0; min-height: 44px; }.platform-trend-row { display: flex; justify-content: space-between; padding: 13px 0; border-bottom: 1px solid #e2e8f0; font-size: 14px; }
</style>
