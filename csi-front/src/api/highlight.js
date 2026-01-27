import { request } from '@/utils/request'

export const highlightApi = {
  setHighlight(entityType, uuid, data) {
    return request.put(`/highlight/${entityType}/${uuid}`, data)
  }
}
