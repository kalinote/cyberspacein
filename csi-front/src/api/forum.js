import { request } from '@/utils/request'

export const forumApi = {
  getForumDetail(uuid) {
    return request.get(`/forum/detail/${uuid}`)
  },
  setHighlight(uuid, data) {
    return request.put(`/forum/highlight/${uuid}`, data)
  },
  getComments(params) {
    return request.get('/forum/comments', params)
  }
}
