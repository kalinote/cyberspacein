import { request } from '@/utils/request'

export const actionApi = {
  getBaseComponents(params = { page: 1, page_size: 10 }) {
    return request.get('/action/resource_management/base_components', params)
  },
}
