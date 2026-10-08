<template>
  <main class="mobile-workbench">
    <header class="workbench-heading">
      <div><p>今天需要关注</p><h1>{{ auth.user?.display_name || auth.user?.username || '我的' }}工作台</h1></div>
      <el-button circle :loading="loading" aria-label="刷新工作台" @click="refresh"><Icon icon="mdi:refresh" /></el-button>
    </header>

    <nav class="workbench-shortcuts" aria-label="工作台快捷入口">
      <button v-if="hasPerm(PERM.pages.search.visible)" type="button" :disabled="!hasPerm(PERM.pages.search.access)" @click="router.push('/search')"><Icon icon="mdi:magnify" />检索情报</button>
      <button v-if="hasPerm(PERM.pages.agent.visible)" type="button" :disabled="!hasPerm(PERM.pages.agent.access)" @click="router.push('/agent')"><Icon icon="mdi:creation-outline" />发起分析</button>
      <button v-if="hasPerm(PERM.pages.action.tasks.visible)" type="button" :disabled="!hasPerm(PERM.pages.action.tasks.access)" @click="router.push('/action/tasks')"><Icon icon="mdi:calendar-check-outline" />计划任务</button>
    </nav>

    <div class="workbench-totals">
      <router-link v-if="canAlerts" to="/alert"><strong>{{ alerts.data ? alerts.data.pending : '—' }}</strong><span>待处理告警</span></router-link>
      <router-link v-if="canActions" to="/action/history"><strong>{{ actions.data ? actions.data.running : '—' }}</strong><span>运行中的行动</span></router-link>
      <router-link v-if="canSessions" to="/agent/sessions"><strong>{{ sessions.data ? sessions.data.pending : '—' }}</strong><span>待审批会话</span></router-link>
    </div>

    <section v-if="canAlerts" class="workbench-section" aria-labelledby="workbench-alert-title">
      <div class="section-heading"><h2 id="workbench-alert-title">待处理告警</h2><router-link to="/alert">查看全部<Icon icon="mdi:chevron-right" /></router-link></div>
      <p v-if="alerts.error" class="section-error" role="status">告警加载失败，请刷新重试。</p>
      <p v-else-if="!alerts.data" class="section-empty">正在加载告警…</p>
      <template v-else>
        <p class="section-caption">{{ alerts.data.firing }} 条待确认 · {{ alerts.data.acknowledged }} 条跟进中</p>
        <router-link v-for="item in alerts.data.items" :key="item.id" class="workbench-row" :to="{ path: '/alert', query: { alert_id: String(item.id) } }">
          <div class="row-heading"><span class="row-title">{{ item.title || item.resource_name || '告警事件' }}</span><el-tag size="small" :type="['critical', 'error'].includes(item.current_severity) ? 'danger' : 'warning'">{{ severityLabels[item.current_severity] || item.current_severity || '告警' }}</el-tag></div>
          <p>{{ item.detail || item.resource_name || item.source_key }}</p>
          <span class="row-meta">{{ item.status === 'acknowledged' ? '已确认，等待处理' : '待确认' }} · {{ formatTime(item.last_triggered_at || item.triggered_at) }}</span>
        </router-link>
        <p v-if="!alerts.data.items.length" class="section-empty">当前没有待处理告警</p>
      </template>
    </section>

    <section v-if="canActions" class="workbench-section" aria-labelledby="workbench-action-title">
      <div class="section-heading"><h2 id="workbench-action-title">行动任务</h2><router-link to="/action/history">查看全部<Icon icon="mdi:chevron-right" /></router-link></div>
      <p v-if="actions.error" class="section-error" role="status">行动加载失败，请刷新重试。</p>
      <p v-else-if="!actions.data" class="section-empty">正在加载行动…</p>
      <template v-else>
        <p class="section-caption">{{ actions.data.running }} 项运行中 · {{ actions.data.failed }} 项失败或超时 · {{ actions.data.partial }} 项部分完成</p>
        <button v-for="item in actions.data.items" :key="item.id" class="workbench-row" :disabled="!canActionDetail" @click="router.push({ name: 'action-detail', params: { id: item.id } })">
          <div class="row-heading"><span class="row-title">{{ item.name || '行动任务' }}</span><el-tag size="small" :type="getStatusTagType(item.status)">{{ getStatusText(item.status) }}</el-tag></div>
          <el-progress v-if="item.status === 'running'" :percentage="Math.max(0, Math.min(100, Number(item.progress) || 0))" :stroke-width="5" />
          <span class="row-meta">{{ item.completed_steps || 0 }}/{{ item.total_steps || 0 }} 步 · {{ formatTime(item.start_at || item.created_at) }}</span>
        </button>
        <p v-if="!actions.data.items.length" class="section-empty">暂无行动任务</p>
        <p v-else class="section-caption">优先显示运行任务，随后显示最近行动</p>
      </template>
    </section>

    <section v-if="canSessions" class="workbench-section" aria-labelledby="workbench-session-title">
      <div class="section-heading"><h2 id="workbench-session-title">会话与审批</h2><router-link to="/agent/sessions">查看全部<Icon icon="mdi:chevron-right" /></router-link></div>
      <p v-if="sessions.error" class="section-error" role="status">会话加载失败，请刷新重试。</p>
      <p v-else-if="!sessions.data" class="section-empty">正在加载会话…</p>
      <template v-else>
        <p v-if="sessions.data.pending" class="section-caption">{{ sessions.data.pending }} 个会话等待审批</p>
        <button v-for="item in sessions.data.items" :key="item.id" class="workbench-row" :disabled="!canSessionDetail || !item.agent_id" @click="router.push({ name: 'agent-analysis-detail', params: { sessionId: item.id }, query: { agent_id: item.agent_id } })">
          <div class="row-heading"><span class="row-title">{{ item.agent_name || '分析会话' }}</span><el-tag size="small" :type="getAgentSessionStatusTagType(item.status)">{{ getAgentSessionStatusLabel(item.status) }}</el-tag></div>
          <p v-if="item.error_message">{{ item.error_message }}</p>
          <span class="row-meta">{{ String(item.id).slice(0, 12) }} · {{ formatTime(item.updated_at || item.created_at) }}</span>
        </button>
        <p v-if="!sessions.data.items.length" class="section-empty">暂无分析会话</p>
      </template>
    </section>

    <section class="workbench-section" aria-labelledby="workbench-recent-title">
      <div class="section-heading"><h2 id="workbench-recent-title">最近访问</h2><el-button v-if="recentVisits.length" text @click="clearRecentVisits">清空</el-button></div>
      <router-link v-for="item in recentVisits" :key="item.key" :to="{ name: item.name, params: item.params, query: item.query }" class="workbench-row recent-row">
        <div><span class="row-meta">{{ item.label }}</span><p class="recent-title">{{ item.title }}</p></div><Icon icon="mdi:chevron-right" />
      </router-link>
      <p v-if="!recentVisits.length" class="section-empty">阅读情报、查看任务或会话后，可从这里继续</p>
    </section>
    <p class="workbench-updated">{{ updatedAt ? `更新于 ${updatedAt}` : '工作台仅显示你有权限查看的内容' }}</p>
  </main>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { alertApi } from '@/api/alert'
