import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearAuth, getAuthState } from '@/stores/auth'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.31.51:8080/api/v1'

const appBase = import.meta.env.BASE_URL || '/'

function appPath(path) {
  const base = appBase.endsWith('/') ? appBase.slice(0, -1) : appBase
  const p = path.startsWith('/') ? path : `/${path}`
  return `${base}${p}`
}

const service = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

service.interceptors.request.use(
  config => {
    const token = getAuthState().accessToken
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  response => {
    const res = response.data
    const code = res?.code

    if (code === 0) return res

    if (typeof code === 'number' && code !== 0) {
      const codeStr = String(code)
      const message = res?.message || '请求失败'

      const requestUrl = response?.config?.url || ''
      const currentPath = window.location.pathname || ''
      const isLoginRequest = requestUrl.includes('/auth/login')
      const isLogoutRequest = requestUrl.includes('/auth/logout')
      const isMeRequest = requestUrl.includes('/auth/me')

      if (codeStr.startsWith('2401')) {
        clearAuth()

        if (!currentPath.endsWith('/login') && !isLoginRequest && !isLogoutRequest && !isMeRequest) {
          window.location.href = appPath('/login')
        }
        ElMessage.warning(message)
        return Promise.reject(new Error(message))
      }

      if (codeStr.startsWith('2403')) {
        if (!currentPath.endsWith('/403')) {
          window.location.href = appPath('/403')
        }
        ElMessage.warning(message)
        return Promise.reject(new Error(message))
      }

      ElMessage.error(message)
      return Promise.reject(new Error(message))
    }

    if (Array.isArray(res?.items) && typeof res?.total === 'number') return res

    ElMessage.error(res?.message || '请求失败')
    return Promise.reject(new Error(res?.message || '请求失败'))
  },
  error => {
    console.error('响应错误:', error)
    
    let message = '网络错误，请稍后重试'
    
    if (error.response) {
      switch (error.response.status) {
        case 400:
          message = '请求参数错误'
          break
        case 401:
          message = '未授权，请登录'
          break
        case 403:
          message = '拒绝访问'
          break
        case 404:
          message = '请求的资源不存在'
          break
        case 500:
          message = '服务器错误'
          break
        case 502:
          message = '网关错误'
          break
        case 503:
          message = '服务不可用'
          break
        case 504:
          message = '网关超时'
          break
        default:
          message = error.response.data?.message || '请求失败'
      }
    } else if (error.request) {
      message = '网络连接失败，请检查网络'
    }
    
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default service

export const request = {
  get(url, params, config = {}) {
    return service.get(url, { params, ...config })
  },
  
  post(url, data, config = {}) {
    return service.post(url, data, config)
  },
  
  put(url, data, config = {}) {
    return service.put(url, data, config)
  },
  
  delete(url, config = {}) {
    return service.delete(url, config)
  },
  
  patch(url, data, config = {}) {
    return service.patch(url, data, config)
  }
}

export const getPaginatedData = async (apiFunc, params = {}) => {
  try {
    const response = await apiFunc(params)

    if (response.code === 0 && response.data) {
      const { items = [], total = 0, page = 1, page_size = 10, total_pages = 1 } = response.data
      return {
        items,
        pagination: {
          total,
          page,
          pageSize: page_size,
          totalPages: total_pages
        }
      }
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

    return {
      items: [],
      pagination: {
        total: 0,
        page: 1,
        pageSize: 10,
        totalPages: 0
      }
    }
  } catch (error) {
    console.error('获取分页数据失败:', error)
    return {
      items: [],
      pagination: {
        total: 0,
        page: 1,
        pageSize: 10,
        totalPages: 0
      }
    }
  }
}
