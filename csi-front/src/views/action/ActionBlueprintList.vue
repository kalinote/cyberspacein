<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    
    <FunctionalPageHeader
      title-prefix="行动蓝图"
      title-suffix="列表"
      subtitle="查看和管理所有行动蓝图"
    />

    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 工具栏 -->
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="flex flex-col md:flex-row gap-4 items-center justify-between">
          <div class="flex-1 w-full md:w-auto">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索蓝图名称或描述..."
              clearable
              @input="handleSearch"
              class="w-full"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <div class="flex items-center gap-3">
            <el-button-group>
              <el-button 
                :type="viewMode === 'grid' ? 'primary' : ''" 
                @click="viewMode = 'grid'"
              >
                <template #icon><Icon icon="mdi:view-grid" /></template>
                网格视图
              </el-button>
              <el-button 
                :type="viewMode === 'list' ? 'primary' : ''" 
                @click="viewMode = 'list'"
              >
                <template #icon><Icon icon="mdi:table" /></template>
                列表视图
              </el-button>
            </el-button-group>
            <button 
              class="bg-blue-500 text-white py-2 px-4 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2"
              @click="handleCreateBlueprint"
            >
              <Icon icon="mdi:rocket-launch-outline" />
              <span>创建蓝图</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[400px]">
          <!-- 网格视图 -->
          <div v-if="viewMode === 'grid'" class="p-6">
            <div v-if="blueprints.length === 0" class="flex flex-col items-center justify-center py-16">
              <Icon icon="mdi:file-document-outline" class="text-6xl text-gray-300 mb-4" />
              <p class="text-gray-500 text-lg mb-2">暂无行动蓝图</p>
              <p class="text-gray-400 text-sm">创建新蓝图后，将显示在这里</p>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
              <div 
                v-for="blueprint in blueprints" 
                :key="blueprint.id"
                class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow flex flex-col"
              >
                <div class="mb-4">
                  <h3 class="text-xl font-bold text-gray-900 mb-4 line-clamp-2">{{ blueprint.title }}</h3>
                  <div class="flex items-center gap-2 flex-wrap">
                    <el-tag 
                      class="border-0" 
                      :style="{ backgroundColor: blueprint.taskTypeTagColor, color: blueprint.taskTypeTagTextColor }"
                    >
                      {{ blueprint.taskType }}
                    </el-tag>
                    <el-tag 
                      v-if="blueprint.isTemplate"
                      type="warning"
                      class="border-0"
                    >
                      模板
                    </el-tag>
                  </div>
                </div>

                <div class="space-y-3 mb-6 flex-1">
                  <div class="flex items-start space-x-3">
                    <Icon icon="mdi:target" class="text-blue-500 text-lg mt-0.5 shrink-0" />
                    <div class="flex-1">
                      <p class="text-sm text-gray-500 mb-1">任务目标</p>
                      <p class="text-sm font-medium text-gray-900 line-clamp-2">{{ blueprint.taskGoal }}</p>
                    </div>
                  </div>

                  <div class="flex items-start space-x-3">
                    <Icon icon="mdi:server-network" class="text-green-500 text-lg mt-0.5 shrink-0" />
                    <div class="flex-1">
                      <p class="text-sm text-gray-500 mb-1">资源分配</p>
                      <p class="text-sm font-medium text-gray-900">{{ blueprint.resourceAllocation }}</p>
                    </div>
                  </div>

                  <div class="flex items-start space-x-3">
                    <Icon icon="mdi:format-list-numbered" class="text-purple-500 text-lg mt-0.5 shrink-0" />
                    <div class="flex-1">
                      <p class="text-sm text-gray-500 mb-1">行动步骤</p>
                      <div class="flex items-center flex-wrap gap-2 text-sm font-medium text-gray-900">
                        <span>{{ blueprint.branchCount }} 个分支，共{{ blueprint.stepCount }} 个步骤</span>
                        <div @click.stop="viewBlueprint(blueprint)" class="text-blue-500 cursor-pointer hover:text-blue-600 transition-colors">
                          查看
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex items-start space-x-3">
                    <Icon icon="mdi:calendar-clock" class="text-amber-500 text-lg mt-0.5 shrink-0" />
                    <div class="flex-1">
                      <p class="text-sm text-gray-500 mb-1">执行期限</p>
                      <p class="text-sm font-medium text-gray-900">{{ blueprint.executionDeadline }}</p>
                    </div>
                  </div>
                </div>

                <div class="pt-4 border-t border-gray-200 flex flex-col gap-2 mt-auto">
                  <el-button 
                    type="primary" 
                    class="w-full ml-0!" 
                    @click="createActionFromBlueprint(blueprint)"
                  >
                    <template #icon><Icon icon="mdi:rocket-launch" /></template>
                    立即执行行动
                  </el-button>
                  <el-button 
                    plain 
                    class="w-full ml-0!" 
                    @click="createBranchVersion(blueprint)"
                  >
                    <template #icon><Icon icon="mdi:source-branch" /></template>
                    从此蓝图创建分支
                  </el-button>
                  <el-button 
                    plain 
                    class="w-full ml-0! text-red-500! border-red-500!" 
                    @click="handleDeleteBlueprint(blueprint)"
                  >
                    <template #icon><Icon icon="mdi:delete-outline" /></template>
                    删除该蓝图
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 列表视图 -->
          <div v-else class="overflow-x-auto">
            <el-table :data="blueprints" stripe style="width: 100%">
              <el-table-column prop="title" label="名称" min-width="200">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ row.title }}</span>
                    <el-tag 
                      v-if="row.isTemplate"
                      type="warning"
                      size="small"
                      class="border-0"
                    >
                      模板
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="taskType" label="类型" width="150">
                <template #default="{ row }">
                  <el-tag 
                    class="border-0" 
                    :style="{ backgroundColor: row.taskTypeTagColor, color: row.taskTypeTagTextColor }"
                  >
                    {{ row.taskType }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="taskGoal" label="目标" min-width="250" show-overflow-tooltip />
              <el-table-column prop="stepCount" label="步骤数" width="120">
                <template #default="{ row }">
                  <div class="text-sm">
                    <span class="font-medium">{{ row.stepCount }}</span>
                    <span class="text-gray-500 ml-1">({{ row.branchCount }}分支)</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="executionDeadline" label="执行期限" width="150" />
              <el-table-column label="操作" width="300" fixed="right">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <el-button type="primary" link size="small" @click="viewBlueprint(row)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link size="small" @click="createActionFromBlueprint(row)">
                      <template #icon><Icon icon="mdi:rocket-launch" /></template>
                      执行
                    </el-button>
                    <el-button plain size="small" @click="createBranchVersion(row)">
                      <template #icon><Icon icon="mdi:source-branch" /></template>
                      分支
                    </el-button>
                    <el-button type="danger" link size="small" @click="handleDeleteBlueprint(row)">
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
        <div v-if="blueprints.length > 0" class="p-6 border-t border-gray-200 flex justify-center">
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

    <!-- 蓝图流程图弹窗 -->
    <BlueprintFlowDialog
      v-model="blueprintDialogVisible"
      :blueprint-id="selectedBlueprintId"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import BlueprintFlowDialog from '@/components/action/BlueprintFlowDialog.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const viewMode = ref('grid')
const searchKeyword = ref('')

const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0
})

