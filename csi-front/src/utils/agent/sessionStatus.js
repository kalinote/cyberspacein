export const AGENT_SESSION_STATUS = Object.freeze({
  IDLE: 'idle',
  RUNNING: 'running',
  AWAITING_APPROVAL: 'awaiting_approval',
  PAUSED: 'paused',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
})

const STATUS_LABEL_MAP = {
  unknown: '未知',
  [AGENT_SESSION_STATUS.IDLE]: '空闲',
  [AGENT_SESSION_STATUS.RUNNING]: '运行中',
  [AGENT_SESSION_STATUS.AWAITING_APPROVAL]: '等待审批',
  [AGENT_SESSION_STATUS.COMPLETED]: '已完成',
  [AGENT_SESSION_STATUS.FAILED]: '失败',
  [AGENT_SESSION_STATUS.PAUSED]: '已暂停',
  [AGENT_SESSION_STATUS.CANCELLED]: '已取消',
}

const STATUS_TAG_TYPE_MAP = {
  unknown: 'info',
  [AGENT_SESSION_STATUS.IDLE]: 'info',
  [AGENT_SESSION_STATUS.RUNNING]: 'primary',
  [AGENT_SESSION_STATUS.AWAITING_APPROVAL]: 'warning',
  [AGENT_SESSION_STATUS.COMPLETED]: 'success',
  [AGENT_SESSION_STATUS.FAILED]: 'danger',
  [AGENT_SESSION_STATUS.PAUSED]: 'info',
  [AGENT_SESSION_STATUS.CANCELLED]: 'info',
}

export const AGENT_SESSION_STATUS_OPTIONS = [
  { label: '空闲', value: AGENT_SESSION_STATUS.IDLE },
  { label: '运行中', value: AGENT_SESSION_STATUS.RUNNING },
  { label: '等待审批', value: AGENT_SESSION_STATUS.AWAITING_APPROVAL },
  { label: '已暂停', value: AGENT_SESSION_STATUS.PAUSED },
  { label: '已完成', value: AGENT_SESSION_STATUS.COMPLETED },
  { label: '失败', value: AGENT_SESSION_STATUS.FAILED },
  { label: '已取消', value: AGENT_SESSION_STATUS.CANCELLED },
]

const TERMINAL_STATUSES = new Set([
  AGENT_SESSION_STATUS.COMPLETED,
  AGENT_SESSION_STATUS.FAILED,
  AGENT_SESSION_STATUS.CANCELLED,
])

export function isAgentSessionTerminalStatus(status) {
  return TERMINAL_STATUSES.has(String(status || ''))
}

export function getAgentSessionStatusLabel(status) {
  const key = String(status || 'unknown')
  return STATUS_LABEL_MAP[key] || key
}

export function getAgentSessionStatusTagType(status) {
  const key = String(status || 'unknown')
  return STATUS_TAG_TYPE_MAP[key] || 'info'
}
