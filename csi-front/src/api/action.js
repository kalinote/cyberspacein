import { request } from '@/utils/request'

export const actionApi = {
  getBaseComponents(params = { page: 1, page_size: 10 }) {
    return request.get('/action/resource_management/base_components', params)
  },
  getNodes(params = {}) {
    return request.get('/action/resource_management/nodes', params)
  },
  createNode(data) {
    return request.post('/action/resource_management/nodes', data)
  },
  createActionBlueprint(data) {
    return request.post('/action/blueprint', data)
  },
  getBlueprint(id) {
    return request.get(`/action/blueprint/${id}`)
  },
  getBlueprintsBaseInfo(params = {page: 1, page_size: 10}) {
    return request.get('/action/blueprint/list', params)
  },
  getActionHistory(params = {page: 1, page_size: 10}) {
    return request.get('/action/list', params)
  },
}
