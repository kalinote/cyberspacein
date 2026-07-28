<template>
  <div v-loading="loading" class="min-h-50">
    <el-alert
      v-if="loadError"
      class="mb-4"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
    >
      <template #default>
        <el-button class="mt-2" type="primary" link @click="fetchFamilies">
          重新加载
        </el-button>
      </template>
    </el-alert>
    <div
      v-else-if="!loading && families.length === 0"
      class="flex flex-col items-center justify-center py-16"
    >
      <Icon icon="mdi:inbox" class="mb-4 text-6xl text-gray-300" />
      <p class="text-gray-500">暂无数据</p>
    </div>
    <div v-else class="space-y-4">
      <div
        v-for="family in families"
        :key="family.node_family_id"
        class="mb-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
      >
        <div class="flex items-start justify-between">
          <div class="flex flex-1 items-start gap-4">
            <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-purple-100">
              <Icon icon="mdi:package-variant" class="text-2xl text-purple-600" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="mb-2 flex flex-wrap items-center gap-3">
                <h3 class="text-lg font-bold text-gray-900">{{ family.name }}</h3>
                <el-tag size="small" type="success" class="border-0">
                  最新 v{{ family.latest_definition_version }}
                </el-tag>
                <el-tag size="small" class="border-0">
                  {{ family.active_version_count }} 个有效版本
                </el-tag>
                <el-tag v-if="family.source_blueprint?.is_deleted" size="small" type="danger">
                  源蓝图已删除
                </el-tag>
              </div>
              <p class="mb-3 text-sm text-gray-600">
                源蓝图：{{ family.source_blueprint?.name || family.source_blueprint?.id || '不可用' }}
              </p>
              <div class="flex flex-wrap items-center gap-6 text-sm">
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:package-up" class="text-blue-500" />
                  <span class="text-gray-600">下次封装:</span>
                  <span class="font-medium text-gray-900">v{{ family.next_definition_version }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <Icon icon="mdi:history" class="text-green-500" />
                  <span class="text-gray-600">历史最高:</span>
                  <span class="font-medium text-gray-900">v{{ family.max_history_version }}</span>
                </div>
                <div class="flex min-w-0 items-center gap-2">
                  <Icon icon="mdi:identifier" class="shrink-0 text-purple-500" />
                  <span class="shrink-0 text-gray-600">资源族ID:</span>
                  <span class="truncate font-mono text-xs text-gray-900">{{ family.node_family_id }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="ml-4 flex shrink-0 items-center gap-2">
            <el-button type="primary" link @click="toggleFamilyVersions(family.node_family_id)">
              <template #icon>
                <Icon icon="mdi:format-list-bulleted" />
              </template>
              {{ isFamilyExpanded(family.node_family_id) ? '收起版本' : '版本管理' }}
            </el-button>
          </div>
        </div>

        <div
          v-if="isFamilyExpanded(family.node_family_id)"
          class="mt-5 border-t border-gray-200 pt-5"
        >
          <div class="mb-3 flex items-center justify-between">
            <h4 class="text-sm font-semibold text-gray-900">版本列表</h4>
            <span class="text-xs text-gray-500">版本号删除后不会复用</span>
          </div>
          <div class="space-y-3">
            <div
              v-for="version in family.versions"
              :key="version.id"
              class="rounded-lg border border-gray-200 bg-gray-50/50 p-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                  <div class="mb-2 flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-gray-900">
                      v{{ version.definition_version }} · {{ version.name }}
                    </span>
                    <el-tag v-if="version.is_latest" size="small" type="success" class="border-0">
                      最新
                    </el-tag>
                  </div>
                  <p class="mb-3 text-sm text-gray-600">
                    {{ version.description || '暂无说明' }}
                  </p>
                  <div class="flex flex-wrap items-center gap-5 text-sm">
                    <div class="flex min-w-0 items-center gap-2">
                      <Icon icon="mdi:file-document-outline" class="shrink-0 text-blue-500" />
                      <span class="shrink-0 text-gray-600">源 Revision:</span>
                      <el-tooltip :content="version.source_revision_id" placement="top">
                        <span class="max-w-64 truncate font-mono text-xs text-gray-900">
                          {{ version.source_revision_id }}
                        </span>
                      </el-tooltip>
                    </div>
                    <div class="flex items-center gap-2">
                      <Icon icon="mdi:calendar-clock" class="text-green-500" />
                      <span class="text-gray-600">创建时间:</span>
                      <span class="font-medium text-gray-900">{{ formatDateTime(version.created_at) }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <Icon icon="mdi:file-link-outline" class="text-orange-500" />
                      <span class="text-gray-600">草稿引用:</span>
                      <el-button
                        v-if="version.draft_reference_count > 0"
                        type="warning"
                        link
                        @click="handleViewReferences(version)"
                      >
                        {{ version.draft_reference_count }} 个蓝图
                      </el-button>
                      <span v-else class="font-medium text-gray-900">无</span>
                    </div>
                  </div>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                  <el-button type="primary" link @click="handleView(version)">
                    <template #icon>
                      <Icon icon="mdi:eye" />
                    </template>
                    查看
                  </el-button>
                  <el-tooltip
                    :disabled="version.draft_reference_count === 0"
                    content="仍被可编辑蓝图引用，请先升级或移除引用"
                    placement="top"
                  >
                    <span>
                      <el-button
                        v-if="canDelete"
                        type="danger"
                        link
                        :disabled="version.draft_reference_count > 0"
                        @click="handleDelete(family, version)"
                      >
                        <template #icon>
                          <Icon icon="mdi:delete" />
                        </template>
                        删除
                      </el-button>
                    </span>
                  </el-tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="pagination.total > 0" class="mt-6 flex justify-center">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>

    <el-dialog
      v-model="detailVisible"
      title="封装节点版本详情"
      width="880px"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="min-h-40">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="节点名称">{{ detail.node.name }}</el-descriptions-item>
            <el-descriptions-item label="定义版本">
              v{{ detail.node.definition_version }}
              <el-tag v-if="detail.node.is_latest" class="ml-2" size="small" type="success">
                最新
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="资源族 ID">
              <span class="font-mono text-xs">{{ detail.node.node_family_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="节点 ID">
              <span class="font-mono text-xs">{{ detail.node.id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="源蓝图">
              {{ detail.source_blueprint?.name || detail.node.source_blueprint_id || '-' }}
              <el-tag
                v-if="detail.source_blueprint?.is_deleted"
                class="ml-2"
                size="small"
                type="danger"
              >
                已删除
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="源 Revision">
              <span class="font-mono text-xs">{{ detail.node.source_revision_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">
              {{ detail.node.description || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">公开 Handles</el-divider>
          <el-empty
            v-if="!detail.node.handles?.length"
            description="没有公开 Handle"
            :image-size="48"
          />
          <el-table v-else :data="detail.node.handles" size="small" max-height="220">
            <el-table-column prop="relabel" label="名称" min-width="130" />
            <el-table-column label="方向" width="90">
              <template #default="{ row }">
                {{ row.type === 'target' ? '输入' : '输出' }}
              </template>
            </el-table-column>
            <el-table-column label="数据类型" width="100">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.data_type === 'reference' ? 'warning' : 'info'"
                >
                  {{ row.data_type === 'reference' ? '引用流' : '值' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="port_id" label="稳定端口 ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="interface_type_id" label="接口类型" min-width="160" show-overflow-tooltip />
          </el-table>

          <el-divider content-position="left">表单输入</el-divider>
          <el-empty
            v-if="!detail.node.inputs?.length"
            description="没有表单输入"
            :image-size="48"
          />
          <el-table v-else :data="detail.node.inputs" size="small" max-height="220">
            <el-table-column prop="label" label="标签" min-width="130" />
            <el-table-column prop="name" label="字段名" min-width="130" />
            <el-table-column prop="type" label="类型" width="120" />
            <el-table-column label="必填" width="80">
              <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
            </el-table-column>
          </el-table>

          <el-divider content-position="left">可编辑蓝图引用</el-divider>
          <ReferenceTable :references="detail.references" />
        </template>
      </div>
    </el-dialog>

    <el-dialog v-model="referencesVisible" title="可编辑蓝图引用" width="720px">
      <div v-loading="detailLoading" class="min-h-24">
        <ReferenceTable :references="referenceItems" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import {
  computed,
  defineComponent,
  h,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox, ElTable, ElTableColumn } from 'element-plus'
import { actionApi } from '@/api/action'
import { formatDateTime } from '@/utils/action'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'

const props = defineProps({
  keyword: { type: String, default: '' }
})

const ReferenceTable = defineComponent({
  name: 'EncapsulatedNodeReferenceTable',
  props: {
    references: { type: Array, default: () => [] }
  },
  setup(referenceProps) {
    return () => {
      if (!referenceProps.references.length) {
        return h('div', { class: 'py-6 text-center text-sm text-gray-400' }, '没有可编辑蓝图引用')
      }
      return h(
        ElTable,
        { data: referenceProps.references, size: 'small' },
        {
          default: () => [
            h(ElTableColumn, { prop: 'blueprint_name', label: '蓝图名称', minWidth: 160 }),
            h(ElTableColumn, { prop: 'blueprint_version', label: '蓝图版本', width: 100 }),
            h(ElTableColumn, { prop: 'instance_count', label: '节点实例数', width: 110 }),
            h(ElTableColumn, {
              prop: 'instance_ids',
              label: '实例 ID',
              minWidth: 190,
              formatter: row => (row.instance_ids || []).join(', ')
            })
          ]
        }
      )
    }
  }
})

const families = ref([])
const loading = ref(false)
const loadError = ref('')
const expandedVersionFamilies = ref(new Set())
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0
})
const detailVisible = ref(false)
const referencesVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const referenceItems = ref([])
const canDelete = computed(() => hasPerm(PERM.operations.action.node.delete))
let keywordTimer = null

const isFamilyExpanded = familyId => expandedVersionFamilies.value.has(familyId)

const toggleFamilyVersions = familyId => {
  const expanded = new Set(expandedVersionFamilies.value)
  if (expanded.has(familyId)) {
    expanded.delete(familyId)
  } else {
    expanded.add(familyId)
  }
  expandedVersionFamilies.value = expanded
}

const fetchFamilies = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await actionApi.getEncapsulatedNodes({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      keyword: props.keyword.trim() || undefined
    })
    const payload = response?.data?.items ? response.data : response
    if (!Array.isArray(payload?.items)) {
      throw new Error('封装节点接口返回格式不正确')
    }
    families.value = payload.items
    pagination.value.total = payload.total || 0
    pagination.value.totalPages = payload.total_pages || 0
  } catch (error) {
    families.value = []
    pagination.value.total = 0
    pagination.value.totalPages = 0
    loadError.value = error?.message || '封装节点列表加载失败'
  } finally {
    loading.value = false
  }
}

const loadDetail = async (nodeId) => {
  detailLoading.value = true
  try {
    const response = await actionApi.getEncapsulatedNodeDetail(nodeId)
    detail.value = response.data || null
    return detail.value
  } catch {
    detail.value = null
    return null
  } finally {
    detailLoading.value = false
  }
}

const handleView = async (version) => {
  detailVisible.value = true
  await loadDetail(version.id)
}

const handleViewReferences = async (version) => {
  referencesVisible.value = true
  referenceItems.value = []
  const loaded = await loadDetail(version.id)
  referenceItems.value = loaded?.references || []
}

const handleDelete = async (family, version) => {
  const remaining = family.versions
    .filter(item => item.id !== version.id)
    .sort((left, right) => right.definition_version - left.definition_version)
  const promotionText = version.is_latest && remaining.length
    ? `删除后 v${remaining[0].definition_version} 将成为最新版。`
    : ''
  const cleanupText = remaining.length === 0
    ? '这是最后一个有效版本，删除后将清理整个资源族及其旧式专属接口；再次封装会从 v1 开始。'
    : '资源族仍有有效版本，历史版本号不会被复用。'
  try {
    await ElMessageBox.confirm(
      `确定删除“${version.name}”v${version.definition_version} 吗？${promotionText}${cleanupText}`,
      '删除封装节点版本',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      }
    )
    const response = await actionApi.deleteEncapsulatedNode(
      version.id,
      { silent: true }
    )
    ElMessage.success(response.data?.family_deleted
      ? '资源族已清理，再次封装将从 v1 开始'
      : `版本已删除，下一次封装将使用 v${response.data?.next_definition_version}`
    )
    await fetchFamilies()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    const references = error?.response?.data?.data?.references || []
    if (error?.code === 240423 && references.length) {
      referenceItems.value = references
      referencesVisible.value = true
      ElMessage.error('该版本仍被可编辑蓝图引用，暂时无法删除')
      return
    }
    ElMessage.error(error?.message || '删除封装节点版本失败')
  }
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchFamilies()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchFamilies()
}

watch(
  () => props.keyword,
  () => {
    if (keywordTimer) clearTimeout(keywordTimer)
    keywordTimer = setTimeout(() => {
      pagination.value.page = 1
      fetchFamilies()
    }, 250)
  }
)

onMounted(fetchFamilies)
onBeforeUnmount(() => {
  if (keywordTimer) clearTimeout(keywordTimer)
})
</script>
