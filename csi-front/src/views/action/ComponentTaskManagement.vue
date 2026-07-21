<template>
  <ConfigCenterLayout
    title-prefix="组件任务"
    title-suffix="管理"
    subtitle="管理完整行动的定时计划与执行记录"
    sidebar-title="组件任务"
    :nav-items="sidebarTabs"
    v-model="activeTab"
    :get-badge="getSidebarCount"
  >
    <template #actions>
      <div class="flex items-center gap-3">
        <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
          <Icon icon="mdi:clipboard-text-outline" class="text-blue-600 text-xl" />
          <div>
            <p class="text-xs text-gray-500">执行任务</p>
            <p class="text-lg font-bold text-gray-900">{{ statistics.task_count }}</p>
          </div>
        </div>
        <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
          <Icon icon="mdi:calendar-clock" class="text-green-600 text-xl" />
          <div>
            <p class="text-xs text-gray-500">调度计划</p>
            <p class="text-lg font-bold text-gray-900">{{ statistics.schedule_count }}</p>
          </div>
        </div>
      </div>
    </template>

    <template #toolbar>
      <div class="bg-white px-6 py-4 border-b border-gray-200 flex flex-col items-stretch gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div class="flex items-center gap-3 shrink-0">
          <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
          <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
          <el-tag :type="schedulerStatus.online ? 'success' : 'danger'" effect="light" class="border-0">
            {{ schedulerStatus.online ? '调度器在线' : '调度器离线' }}
          </el-tag>
        </div>
        <div class="flex flex-wrap lg:flex-nowrap items-center gap-3 w-full xl:w-auto">
          <el-input v-model="filters.keyword" placeholder="搜索计划或蓝图..." clearable class="w-full! lg:w-64!" @keyup.enter="refreshCurrent" @clear="refreshCurrent">
            <template #prefix><Icon icon="mdi:magnify" class="text-gray-400" /></template>
          </el-input>
          <el-select v-if="activeTab === 'tasks'" v-model="filters.status" placeholder="全部状态" clearable class="flex-1 min-w-32 lg:flex-none lg:w-36!" @change="fetchTaskList()">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-else v-model="filters.enabled" placeholder="全部计划" clearable class="flex-1 min-w-32 lg:flex-none lg:w-36!" @change="fetchScheduleList()">
            <el-option label="已启用" :value="true" />
            <el-option label="已停用" :value="false" />
          </el-select>
          <el-button v-if="activeTab === 'tasks'" type="primary" @click="router.push('/action/blueprints')">
            <template #icon><Icon icon="mdi:play" /></template>
            执行行动
          </el-button>
          <el-button v-else-if="canCreate" type="primary" @click="openCreateDrawer">
            <template #icon><Icon icon="mdi:plus" /></template>
            新增调度计划
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="!schedulerStatus.online"
      title="行动调度器当前离线，计划仍可编辑，但不会自动触发。"
      type="warning"
      :closable="false"
      show-icon
      class="mb-4"
    />

    <div v-if="activeTab === 'tasks'">
      <div v-loading="taskLoading" element-loading-text="加载中..." class="min-h-50 space-y-4">
        <article v-for="task in taskList" :key="task.action_id" class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:shadow-md transition-shadow">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-4 min-w-0">
              <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" :class="getActionStatusIcon(task.status).bgClass">
                <Icon :icon="getActionStatusIcon(task.status).icon" class="text-2xl" :class="getActionStatusIcon(task.status).iconClass" />
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <h3 class="text-lg font-bold text-gray-900">{{ task.blueprint_name }}</h3>
                  <el-tag :type="getStatusTagType(task.status)" size="small" class="border-0">{{ getStatusText(task.status) }}</el-tag>
                  <el-tag type="warning" size="small" class="border-0">优先级 {{ task.priority }}</el-tag>
                </div>
                <p class="text-sm text-gray-500 mt-1">{{ task.schedule_name }}</p>
                <p v-if="task.error_message" class="text-sm text-red-600 mt-2">{{ task.error_message }}</p>
                <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm mt-4">
                  <div class="flex items-center gap-2"><Icon icon="mdi:calendar-clock" class="text-blue-500" /><span class="text-gray-600">计划时间</span><span class="font-medium text-gray-900">{{ formatDateTime(task.scheduled_for) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:play-circle-outline" class="text-green-500" /><span class="text-gray-600">开始时间</span><span class="font-medium text-gray-900">{{ formatDateTime(task.start_at) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:stop-circle-outline" class="text-gray-500" /><span class="text-gray-600">结束时间</span><span class="font-medium text-gray-900">{{ formatDateTime(task.finished_at) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:timer-outline" class="text-purple-500" /><span class="text-gray-600">执行耗时</span><span class="font-medium text-gray-900">{{ formatDuration(task.duration) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:chart-line" class="text-amber-500" /><span class="text-gray-600">执行进度</span><span class="font-medium text-gray-900">{{ Math.round(task.progress || 0) }}%（{{ task.completed_steps }}/{{ task.total_steps }}）</span></div>
                </div>
              </div>
            </div>
            <el-button type="primary" link @click="router.push(`/action/${task.action_id}`)">
              <template #icon><Icon icon="mdi:eye-outline" /></template>
              查看行动详情
            </el-button>
          </div>
        </article>
        <div v-if="!taskLoading && !taskList.length" class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80">
          <Icon icon="mdi:clipboard-search-outline" class="text-6xl text-gray-300 mb-4" />
          <p class="text-gray-500">暂无定时行动执行记录</p>
        </div>
      </div>
      <div v-if="taskPagination.total" class="flex justify-center mt-6">
        <el-pagination v-model:current-page="taskPagination.page" v-model:page-size="taskPagination.pageSize" :page-sizes="[10, 20, 50, 100]" :total="taskPagination.total" layout="total, sizes, prev, pager, next, jumper" @current-change="handleTaskPage" @size-change="handleTaskSize" />
      </div>
    </div>

    <div v-else>
      <div v-loading="scheduleLoading" element-loading-text="加载中..." class="min-h-50 space-y-4">
        <article v-for="schedule in scheduleList" :key="schedule.id" class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:shadow-md transition-shadow">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-4 min-w-0">
              <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" :class="schedule.enabled ? 'bg-green-100' : 'bg-gray-100'">
                <Icon :icon="schedule.enabled ? 'mdi:calendar-check' : 'mdi:calendar-remove'" class="text-2xl" :class="schedule.enabled ? 'text-green-600' : 'text-gray-500'" />
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <h3 class="text-lg font-bold text-gray-900">{{ schedule.name }}</h3>
                  <el-tag :type="schedule.enabled ? 'success' : 'info'" size="small" class="border-0">{{ schedule.enabled ? '已启用' : '已停用' }}</el-tag>
                  <el-tag type="warning" size="small" class="border-0">优先级 {{ schedule.priority }}</el-tag>
                  <el-tag v-if="schedule.last_trigger_status === 'failed' || schedule.last_trigger_status === 'invalid'" type="danger" size="small" class="border-0">触发异常</el-tag>
                </div>
                <p class="text-sm text-gray-500 mt-1">{{ schedule.description || '暂无描述' }}</p>
                <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm mt-4">
                  <div class="flex items-center gap-2"><Icon icon="mdi:graph-outline" class="text-blue-500" /><span class="text-gray-600">行动蓝图</span><span class="font-medium text-gray-900">{{ schedule.blueprint_name }}（{{ schedule.blueprint_version }}）</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:calendar-sync" class="text-green-500" /><span class="font-medium text-gray-900">{{ scheduleDescription(schedule) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:map-clock-outline" class="text-cyan-500" /><span class="text-gray-600">时区</span><span class="font-medium text-gray-900">{{ schedule.timezone }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:clock-outline" class="text-purple-500" /><span class="text-gray-600">下次执行</span><span class="font-medium text-gray-900">{{ formatDateTime(schedule.next_run_at) }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:layers-outline" class="text-amber-500" /><span class="text-gray-600">重叠</span><span class="font-medium text-gray-900">{{ schedule.overlap_policy === 'forbid' ? '禁止' : '允许' }}</span></div>
                  <div class="flex items-center gap-2"><Icon icon="mdi:history" class="text-cyan-500" /><span class="text-gray-600">错过</span><span class="font-medium text-gray-900">{{ schedule.misfire_policy === 'fire_once' ? '补一次' : '跳过' }}</span></div>
                </div>
                <p v-if="schedule.last_error" class="text-sm text-red-600 mt-2">{{ schedule.last_error }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <el-switch v-if="canUpdate" :model-value="schedule.enabled" @change="toggleSchedule(schedule, $event)" />
              <el-button v-if="canUpdate" type="primary" link @click="openEditDrawer(schedule)"><template #icon><Icon icon="mdi:pencil-outline" /></template>编辑</el-button>
              <el-button type="primary" link @click="showScheduleRuns(schedule)"><template #icon><Icon icon="mdi:history" /></template>执行记录</el-button>
              <el-button v-if="canDelete" type="danger" link @click="removeSchedule(schedule)"><template #icon><Icon icon="mdi:delete-outline" /></template>删除</el-button>
            </div>
          </div>
        </article>
        <div v-if="!scheduleLoading && !scheduleList.length" class="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-gray-200 bg-gray-50/80">
          <Icon icon="mdi:calendar-blank-outline" class="text-6xl text-gray-300 mb-4" />
          <p class="text-gray-500">暂无调度计划</p>
        </div>
      </div>
      <div v-if="schedulePagination.total" class="flex justify-center mt-6">
        <el-pagination v-model:current-page="schedulePagination.page" v-model:page-size="schedulePagination.pageSize" :page-sizes="[10, 20, 50, 100]" :total="schedulePagination.total" layout="total, sizes, prev, pager, next, jumper" @current-change="handleSchedulePage" @size-change="handleScheduleSize" />
      </div>
    </div>

    <el-drawer v-model="drawerVisible" :title="editingScheduleId ? '编辑调度计划' : '新增调度计划'" size="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="grid grid-cols-2 gap-x-4">
          <el-form-item label="计划名称" prop="name"><el-input v-model="form.name" placeholder="请输入计划名称" maxlength="100" /></el-form-item>
          <el-form-item label="行动蓝图" prop="blueprint_id">
            <el-select v-model="form.blueprint_id" placeholder="请选择行动蓝图" filterable class="w-full!" @change="handleBlueprintChange">
              <el-option v-for="item in blueprints" :key="item.id" :label="`${item.name}（${item.version}）`" :value="item.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" placeholder="请输入计划描述" :rows="2" maxlength="500" /></el-form-item>

        <div v-if="templateParams.length" class="rounded-lg border border-blue-100 bg-blue-50/40 p-4 mb-4">
          <p class="font-medium text-gray-800 mb-3">行动模板参数</p>
          <el-form-item v-for="param in templateParams" :key="param.name" :label="param.label" :required="param.required">
            <InputRenderer :input-config="templateInputConfig(param)" v-model="form.params[param.name]" :node-id="null" />
          </el-form-item>
        </div>

        <div class="grid grid-cols-2 gap-x-4">
          <el-form-item label="调度类型" prop="schedule_type">
            <el-radio-group v-model="form.schedule_type" @change="resetScheduleFields">
              <el-radio-button value="cron">Cron</el-radio-button>
              <el-radio-button value="interval">固定间隔</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="时区" prop="timezone">
            <el-select v-model="form.timezone" filterable class="w-full!">
              <el-option v-for="zone in timezoneOptions" :key="zone" :label="zone" :value="zone" />
            </el-select>
          </el-form-item>
        </div>

        <template v-if="form.schedule_type === 'cron'">
          <el-form-item label="快捷配置">
            <el-radio-group v-model="cronPreset" @change="applyCronPreset">
              <el-radio-button value="daily">每天 8 点</el-radio-button>
              <el-radio-button value="weekly">每周一 8 点</el-radio-button>
              <el-radio-button value="monthly">每月 1 日 8 点</el-radio-button>
              <el-radio-button value="custom">自定义</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="Cron 表达式" prop="cron_expression"><el-input v-model="form.cron_expression" placeholder="例如：0 8 * * *" class="font-mono" /></el-form-item>
        </template>
        <el-form-item v-else label="固定间隔" prop="interval_value">
          <div class="flex gap-2 w-full">
            <el-input-number v-model="form.interval_value" :min="1" class="flex-1" />
            <el-select v-model="form.interval_unit" class="w-32! shrink-0">
              <el-option label="分钟" value="minute" />
              <el-option label="小时" value="hour" />
              <el-option label="天" value="day" />
            </el-select>
          </div>
        </el-form-item>

        <div class="grid grid-cols-2 gap-x-4">
          <el-form-item label="开始时间" prop="start_at"><el-date-picker v-model="form.start_at" type="datetime" class="w-full!" /></el-form-item>
          <el-form-item label="结束时间"><el-date-picker v-model="form.end_at" type="datetime" clearable class="w-full!" /></el-form-item>
          <el-form-item label="优先级"><el-input-number v-model="form.priority" :min="1" :max="10" class="w-full!" /></el-form-item>
          <el-form-item label="启用计划"><el-switch v-model="form.enabled" /></el-form-item>
          <el-form-item label="重叠执行">
            <el-select v-model="form.overlap_policy" class="w-full!"><el-option label="禁止重叠" value="forbid" /><el-option label="允许重叠" value="allow" /></el-select>
          </el-form-item>
          <el-form-item label="错过执行">
            <el-select v-model="form.misfire_policy" class="w-full!"><el-option label="恢复后补一次" value="fire_once" /><el-option label="直接跳过" value="skip" /></el-select>
          </el-form-item>
        </div>

        <div v-if="previewRuns.length" class="rounded-lg bg-gray-50 p-4">
          <p class="font-medium text-gray-800 mb-2">未来执行时间</p>
          <p v-for="item in previewRuns" :key="item" class="text-sm text-gray-600">{{ formatDateTime(item, { includeSecond: true }) }}</p>
        </div>
      </el-form>
      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button @click="previewForm" :loading="previewing">预览</el-button>
          <el-button type="primary" @click="saveSchedule" :loading="submitting">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </ConfigCenterLayout>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import InputRenderer from '@/components/action/nodes/components/InputRenderer.vue'
import { actionScheduleApi } from '@/api/actionSchedule'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { ACTION_STATUS, cronToDescription, formatDateTime, formatDuration, getActionStatusIcon, getStatusTagType, getStatusText } from '@/utils/action'
import { INPUT_TYPE_DEFAULTS } from '@/utils/action/constants'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

defineOptions({ name: 'ComponentTaskManagement' })

const route = useRoute()
const router = useRouter()
const activeTab = ref(route.query.tab === 'schedule' ? 'schedule' : 'tasks')
const taskList = ref([])
const scheduleList = ref([])
const taskLoading = ref(false)
const scheduleLoading = ref(false)
const taskPagination = reactive({ page: 1, pageSize: 10, total: 0 })
const schedulePagination = reactive({ page: 1, pageSize: 10, total: 0 })
const statistics = reactive({ task_count: 0, schedule_count: 0 })
const schedulerStatus = ref({ online: false, last_heartbeat_at: null, last_scan_at: null })
const filters = reactive({ keyword: '', status: '', enabled: null, schedule_id: '' })
const sidebarTabs = [
  { key: 'tasks', label: '执行任务', icon: 'mdi:clipboard-text-outline' },
  { key: 'schedule', label: '调度计划', icon: 'mdi:calendar-clock' }
]
const statusOptions = [
  { label: '待执行', value: ACTION_STATUS.READY },
  { label: '运行中', value: ACTION_STATUS.RUNNING },
  { label: '已完成', value: ACTION_STATUS.COMPLETED },
  { label: '失败', value: ACTION_STATUS.FAILED },
  { label: '已取消', value: ACTION_STATUS.CANCELLED }
]
const timezoneOptions = ['Asia/Shanghai', 'UTC', 'Asia/Tokyo', 'Europe/London', 'America/New_York']
const canCreate = computed(() => hasPerm(PERM.operations.action.schedule.create))
const canUpdate = computed(() => hasPerm(PERM.operations.action.schedule.update))
const canDelete = computed(() => hasPerm(PERM.operations.action.schedule.delete))
const currentTabLabel = computed(() => activeTab.value === 'tasks' ? '执行任务' : '调度计划')
const currentTabIcon = computed(() => activeTab.value === 'tasks' ? 'mdi:clipboard-text-outline' : 'mdi:calendar-clock')

const drawerVisible = ref(false)
const editingScheduleId = ref('')
const formRef = ref(null)
const submitting = ref(false)
const previewing = ref(false)
const previewRuns = ref([])
const blueprints = ref([])
const selectedBlueprint = ref(null)
const cronPreset = ref('daily')
const form = reactive(defaultForm())
const formRules = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  blueprint_id: [{ required: true, message: '请选择行动蓝图', trigger: 'change' }],
  schedule_type: [{ required: true, message: '请选择调度类型', trigger: 'change' }],
  cron_expression: [{ required: true, message: '请输入 Cron 表达式', trigger: 'blur' }],
  interval_value: [{ required: true, message: '请输入固定间隔', trigger: 'change' }],
  timezone: [{ required: true, message: '请选择时区', trigger: 'change' }],
  start_at: [{ required: true, message: '请选择开始时间', trigger: 'change' }]
}
const templateParams = computed(() => selectedBlueprint.value?.template?.params || [])
let refreshTimer = null

function defaultForm() {
  return {
    name: '', description: '', blueprint_id: '', params: {}, schedule_type: 'cron',
    cron_expression: '0 8 * * *', interval_value: 1, interval_unit: 'hour',
    timezone: 'Asia/Shanghai', start_at: new Date(), end_at: null, enabled: true,
    priority: 5, overlap_policy: 'forbid', misfire_policy: 'fire_once'
  }
}

function intervalSeconds() {
  const multiplier = { minute: 60, hour: 3600, day: 86400 }[form.interval_unit]
  return form.interval_value * multiplier
}

function payloadFromForm() {
  return {
    name: form.name.trim(), description: form.description, blueprint_id: form.blueprint_id,
    params: { ...form.params }, schedule_type: form.schedule_type,
    cron_expression: form.schedule_type === 'cron' ? form.cron_expression.trim() : null,
    interval_seconds: form.schedule_type === 'interval' ? intervalSeconds() : null,
    timezone: form.timezone, start_at: form.start_at, end_at: form.end_at,
    enabled: form.enabled, priority: form.priority,
    overlap_policy: form.overlap_policy, misfire_policy: form.misfire_policy
  }
}

function previewPayload() {
  const payload = payloadFromForm()
  return {
    schedule_type: payload.schedule_type, cron_expression: payload.cron_expression,
    interval_seconds: payload.interval_seconds, timezone: payload.timezone,
    start_at: payload.start_at, end_at: payload.end_at
  }
}

function templateInputConfig(param) {
  return { ...param, id: param.name, name: param.name, placeholder: `请输入${param.label}` }
}

function resetForm() {
  Object.assign(form, defaultForm())
  selectedBlueprint.value = null
  editingScheduleId.value = ''
  previewRuns.value = []
  cronPreset.value = 'daily'
}

function applyCronPreset(value) {
  const expressions = { daily: '0 8 * * *', weekly: '0 8 * * 1', monthly: '0 8 1 * *' }
  if (expressions[value]) form.cron_expression = expressions[value]
}

function resetScheduleFields() {
  previewRuns.value = []
  if (form.schedule_type === 'cron' && !form.cron_expression) form.cron_expression = '0 8 * * *'
}

async function handleBlueprintChange(blueprintId, existingParams = null) {
  selectedBlueprint.value = null
  form.params = {}
  if (!blueprintId) return
  const response = await actionApi.getBlueprint(blueprintId)
  if (response.code !== 0 || !response.data) return
  selectedBlueprint.value = response.data
  for (const param of templateParams.value) {
    form.params[param.name] = existingParams?.[param.name] ?? INPUT_TYPE_DEFAULTS[param.type]
  }
}

async function loadBlueprints() {
  const result = await getPaginatedData(actionApi.getBlueprintsBaseInfo, { page: 1, page_size: 100 })
  blueprints.value = result.items || []
}

async function fetchTaskList(silent = false) {
  if (!silent) taskLoading.value = true
  try {
    const result = await getPaginatedData(actionScheduleApi.getRuns, {
      page: taskPagination.page, page_size: taskPagination.pageSize,
      keyword: filters.keyword || undefined, status: filters.status || undefined,
      schedule_id: filters.schedule_id || undefined
    })
    taskList.value = result.items || []
    taskPagination.total = result.pagination?.total || 0
    statistics.task_count = taskPagination.total
  } finally {
    if (!silent) taskLoading.value = false
  }
}

async function fetchScheduleList(silent = false) {
  if (!silent) scheduleLoading.value = true
  try {
    const result = await getPaginatedData(actionScheduleApi.getSchedules, {
      page: schedulePagination.page, page_size: schedulePagination.pageSize,
      keyword: filters.keyword || undefined,
      enabled: filters.enabled === null ? undefined : filters.enabled
    })
    scheduleList.value = result.items || []
    schedulePagination.total = result.pagination?.total || 0
    statistics.schedule_count = schedulePagination.total
  } finally {
    if (!silent) scheduleLoading.value = false
  }
}

async function fetchSchedulerStatus() {
  const response = await actionScheduleApi.getStatus()
  if (response.code === 0 && response.data) schedulerStatus.value = response.data
}

function refreshCurrent() {
  if (activeTab.value === 'tasks') fetchTaskList()
  else fetchScheduleList()
}

function getSidebarCount(key) {
  return key === 'tasks' ? statistics.task_count : statistics.schedule_count
}

function scheduleDescription(schedule) {
  if (schedule.schedule_type === 'interval') return `每 ${formatDuration(schedule.interval_seconds)}执行`
  return `Cron：${schedule.cron_expression}（${cronToDescription(schedule.cron_expression) || '自定义'}）`
}

function openCreateDrawer() {
  resetForm()
  drawerVisible.value = true
}

async function openEditDrawer(schedule) {
  resetForm()
  editingScheduleId.value = schedule.id
  let intervalValue = 1
  let intervalUnit = 'minute'
  if (schedule.interval_seconds) {
    if (schedule.interval_seconds % 86400 === 0) [intervalValue, intervalUnit] = [schedule.interval_seconds / 86400, 'day']
    else if (schedule.interval_seconds % 3600 === 0) [intervalValue, intervalUnit] = [schedule.interval_seconds / 3600, 'hour']
    else intervalValue = schedule.interval_seconds / 60
  }
  Object.assign(form, {
    ...schedule, start_at: new Date(schedule.start_at), end_at: schedule.end_at ? new Date(schedule.end_at) : null,
    interval_value: intervalValue, interval_unit: intervalUnit
  })
  drawerVisible.value = true
  await handleBlueprintChange(schedule.blueprint_id, schedule.params)
}

async function previewForm() {
  previewing.value = true
  try {
    const response = await actionScheduleApi.previewSchedule(previewPayload())
    if (response.code !== 0) throw new Error(response.message)
    previewRuns.value = response.data?.next_runs || []
    if (!previewRuns.value.length) ElMessage.warning('当前有效期内没有可执行时刻')
  } catch (error) {
    ElMessage.error(error.message || '预览执行时间失败')
  } finally {
    previewing.value = false
  }
}

async function saveSchedule() {
  try {
    await formRef.value.validate()
    for (const param of templateParams.value) {
      const value = form.params[param.name]
      if (param.required && (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length))) {
        throw new Error(`请填写模板参数：${param.label}`)
      }
    }
    submitting.value = true
    const response = editingScheduleId.value
      ? await actionScheduleApi.updateSchedule(editingScheduleId.value, payloadFromForm())
      : await actionScheduleApi.createSchedule(payloadFromForm())
    if (response.code !== 0) throw new Error(response.message)
    ElMessage.success(editingScheduleId.value ? '调度计划已更新' : '调度计划已创建')
    drawerVisible.value = false
    await fetchScheduleList()
  } catch (error) {
    if (error?.message) ElMessage.error(error.message)
  } finally {
    submitting.value = false
  }
}

async function toggleSchedule(schedule, enabled) {
  const response = await actionScheduleApi.updateSchedule(schedule.id, { enabled })
  if (response.code !== 0) {
    ElMessage.error(response.message || '更新计划状态失败')
    return
  }
  Object.assign(schedule, response.data)
  ElMessage.success(enabled ? '计划已启用' : '计划已停用')
}

async function removeSchedule(schedule) {
  await ElMessageBox.confirm(`确定删除调度计划“${schedule.name}”吗？历史行动不会被删除。`, '删除调度计划', { type: 'warning' })
  const response = await actionScheduleApi.deleteSchedule(schedule.id)
  if (response.code !== 0) return ElMessage.error(response.message || '删除失败')
  ElMessage.success('调度计划已删除')
  fetchScheduleList()
}

function showScheduleRuns(schedule) {
  filters.schedule_id = schedule.id
  activeTab.value = 'tasks'
}

function handleTaskPage(page) { taskPagination.page = page; fetchTaskList() }
function handleTaskSize(size) { taskPagination.pageSize = size; taskPagination.page = 1; fetchTaskList() }
function handleSchedulePage(page) { schedulePagination.page = page; fetchScheduleList() }
function handleScheduleSize(size) { schedulePagination.pageSize = size; schedulePagination.page = 1; fetchScheduleList() }

watch(activeTab, value => {
  router.replace({ query: { tab: value } })
  if (value === 'tasks') fetchTaskList()
  else fetchScheduleList()
})

onMounted(async () => {
  await Promise.all([loadBlueprints(), fetchSchedulerStatus()])
  refreshCurrent()
  if (route.query.create === '1' && canCreate.value) nextTick(openCreateDrawer)
  refreshTimer = window.setInterval(() => {
    fetchSchedulerStatus()
    if (activeTab.value === 'tasks' && taskList.value.some(item => [ACTION_STATUS.READY, ACTION_STATUS.RUNNING].includes(item.status))) fetchTaskList(true)
    if (activeTab.value === 'schedule') fetchScheduleList(true)
  }, 5000)
})

onUnmounted(() => window.clearInterval(refreshTimer))
</script>