import { actionApi } from '@/api/action'
import { agentApi } from '@/api/agent'
import { getAuthState } from '@/stores/auth'
import { clearRecentVisits, recentVisits } from '@/stores/recentVisits'
import { hasAll, hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { getStatusTagType, getStatusText } from '@/utils/action/status'
import { getAgentSessionStatusLabel, getAgentSessionStatusTagType } from '@/utils/agent/sessionStatus'

const props = defineProps({ active: { type: Boolean, default: true } })
const router = useRouter()
const auth = getAuthState()
const canAlerts = computed(() => hasAll([PERM.pages.system.alert.visible, PERM.pages.system.alert.access, PERM.operations.alert.instance.read]))
const canActions = computed(() => hasAll([PERM.pages.action.history.visible, PERM.pages.action.history.access, PERM.operations.action.instance.read]))
const canSessions = computed(() => hasAll([PERM.pages.agent.sessions.visible, PERM.pages.agent.sessions.access, PERM.operations.agent.session.read]))
const canActionDetail = computed(() => hasAll([PERM.pages.action.detail.access, PERM.operations.action.instance.read]))
const canSessionDetail = computed(() => hasAll([PERM.pages.agent.analysis.access, PERM.operations.agent.session.read]))
const alerts = reactive({ data: null, error: false })
const actions = reactive({ data: null, error: false })
const sessions = reactive({ data: null, error: false })
const loading = ref(false)
const updatedAt = ref('')
const severityLabels = { critical: '致命', error: '严重', warning: '重要', info: '一般' }
let active = false
let timer = null
let generation = 0

/** """将统一响应与分页响应还原为工作台数据，保留失败状态。""" */
function payload(response) {
  const data = response?.code === 0 ? response.data : response
  if (!data || typeof data !== 'object' || (typeof response?.code === 'number' && response.code !== 0)) throw new Error('工作台数据不可用')
  return data
}

/** """将接口时间格式化为手机上的简短本地时间。""" */
function formatTime(value) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/**
 * 独立刷新各工作台区块，离页、权限变化或新请求后丢弃旧响应。
 * @returns {Promise<void>} 所有授权区块刷新结束。
 */
async function refresh() {
  if (!active) return
  const requestId = ++generation
  loading.value = true
  const jobs = []
  if (canAlerts.value) jobs.push({
    state: alerts,
    request: Promise.all([alertApi.getStats({ silent: true }), alertApi.getInstances({ page: 1, page_size: 3, status: 'firing' }, { silent: true }), alertApi.getInstances({ page: 1, page_size: 3, status: 'acknowledged' }, { silent: true })]),
    select: ([stats, firing, acknowledged]) => {
      const summary = payload(stats)
      return { firing: summary.firing || 0, acknowledged: summary.acknowledged || 0, pending: (summary.firing || 0) + (summary.acknowledged || 0), items: [...(payload(firing).items || []), ...(payload(acknowledged).items || [])].slice(0, 3) }
    },
  })
  if (canActions.value) jobs.push({
    state: actions,
    request: Promise.all([actionApi.getActionHistorySummary({ silent: true }), actionApi.getActionHistory({ page: 1, page_size: 3, status: 'running' }, { silent: true }), actionApi.getActionHistory({ page: 1, page_size: 3 }, { silent: true })]),
    select: ([summaryResponse, running, recent]) => {
      const summary = payload(summaryResponse)
      const items = [...new Map([...(payload(running).items || []), ...(payload(recent).items || [])].map(item => [item.id, item])).values()].slice(0, 4)
      return { running: summary.running || 0, failed: summary.failed || 0, partial: summary.partially_completed || 0, items }
    },
  })
  if (canSessions.value) jobs.push({
    state: sessions,
    request: Promise.all([agentApi.getAgentSessionList({ page: 1, page_size: 3, status: 'awaiting_approval' }, { silent: true }), agentApi.getAgentSessionList({ page: 1, page_size: 3 }, { silent: true })]),
    select: ([pendingResponse, recentResponse]) => {
      const pending = payload(pendingResponse)
      const items = [...new Map([...(pending.items || []), ...(payload(recentResponse).items || [])].map(item => [item.id, item])).values()].slice(0, 4)
      return { pending: pending.total || 0, items }
    },
  })
  await Promise.all(jobs.map(async job => {
    try {
      const data = job.select(await job.request)
      if (requestId === generation && active) Object.assign(job.state, { data, error: false })
    } catch {
      if (requestId === generation && active) Object.assign(job.state, { data: null, error: true })
    }
  }))
  if (requestId === generation && active) {
    loading.value = false
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
}

/** """进入工作台后刷新，并只在页面可见时轮询。""" */
function activate() {
  if (active || !props.active) return
  active = true
  void refresh()
  timer = window.setInterval(() => { if (document.visibilityState === 'visible' && !loading.value) void refresh() }, 60000)
}

/** """离开工作台后停止轮询并使未完成请求失效。""" */
function deactivate() {
  active = false
  generation += 1
  loading.value = false
  window.clearInterval(timer)
}

watch([canAlerts, canActions, canSessions], () => {
  for (const state of [alerts, actions, sessions]) Object.assign(state, { data: null, error: false })
  void refresh()
})
watch(() => props.active, value => { if (value) activate(); else deactivate() })
onMounted(activate)
onActivated(activate)
onDeactivated(deactivate)
onBeforeUnmount(deactivate)
</script>

<style scoped>
.mobile-workbench { padding: 20px 16px 24px; background: #f4f7fb; min-height: calc(100dvh - var(--mobile-header-height) - var(--mobile-nav-height)); color: #172b4d; }
.workbench-heading, .section-heading, .row-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.workbench-heading p { color: #65758d; font-size: 13px; margin: 0 0 6px; }
.workbench-heading h1 { font-size: 23px; font-weight: 700; margin: 0; overflow-wrap: anywhere; }
.workbench-heading .el-button { flex-shrink: 0; width: 44px; height: 44px; }
.workbench-shortcuts { display: flex; gap: 8px; margin: 22px 0 16px; }
.workbench-shortcuts button { flex: 1; display: flex; align-items: center; justify-content: center; gap: 5px; min-height: 48px; border: 1px solid #dbe5f3; border-radius: 12px; background: #fff; color: #285a97; font-size: 13px; }
.workbench-shortcuts button:disabled { opacity: .45; cursor: not-allowed; }
.workbench-shortcuts svg { font-size: 18px; flex-shrink: 0; }
.workbench-totals { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 18px; }
.workbench-totals a { border-radius: 14px; background: #e9f0fc; padding: 14px 6px; display: flex; flex-direction: column; align-items: center; gap: 5px; color: #28508d; }
.workbench-totals strong { font-size: 27px; line-height: 1.2; }
.workbench-totals span { font-size: 11px; }
.workbench-section { padding: 15px; border: 1px solid #e6ebf2; border-radius: 16px; background: #fff; margin-bottom: 14px; overflow: hidden; }
.section-heading { min-height: 34px; }
.section-heading h2 { font-size: 17px; font-weight: 650; margin: 0; }
.section-heading a { display: flex; align-items: center; color: #4c6c94; font-size: 12px; min-height: 44px; }
.section-heading .el-button { min-height: 44px; }
.section-caption { margin: 4px 0 10px; color: #6b7e96; font-size: 12px; line-height: 1.7; }
.workbench-row { display: block; width: 100%; text-align: left; padding: 14px 0; border: 0; border-top: 1px solid #edf1f6; background: transparent; color: inherit; cursor: pointer; }
.workbench-row:disabled { cursor: default; }
.row-heading { align-items: flex-start; }
.row-heading .el-tag { flex-shrink: 0; }
.row-title { font-size: 14px; line-height: 1.5; font-weight: 600; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.workbench-row p { color: #66788e; font-size: 12px; line-height: 1.6; margin: 6px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.row-meta { display: inline-block; color: #7a899f; font-size: 11px; line-height: 1.6; margin-top: 5px; overflow-wrap: anywhere; }
.workbench-row :deep(.el-progress) { margin-top: 10px; }
.recent-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.recent-row > div { min-width: 0; }
.recent-row svg { flex-shrink: 0; }
.recent-row .recent-title { color: #30435c; margin-bottom: 0; font-size: 14px; }
.section-empty, .section-error { color: #7a899f; font-size: 13px; line-height: 1.8; padding: 16px 0; margin: 0; }
.section-error { color: #b45309; }
.workbench-updated { text-align: center; font-size: 11px; color: #8895a7; }
</style>
