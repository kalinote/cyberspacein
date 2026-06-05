<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <FunctionalPageHeader
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

    <div class="max-w-480 mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
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

      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between gap-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center gap-2 shrink-0">
            <Icon icon="mdi:format-list-bulleted" class="text-blue-600" />
            会话列表
          </h2>
          <div class="flex items-center gap-3 shrink-0">
            <AgentAutoApproveSwitch />
            <div class="w-52 shrink-0">
              <SplitButton
                main-button-text="运行分析引擎"
                loading-text="启动中..."
                :disabled="analyzing || !runAgentOptions.length"
                :loading="analyzing"
                :options="runAgentOptions"
                main-button-icon="mdi:play-circle-outline"
                compact
                element-primary
                @main-click="handleRunAgentMain"
                @option-click="handleRunAgentOption"
              />
            </div>
          </div>
        </div>

        <div v-loading="loading" element-loading-text="加载中..." class="min-h-48">
          <el-table v-if="sessions.length" :data="sessions" stripe class="w-full">
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
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'AgentSessionList' })

import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import SplitButton from '@/components/SplitButton.vue'
import AgentAutoApproveSwitch from '@/components/agent/AgentAutoApproveSwitch.vue'
import { getAgentAutoApproveValue } from '@/composables/useAgentAutoApprove'
import { agentApi } from '@/api/agent'
import { getPaginatedData } from '@/utils/request'
import { formatDateTime } from '@/utils/action'
import {
  AGENT_SESSION_STATUS,
  AGENT_SESSION_STATUS_OPTIONS,
  getAgentSessionStatusLabel,
  getAgentSessionStatusTagType,
} from '@/utils/agent/sessionStatus'

const router = useRouter()

const loading = ref(false)
const analyzing = ref(false)
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
  loading.value = true
  try {
    const result = await getPaginatedData(agentApi.getAgentSessionList, buildQueryParams())
    sessions.value = result.items || []
    pagination.value = {
      ...pagination.value,
      ...result.pagination,
    }
  } finally {
    loading.value = false
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

function handleRunAgentMain() {
  if (!runAgentOptions.value.length) {
    ElMessage.warning('暂无可用的分析引擎')
    return
  }
  ElMessage.info('请点击右侧下拉箭头，选择要运行的分析引擎')
}

async function handleRunAgentOption(option) {
  if (!option?.value) return
  try {
    await ElMessageBox.confirm(
      `确定要运行「${option.label}」吗？`,
      '确认运行',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    analyzing.value = true
    const response = await agentApi.startAgent({
      agent_id: option.value,
      auto_approve: getAgentAutoApproveValue(),
    })

    if (response.code === 0 && response.data?.agent_id) {
      const sid = response.data.session_id
      if (!sid) {
        ElMessage.error('未返回 session_id，无法进入详情')
        return
      }
      ElMessage.success('分析引擎已启动')
      router.push({
        name: 'agent-analysis-detail',
        params: { sessionId: String(sid) },
        query: { agent_id: String(response.data.agent_id) },
      })
    } else {
      ElMessage.error(response.message || '启动分析引擎失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('启动分析引擎失败:', err)
      ElMessage.error('启动分析引擎失败，请稍后重试')
    }
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  loadAgentOptions()
  fetchSessions()
})
</script>
