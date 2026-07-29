import { request } from '@/utils/request'

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://192.168.31.51:8080/api/v1'

export const alertApi = {
  getSources() {
    return request.get('/alerts/sources')
  },
  getSourcesStatus() {
    return request.get('/alerts/sources/status')
  },
  getRules(params = {}) {
    return request.get('/alerts/rules', params)
  },
  getRule(ruleId) {
    return request.get(`/alerts/rules/${ruleId}`)
  },
  validateRule(data) {
    return request.post('/alerts/rules/validate', data)
  },
  createRule(data) {
    return request.post('/alerts/rules', data)
  },
  updateRule(ruleId, data) {
    return request.patch(`/alerts/rules/${ruleId}`, data)
  },
  setRuleEnabled(ruleId, data) {
    return request.patch(`/alerts/rules/${ruleId}/enabled`, data)
  },
  deleteRule(ruleId, expectedVersion) {
    return request.delete(`/alerts/rules/${ruleId}`, {
      params: { expected_version: expectedVersion }
    })
  },
  testRule(ruleId, maxResources = 100) {
    return request.post(`/alerts/rules/${ruleId}/test`, null, {
      params: { max_resources: maxResources }
    })
  },
  getInstances(params = {}) {
    return request.get('/alerts/instances', params)
  },
  getInstance(alertId) {
    return request.get(`/alerts/instances/${alertId}`)
  },
  getEvents(alertId, params = {}) {
    return request.get(`/alerts/instances/${alertId}/events`, params)
  },
  acknowledge(alertId, expectedVersion) {
    return request.post(`/alerts/instances/${alertId}/acknowledge`, {
      expected_version: expectedVersion
    })
  },
  resolve(alertId, expectedVersion, note) {
    return request.post(`/alerts/instances/${alertId}/resolve`, {
      expected_version: expectedVersion,
      note
    })
  },
  getStats() {
    return request.get('/alerts/stats')
  },
  getWorkerStatus() {
    return request.get('/alerts/worker/status')
  },
  streamUrl(afterId = '') {
    const query = afterId ? `?after_id=${encodeURIComponent(afterId)}` : ''
    return `${apiBase}/alerts/stream${query}`
  }
}
