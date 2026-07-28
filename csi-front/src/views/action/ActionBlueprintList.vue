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
                  <div class="flex flex-wrap items-center justify-center gap-2 pb-1">
                    <el-tooltip
                      v-if="hasPerm(PERM.operations.action.blueprint.update)"
                      content="编辑：修改蓝图配置与流程"
                      placement="top"
                      :show-after="250"
                    >
                      <el-button
                        plain
                        circle
                        size="small"
                        class="ml-0!"
                        aria-label="编辑蓝图"
                        @click="editBlueprint(blueprint)"
                      >
                        <Icon icon="mdi:pencil-outline" class="text-base" />
                      </el-button>
                    </el-tooltip>
                    <el-tooltip
                      v-if="hasPerm(PERM.operations.action.blueprint.publish)"
                      content="发布：生成不可变的蓝图版本"
                      placement="top"
                      :show-after="250"
                    >
                      <el-button
                        plain
                        circle
                        size="small"
                        class="ml-0!"
                        aria-label="发布不可变版本"
                        @click="openPublishDialog(blueprint)"
                      >
                        <Icon icon="mdi:tag-arrow-up-outline" class="text-base" />
                      </el-button>
                    </el-tooltip>
                    <el-tooltip
                      v-if="canEncapsulate"
                      content="封装：将蓝图封装为节点"
                      placement="top"
                      :show-after="250"
                    >
                      <el-button
                        plain
                        circle
                        size="small"
                        class="ml-0!"
                        aria-label="封装为节点"
                        @click="openEncapsulateDialog(blueprint)"
                      >
                        <Icon icon="mdi:package-variant-closed" class="text-base" />
                      </el-button>
                    </el-tooltip>
                    <el-tooltip
                      content="历史：查看已发布的不可变版本"
                      placement="top"
                      :show-after="250"
                    >
                      <el-button
                        plain
                        circle
                        size="small"
                        class="ml-0!"
                        aria-label="查看发布历史"
                        @click="openRevisionHistory(blueprint)"
                      >
                        <Icon icon="mdi:history" class="text-base" />
                      </el-button>
                    </el-tooltip>
                    <el-tooltip
                      content="分支：从当前蓝图创建新分支"
                      placement="top"
                      :show-after="250"
                    >
                      <el-button
                        plain
                        circle
                        size="small"
                        class="ml-0!"
                        aria-label="从此蓝图创建分支"
                        @click="createBranchVersion(blueprint)"
                      >
                        <Icon icon="mdi:source-branch" class="text-base" />
                      </el-button>
                    </el-tooltip>
                  </div>
                  <el-button 
                    type="primary" 
                    class="w-full ml-0!" 
                    @click="createActionFromBlueprint(blueprint)"
                  >
                    <template #icon><Icon icon="mdi:rocket-launch" /></template>
                    立即执行行动
                  </el-button>
                  <el-button 
                    v-if="hasPerm(PERM.operations.action.blueprint.delete)"
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
              <el-table-column label="操作" width="420" fixed="right">
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
                    <el-button v-if="hasPerm(PERM.operations.action.blueprint.update)" type="primary" link size="small" @click="editBlueprint(row)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button v-if="hasPerm(PERM.operations.action.blueprint.publish)" type="primary" link size="small" @click="openPublishDialog(row)">
                      发布
                    </el-button>
                    <el-button v-if="canEncapsulate" type="primary" link size="small" @click="openEncapsulateDialog(row)">
                      封装
                    </el-button>
                    <el-button type="primary" link size="small" @click="openRevisionHistory(row)">
                      版本
                    </el-button>
                    <el-button plain size="small" @click="createBranchVersion(row)">
                      <template #icon><Icon icon="mdi:source-branch" /></template>
                      分支
                    </el-button>
                    <el-button v-if="hasPerm(PERM.operations.action.blueprint.delete)" type="danger" link size="small" @click="handleDeleteBlueprint(row)">
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

    <!-- 模板参数输入弹窗 -->
    <TemplateParamsDialog
      v-model="templateParamsDialogVisible"
      :blueprint-id="selectedBlueprintForRun?.id"
      @submit="handleParamsSubmit"
    />
    <BlueprintPublishDialog
      v-model="publishDialogVisible"
      :submitting="publishing"
      @submit="handlePublish"
    />
    <BlueprintEncapsulateDialog
      v-model="encapsulateDialogVisible"
      :interfaces="encapsulateInterfaces"
      :target-nodes="encapsulatedTargetNodes"
      :submitting="encapsulating"
      @submit="handleEncapsulate"
    />
    <el-dialog v-model="revisionDialogVisible" title="蓝图发布历史" width="720px">
      <el-table v-loading="revisionsLoading" :data="revisions" size="small">
        <el-table-column prop="revision_number" label="Revision" width="100" />
        <el-table-column prop="version" label="蓝图版本" width="120" />
        <el-table-column label="内容哈希" min-width="220">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.content_hash?.slice(0, 16) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" min-width="180">
          <template #default="{ row }">{{ formatPublishedAt(row.published_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!revisionsLoading && revisions.length === 0"
        description="尚未发布 Revision"
        :image-size="56"
      />
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'ActionBlueprintList' })
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import BlueprintFlowDialog from '@/components/action/BlueprintFlowDialog.vue'
import TemplateParamsDialog from '@/components/action/template/TemplateParamsDialog.vue'
import BlueprintPublishDialog from '@/components/action/BlueprintPublishDialog.vue'
import BlueprintEncapsulateDialog from '@/components/action/BlueprintEncapsulateDialog.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { PERM } from '@/utils/permissions'
import { hasAll, hasPerm } from '@/utils/permissionKit'

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
const templateParamsDialogVisible = ref(false)
const selectedBlueprintForRun = ref(null)
const selectedBlueprintForRelease = ref(null)
const publishDialogVisible = ref(false)
const encapsulateDialogVisible = ref(false)
const publishing = ref(false)
const encapsulating = ref(false)
const encapsulateInterfaces = ref([])
const encapsulatedTargetNodes = ref([])
const revisionDialogVisible = ref(false)
const revisionsLoading = ref(false)
const revisions = ref([])
const canEncapsulate = computed(() => hasAll([
  PERM.operations.action.blueprint.read,
  PERM.operations.action.blueprint.publish,
  PERM.operations.action.node.create
]))
const formatPublishedAt = value => (
  value ? new Date(value).toLocaleString('zh-CN') : '-'
)

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
        isTemplate: item.is_template || false,
        latestRevisionNumber: item.latest_revision_number,
        encapsulatedNodeCount: item.encapsulated_node_count || 0
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

  if (blueprint.isTemplate) {
    templateParamsDialogVisible.value = true
    selectedBlueprintForRun.value = blueprint
  } else {
    await runBlueprint(blueprint.id, null)
  }
}

