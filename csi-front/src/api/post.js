import { request } from '@/utils/request'

export const postApi = {
  getPostDetail(uuid) {
    return request.get(`/post/detail/${encodeURIComponent(uuid)}`)
  }
}
