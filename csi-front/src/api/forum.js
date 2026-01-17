import { request } from '@/utils/request'

export const forumApi = {
  getForumDetail(uuid) {
    return request.get(`/forum/detail/${uuid}`)
  }
}
