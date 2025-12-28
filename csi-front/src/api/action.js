import { request } from '@/utils/request'

export const actionApi = {
  getBaseComponents(params = { page: 1, page_size: 10 }) {
    return request.get('/action/resource/base_components', params)
  },
  getNodes(params = {}) {
    return request.get('/action/resource/nodes', params)
  },
  createNode(data) {
    return request.post('/action/resource/nodes', data)
  },
  createActionBlueprint(data) {
    return request.post('/action/blueprint', data)
  },
  getBlueprint(id) {
    return request.get(`/action/blueprint/detail/${id}`)
  },
  getBlueprintsBaseInfo(params = {page: 1, page_size: 10}) {
    return request.get('/action/blueprint/list', params)
  },
  getActionHistory(params = {page: 1, page_size: 10}) {
    return request.get('/action/list', params)
  },
  runAction(data) {
    return request.post(`/action/start`, data)
  },
  getActionDetail(id) {
    return request.get(`/action/detail/${id}`)
  },
}
