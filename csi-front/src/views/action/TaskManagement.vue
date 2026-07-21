<template>
  <div>
    <Header />
    <section class="bg-linear-to-br from-blue-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">基础组件</span>任务</h1>
            <p class="text-gray-600 text-lg mb-6">统一管理完整行动的定时计划与执行记录，节点仍按行动依赖关系依次运行。</p>
            <div class="flex flex-wrap gap-4">
              <div v-for="item in metricCards" :key="item.label" class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" :class="item.bgClass">
                  <Icon :icon="item.icon" class="text-xl" :class="item.iconClass" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">{{ item.label }}</p>
                  <p class="text-xl font-bold text-gray-900">{{ item.value }}</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">快速操作</h3>
            <div class="space-y-4">
              <button
                v-if="canCreateSchedule"
                class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2"
                @click="openCreateSchedule"
              >
                <Icon icon="mdi:calendar-plus" />
                <span>创建调度计划</span>
              </button>
              <button
                class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2"
                @click="openTaskList('tasks')"
              >
                <Icon icon="mdi:clipboard-text-outline" />
                <span>执行任务管理</span>
              </button>
              <button
                class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2"
                @click="openTaskList('schedule')"
              >
                <Icon icon="mdi:calendar-clock" />
                <span>调度计划管理</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="py-12 bg-linear-to-b from-white to-gray-50 min-h-96">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Icon icon="mdi:history" class="text-blue-600" />
            <span><span class="text-blue-500">最近</span>执行</span>
          </h2>
          <el-button type="primary" link @click="openTaskList('tasks')">
            <template #icon><Icon icon="mdi:arrow-right" /></template>
            查看全部
          </el-button>
        </div>
        <div v-loading="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 min-h-48">
          <button
            v-for="run in summary.recent_runs"
            :key="run.action_id"
            class="text-left bg-white rounded-2xl border border-blue-100 p-6 shadow-lg hover:border-blue-300 hover:shadow-xl transition-all"
            @click="router.push(`/action/${run.action_id}`)"
          >
            <div class="flex items-start justify-between gap-3 mb-3">
              <div>
                <h3 class="font-bold text-gray-900">{{ run.blueprint_name }}</h3>
                <p class="text-sm text-gray-500 mt-1">{{ run.schedule_name }}</p>
              </div>
              <el-tag :type="getStatusTagType(run.status)" size="small">{{ getStatusText(run.status) }}</el-tag>
            </div>
            <div class="space-y-3 text-sm">
              <div class="flex items-center gap-2"><Icon icon="mdi:calendar-clock" class="text-blue-500" /><span class="text-gray-500">计划时间</span><span class="font-medium text-gray-900">{{ formatDateTime(run.scheduled_for) }}</span></div>
              <div class="flex items-center gap-2"><Icon icon="mdi:timer-outline" class="text-purple-500" /><span class="text-gray-500">执行耗时</span><span class="font-medium text-gray-900">{{ formatDuration(run.duration) }}</span></div>
              <div>
                <div class="flex justify-between text-xs text-gray-600 mb-1">
                  <span>执行进度</span>
                  <span>{{ Math.round(run.progress || 0) }}%（{{ run.completed_steps }}/{{ run.total_steps }} 节点）</span>
                </div>
                <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div class="h-full bg-linear-to-r from-blue-500 to-cyan-400 rounded-full" :style="{ width: `${Math.min(100, Math.max(0, run.progress || 0))}%` }"></div>
                </div>
              </div>
            </div>
          </button>
          <div v-if="!loading && !summary.recent_runs.length" class="md:col-span-2 lg:col-span-3 flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-gray-200 bg-white/80">
            <Icon icon="mdi:clipboard-search-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-1">暂无定时行动执行记录</p>
            <p class="text-sm text-gray-400">创建并启用调度计划后，执行记录将显示在这里</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import { actionScheduleApi } from '@/api/actionSchedule'
import { formatDateTime, formatDuration, getStatusTagType, getStatusText } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

defineOptions({ name: 'TaskManagement' })

const router = useRouter()
const loading = ref(false)
const summary = ref({
  schedule_count: 0,
  enabled_schedule_count: 0,
  task_count: 0,
  running_count: 0,
  pending_count: 0,
  failed_count: 0,
  recent_runs: []
})
const canCreateSchedule = computed(() => hasPerm(PERM.operations.action.schedule.create))
const metricCards = computed(() => [
  { label: '执行任务', value: summary.value.task_count, icon: 'mdi:clipboard-list-outline', bgClass: 'bg-blue-100', iconClass: 'text-blue-600' },
  { label: '运行中', value: summary.value.running_count, icon: 'mdi:progress-clock', bgClass: 'bg-green-100', iconClass: 'text-green-600' },
  { label: '待执行', value: summary.value.pending_count, icon: 'mdi:clock-outline', bgClass: 'bg-amber-100', iconClass: 'text-amber-600' },
  { label: '失败', value: summary.value.failed_count, icon: 'mdi:alert-circle-outline', bgClass: 'bg-red-100', iconClass: 'text-red-600' }
])

function openTaskList(tab) {
  router.push({ path: '/action/component-tasks', query: { tab } })
}

function openCreateSchedule() {
  router.push({ path: '/action/component-tasks', query: { tab: 'schedule', create: '1' } })
}

async function fetchSummary() {
  loading.value = true
  try {
    const response = await actionScheduleApi.getSummary()
    if (response.code === 0 && response.data) summary.value = response.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchSummary)
</script>
