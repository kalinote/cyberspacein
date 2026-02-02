import { request } from '@/utils/request'

export const agentApi = {
  getModelList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/configs/models', params)
  },
  createModel(data) {
    return request.post('/agent/configs/models', data)
  },
  getPromptTemplateList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/configs/prompt-templates', params)
  },
  createPromptTemplate(data) {
    return request.post('/agent/configs/prompt-templates', data)
  },
  getToolsList() {
    return request.get('/agent/configs/tools')
  }
}
