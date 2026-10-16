<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    <MobileBlueprintList v-if="isMobile" :blueprints="blueprints" :pagination="pagination" :loading="loading" :error="listError" :pinned="mobilePinned" :starting="actionStarting" :preparing="preparingEncapsulation" :can-encapsulate="canEncapsulate"
      @retry="fetchBlueprints" @create="handleCreateBlueprint" @page-change="handlePageChange" @filter="mobilePinned = $event; handleSearch()" @pin-change="handleMobilePinChange" @view="viewBlueprint" @edit="editBlueprint" @history="openRevisionHistory" @publish="openPublishDialog" @encapsulate="openEncapsulateDialog" @delete="handleDeleteBlueprint" @run="createActionFromBlueprint" />
    <template v-else>
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
              <ActionBlueprintCard
                v-for="blueprint in blueprints"
                :key="blueprint.id"
                :blueprint="blueprint"
                :disabled="actionStarting"
                @pin-change="blueprint.isPinned = $event"
                @view="viewBlueprint(blueprint)"
                @edit="editBlueprint(blueprint)"
                @publish="openPublishDialog(blueprint)"
                @encapsulate="openEncapsulateDialog(blueprint)"
                @history="openRevisionHistory(blueprint)"
                @branch="createBranchVersion(blueprint)"
                @run="createActionFromBlueprint(blueprint, false, $event)"
                @debug="createActionFromBlueprint(blueprint, true, $event)"
                @delete="handleDeleteBlueprint(blueprint)"
              />
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
                    v-if="row.taskType"
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
              <el-table-column
                v-if="hasPerm(PERM.operations.action.blueprint.update)"
                label="主页置顶"
                width="140"
              >
                <template #default="{ row }">
                  <BlueprintPinButton :blueprint="row" @change="row.isPinned = $event" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="420" fixed="right">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <el-button type="primary" link size="small" @click="viewBlueprint(row)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <BlueprintRunControl
                      compact
                      :disabled="actionStarting"
                      :scheduling-mode="row.defaultSchedulingMode"
                      @run="createActionFromBlueprint(row, false, $event)"
                      @debug="createActionFromBlueprint(row, true, $event)"
                    />
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

    </template>
    <!-- 蓝图流程图弹窗 -->
    <BlueprintFlowDialog
      v-model="blueprintDialogVisible"
      :blueprint-id="selectedBlueprintId"
    />

    <!-- 模板参数输入弹窗 -->
    <TemplateParamsDialog
      v-model="templateParamsDialogVisible"
      :blueprint-id="selectedBlueprintForRun?.id"
      :debug="selectedRunDebug"
      :scheduling-mode="selectedRunSchedulingMode"
      :submitting="actionStarting"
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
    <component :is="isMobile ? MobileSheet : 'el-dialog'" v-model="revisionDialogVisible" title="蓝图发布历史" width="720px">
      <div v-if="isMobile" class="mobile-revision-history" v-loading="revisionsLoading"><p class="mobile-revision-title">{{ revisionBlueprint?.title }}</p><div v-if="revisionError" class="mobile-revision-error" role="alert"><p>{{ revisionError }}</p><el-button @click="openRevisionHistory(revisionBlueprint)">重新加载</el-button></div><article v-else v-for="revision in revisions" :key="revision.id" class="mobile-revision-card"><div><strong>Revision {{ revision.revision_number }}</strong><el-tag size="small">{{ revision.version }}</el-tag></div><p>{{ formatPublishedAt(revision.published_at) }}</p><details><summary>版本标识与公开接口</summary><dl><dt>版本 ID</dt><dd>{{ revision.id }}</dd><dt>内容哈希</dt><dd>{{ revision.content_hash }}</dd><dt>发布人</dt><dd>{{ revision.published_by || '未记录' }}</dd></dl><div v-for="direction in ['inputs', 'outputs']" :key="direction"><h3>{{ direction === 'inputs' ? '输入' : '输出' }}</h3><p v-for="port in revision.interface_snapshot?.[direction] || []" :key="port.id">{{ port.label || port.name }} · {{ port.interface_type_id }}</p><p v-if="!revision.interface_snapshot?.[direction]?.length">暂无</p></div></details></article></div>
      <el-table v-else v-loading="revisionsLoading" :data="revisions" size="small">
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
        v-if="!revisionsLoading && !revisionError && revisions.length === 0"
        description="尚未发布 Revision"
        :image-size="56"
      />
    </component>
  </div>
</template>

