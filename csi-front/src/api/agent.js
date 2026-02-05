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
  getPromptTemplateDetail(promptTemplateId) {
    return request.get(`/agent/configs/prompt-template/${promptTemplateId}`)
  },
  createPromptTemplate(data) {
    return request.post('/agent/configs/prompt-templates', data)
  },
  updatePromptTemplate(promptTemplateId, data) {
    return request.put(`/agent/configs/prompt-template/${promptTemplateId}`, data)
  },
  getToolsList() {
    return request.get('/agent/configs/tools')
  },
  getToolsListForAgent() {
    return request.get('/agent/configs/tools-list')
  },
  getModelsList() {
    return request.get('/agent/configs/models-list')
  },
  getAgentList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/agents', params)
  },
  getAgentsConfigList() {
    return request.get('/agent/configs/agents-list')
  },
  getConfigStatistics() {
    return request.get('/agent/configs/statistics')
  },
  createAgent(data) {
    return request.post('/agent/agents', data)
  },
  startAgent(data) {
    return request.post('/agent/start', data)
  },
  getAgentStatusUrl(threadId) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    return `${baseUrl}/agent/status?thread_id=${threadId}`
  },
  approveAgent(data) {
    return request.post('/agent/approve', data)
  }
}
