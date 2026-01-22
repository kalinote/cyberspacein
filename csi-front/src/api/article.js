import { request } from '@/utils/request'

export const articleApi = {
  getArticleDetail(uuid) {
    return request.get(`/article/detail/${uuid}`)
  },
  setHighlight(uuid, data) {
    return request.put(`/article/highlight/${uuid}`, data)
  }
}
