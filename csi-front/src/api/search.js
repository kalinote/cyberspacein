import { request } from '@/utils/request'

export const searchApi = {
  searchEntity(params) {
    return request.post('/search/entity', params)
  },
  getTemplateList(params) {
    return request.get('/search/templates', params)
  },
  createTemplate(data) {
    return request.post('/search/template', data)
  },
  getTemplate(id) {
    return request.get(`/search/template/${id}`)
  },
  updateTemplate(id, data) {
    return request.put(`/search/template/${id}`, data)
  },
  deleteTemplate(id) {
    return request.delete(`/search/template/${id}`)
  }
}
