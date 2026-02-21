import { request } from '@/utils/request'

export const annotationApi = {
  list(entityUuid, entityType) {
    return request.get('/annotation/list', { entity_uuid: entityUuid, entity_type: entityType })
  },
  create(data) {
    return request.post('/annotation', data)
  },
  update(id, data) {
    return request.put(`/annotation/${id}`, data)
  },
  delete(id) {
    return request.delete(`/annotation/${id}`)
  }
}
