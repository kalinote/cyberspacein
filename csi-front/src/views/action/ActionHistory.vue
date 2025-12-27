<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    
    <section class="bg-linear-to-br from-blue-50 to-white py-6 border-b border-gray-200">
      <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-6">
            <el-button type="primary" link @click="$router.back()" class="shrink-0">
              <template #icon>
                <Icon icon="mdi:arrow-left" />
              </template>
              返回
            </el-button>
            <div class="border-l border-gray-300 h-8"></div>
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-1">
                <span class="text-blue-500">历史行动</span>记录
              </h1>
              <p class="text-sm text-gray-600">查看所有已创建和已执行的行动历史记录</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 筛选栏 -->
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">搜索行动</label>
            <el-input
              v-model="filters.keyword"
              placeholder="搜索行动名称或描述..."
              clearable
              @input="handleFilterChange"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">状态筛选</label>
            <el-select
              v-model="filters.status"
              placeholder="全部状态"
              clearable
              class="w-full"
              @change="handleFilterChange"
            >
              <el-option label="全部状态" value="" />
              <el-option label="执行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="已暂停" value="paused" />
              <el-option label="已停止" value="stopped" />
              <el-option label="失败" value="failed" />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">时间范围</label>
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              class="w-full"
              @change="handleFilterChange"
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

      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <div class="bg-white rounded-xl p-6 shadow-sm border border-blue-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">总行动数</p>
              <p class="text-2xl font-bold text-gray-900">{{ statistics.total }}</p>
            </div>
            <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <Icon icon="mdi:file-document-multiple" class="text-blue-600 text-2xl" />
            </div>
          </div>
        </div>
        <div class="bg-white rounded-xl p-6 shadow-sm border border-green-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">已完成</p>
              <p class="text-2xl font-bold text-gray-900">{{ statistics.completed }}</p>
            </div>
            <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <Icon icon="mdi:check-circle" class="text-green-600 text-2xl" />
            </div>
          </div>
        </div>
        <div class="bg-white rounded-xl p-6 shadow-sm border border-amber-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">执行中</p>
              <p class="text-2xl font-bold text-gray-900">{{ statistics.running }}</p>
            </div>
            <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
              <Icon icon="mdi:play-circle" class="text-amber-600 text-2xl" />
            </div>
          </div>
        </div>
        <div class="bg-white rounded-xl p-6 shadow-sm border border-red-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">失败</p>
              <p class="text-2xl font-bold text-gray-900">{{ statistics.failed }}</p>
            </div>
            <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
              <Icon icon="mdi:alert-circle" class="text-red-600 text-2xl" />
            </div>
          </div>
        </div>
      </div>

      <!-- 行动列表 -->
      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 class="text-lg font-bold text-gray-900">行动列表</h2>
          <div class="flex items-center gap-3">
            <el-button-group>
              <el-button :type="viewMode === 'card' ? 'primary' : ''" @click="viewMode = 'card'">
                <template #icon><Icon icon="mdi:view-grid" /></template>
                卡片视图
              </el-button>
              <el-button :type="viewMode === 'table' ? 'primary' : ''" @click="viewMode = 'table'">
                <template #icon><Icon icon="mdi:table" /></template>
                表格视图
              </el-button>
            </el-button-group>
          </div>
        </div>

        <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[400px]">
          <!-- 卡片视图 -->
          <div v-if="viewMode === 'card'" class="p-6">
            <div v-if="filteredActions.length === 0" class="flex flex-col items-center justify-center py-16">
              <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
              <p class="text-gray-500 text-lg mb-2">暂无行动记录</p>
              <p class="text-gray-400 text-sm">创建新行动后，历史记录将显示在这里</p>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
              <div
                v-for="action in filteredActions"
                :key="action.id"
                class="bg-gray-50 rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all cursor-pointer"
                @click="viewActionDetail(action.id)"
              >
                <div class="flex items-start justify-between mb-4">
                  <div class="flex-1">
                    <h3 class="text-lg font-bold text-gray-900 mb-2 line-clamp-1">{{ action.name }}</h3>
                    <p class="text-sm text-gray-600 line-clamp-2 mb-3">{{ action.description }}</p>
                  </div>
                  <el-tag
                    :type="getStatusTagType(action.status)"
                    size="small"
                    class="shrink-0 ml-2 border-0"
                  >
                    {{ getStatusText(action.status) }}
                  </el-tag>
                </div>

                <div class="space-y-2 mb-4">
                  <div v-if="action.startTime" class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:play-circle" class="text-green-500" />
                      开始时间
                    </span>
                    <span class="font-medium text-gray-900">{{ formatDateTime(action.startTime) }}</span>
                  </div>
                  <div v-if="action.endTime" class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:stop-circle" class="text-red-500" />
                      结束时间
                    </span>
                    <span class="font-medium text-gray-900">{{ formatDateTime(action.endTime) }}</span>
                  </div>
                  <div v-if="action.duration" class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:clock-outline" class="text-purple-500" />
                      执行时长
                    </span>
                    <span class="font-medium text-gray-900">{{ formatDuration(action.duration, 'milliseconds') }}</span>
                  </div>
                </div>

                <div v-if="action.status === 'running' || action.status === 'completed'" class="mb-4">
                  <div class="flex justify-between text-xs text-gray-600 mb-1">
                    <span>执行进度</span>
                    <span v-if="action.completedSteps && action.totalSteps">
                      {{ action.completedSteps }}/{{ action.totalSteps }} 步骤
                    </span>
                  </div>
                  <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-linear-to-r from-blue-500 to-cyan-400 rounded-full transition-all"
                      :style="{ width: (action.progress || 0) + '%' }"
                    ></div>
                  </div>
                </div>

                <div class="flex items-center gap-2 pt-4 border-t border-gray-200">
                  <el-button type="primary" link size="small" class="flex-1" @click.stop="viewActionDetail(action.id)">
                    <template #icon><Icon icon="mdi:eye" /></template>
                    查看详情
                  </el-button>
                  <el-button
                    v-if="action.status === 'completed'"
                    type="success"
                    link
                    size="small"
                    @click.stop="rerunAction(action.id)"
                  >
                    <template #icon><Icon icon="mdi:replay" /></template>
                    重新执行
                  </el-button>
                  <el-button type="danger" link size="small" @click.stop="deleteAction(action.id)">
                    <template #icon><Icon icon="mdi:delete" /></template>
                    删除
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 表格视图 -->
          <div v-else class="overflow-x-auto">
            <el-table :data="filteredActions" stripe style="width: 100%">
              <el-table-column prop="name" label="行动名称" min-width="200">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full" :class="getStatusDotClass(row.status)"></div>
                    <span class="font-medium">{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="getStatusTagType(row.status)" size="small" class="border-0">
                    {{ getStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="startTime" label="开始时间" width="180">
                <template #default="{ row }">
                  {{ row.startTime ? formatDateTime(row.startTime) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="endTime" label="结束时间" width="180">
                <template #default="{ row }">
                  {{ row.endTime ? formatDateTime(row.endTime) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="progress" label="进度" width="120">
                <template #default="{ row }">
                  <div v-if="row.progress !== undefined" class="flex items-center gap-2">
                    <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        class="h-full bg-blue-500 rounded-full"
                        :style="{ width: row.progress + '%' }"
                      ></div>
                    </div>
                    <span class="text-xs text-gray-600 w-10 text-right">{{ row.progress }}%</span>
                  </div>
                  <span v-else class="text-gray-400">-</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <el-button type="primary" link size="small" @click="viewActionDetail(row.id)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button
                      v-if="row.status === 'completed'"
                      type="success"
                      link
                      size="small"
                      @click="rerunAction(row.id)"
                    >
                      <template #icon><Icon icon="mdi:replay" /></template>
                      重跑
                    </el-button>
                    <el-button type="danger" link size="small" @click="deleteAction(row.id)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="filteredActions.length > 0" class="p-6 border-t border-gray-200 flex justify-center">
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  formatDateTime,
  formatDuration,
  getStatusText,
  getStatusTagType,
  getStatusDotClass
} from '@/utils/action'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const viewMode = ref('card')

const filters = ref({
  keyword: '',
  status: '',
  dateRange: null
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const statistics = ref({
  total: 0,
  completed: 0,
  running: 0,
  failed: 0
})

const actions = ref([])

const filteredActions = computed(() => {
  let result = [...actions.value]

  if (filters.value.keyword) {
    const keyword = filters.value.keyword.toLowerCase()
    result = result.filter(action =>
      action.name.toLowerCase().includes(keyword) ||
      action.description.toLowerCase().includes(keyword)
    )
  }

  if (filters.value.status) {
    result = result.filter(action => action.status === filters.value.status)
  }

  return result
})

const fetchActions = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    
    const result = await getPaginatedData(actionApi.getActionHistory, params)
    
    actions.value = (result.items || []).map(item => ({
      ...item,
      startTime: item.start_at || null,
      endTime: item.finished_at || null,
      completedSteps: item.completed_steps || 0,
      totalSteps: item.total_steps || 0,
      duration: item.duration ? item.duration * 1000 : 0
    }))
    
    pagination.value.total = result.pagination.total
    pagination.value.page = result.pagination.page
    pagination.value.pageSize = result.pagination.pageSize
    
    updateStatistics()
  } catch (error) {
    console.error('获取行动历史失败:', error)
    actions.value = []
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  pagination.value.page = 1
  fetchActions()
}

const updateStatistics = () => {
  statistics.value.total = actions.value.length
  statistics.value.completed = actions.value.filter(a => a.status === 'completed').length
  statistics.value.running = actions.value.filter(a => a.status === 'running').length
  statistics.value.failed = actions.value.filter(a => a.status === 'failed').length
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchActions()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchActions()
}

const viewActionDetail = (actionId) => {
  router.push(`/action/${actionId}`)
}

const rerunAction = (actionId) => {
  ElMessageBox.confirm(
    '确定要重新执行此行动吗？',
    '确认重新执行',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    }
  ).then(() => {
    ElMessage.success('行动已加入执行队列')
  }).catch(() => {
    ElMessage.info('已取消')
  })
}

const deleteAction = (actionId) => {
  ElMessageBox.confirm(
    '确定要删除此行动吗？此操作不可恢复。',
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    const index = actions.value.findIndex(a => a.id === actionId)
    if (index > -1) {
      actions.value.splice(index, 1)
      updateStatistics()
      ElMessage.success('行动已删除')
    }
  }).catch(() => {
    ElMessage.info('已取消删除')
  })
}

onMounted(() => {
  fetchActions()
})
</script>