const blueprints = ref([])
const blueprintDialogVisible = ref(false)
const selectedBlueprintId = ref(null)

const formatImplementationPeriod = (seconds) => {
  if (!seconds || seconds <= 0) {
    return '未设置'
  }
  
  const oneDay = 24 * 3600
  const oneHour = 3600
  const oneMinute = 60
  
  if (seconds >= oneDay) {
    const days = Math.floor(seconds / oneDay)
    return `${days}天`
  } else if (seconds >= oneHour) {
    const hours = Math.floor(seconds / oneHour)
    return `${hours}小时`
  } else if (seconds >= oneMinute) {
    const minutes = Math.floor(seconds / oneMinute)
    return `${minutes}分钟`
  } else {
    return `${seconds}秒`
  }
}

const fetchBlueprints = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    const result = await getPaginatedData(actionApi.getBlueprintsBaseInfo, params)
    
    blueprints.value = (result.items || []).map(item => {
      return {
        id: item.id,
        title: item.name || '',
        taskType: item.type || '尚未实现',
        taskTypeTagColor: item.type_tag_color || '#dbeafe',
        taskTypeTagTextColor: item.type_text_color || '#1e40af',
        taskGoal: item.target || '',
        resourceAllocation: '未配置',
        executionDeadline: formatImplementationPeriod(item.implementation_period),
        branchCount: item.branches || 0,
        stepCount: item.steps || 0,
        isTemplate: item.is_template || false
      }
    })
    
    pagination.value.total = result.pagination.total
    pagination.value.page = result.pagination.page
    pagination.value.pageSize = result.pagination.pageSize
  } catch (error) {
    console.error('获取行动蓝图失败:', error)
    ElMessage.error('获取行动蓝图失败')
    blueprints.value = []
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.page = 1
  fetchBlueprints()
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchBlueprints()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchBlueprints()
}

const viewBlueprint = (blueprint) => {
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }
  selectedBlueprintId.value = blueprint.id
  blueprintDialogVisible.value = true
}

const createActionFromBlueprint = async (blueprint) => {
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }

  try {
    const response = await actionApi.runAction({
      blueprint_id: blueprint.id
    })

    if (response.code === 0 && response.data && response.data.action_id) {
      ElMessage.success('行动已创建并开始执行')
      router.push(`/action/${response.data.action_id}`)
    } else {
      ElMessage.error(response.message || '创建行动失败')
    }
  } catch (error) {
    console.error('创建行动失败:', error)
    ElMessage.error(error.message || '创建行动失败，请稍后重试')
  }
}

const createBranchVersion = (blueprint) => {
  ElMessage.info('创建分支版本功能开发中...')
}

const handleCreateBlueprint = () => {
  router.push('/action/new')
}

const handleDeleteBlueprint = (blueprint) => {
  ElMessageBox.confirm(
    '确定要删除此蓝图吗？',
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    const index = blueprints.value.findIndex(b => b.id === blueprint.id)
    if (index > -1) {
      blueprints.value.splice(index, 1)
      pagination.value.total -= 1
      ElMessage.success('已删除')
    }
  }).catch(() => {
    ElMessage.info('已取消删除')
  })
}

onMounted(() => {
  fetchBlueprints()
})
</script>

