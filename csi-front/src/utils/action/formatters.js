// 格式化日期时间
export const formatDateTime = (dateStr, options = {}) => {
  if (!dateStr) return options.defaultValue || '-'
  
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return options.defaultValue || '-'
  
  const defaultOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...(options.includeSecond ? { second: '2-digit' } : {})
  }
  
  return date.toLocaleString('zh-CN', defaultOptions)
}

// 格式化持续时间（统一处理秒和毫秒）
export const formatDuration = (value, unit = 'seconds') => {
  if (!value) return '-'
  
  // 统一转换为秒
  const seconds = unit === 'milliseconds' 
    ? Math.floor(value / 1000) 
    : Math.floor(value)
  
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 86400 % 3600) / 60)
  const remainingSeconds = seconds % 86400 % 3600 % 60
  
  if (days > 0) {
    return `${days}天${hours}小时${minutes}分钟`
  } else if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟${remainingSeconds}秒`
  } else {
    return `${remainingSeconds}秒`
  }
}

// 格式化日志时间
export const formatLogTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
