import { request } from '@/utils/request'

export const articleApi = {
  getArticleDetail(uuid) {
    return request.get(`/article/detail/${uuid}`)
  }
}
