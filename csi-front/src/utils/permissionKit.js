import { ElMessage } from 'element-plus'
import { hasAllPermissions } from '@/stores/auth'

export const DEFAULT_NO_PERMISSION_MESSAGE = '无权限执行该操作'

function reportInvalid(value) {
  if (import.meta.env.DEV) console.error('无效权限配置，已默认拒绝:', value)
}

export function hasAll(codes) {
  if (!Array.isArray(codes)) {
    reportInvalid(codes)
    return false
  }
  return hasAllPermissions(codes)
}

export function hasPerm(code) {
  if (typeof code !== 'string' || !code) {
    reportInvalid(code)
    return false
  }
  return hasAllPermissions([code])
}

export function hasAny(codes) {
  if (!Array.isArray(codes) || codes.length === 0) {
    reportInvalid(codes)
    return false
  }
  return codes.some(code => hasPerm(code))
}

export function noPerm(message = DEFAULT_NO_PERMISSION_MESSAGE) {
  ElMessage.error(message)
}

export function guardPermission(code, message = DEFAULT_NO_PERMISSION_MESSAGE) {
  if (hasPerm(code)) return true
  noPerm(message)
  return false
}
