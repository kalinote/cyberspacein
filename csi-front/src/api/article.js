import { request } from '@/utils/request'

export const articleApi = {
  getArticleDetail(uuid) {
    return request.get(`/article/detail/${uuid}`)
  },

  analyzeArticle(uuid) {
    return request.post(`/article/analyze/${uuid}`)
  }
}
