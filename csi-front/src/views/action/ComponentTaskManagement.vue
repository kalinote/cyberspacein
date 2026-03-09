<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <Header />

    <FunctionalPageHeader
      title-prefix="组件任务"
      title-suffix="管理"
      subtitle="管理组件任务与调度"
    >
      <template #actions>
        <div class="flex items-center gap-3">
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
            <Icon icon="mdi:clipboard-text-outline" class="text-blue-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">任务数</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.task_count }}</p>
            </div>
          </div>
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
            <Icon icon="mdi:calendar-clock" class="text-green-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">调度数</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.schedule_count }}</p>
            </div>
          </div>
        </div>
      </template>
    </FunctionalPageHeader>

    <div class="flex-1 flex overflow-hidden">
      <div class="bg-white w-72 border-r border-gray-200 shrink-0 overflow-y-auto">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-gray-500 uppercase mb-3">组件任务</h3>
          <div class="space-y-1">
            <div
              v-for="tab in sidebarTabs"
              :key="tab.key"
              class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
              :class="activeTab === tab.key
                ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50'"
              @click="activeTab = tab.key"
            >
              <span class="w-5"></span>
              <Icon :icon="tab.icon" class="text-xl shrink-0" />
              <span>{{ tab.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="flex-1 flex flex-col overflow-hidden">
        <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
            <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
          </div>
          <div class="flex items-center gap-3">
            <el-input
              v-model="searchKeyword"
              :placeholder="activeTab === 'tasks' ? '搜索任务...' : '搜索调度...'"
              clearable
              class="w-64"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button type="primary" @click="handleAdd">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              新增{{ currentTabLabel }}
            </el-button>
          </div>
        </div>

        <div class="flex-1 overflow-auto p-6">
          <div v-if="activeTab === 'tasks'" class="space-y-4">
            <div v-loading="taskLoading" element-loading-text="加载中..." class="min-h-[200px]">
              <div
                v-for="task in filteredTaskList"
                :key="task.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div
                      class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                      :class="getTaskStatusBgClass(task.status)"
                    >
                      <Icon
                        :icon="getTaskStatusIcon(task.status)"
                        class="text-2xl"
                        :class="getTaskStatusIconClass(task.status)"
                      />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ task.component_name || task.id }}</h3>
                        <el-tag
                          :type="getTaskStatusTagType(task.status)"
                          size="small"
                          class="border-0"
                        >
                          {{ getTaskStatusText(task.status) }}
                        </el-tag>
                        <el-tag v-if="task.priority != null" size="small" class="border-0" type="info">
                          优先级 {{ task.priority }}
                        </el-tag>
                      </div>
                      <p v-if="task.error_message" class="text-sm text-red-600 mb-2">{{ task.error_message }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:identifier" class="text-orange-500" />
                          <span class="text-gray-600">任务ID:</span>
                          <span class="font-mono text-xs text-gray-900">{{ task.id }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-blue-500" />
                          <span class="text-gray-600">创建:</span>
                          <span class="font-medium text-gray-900">{{ formatDateTime(task.created_at, { defaultValue: '-' }) }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:play-circle" class="text-green-500" />
                          <span class="text-gray-600">开始:</span>
                          <span class="font-medium text-gray-900">{{ formatDateTime(task.start_at, { defaultValue: '-' }) }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:stop-circle" class="text-purple-500" />
                          <span class="text-gray-600">结束:</span>
                          <span class="font-medium text-gray-900">{{ formatDateTime(task.end_at, { defaultValue: '-' }) }}</span>
                        </div>
                        <div v-if="task.total_duration != null" class="flex items-center gap-2">
                          <Icon icon="mdi:timer-outline" class="text-teal-500" />
                          <span class="text-gray-600">耗时:</span>
                          <span class="font-medium text-gray-900">{{ formatDuration(task.total_duration, 'milliseconds') }}</span>
                        </div>
                        <div v-if="task.schedule_name" class="flex items-center gap-2">
                          <Icon icon="mdi:calendar-clock" class="text-indigo-500" />
                          <span class="text-gray-600">调度:</span>
                          <span class="font-medium text-gray-900">{{ task.schedule_name }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="!taskLoading && filteredTaskList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>

            <div v-if="!searchKeyword && taskList.length > 0" class="flex justify-center mt-6">
              <el-pagination
                v-model:current-page="taskPagination.page"
                v-model:page-size="taskPagination.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="taskPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleTaskPageChange"
                @size-change="handleTaskPageSizeChange"
              />
            </div>
          </div>

          <div v-else class="flex flex-col items-center justify-center py-16">
            <Icon icon="mdi:wrench" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">功能开发中</p>
            <p class="text-gray-400 text-sm">{{ currentTabLabel }}内容即将上线</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { taskConfigApi } from '@/api/taskConfig'
import { formatDateTime, formatDuration } from '@/utils/action'
import { getPaginatedData } from '@/utils/request'

const TASK_STATUS_CONFIG = {
  completed: { text: '成功', tagType: 'success', icon: 'mdi:check-circle', iconClass: 'text-green-600', bgClass: 'bg-green-100' },
  finished: { text: '成功', tagType: 'success', icon: 'mdi:check-circle', iconClass: 'text-green-600', bgClass: 'bg-green-100' },
  running: { text: '运行中', tagType: 'primary', icon: 'mdi:loading', iconClass: 'text-blue-600', bgClass: 'bg-blue-100' },
  error: { text: '失败', tagType: 'danger', icon: 'mdi:alert-circle', iconClass: 'text-red-600', bgClass: 'bg-red-100' },
  unknown: { text: '未知', tagType: 'info', icon: 'mdi:clock-outline', iconClass: 'text-gray-600', bgClass: 'bg-gray-100' }
}
const DEFAULT_TASK_STATUS = { text: '', tagType: '', icon: 'mdi:help-circle', iconClass: 'text-gray-600', bgClass: 'bg-gray-100' }

export default {
  name: 'ComponentTaskManagement',
  components: {
    Header,
    Icon,
    FunctionalPageHeader
  },
  data() {
    return {
      activeTab: 'tasks',
      searchKeyword: '',
      taskList: [],
      taskLoading: false,
      taskPagination: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
      statistics: {
        task_count: 0,
        schedule_count: 0
      },
      sidebarTabs: [
        { key: 'tasks', label: '执行任务', icon: 'mdi:clipboard-text-outline' },
        { key: 'schedule', label: '调度计划', icon: 'mdi:calendar-clock' }
      ]
    }
  },
  watch: {
    activeTab(val) {
      if (val === 'tasks') this.fetchTaskList()
    }
  },
  mounted() {
    if (this.activeTab === 'tasks') this.fetchTaskList()
  },
  methods: {
    getTaskStatusConfig(status, configKey) {
      const config = TASK_STATUS_CONFIG[status] || DEFAULT_TASK_STATUS
      return configKey ? config[configKey] : config
    },
    getTaskStatusText(status) {
      return this.getTaskStatusConfig(status, 'text') || status
    },
    getTaskStatusTagType(status) {
      return this.getTaskStatusConfig(status, 'tagType')
    },
    getTaskStatusIcon(status) {
      return this.getTaskStatusConfig(status, 'icon')
    },
    getTaskStatusIconClass(status) {
      return this.getTaskStatusConfig(status, 'iconClass')
    },
    getTaskStatusBgClass(status) {
      return this.getTaskStatusConfig(status, 'bgClass')
    },
    formatDateTime,
    formatDuration,
    async fetchTaskList() {
      this.taskLoading = true
      try {
        const result = await getPaginatedData(taskConfigApi.getTaskList, {
          page: this.taskPagination.page,
          page_size: this.taskPagination.pageSize
        })
        this.taskList = result.items
        this.taskPagination = { ...this.taskPagination, ...result.pagination }
        this.statistics.task_count = result.pagination?.total ?? 0
      } catch {
        this.taskList = []
      } finally {
        this.taskLoading = false
      }
    },
    handleTaskPageChange(page) {
      this.taskPagination.page = page
      this.fetchTaskList()
    },
    handleTaskPageSizeChange(pageSize) {
      this.taskPagination.pageSize = pageSize
      this.taskPagination.page = 1
      this.fetchTaskList()
    },
    handleAdd() {
      this.$message.info(`新增${this.currentTabLabel}功能开发中`)
    }
  },
  computed: {
    filteredTaskList() {
      if (!this.searchKeyword?.trim()) return this.taskList
      const kw = this.searchKeyword.trim().toLowerCase()
      return this.taskList.filter(
        t =>
          (t.component_name && t.component_name.toLowerCase().includes(kw)) ||
          (t.schedule_name && t.schedule_name.toLowerCase().includes(kw)) ||
          (t.id && t.id.toLowerCase().includes(kw))
      )
    },
    currentTabIcon() {
      const tab = this.sidebarTabs.find(t => t.key === this.activeTab)
      return tab ? tab.icon : 'mdi:help'
    },
    currentTabLabel() {
      const tab = this.sidebarTabs.find(t => t.key === this.activeTab)
      return tab ? tab.label : ''
    }
  }
}
</script>