<script setup>
defineOptions({ name: 'ActionBlueprintList' })
import { ref, computed, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import ActionBlueprintCard from '@/components/action/ActionBlueprintCard.vue'
import BlueprintFlowDialog from '@/components/action/BlueprintFlowDialog.vue'
import TemplateParamsDialog from '@/components/action/template/TemplateParamsDialog.vue'
import BlueprintPublishDialog from '@/components/action/BlueprintPublishDialog.vue'
import BlueprintEncapsulateDialog from '@/components/action/BlueprintEncapsulateDialog.vue'
import BlueprintRunControl from '@/components/action/BlueprintRunControl.vue'
import BlueprintPinButton from '@/components/action/BlueprintPinButton.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { buildActionRunRequest } from '@/utils/action/run'
import { PERM } from '@/utils/permissions'
import { hasAll, hasPerm } from '@/utils/permissionKit'
import MobileBlueprintList from '@/components/action/MobileBlueprintList.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'

const router = useRouter()
const { isMobile } = useMobileViewport()
const mobilePinned = ref('')
const listError = ref('')
const revisionError = ref('')
const revisionBlueprint = ref(null)
const preparingEncapsulation = ref(false)
let listGeneration = 0
let revisionGeneration = 0
let encapsulationGeneration = 0
let pageActive = true
const canExecute = computed(() => hasAll([PERM.operations.action.blueprint.read, PERM.operations.action.instance.execute]))

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
const selectedRunDebug = ref(false)
const selectedRunSchedulingMode = ref('barrier')
const actionStarting = ref(false)
const selectedBlueprintForRelease = ref(null)
const selectedBlueprintForEncapsulation = ref(null)
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
  PERM.operations.action.node.create,
  ...(isMobile.value ? [PERM.operations.action.node.read] : [])
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
  if (!pageActive || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.read))) return
  const generation = ++listGeneration
  listError.value = ''
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (isMobile.value && mobilePinned.value !== '') params.is_pinned = mobilePinned.value === 'true'
    
    const result = await getPaginatedData(actionApi.getBlueprintsBaseInfo, params)
    if (!pageActive || generation !== listGeneration) return
    
    blueprints.value = (result.items || []).map(item => {
      return {
        id: item.id,
        title: item.name || '',
        description: item.description || '',
        taskType: item.default_scheduling_mode === 'streaming' ? '异步执行' : '',
        taskTypeTagColor: item.type_tag_color || '#dbeafe',
        taskTypeTagTextColor: item.type_text_color || '#1e40af',
        taskGoal: item.target || '',
        resourceAllocation: '未配置',
        executionDeadline: formatImplementationPeriod(item.implementation_period),
        branchCount: item.branches || 0,
        stepCount: item.steps || 0,
        isTemplate: item.is_template || false,
        isPinned: item.is_pinned || false,
        defaultSchedulingMode: item.default_scheduling_mode === 'streaming' ? 'streaming' : 'barrier',
        latestRevisionNumber: item.latest_revision_number,
        encapsulatedNodeCount: item.encapsulated_node_count || 0
      }
    })
    
    pagination.value.total = result.pagination.total
    pagination.value.page = result.pagination.page
    pagination.value.pageSize = result.pagination.pageSize
  } catch (error) {
    if (!pageActive || generation !== listGeneration) return
    console.error('获取行动蓝图失败:', error)
    ElMessage.error('获取行动蓝图失败')
    blueprints.value = []
    listError.value = '蓝图列表加载失败，请重试'
  } finally {
    if (generation === listGeneration) loading.value = false
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
  if (isMobile.value && !hasPerm(PERM.operations.action.blueprint.read)) return
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }
  selectedBlueprintId.value = blueprint.id
  blueprintDialogVisible.value = true
}

const createActionFromBlueprint = async (
  blueprint,
  debug = false,
  schedulingMode = blueprint?.defaultSchedulingMode || 'barrier'
) => {
  if (!pageActive || actionStarting.value || (isMobile.value && !canExecute.value)) return
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }

  if (debug && !blueprint.isTemplate) {
    try {
      await ElMessageBox.confirm(
        '调试运行会启用蓝图中的调试输出节点，并将接收到的数据写入行动日志。',
        '调试运行',
        {
          confirmButtonText: '开始调试',
          cancelButtonText: '取消',
          type: 'info'
        }
      )
    } catch {
      return
    }
  }

  if (!pageActive || (isMobile.value && !canExecute.value)) return
  selectedRunDebug.value = debug
  selectedRunSchedulingMode.value = schedulingMode === 'streaming' ? 'streaming' : 'barrier'
  if (blueprint.isTemplate) {
    templateParamsDialogVisible.value = true
    selectedBlueprintForRun.value = blueprint
  } else {
    await runBlueprint(blueprint.id, null, debug, selectedRunSchedulingMode.value)
  }
}

const runBlueprint = async (blueprintId, params, debug = false, schedulingMode = 'barrier') => {
  if (!pageActive || actionStarting.value || (isMobile.value && !canExecute.value)) return false
  actionStarting.value = true
  try {
    const data = buildActionRunRequest(blueprintId, params, debug, schedulingMode)

    const response = await actionApi.runAction(data)

    if (response.code === 0 && response.data && response.data.action_id) {
      ElMessage.success('行动已创建并开始执行')
      if (pageActive && (!isMobile.value || hasPerm(PERM.pages.action.detail.access))) router.push(`/action/${response.data.action_id}`)
      return true
    } else {
      ElMessage.error(response.message || '创建行动失败')
      return false
    }
  } catch (error) {
    console.error('创建行动失败:', error)
    ElMessage.error(error.message || '创建行动失败，请稍后重试')
    return false
  } finally {
    actionStarting.value = false
  }
}

