import { request } from '@/utils/request'

export const agentApi = {
  getModelList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/configs/models', params)
  },
  createModel(data) {
    return request.post('/agent/configs/models', data)
  },
  getModelDetail(modelConfigId) {
    return request.get(`/agent/configs/model/${modelConfigId}`)
  },
  updateModel(modelConfigId, data) {
    return request.put(`/agent/configs/model/${modelConfigId}`, data)
  },
  deleteModel(modelConfigId) {
    return request.delete(`/agent/configs/model/${modelConfigId}`)
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
  deletePromptTemplate(promptTemplateId) {
    return request.delete(`/agent/configs/prompt-template/${promptTemplateId}`)
  },
  getSystemPromptList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/configs/system-prompts', params)
  },
  getSystemPromptDetail(systemPromptId) {
    return request.get(`/agent/configs/system-prompts/${systemPromptId}`)
  },
  createSystemPrompt(data) {
    return request.post('/agent/configs/system-prompts', data)
  },
  updateSystemPrompt(systemPromptId, data) {
    return request.put(`/agent/configs/system-prompts/${systemPromptId}`, data)
  },
  deleteSystemPrompt(systemPromptId) {
    return request.delete(`/agent/configs/system-prompts/${systemPromptId}`)
  },
  getToolsList() {
    return request.get('/agent/configs/tools')
  },
  getAgentBuiltinPromptOptions() {
    return request.get('/agent/configs/filter/agent-prompts')
  },
  getToolsListForAgent() {
    return request.get('/agent/configs/tools-list')
  },
  getSkillsList() {
    return request.get('/agent/configs/skills-list')
  },
  getSkillsListForAgent(workspaceId) {
    return request.get('/agent/configs/filter/skills', { workspace_id: workspaceId })
  },
  getModelsList() {
    return request.get('/agent/configs/models-list')
  },
  getAgentList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/agents', params)
  },
  getAgentSessionList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/sessions', params)
  },
  getAgentSessionDetail(sessionId) {
    return request.get(`/agent/sessions/${sessionId}`)
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
  sendAgentMessage(data) {
    return request.post('/agent/message', data)
  },
  cancelAgent(data) {
    return request.post('/agent/cancel', data)
  },
  getAgentStatusUrl(agentId, sessionId) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    return `${baseUrl}/agent/status?agent_id=${encodeURIComponent(agentId)}&session_id=${encodeURIComponent(sessionId)}`
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
  },

  getSkillList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/skills', params)
  },
  uploadSkill(file) {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/agent/skills/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deleteSkill(skillId) {
    return request.delete(`/agent/skills/${skillId}`)
  },
  getSkillDetail(skillId) {
    return request.get(`/agent/skills/${skillId}`)
  },
  getSkillFileContent(skillId, path) {
    return request.get(`/agent/skills/${skillId}/files/content`, { path })
  },
  updateSkillFileContent(skillId, path, content) {
    return request.put(`/agent/skills/${skillId}/files/content`, { content }, { params: { path } })
  },

  createSandbox(data = {}) {
    return request.post('/agent/sandbox/create', data)
  },
  getSandboxDetail(sandboxId) {
    return request.get(`/agent/sandbox/detail/${sandboxId}`)
  },
  destroySandbox(sandboxId) {
    return request.delete(`/agent/sandbox/${sandboxId}`)
  },
  getSandboxList(params = { page: 1, page_size: 10 }) {
    return request.get('/agent/sandbox/list', params)
  }
}
