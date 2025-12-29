// 状态文本映射
const STATUS_TEXT_MAP = {
  'unready': '未就绪',
  'ready': '已就绪',
  'running': '执行中',
  'completed': '已完成',
  'failed': '失败',
  'cancelled': '已取消',
  'timeout': '超时',
  'paused': '已暂停',
}

// 状态标签类型映射
// TODO: 这里后续改成通过接口获取tag和文字颜色
const STATUS_TAG_TYPE_MAP = {
  'unready': 'info',
  'ready': 'success',
  'running': 'primary',
  'completed': 'success',
  'paused': 'warning',
  'cancelled': 'danger',
  'timeout': 'danger',
  'failed': 'danger',
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
    'running': 'bg-blue-500 animate-pulse',
    'completed': 'bg-green-500',
    'paused': 'bg-amber-500',
    'stopped': 'bg-gray-500',
    'failed': 'bg-red-500',
    'pending': 'bg-gray-400'
  }
  return classMap[status] || 'bg-gray-400'
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

