import { request } from '@/utils/request'

export const timelineApi = {
  getTimeline(entityType, sourceId, params) {
    return request.get(`/timeline/${entityType}/${sourceId}`, params)
  }
}