const runBlueprint = async (blueprintId, params) => {
  try {
    const data = { blueprint_id: blueprintId }
    if (params) {
      data.params = params
    }

    const response = await actionApi.runAction(data)

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

const handleParamsSubmit = async (params) => {
  await runBlueprint(selectedBlueprintForRun.value.id, params)
  templateParamsDialogVisible.value = false
}

const createBranchVersion = (blueprint) => {
  ElMessage.info('创建分支版本功能开发中...')
}

const editBlueprint = (blueprint) => {
  if (!blueprint?.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }
  router.push({
    name: 'edit-action-blueprint',
    params: { blueprintId: blueprint.id }
  })
}

const openPublishDialog = (blueprint) => {
  selectedBlueprintForRelease.value = blueprint
  publishDialogVisible.value = true
}

const openRevisionHistory = async (blueprint) => {
  if (!blueprint?.id || revisionsLoading.value) return
  revisionDialogVisible.value = true
  revisionsLoading.value = true
  revisions.value = []
  try {
    const response = await actionApi.getBlueprintRevisions(blueprint.id)
    revisions.value = response.data || []
  } catch {
    revisions.value = []
  } finally {
    revisionsLoading.value = false
  }
}

const openEncapsulateDialog = async (blueprint) => {
  selectedBlueprintForRelease.value = blueprint
  try {
    const [detailResponse, nodesResponse, validationResponse] = await Promise.all([
      actionApi.getBlueprint(blueprint.id),
      actionApi.getNodes(),
      actionApi.validateBlueprint(blueprint.id)
    ])
    const validation = validationResponse.data || {}
    if (!validation.valid) {
      ElMessage.error(validation.errors?.[0]?.message || '蓝图校验未通过')
      return
    }
    const detail = detailResponse.data || {}
    const interfaceSpec = detail.interface || validation.interface || {}
    encapsulateInterfaces.value = [
      ...(interfaceSpec.inputs || []),
      ...(interfaceSpec.outputs || [])
    ].map(item => ({
      ...item,
      interfaceTypeId: item.interface_type_id
    }))
    encapsulatedTargetNodes.value = (nodesResponse.data || []).filter(node => (
      node.node_kind === 'encapsulated'
      && node.source_blueprint_id === blueprint.id
      && node.is_latest
    ))
    encapsulateDialogVisible.value = true
  } catch (error) {
    console.error('准备封装蓝图失败:', error)
    ElMessage.error('准备封装蓝图失败')
  }
}

const handlePublish = async () => {
  const blueprint = selectedBlueprintForRelease.value
  if (!blueprint?.id) return
  publishing.value = true
  try {
    const response = await actionApi.publishBlueprint(blueprint.id)
    ElMessage.success(`已发布 Revision ${response.data?.revision?.revision_number || ''}`)
    publishDialogVisible.value = false
    await fetchBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  } finally {
    publishing.value = false
  }
}

const handleEncapsulate = async (form) => {
  const blueprint = selectedBlueprintForRelease.value
  if (!blueprint?.id) return
  encapsulating.value = true
  try {
    const response = await actionApi.encapsulateBlueprint(blueprint.id, form)
    ElMessage.success(`已生成封装节点 ${response.data?.encapsulated_node?.name || ''}`)
    encapsulateDialogVisible.value = false
    await fetchBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  } finally {
    encapsulating.value = false
  }
}

const handleCreateBlueprint = () => {
  router.push('/action/new')
}

const handleDeleteBlueprint = async (blueprint) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除蓝图“${blueprint.title}”吗？其所有历史行动和运行日志也将被永久删除，此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    ElMessage.info('已取消删除')
    return
  }

  try {
    await actionApi.deleteBlueprint(blueprint.id)
    ElMessage.success('蓝图及历史行动已删除')
    if (blueprints.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }
    await fetchBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  }
}

onMounted(() => {
  fetchBlueprints()
})
</script>

