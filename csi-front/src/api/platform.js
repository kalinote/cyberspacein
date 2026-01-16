import { request } from '@/utils/request'

export const platformApi = {
  // 获取平台列表
  getPlatformList(params = { page: 1, page_size: 10 }) {
    return request.get('/platform/list', params)
  }
}
