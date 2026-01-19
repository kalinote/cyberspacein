import { request } from '@/utils/request'

export const platformApi = {
  // 获取平台列表
  getPlatformList(params = { page: 1, page_size: 10 }) {
    return request.get('/platform/list', params)
  },
  // 获取平台详情
  getPlatformDetail(platformId) {
    return request.get(`/platform/detail/${platformId}`)
  },
  // 创建平台
  createPlatform(data) {
    return request.post('/platform', data)
  }
}
