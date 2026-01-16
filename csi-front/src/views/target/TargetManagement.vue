<template>
  <div>
    <Header />

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
              <button class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2">
                <Icon icon="mdi:clipboard-text-search-outline" />
                <span>新建分析任务</span>
              </button>
              <button class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2" @click="$router.push('/platforms')">
                <Icon icon="mdi:server-network" />
                <span>目标平台管理</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                <Icon icon="mdi:database" />
                <span>重点实体库</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 目标列表区域 -->
    <section class="py-12 bg-linear-to-b from-white to-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:format-list-bulleted" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">重点</span>实体</span>
          </h2>
          <div class="flex items-center gap-4">
            <el-input
              placeholder="搜索目标..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button type="primary">
              <template #icon><Icon icon="mdi:filter" /></template>
              筛选
            </el-button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="target in targets"
            :key="target.id"
            class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="flex-1">
                <h3 class="text-lg font-bold text-gray-900 mb-2">{{ target.name }}</h3>
                <el-tag :type="target.statusType" size="small">{{ target.status }}</el-tag>
              </div>
              <div class="ml-3 shrink-0">
                <div :class="['w-12 h-12 rounded-xl flex items-center justify-center', target.priorityBgColor]">
                  <Icon :icon="target.priorityIcon" :class="['text-2xl', target.priorityIconColor]" />
                </div>
              </div>
            </div>

            <div class="space-y-3 mb-4">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:tag" class="text-blue-500" />
                  优先级
                </span>
                <span class="font-medium text-gray-900">{{ target.priority }}</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:link-variant" class="text-green-500" />
                  关联行动
                </span>
                <span class="font-medium text-gray-900">{{ target.linkedActions }} 个</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:calendar" class="text-purple-500" />
                  创建时间
                </span>
                <span class="font-medium text-gray-900">{{ target.createdAt }}</span>
              </div>
            </div>

            <div class="pt-4 border-t border-gray-200">
              <div class="flex items-center gap-2">
                <el-button type="primary" link size="small" class="flex-1">
                  <template #icon><Icon icon="mdi:eye" /></template>
                  查看详情
                </el-button>
                <el-button type="primary" link size="small">
                  <template #icon><Icon icon="mdi:pencil" /></template>
                  编辑
                </el-button>
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
  </div>
</template>

<script>
import Header from '@/components/Header.vue'
import { Icon } from '@iconify/vue'

export default {
  name: 'TargetManagement',
  components: {
    Header,
    Icon
  },
  data() {
    return {
      statsTimeRange: 'week',
      targets: [
        {
          id: 1,
          name: '社交媒体舆情监控',
          status: '进行中',
          statusType: 'success',
          priority: '高',
          priorityIcon: 'mdi:alert-octagon',
          priorityBgColor: 'bg-red-100',
          priorityIconColor: 'text-red-600',
          linkedActions: 3,
          createdAt: '2025-01-05'
        },
        {
          id: 2,
          name: '网络安全威胁情报',
          status: '进行中',
          statusType: 'success',
          priority: '高',
          priorityIcon: 'mdi:alert-octagon',
          priorityBgColor: 'bg-red-100',
          priorityIconColor: 'text-red-600',
          linkedActions: 2,
          createdAt: '2025-01-03'
        },
        {
          id: 3,
          name: '技术论坛信息收集',
          status: '待启动',
          statusType: 'warning',
          priority: '中',
          priorityIcon: 'mdi:alert',
          priorityBgColor: 'bg-amber-100',
          priorityIconColor: 'text-amber-600',
          linkedActions: 1,
          createdAt: '2025-01-07'
        },
        {
          id: 4,
          name: '市场动态追踪',
          status: '进行中',
          statusType: 'success',
          priority: '中',
          priorityIcon: 'mdi:alert',
          priorityBgColor: 'bg-amber-100',
          priorityIconColor: 'text-amber-600',
          linkedActions: 2,
          createdAt: '2025-01-04'
        },
        {
          id: 5,
          name: '政策法规更新监控',
          status: '暂停',
          statusType: 'info',
          priority: '低',
          priorityIcon: 'mdi:information',
          priorityBgColor: 'bg-blue-100',
          priorityIconColor: 'text-blue-600',
          linkedActions: 0,
          createdAt: '2025-01-02'
        },
        {
          id: 6,
          name: '竞品动态分析',
          status: '已完成',
          statusType: '',
          priority: '中',
          priorityIcon: 'mdi:alert',
          priorityBgColor: 'bg-amber-100',
          priorityIconColor: 'text-amber-600',
          linkedActions: 1,
          createdAt: '2024-12-28'
        }
      ],
      targetStats: [
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
      ]
    }
  }
}
</script>

