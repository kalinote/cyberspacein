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
    return request.get('/agent/agents-list')
  },
  getConfigStatistics() {
    return request.get('/agent/configs/statistics')
  },
  createAgent(data) {
    return request.post('/agent/agents', data)
  },
  getAgentDetail(agentId) {
    return request.get(`/agent/agents/${agentId}`)
  },
  updateAgent(agentId, data) {
    return request.put(`/agent/agents/${agentId}`, data)
  },
  deleteAgent(agentId) {
    return request.delete(`/agent/agents/${agentId}`)
  },
  startAgent(data) {
    return request.post('/agent/start', data)
  },
  cancelAgent(data) {
    return request.post('/agent/cancel', data)
  },
  getAgentStatusUrl(agentId) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    return `${baseUrl}/agent/status?agent_id=${encodeURIComponent(agentId)}&debug=true`
  },
  approveAgent(data) {
    return request.post('/agent/approve', data)
  },

  getWorkspaceList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/workspaces', params)
  },
  createWorkspace(data) {
    return request.post('/agent/workspaces', data)
  },
  getWorkspaceDetail(workspaceId) {
    return request.get(`/agent/workspaces/${workspaceId}`)
  },
  updateWorkspace(workspaceId, data) {
    return request.put(`/agent/workspaces/${workspaceId}`, data)
  },
  deleteWorkspace(workspaceId) {
    return request.delete(`/agent/workspaces/${workspaceId}`)
  }
}
