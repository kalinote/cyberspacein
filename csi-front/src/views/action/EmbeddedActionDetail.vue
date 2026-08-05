<template>
  <el-drawer
    v-model="visible"
    title="封装节点内部行动"
    size="72%"
    destroy-on-close
    @open="loadDetail"
  >
    <div v-loading="loading" class="min-h-72 space-y-5">
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
      />
      <template v-else-if="detail">
        <div class="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-xs text-gray-500">内部行动</p>
            <p class="mt-1 font-medium text-gray-900">{{ detail.name }}</p>
          </div>
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-xs text-gray-500">状态</p>
            <el-tag class="mt-1" :type="getStatusTagType(detail.status)">
              {{ getStatusText(detail.status) }}
            </el-tag>
          </div>
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-xs text-gray-500">进度</p>
            <el-progress class="mt-2" :percentage="detail.progress || 0" />
          </div>
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-xs text-gray-500">节点</p>
            <p class="mt-1 font-medium text-gray-900">
              {{ detail.completed_steps || 0 }} / {{ detail.total_steps || 0 }}
            </p>
          </div>
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-xs text-gray-500">执行模式</p>
            <p class="mt-1 font-medium text-gray-900">
              {{ detail.scheduling_mode === 'streaming' ? '异步执行' : '同步执行' }}
            </p>
          </div>
        </div>

        <div>
          <h4 class="mb-2 text-sm font-semibold text-gray-800">内部节点</h4>
          <el-table :data="nodeRows" size="small" max-height="320">
            <el-table-column prop="name" label="节点" min-width="180" />
            <el-table-column label="类型" width="130">
              <template #default="{ row }">
                {{ row.detail.node_kind || row.detail.driver || 'ordinary' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="130">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.detail.status)" size="small">
                  {{ getStatusText(row.detail.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="detail.skip_reason" label="跳过原因" min-width="220" />
          </el-table>
        </div>

        <div>
          <div class="mb-2 flex items-center justify-between">
            <h4 class="text-sm font-semibold text-gray-800">内部聚合日志</h4>
            <el-button link type="primary" :loading="logsLoading" @click="loadLogs(true)">
              刷新
            </el-button>
          </div>
          <div class="max-h-80 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50">
            <div
              v-for="item in logs"
              :key="item.event_id"
              class="border-b border-gray-200 px-3 py-2 text-xs last:border-b-0"
            >
              <div class="flex gap-2">
                <span class="shrink-0 text-gray-500">{{ formatLogTime(item.occurred_at) }}</span>
                <span class="shrink-0 font-medium">{{ item.level }}</span>
                <span class="shrink-0 text-gray-500">{{ item.handler || item.component_id || item.source }}</span>
                <span class="min-w-0 whitespace-pre-wrap break-all text-gray-700">{{ item.message }}</span>
              </div>
            </div>
            <p v-if="!logsLoading && logs.length === 0" class="p-8 text-center text-sm text-gray-400">
              暂无内部日志
            </p>
            <div v-if="hasMoreLogs" class="border-t border-gray-200 p-2 text-center">
              <el-button link type="primary" :loading="logsLoading" @click="loadLogs()">
                加载更早日志
              </el-button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { actionApi } from '@/api/action'
import {
  formatLogTime,
  getStatusTagType,
  getStatusText
} from '@/utils/action'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  parentActionId: { type: String, default: '' },
  nodeId: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const loading = ref(false)
const logsLoading = ref(false)
const errorMessage = ref('')
const detail = ref(null)
const logs = ref([])
const previousLogCursor = ref(null)
const hasMoreLogs = ref(false)

const nodeRows = computed(() => {
  const names = Object.fromEntries(
    (detail.value?.graph?.nodes || []).map(node => [
      node.id,
      node.data?.definition_id || node.type || node.id
    ])
  )
  return Object.entries(detail.value?.node_details || {}).map(([nodeId, nodeDetail]) => ({
    id: nodeId,
    name: names[nodeId] || nodeId,
    detail: nodeDetail
  }))
})

const loadLogs = async (reset = false) => {
  if (!props.parentActionId || !props.nodeId || logsLoading.value) return
  logsLoading.value = true
  try {
    const response = await actionApi.getEmbeddedActionLogs(
      props.parentActionId,
      props.nodeId,
      {
        limit: 100,
        ...(!reset && previousLogCursor.value
          ? { before_cursor: previousLogCursor.value }
          : {})
      }
    )
    const page = response.data || {}
    logs.value = reset
      ? (page.items || [])
      : [...(page.items || []), ...logs.value]
    previousLogCursor.value = page.previous_cursor || null
    hasMoreLogs.value = Boolean(page.has_more && previousLogCursor.value)
  } finally {
    logsLoading.value = false
  }
}

const loadDetail = async () => {
  if (!props.parentActionId || !props.nodeId) return
  loading.value = true
  errorMessage.value = ''
  detail.value = null
  logs.value = []
  previousLogCursor.value = null
  hasMoreLogs.value = false
  try {
    const response = await actionApi.getEmbeddedAction(
      props.parentActionId,
      props.nodeId
    )
    if (response.code !== 0) {
      errorMessage.value = response.message || '获取内部行动失败'
      return
    }
    detail.value = response.data
    await loadLogs(true)
  } catch (error) {
    errorMessage.value = error.message || '获取内部行动失败'
  } finally {
    loading.value = false
  }
}
</script>
