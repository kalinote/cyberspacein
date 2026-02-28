import { request } from '@/utils/request'

export const timelineApi = {
  getTimeline(entityType, sourceId, params) {
    return request.get(`/timeline/${entityType}/${sourceId}`, params)
  },
  getDiffCompare(entityType, uuid) {
    return request.get(`/timeline/${entityType}/${uuid}/diff-compare`)
  }
}
