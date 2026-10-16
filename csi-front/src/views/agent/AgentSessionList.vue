<template>
  <div class="min-h-screen bg-gray-50" :class="{ 'mobile-session-list': isMobile }">
    <Header />

    <FunctionalPageHeader
      v-if="!isMobile"
      title-prefix="分析引擎"
      title-suffix="会话管理"
      subtitle="查询历史与进行中的分析会话，查看状态并进入详情"
    >
      <template #actions>
        <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
          <Icon icon="mdi:clipboard-text-search-outline" class="text-blue-600 text-xl" />
          <div>
            <p class="text-xs text-gray-500">会话总数</p>
            <p class="text-lg font-bold text-gray-900">{{ pagination.total }}</p>
          </div>
        </div>
      </template>
    </FunctionalPageHeader>

    <header v-else class="mobile-sessions-heading">
      <div><h1>分析会话</h1><p>{{ pagination.total }} 个会话 · 查看进度与结果</p></div>
      <button type="button" @click="mobileFiltersOpen = true"><Icon icon="mdi:tune-variant" /> 筛选</button>
    </header>

    <div class="session-list-content max-w-480 mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div v-if="!isMobile" class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">运行状态</label>
            <el-select
              v-model="filters.status"
              placeholder="全部状态"
              clearable
              class="w-full"
            >
              <el-option label="全部状态" value="" />
              <el-option
                v-for="opt in AGENT_SESSION_STATUS_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">分析引擎</label>
            <el-select
              v-model="filters.agentId"
              placeholder="全部引擎"
              clearable
              filterable
              class="w-full"
            >
              <el-option label="全部引擎" value="" />
              <el-option
                v-for="agent in agentOptions"
                :key="agent.value"
                :label="agent.label"
                :value="agent.value"
              />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">工作区 ID</label>
            <el-input
              v-model="filters.workspaceId"
              placeholder="按 workspace_id 筛选"
              clearable
            />
          </div>
          <div class="flex items-end">
            <el-button type="primary" class="w-full" @click="handleFilterChange">
              <template #icon><Icon icon="mdi:filter" /></template>
              应用筛选
            </el-button>
          </div>
        </div>
      </div>

      <nav v-if="isMobile" class="mobile-session-status" aria-label="会话状态">
        <button type="button" :aria-pressed="!filters.status" :class="{ active: !filters.status }" @click="filters.status = ''; handleFilterChange()">全部</button>
        <button v-for="opt in AGENT_SESSION_STATUS_OPTIONS" :key="opt.value" type="button" :aria-pressed="filters.status === opt.value" :class="{ active: filters.status === opt.value }" @click="filters.status = opt.value; handleFilterChange()">{{ opt.label }}</button>
      </nav>
      <MobileSheet v-model="mobileFiltersOpen" title="筛选分析会话">
        <el-form label-position="top">
          <el-form-item label="运行状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="opt in AGENT_SESSION_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" /></el-select></el-form-item>
          <el-form-item label="分析引擎"><el-select v-model="filters.agentId" clearable filterable placeholder="全部引擎"><el-option v-for="agent in agentOptions" :key="agent.value" :label="agent.label" :value="agent.value" /></el-select></el-form-item>
          <el-form-item label="工作区"><el-input v-model="filters.workspaceId" clearable placeholder="输入工作区标识" /></el-form-item>
        </el-form>
        <template #footer><el-button type="primary" class="w-full" @click="mobileFiltersOpen = false; handleFilterChange()">应用筛选</el-button></template>
      </MobileSheet>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="session-list-toolbar p-6 border-b border-gray-200 flex items-center justify-between gap-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center gap-2 shrink-0">
            <Icon icon="mdi:format-list-bulleted" class="text-blue-600" />
            会话列表
          </h2>
          <button v-if="isMobile" type="button" class="mobile-session-refresh" :disabled="loading" @click="fetchSessions"><Icon icon="mdi:refresh" /> 刷新</button>
          <div v-else class="shrink-0">
            <AgentStartButton
              button-text="运行分析引擎"
              loading-text="启动中..."
              :disabled="!runAgentOptions.length"
              :agent-options="runAgentOptions"
              icon="mdi:play-circle-outline"
              compact
              element-primary
              @started="handleAgentStarted"
            />
          </div>
        </div>

        <div v-loading="loading" element-loading-text="加载中..." class="min-h-48">
          <div v-if="fetchError" class="p-5 text-center text-sm text-red-600"><p>{{ fetchError }}</p><el-button class="mt-3" @click="fetchSessions">重试</el-button></div>
          <div v-else-if="isMobile && sessions.length" class="mobile-session-cards">
            <button v-for="row in sessions" :key="row.id" type="button" class="mobile-session-card" :disabled="!canReadSession" @click="canReadSession && goToDetail(row)">
              <div class="flex items-start justify-between gap-3"><strong>{{ row.agent_name || '未命名引擎' }}</strong><el-tag :type="getAgentSessionStatusTagType(row.status)" size="small">{{ getAgentSessionStatusLabel(row.status) }}</el-tag></div>
              <p v-if="shouldShowStatusErrorTooltip(row)" class="mobile-session-error">{{ row.error_message }}</p>
              <p class="mobile-session-time">{{ formatDateTime(row.updated_at || row.created_at) }}</p>
              <div class="flex justify-between items-center gap-3"><span class="font-mono text-xs text-gray-400 truncate">{{ row.id }}</span><span class="text-blue-600 text-sm shrink-0">查看会话 →</span></div>
            </button>
          </div>
          <el-table v-else-if="sessions.length" :data="sessions" stripe class="w-full">
            <el-table-column label="分析引擎" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="font-medium text-gray-900">{{ row.agent_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="会话 ID" min-width="200">
              <template #default="{ row }">
                <el-tooltip :content="row.id" placement="top">
                  <span class="font-mono text-sm text-gray-700 truncate block max-w-48">{{ row.id }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120" align="center">
              <template #default="{ row }">
                <el-tooltip
                  v-if="shouldShowStatusErrorTooltip(row)"
                  :content="row.error_message"
                  placement="top"
                >
                  <el-tag
                    :type="getAgentSessionStatusTagType(row.status)"
                    size="small"
                    class="cursor-help"
                  >
                    {{ getAgentSessionStatusLabel(row.status) }}
                  </el-tag>
                </el-tooltip>
                <el-tag
                  v-else
                  :type="getAgentSessionStatusTagType(row.status)"
                  size="small"
                >
                  {{ getAgentSessionStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="workspace_id" label="工作区" min-width="120" show-overflow-tooltip />
            <el-table-column label="创建时间" min-width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at, { includeSecond: true }) }}
              </template>
            </el-table-column>
            <el-table-column label="开始时间" min-width="160">
              <template #default="{ row }">
                {{ row.started_at ? formatDateTime(row.started_at, { includeSecond: true }) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="结束时间" min-width="160">
              <template #default="{ row }">
                {{ row.finished_at ? formatDateTime(row.finished_at, { includeSecond: true }) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="goToDetail(row)">
                  <template #icon><Icon icon="mdi:eye" /></template>
                  查看详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div v-else class="flex flex-col items-center justify-center py-16">
            <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500">暂无会话数据</p>
          </div>
        </div>

        <div
          v-if="!loading && sessions.length > 0"
          class="p-6 border-t border-gray-200 flex justify-center"
        >
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="pagination.total"
            :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
            :pager-count="isMobile ? 5 : 7"
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>
      </div>
    </div>
    <MobileActionBar v-if="isMobile" aria-label="会话操作">
      <AgentStartButton button-text="发起新的分析" :disabled="!runAgentOptions.length" :agent-options="runAgentOptions" icon="mdi:plus" block element-primary @started="handleAgentStarted" />
    </MobileActionBar>
  </div>
</template>

<script setup>
defineOptions({ name: 'AgentSessionList' })

import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import AgentStartButton from '@/components/agent/AgentStartButton.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import MobileActionBar from '@/components/mobile/MobileActionBar.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { agentApi } from '@/api/agent'
import { formatDateTime } from '@/utils/action'
import {
  AGENT_SESSION_STATUS,
  AGENT_SESSION_STATUS_OPTIONS,
  getAgentSessionStatusLabel,
  getAgentSessionStatusTagType,
} from '@/utils/agent/sessionStatus'

const router = useRouter()
const { isMobile } = useMobileViewport()
const mobileFiltersOpen = ref(false)
const fetchError = ref('')
const canReadSession = computed(() => hasPerm(PERM.pages.agent.analysis.access) && hasPerm(PERM.operations.agent.session.read))
let sessionRequest = 0
let needsSessionRefresh = false

const loading = ref(false)
const sessions = ref([])
const agentOptions = ref([])

const runAgentOptions = computed(() =>
  agentOptions.value.map((item) => ({
    label: item.label,
    value: item.value,
    icon: 'mdi:brain',
  }))
)

const filters = ref({
  status: '',
  agentId: '',
  workspaceId: '',
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

function buildQueryParams() {
  const params = {
    page: pagination.value.page,
    page_size: pagination.value.pageSize,
  }
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.agentId) params.agent_id = filters.value.agentId
  const ws = filters.value.workspaceId?.trim()
  if (ws) params.workspace_id = ws
  return params
}

async function fetchSessions() {
  const requestId = ++sessionRequest
  loading.value = true
  fetchError.value = ''
  try {
    const response = await agentApi.getAgentSessionList(buildQueryParams())
    if (requestId !== sessionRequest) return
    const data = response?.code === 0 && response.data
      ? response.data
      : Array.isArray(response?.items) && typeof response.total === 'number' ? response : null
    if (!data || !Array.isArray(data.items)) throw new Error('会话列表返回无效')
    sessions.value = data.items
    pagination.value = {
      ...pagination.value,
      total: data.total ?? 0,
      page: data.page ?? pagination.value.page,
      pageSize: data.page_size ?? pagination.value.pageSize,
      totalPages: data.total_pages ?? 0,
    }
  } catch {
    if (requestId === sessionRequest) fetchError.value = '会话加载失败，请重试'
  } finally {
    if (requestId === sessionRequest) loading.value = false
  }
}

async function loadAgentOptions() {
  try {
    const res = await agentApi.getAgentsConfigList()
    const list = res?.data || []
    agentOptions.value = list.map((item) => ({
      label: item.name,
      value: item.id,
    }))
  } catch {
    agentOptions.value = []
  }
}

function handleFilterChange() {
  pagination.value.page = 1
  fetchSessions()
}

function handlePageChange(page) {
  pagination.value.page = page
  fetchSessions()
}

function handlePageSizeChange(pageSize) {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchSessions()
}

function shouldShowStatusErrorTooltip(row) {
  return Boolean(
    row?.error_message?.trim() && row.status === AGENT_SESSION_STATUS.FAILED
  )
}

function goToDetail(row) {
  if (!row?.id || !row?.agent_id) return
  router.push({
    name: 'agent-analysis-detail',
    params: { sessionId: row.id },
    query: { agent_id: row.agent_id },
  })
}

function handleAgentStarted({ agentId, sessionId }) {
  router.push({
    name: 'agent-analysis-detail',
    params: { sessionId: String(sessionId) },
    query: { agent_id: String(agentId) },
  })
}

onMounted(() => {
  loadAgentOptions()
  fetchSessions()
})
onDeactivated(() => {
  mobileFiltersOpen.value = false
  sessionRequest += 1
  loading.value = false
  needsSessionRefresh = true
})
onActivated(() => {
  if (!needsSessionRefresh) return
  needsSessionRefresh = false
  fetchSessions()
})
onUnmounted(() => { sessionRequest += 1 })
</script>

<style scoped>
.mobile-sessions-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 20px 16px 12px; }
.mobile-sessions-heading h1 { font-size: 24px; font-weight: 700; color: #0f172a; }
.mobile-sessions-heading p { margin-top: 4px; color: #64748b; font-size: 12px; }
.mobile-sessions-heading button, .mobile-session-refresh { display: flex; align-items: center; gap: 5px; min-height: 44px; color: #2563eb; font-size: 14px; }
.mobile-session-list .session-list-content { padding: 0 12px 16px; }
.mobile-session-list .session-list-toolbar { padding: 8px 14px; }
.mobile-session-status { display: flex; gap: 8px; overflow-x: auto; padding: 4px 0 12px; }
.mobile-session-status button { flex-shrink: 0; min-height: 44px; padding: 8px 14px; border: 1px solid #e2e8f0; border-radius: 999px; background: #fff; color: #64748b; font-size: 13px; }
.mobile-session-status button.active { color: #1d4ed8; border-color: #bfdbfe; background: #eff6ff; }
.mobile-session-cards { display: flex; flex-direction: column; }
.mobile-session-card { width: 100%; text-align: left; padding: 16px; border-bottom: 1px solid #f1f5f9; }
.mobile-session-card strong { min-width: 0; overflow-wrap: anywhere; color: #0f172a; font-size: 16px; }
.mobile-session-card:disabled { opacity: .6; }
.mobile-session-time { margin: 10px 0; color: #64748b; font-size: 12px; }
.mobile-session-error { padding: 10px; margin-top: 10px; border-radius: 8px; background: #fef2f2; color: #b91c1c; font-size: 13px; overflow-wrap: anywhere; }
</style>
