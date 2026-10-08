import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionApi } from '@/api/action'
import { ACTION_STATUS } from '@/utils/action'
import { PERM } from '@/utils/permissions'
import { guardPermission } from '@/utils/permissionKit'

/** """返回与现有行动控制一致的可执行操作。""" */
export function getActionOperations(status) {
  if (status === ACTION_STATUS.RUNNING) return ['pause', 'stop']
  if (status === ACTION_STATUS.PAUSED) return ['resume', 'stop']
  if ([ACTION_STATUS.FAILED, ACTION_STATUS.TIMEOUT, ACTION_STATUS.COMPLETED, ACTION_STATUS.PARTIALLY_COMPLETED].includes(status)) return ['retry']
  return []
}

/** """按行动状态区分重试、重新执行与其他操作文案。""" */
export function getActionOperationLabel(status, operation) {
  return operation === 'retry'
    ? ([ACTION_STATUS.FAILED, ACTION_STATUS.TIMEOUT].includes(status) ? '重试' : '重新执行')
    : { pause: '暂停', resume: '恢复', stop: '停止' }[operation]
}

/**
 * 复用既有行动接口，在移动列表和详情中确认并执行状态操作。
 * @param {object} options 更新列表与打开重放行动的回调。
 * @returns {{ busyId: import('vue').Ref<string>, operateAction: Function }} 操作状态和执行入口。
 */
export function useMobileActionOperations({ onUpdated, onCreated } = {}) {
  const busyId = ref('')

  /**
   * 校验权限和行动状态，执行一次操作后刷新来源列表。
   * @param {object} action 行动列表或详情对象。
   * @param {string} operation 暂停、恢复、停止或重放操作。
   */
  const operateAction = async (action, operation) => {
    const id = action.id || action.action_id
    if (!id || busyId.value || !getActionOperations(action.status).includes(operation)) return
    if (!guardPermission(PERM.operations.action.instance.execute)) return
    const label = getActionOperationLabel(action.status, operation)
    busyId.value = id
    try {
      if (operation !== 'resume') {
        await ElMessageBox.confirm(
          operation === 'retry' ? `确定${label}此行动吗？将基于执行快照创建并启动一个新行动。`
            : operation === 'stop' ? '确定停止此行动吗？停止后无法恢复。' : '确定暂停此行动吗？',
          `确认${label}`, { confirmButtonText: `确定${label}`, cancelButtonText: '取消', type: 'warning' }
        )
      }
      const response = await actionApi[{ pause: 'pauseAction', resume: 'resumeAction', stop: 'stopAction', retry: 'retryAction' }[operation]](id)
      if (response.code !== 0 || (operation === 'retry' && !response.data?.action_id)) {
        throw new Error(response.message || `${label}失败`)
      }
      ElMessage.success(operation === 'retry' ? '新行动已创建并开始执行' : `行动已${label}`)
      if (operation === 'retry' && onCreated) await onCreated(response.data.action_id)
      else await onUpdated?.()
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || `${label}失败`)
    } finally {
      busyId.value = ''
    }
  }
  return { busyId, operateAction }
}
