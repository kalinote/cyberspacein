export const ACTION_STATUS = Object.freeze({
  UNKNOWN: 'unknown',
  UNREADY: 'unready',
  PENDING: 'pending',
  READY: 'ready',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  TIMEOUT: 'timeout',
  PAUSED: 'paused',
  STOPPED: 'stopped',
})

export const TODO_ITEM_STATUS = Object.freeze({
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
})

// 状态文本映射
const STATUS_TEXT_MAP = {
  [ACTION_STATUS.UNKNOWN]: '未知',
  [ACTION_STATUS.UNREADY]: '未就绪',
  [ACTION_STATUS.PENDING]: '待执行',
  [ACTION_STATUS.READY]: '已就绪',
  [ACTION_STATUS.RUNNING]: '执行中',
  [ACTION_STATUS.COMPLETED]: '已完成',
  [ACTION_STATUS.FAILED]: '失败',
  [ACTION_STATUS.CANCELLED]: '已取消',
  [ACTION_STATUS.TIMEOUT]: '超时',
  [ACTION_STATUS.PAUSED]: '已暂停',
}

// 状态标签类型映射
// TODO: 这里后续改成通过接口获取tag和文字颜色
const STATUS_TAG_TYPE_MAP = {
  [ACTION_STATUS.UNREADY]: 'info',
  [ACTION_STATUS.PENDING]: 'info',
  [ACTION_STATUS.READY]: 'success',
  [ACTION_STATUS.RUNNING]: 'primary',
  [ACTION_STATUS.COMPLETED]: 'success',
  [ACTION_STATUS.PAUSED]: 'warning',
  [ACTION_STATUS.CANCELLED]: 'danger',
  [ACTION_STATUS.TIMEOUT]: 'danger',
  [ACTION_STATUS.FAILED]: 'danger',
}

// 获取状态文本
export const getStatusText = (status) => {
  return STATUS_TEXT_MAP[status] || status
}

// 获取状态标签类型
export const getStatusTagType = (status) => {
  return STATUS_TAG_TYPE_MAP[status] || 'info'
}

// 获取状态点样式类
export const getStatusDotClass = (status) => {
  const classMap = {
    [ACTION_STATUS.RUNNING]: 'bg-blue-500 animate-pulse',
    [ACTION_STATUS.COMPLETED]: 'bg-green-500',
    [ACTION_STATUS.PAUSED]: 'bg-amber-500',
    [ACTION_STATUS.STOPPED]: 'bg-gray-500',
    [ACTION_STATUS.FAILED]: 'bg-red-500',
    [ACTION_STATUS.PENDING]: 'bg-gray-400'
  }
  return classMap[status] || 'bg-gray-400'
}

export const getActionStatusIcon = (status) => {
  const map = {
    [ACTION_STATUS.RUNNING]: { icon: 'mdi:loading', bgClass: 'bg-blue-100', iconClass: 'text-blue-600 animate-spin' },
    [ACTION_STATUS.COMPLETED]: { icon: 'mdi:check-circle', bgClass: 'bg-green-100', iconClass: 'text-green-600' },
    [ACTION_STATUS.PAUSED]: { icon: 'mdi:pause', bgClass: 'bg-amber-100', iconClass: 'text-amber-600' },
    [ACTION_STATUS.STOPPED]: { icon: 'mdi:stop', bgClass: 'bg-gray-100', iconClass: 'text-gray-600' },
    [ACTION_STATUS.CANCELLED]: { icon: 'mdi:stop', bgClass: 'bg-gray-100', iconClass: 'text-gray-600' },
    [ACTION_STATUS.FAILED]: { icon: 'mdi:alert-circle', bgClass: 'bg-red-100', iconClass: 'text-red-600' },
    [ACTION_STATUS.TIMEOUT]: { icon: 'mdi:alert-circle', bgClass: 'bg-red-100', iconClass: 'text-red-600' }
  }
  return map[status] || { icon: 'mdi:clock-outline', bgClass: 'bg-gray-100', iconClass: 'text-gray-600' }
}

// 获取日志级别样式类
export const getLogLevelClass = (level) => {
  const classMap = {
    'fatal': 'bg-red-300',
    'info': 'bg-blue-50',
    'error': 'bg-red-50',
    'warning': 'bg-yellow-50',
    'debug': 'bg-gray-50'
  }
  return classMap[level] || 'bg-gray-50'
}

// 获取日志级别文本样式类
export const getLogLevelTextClass = (level) => {
  const classMap = {
    'fatal': 'text-red-700',
    'info': 'text-blue-600',
    'error': 'text-red-600',
    'warning': 'text-yellow-600',
    'debug': 'text-gray-600'
  }
  return classMap[level] || 'text-gray-600'
}

