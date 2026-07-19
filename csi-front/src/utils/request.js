import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearAuth, getAuthState } from '@/stores/auth'
import { classifyAuthorizationFailure } from '@/utils/authHttpPolicy'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.31.51:8080/api/v1'
const appBase = import.meta.env.BASE_URL || '/'

let permissionRefresher = null
let permissionRefreshPromise = null

export function registerPermissionRefresher(refresher) {
  permissionRefresher = typeof refresher === 'function' ? refresher : null
}

function appPath(path) {
  const base = appBase.endsWith('/') ? appBase.slice(0, -1) : appBase
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

function makeApiError(message, code, response) {
  const error = new Error(message)
  error.code = code
  error.response = response
  return error
}

function isLoginPath() {
  return (window.location.pathname || '').endsWith('/login')
}

function handleUnauthorized(message, requestUrl = '') {
  clearAuth()
  const isAuthRequest = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/logout')
  if (!isLoginPath() && !isAuthRequest) window.location.href = appPath('/login')
  ElMessage.warning(message)
}

async function refreshAfterPermissionChange(requestUrl = '') {
  if (!permissionRefresher || requestUrl.includes('/auth/me')) return
  if (!permissionRefreshPromise) {
    permissionRefreshPromise = Promise.resolve(permissionRefresher()).finally(() => {
      permissionRefreshPromise = null
    })
  }
  try { await permissionRefreshPromise } catch { /* 401 handler owns session cleanup */ }
}

const service = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

service.interceptors.request.use(config => {
  const token = getAuthState().accessToken
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(async response => {
  const res = response.data
  const code = res?.code
  const requestUrl = response?.config?.url || ''
  const serverVersionRaw = response.headers?.['x-authorization-version']
  const serverVersion = serverVersionRaw == null ? null : Number(serverVersionRaw)
  const localVersion = getAuthState().authorizationVersion
  let refreshedForVersion = false

  if (
    Number.isInteger(serverVersion) &&
    Number.isInteger(localVersion) &&
    serverVersion !== localVersion &&
    !requestUrl.includes('/auth/me')
  ) {
    await refreshAfterPermissionChange(requestUrl)
    refreshedForVersion = true
  }

  if (code === 0) return res
  if (typeof code === 'number' && code !== 0) {
    const message = res?.message || '请求失败'
    const failureKind = classifyAuthorizationFailure(code, null)
    if (failureKind === 'unauthorized') {
      handleUnauthorized(message, requestUrl)
      throw makeApiError(message, code, response)
    }
    if (failureKind === 'forbidden') {
      if (!refreshedForVersion) await refreshAfterPermissionChange(requestUrl)
      if (!response?.config?.silent) ElMessage.warning(message)
      throw makeApiError(message, code, response)
    }
    if (!response?.config?.silent) ElMessage.error(message)
    throw makeApiError(message, code, response)
  }
  if (Array.isArray(res?.items) && typeof res?.total === 'number') return res
  const message = res?.message || '请求失败'
  if (!response?.config?.silent) ElMessage.error(message)
  throw makeApiError(message, code, response)
}, async error => {
  const status = error.response?.status
  const requestUrl = error.response?.config?.url || error.config?.url || ''
  const message = error.response?.data?.message || (status === 401
    ? '登录已失效，请重新登录'
    : status === 403 ? '无权限执行该操作' : '网络错误，请稍后重试')
  const failureKind = classifyAuthorizationFailure(null, status)
  if (failureKind === 'unauthorized') handleUnauthorized(message, requestUrl)
  else if (failureKind === 'forbidden') {
    await refreshAfterPermissionChange(requestUrl)
    if (!error.config?.silent) ElMessage.warning(message)
  } else if (!error.config?.silent) ElMessage.error(message)
  return Promise.reject(error)
})

export default service

export const request = {
  get(url, params, config = {}) { return service.get(url, { params, ...config }) },
  post(url, data, config = {}) { return service.post(url, data, config) },
  put(url, data, config = {}) { return service.put(url, data, config) },
  delete(url, config = {}) { return service.delete(url, config) },
  patch(url, data, config = {}) { return service.patch(url, data, config) }
}

export const getPaginatedData = async (apiFunc, params = {}) => {
  try {
    const response = await apiFunc(params)
    if (response.code === 0 && response.data) {
      const { items = [], total = 0, page = 1, page_size = 10, total_pages = 1 } = response.data
      return { items, pagination: { total, page, pageSize: page_size, totalPages: total_pages } }
    }
    if (Array.isArray(response.items) && typeof response.total === 'number') {
      return {
        items: response.items,
        pagination: {
          total: response.total,
          page: response.page ?? 1,
          pageSize: response.page_size ?? 10,
          totalPages: response.total_pages ?? 0
        }
      }
    }
  } catch (error) {
    if (import.meta.env.DEV) console.error('获取分页数据失败:', error)
  }
  return { items: [], pagination: { total: 0, page: 1, pageSize: 10, totalPages: 0 } }
}
