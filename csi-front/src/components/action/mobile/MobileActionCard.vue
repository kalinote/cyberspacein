<template>
  <article class="mobile-action-card" :class="{ 'has-issue': hasIssue }">
    <div class="action-card-heading">
      <el-tag :type="getStatusTagType(action.status)" size="small">{{ getStatusText(action.status) }}</el-tag>
      <span>{{ (action.schedulingMode || action.scheduling_mode) === 'streaming' ? '异步执行' : '同步执行' }}</span>
      <el-tag v-if="action.debug" type="info" size="small" effect="plain">调试</el-tag>
    </div>
    <button v-if="showDetail && canViewDetail" class="action-card-title" type="button" @click="$emit('view', action)">{{ action.name || action.blueprint_name || '未命名行动' }}<Icon icon="mdi:chevron-right" /></button>
    <h2 v-else class="action-card-title">{{ action.name || action.blueprint_name || '未命名行动' }}</h2>
    <p v-if="action.error_message || action.errorMessage" class="action-card-error">{{ action.error_message || action.errorMessage }}</p>
    <p v-else-if="action.status === ACTION_STATUS.AWAITING_APPROVAL" class="action-card-notice">等待人工审批，进入详情查看待审批节点。</p>
    <p v-else-if="action.status === ACTION_STATUS.PARTIALLY_COMPLETED" class="action-card-notice">部分节点已完成，请查看节点结果与异常。</p>
    <div class="action-card-progress">
      <div><span>执行进度</span><strong>{{ progress }}%<template v-if="totalSteps"> · {{ action.completedSteps ?? action.completed_steps ?? 0 }}/{{ totalSteps }} 节点</template></strong></div>
      <div class="action-progress-track"><div :style="{ width: `${progress}%` }" :class="{ failed: hasIssue }"></div></div>
    </div>
    <p v-if="action.schedule_name" class="action-card-meta">计划：{{ action.schedule_name }}</p>
    <p class="action-card-meta">{{ action.finished_at || action.endTime ? '结束' : action.start_at || action.startTime ? '开始' : '计划' }}：{{ formatDateTime(action.finished_at || action.endTime || action.start_at || action.startTime || action.scheduled_for || action.created_at) }}</p>
    <details v-if="action.description" class="action-card-description"><summary>行动说明</summary><p>{{ action.description }}</p></details>
    <div class="action-card-controls">
      <el-button v-if="showDetail && canViewDetail" type="primary" plain @click="$emit('view', action)">查看{{ terminal ? '结果' : '进度' }}</el-button>
      <template v-if="interactive && hasPerm(PERM.operations.action.instance.execute)">
        <el-button v-for="operation in operations" :key="operation" :type="operation === 'stop' ? 'danger' : 'default'"
          :loading="busy" :disabled="disabled" @click="$emit('operate', action, operation)">
          {{ getActionOperationLabel(action.status, operation) }}
        </el-button>
      </template>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ACTION_STATUS, formatDateTime, getStatusTagType, getStatusText } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'
import { getActionOperations, getActionOperationLabel } from './actionOperations'

const props = defineProps({ action: { type: Object, required: true }, busy: Boolean, disabled: Boolean, showDetail: { type: Boolean, default: true }, interactive: { type: Boolean, default: true } })
defineEmits(['view', 'operate'])
const progress = computed(() => Math.max(0, Math.min(100, Math.round(Number(props.action.progress) || 0))))
const totalSteps = computed(() => props.action.totalSteps ?? props.action.total_steps ?? 0)
const hasIssue = computed(() => [ACTION_STATUS.FAILED, ACTION_STATUS.TIMEOUT, ACTION_STATUS.CANCELLED, ACTION_STATUS.STOPPED].includes(props.action.status))
const terminal = computed(() => hasIssue.value || [ACTION_STATUS.COMPLETED, ACTION_STATUS.PARTIALLY_COMPLETED].includes(props.action.status))
const operations = computed(() => getActionOperations(props.action.status))
const canViewDetail = computed(() => hasPerm(PERM.pages.action.detail.access))
</script>

<style scoped>
.mobile-action-card { padding: 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; min-width: 0; }
.mobile-action-card.has-issue { border-color: #fecaca; }
.action-card-heading { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: #64748b; font-size: 12px; }
.action-card-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; min-height: 44px; padding: 10px 0 4px; margin: 0; text-align: left; background: none; border: 0; color: #0f172a; font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
button.action-card-title { cursor: pointer; }
.action-card-title svg { flex-shrink: 0; }
.action-card-error, .action-card-notice { margin: 10px 0; padding: 10px; border-radius: 8px; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; white-space: pre-wrap; }
.action-card-error { background: #fef2f2; color: #b91c1c; }
.action-card-notice { background: #fffbeb; color: #92400e; }
.action-card-progress { margin: 12px 0; }
.action-card-progress > div:first-child { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #64748b; }
.action-card-progress strong { color: #334155; }
.action-progress-track { margin-top: 8px; height: 6px; border-radius: 8px; overflow: hidden; background: #e2e8f0; }
.action-progress-track > div { height: 100%; background: linear-gradient(90deg,#3b82f6,#22d3ee); }
.action-progress-track > div.failed { background: linear-gradient(90deg,#ef4444,#facc15); }
.action-card-meta { margin: 6px 0; color: #64748b; font-size: 12px; overflow-wrap: anywhere; }
.action-card-description { font-size: 13px; color: #475569; }
.action-card-description summary { display: flex; align-items: center; min-height: 44px; cursor: pointer; }
.action-card-description p { margin-bottom: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
.action-card-controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.action-card-controls:empty { display: none; }
.action-card-controls :deep(.el-button) { min-height: 44px; margin: 0; flex: 1; padding: 10px; }
</style>
