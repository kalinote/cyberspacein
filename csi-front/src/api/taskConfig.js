import { request } from '@/utils/request'

export const taskConfigApi = {
  getTaskList(params = { page: 1, page_size: 10 }) {
    return request.get('/action/components-task/tasks', params)
  },
  getConfigList(params = { page: 1, page_size: 10 }) {
    return request.get('/action/components-task/configs', params)
  },
  getConfigDetail(configId) {
    return request.get(`/action/components-task/configs/detail/${configId}`)
  },
  createConfig(data) {
    return request.post('/action/components-task/configs', data)
  },
  updateConfig(configId, data) {
    return request.patch(`/action/components-task/configs/${configId}`, data)
  },
  deleteConfig(configId) {
    return request.delete(`/action/components-task/configs/${configId}`)
  }
}
