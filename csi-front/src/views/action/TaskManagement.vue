<template>
  <div>
    <Header />
    
    <!-- 英雄区域 -->
    <section class="bg-linear-to-br from-blue-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">任务</span>管理</h1>
            <p class="text-gray-600 text-lg mb-6">统一管理和监控所有任务执行状态，从任务创建、分配到完成的全流程跟踪平台。</p>
            <div class="flex flex-wrap gap-4">
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:clipboard-list" class="text-blue-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">总任务数</p>
                  <p class="text-xl font-bold text-gray-900">156</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:check-circle" class="text-green-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">进行中任务</p>
                  <p class="text-xl font-bold text-gray-900">23</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:clock-outline" class="text-amber-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">待处理任务</p>
                  <p class="text-xl font-bold text-gray-900">8</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">快速操作</h3>
            <div class="space-y-4">
              <button class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2">
                <Icon icon="mdi:plus-circle-outline" />
                <span>创建新任务</span>
              </button>
              <button class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2">
                <Icon icon="mdi:filter-outline" />
                <span>筛选任务</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                <Icon icon="mdi:export" />
                <span>导出任务列表</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 任务列表 -->
    <section class="py-12 bg-linear-to-b from-white to-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:format-list-bulleted" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">任务</span>列表</span>
          </h2>
          <el-button type="primary" link>
            <template #icon><Icon icon="mdi:arrow-right" /></template>
            查看全部任务
          </el-button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div 
            v-for="task in placeholderTasks" 
            :key="task.id"
            class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-all hover:border-blue-300"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="flex-1">
                <h3 class="text-lg font-bold text-gray-900 mb-2 line-clamp-1">{{ task.name }}</h3>
                <p class="text-sm text-gray-600 line-clamp-2 mb-3">{{ task.description }}</p>
              </div>
              <div class="ml-3 shrink-0">
                <el-tag 
                  :type="task.statusType"
                  size="small"
                >
                  {{ task.status }}
                </el-tag>
              </div>
            </div>

            <div class="space-y-3 mb-4">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:account" class="text-blue-500" />
                  负责人
                </span>
                <span class="font-medium text-gray-900">{{ task.assignee }}</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:calendar-clock" class="text-green-500" />
                  截止时间
                </span>
                <span class="font-medium text-gray-900">{{ task.deadline }}</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:chart-line" class="text-purple-500" />
                  完成进度
                </span>
                <span class="font-medium text-gray-900">{{ task.progress }}%</span>
              </div>
            </div>

            <div class="mb-4">
              <div class="flex justify-between text-xs text-gray-600 mb-1">
                <span>执行进度</span>
                <span>{{ task.completedSteps }}/{{ task.totalSteps }} 步骤</span>
              </div>
              <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  class="h-full bg-linear-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
                  :style="{ width: task.progress + '%' }"
                ></div>
              </div>
            </div>

            <div class="flex items-center gap-2 pt-4 border-t border-gray-200">
              <el-button type="primary" link size="small" class="flex-1">
                <template #icon><Icon icon="mdi:eye" /></template>
                查看详情
              </el-button>
              <el-button type="warning" link size="small">
                <template #icon><Icon icon="mdi:pencil" /></template>
                编辑
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="placeholderTasks.length === 0" class="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-300">
          <Icon icon="mdi:clipboard-outline" class="text-6xl text-gray-300 mb-4" />
          <p class="text-gray-500 text-lg mb-2">暂无任务</p>
          <p class="text-gray-400 text-sm">创建新任务后，将显示在这里</p>
        </div>
      </div>
    </section>

    <!-- 任务统计 -->
    <section class="py-12 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:chart-bar" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">任务</span>统计</span>
          </h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 border border-blue-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:clipboard-list" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">总任务数</h3>
                  <p class="text-sm text-gray-500">全部任务</p>
                </div>
              </div>
            </div>
            <p class="text-3xl font-bold text-gray-900">156</p>
          </div>

          <div class="bg-linear-to-br from-green-50 to-white rounded-2xl p-6 border border-green-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-green-500 to-emerald-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:check-circle" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">已完成</h3>
                  <p class="text-sm text-gray-500">成功完成</p>
                </div>
              </div>
            </div>
            <p class="text-3xl font-bold text-gray-900">125</p>
          </div>

          <div class="bg-linear-to-br from-amber-50 to-white rounded-2xl p-6 border border-amber-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-amber-500 to-orange-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:clock-outline" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">进行中</h3>
                  <p class="text-sm text-gray-500">正在执行</p>
                </div>
              </div>
            </div>
            <p class="text-3xl font-bold text-gray-900">23</p>
          </div>

          <div class="bg-linear-to-br from-red-50 to-white rounded-2xl p-6 border border-red-100 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-red-500 to-pink-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:alert-circle" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">待处理</h3>
                  <p class="text-sm text-gray-500">等待处理</p>
                </div>
              </div>
            </div>
            <p class="text-3xl font-bold text-gray-900">8</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'

export default {
  name: 'TaskManagement',
  components: {
    Header,
    Icon
  },
  data() {
    return {
      placeholderTasks: [
        {
          id: 'task-001',
          name: '数据采集任务',
          description: '收集社交媒体平台的技术讨论和热点话题信息',
          status: '进行中',
          statusType: 'warning',
          assignee: '系统管理员',
          deadline: '2024-12-31',
          progress: 65,
          completedSteps: 13,
          totalSteps: 20
        },
        {
          id: 'task-002',
          name: '信息分析任务',
          description: '分析收集到的数据，提取关键信息和趋势',
          status: '进行中',
          statusType: 'warning',
          assignee: '数据分析师',
          deadline: '2024-12-30',
          progress: 45,
          completedSteps: 9,
          totalSteps: 20
        },
        {
          id: 'task-003',
          name: '报告生成任务',
          description: '生成月度分析报告，汇总所有收集和分析结果',
          status: '待处理',
          statusType: 'info',
          assignee: '报告专员',
          deadline: '2025-01-05',
          progress: 0,
          completedSteps: 0,
          totalSteps: 10
        }
      ]
    }
  }
}
</script>