const handleParamsSubmit = async (params) => {
  if (!selectedBlueprintForRun.value?.id) return
  const started = await runBlueprint(
    selectedBlueprintForRun.value.id,
    params,
    selectedRunDebug.value,
    selectedRunSchedulingMode.value
  )
  if (started) templateParamsDialogVisible.value = false
}

const createBranchVersion = (blueprint) => {
  ElMessage.info('创建分支版本功能开发中...')
}

const editBlueprint = (blueprint) => {
  if (isMobile.value && !hasAll([PERM.operations.action.blueprint.update, PERM.pages.action.create.access])) return
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
  if (publishing.value || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.publish))) return
  selectedBlueprintForRelease.value = blueprint
  publishDialogVisible.value = true
}

const openRevisionHistory = async (blueprint) => {
  if (!blueprint?.id || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.read))) return
  const generation = ++revisionGeneration
  revisionBlueprint.value = blueprint
  revisionError.value = ''
  revisionDialogVisible.value = true
  revisionsLoading.value = true
  revisions.value = []
  try {
    const response = await actionApi.getBlueprintRevisions(blueprint.id)
    if (!pageActive || generation !== revisionGeneration) return
    revisions.value = response.data || []
  } catch {
    if (!pageActive || generation !== revisionGeneration) return
    revisions.value = []
    revisionError.value = '发布历史加载失败，请重试'
  } finally {
    if (generation === revisionGeneration) revisionsLoading.value = false
  }
}

const openEncapsulateDialog = async (blueprint) => {
  if (!blueprint?.id || preparingEncapsulation.value || encapsulating.value || (isMobile.value && !canEncapsulate.value)) return
  const generation = ++encapsulationGeneration
  preparingEncapsulation.value = true
  selectedBlueprintForEncapsulation.value = blueprint
  try {
    const [detailResponse, nodesResponse, validationResponse] = await Promise.all([
      actionApi.getBlueprint(blueprint.id),
      actionApi.getNodes(),
      actionApi.validateBlueprint(blueprint.id)
    ])
    if (!pageActive || generation !== encapsulationGeneration || (isMobile.value && !canEncapsulate.value)) return
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
    if (!pageActive || generation !== encapsulationGeneration) return
    console.error('准备封装蓝图失败:', error)
    ElMessage.error('准备封装蓝图失败')
  } finally {
    if (generation === encapsulationGeneration) preparingEncapsulation.value = false
  }
}

const handlePublish = async () => {
  const blueprint = selectedBlueprintForRelease.value
  if (!pageActive || !blueprint?.id || publishing.value || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.publish))) return
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
  const blueprint = selectedBlueprintForEncapsulation.value
  if (!pageActive || !blueprint?.id || encapsulating.value || (isMobile.value && !canEncapsulate.value)) return
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
  if (isMobile.value && !hasAll([PERM.operations.action.blueprint.create, PERM.pages.action.create.access])) return
  router.push('/action/new')
}

const handleDeleteBlueprint = async (blueprint) => {
  if (!blueprint?.id || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.delete))) return
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
    if (!pageActive || (isMobile.value && !hasPerm(PERM.operations.action.blueprint.delete))) return
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

/** """同步手机详情的置顶状态，当前筛选不再匹配时重新加载。""" */
const handleMobilePinChange = (id, pinned) => {
  const blueprint = blueprints.value.find(item => item.id === id)
  if (blueprint) blueprint.isPinned = pinned
  if (mobilePinned.value !== '' && String(pinned) !== mobilePinned.value) fetchBlueprints()
}

onActivated(() => {
  pageActive = true
  fetchBlueprints()
})
onDeactivated(() => {
  pageActive = false
  listGeneration++; revisionGeneration++; encapsulationGeneration++
  loading.value = false; revisionsLoading.value = false; preparingEncapsulation.value = false
  blueprintDialogVisible.value = false; templateParamsDialogVisible.value = false; publishDialogVisible.value = false; encapsulateDialogVisible.value = false; revisionDialogVisible.value = false
})
onBeforeUnmount(() => { pageActive = false; listGeneration++; revisionGeneration++; encapsulationGeneration++ })
</script>

<style scoped>
.mobile-revision-history { min-height: 100px; overflow-wrap: anywhere; }.mobile-revision-title { font-size: 14px; color: #64748b; margin-bottom: 12px; }.mobile-revision-error { text-align: center; padding: 18px 0; }.mobile-revision-error p { margin-bottom: 12px; }.mobile-revision-card { padding: 16px; border: 1px solid #e2e8f0; border-radius: 14px; margin-bottom: 12px; }.mobile-revision-card > div { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }.mobile-revision-card > p { color: #64748b; font-size: 12px; margin: 10px 0; }.mobile-revision-card summary { cursor: pointer; padding: 12px 0; font-size: 14px; color: #2563eb; }.mobile-revision-card dl { display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 10px; font-size: 12px; }.mobile-revision-card dt { color: #64748b; }.mobile-revision-card dd { margin: 0; }.mobile-revision-card h3 { margin: 14px 0 6px; font-size: 13px; font-weight: 700; }.mobile-revision-card details p { font-size: 12px; color: #475569; }
</style>

