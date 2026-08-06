import { request } from '@/utils/request'

export const actionApi = {
  // 获取基础构建列表
  getBaseComponents(params = { page: 1, page_size: 10 }) {
    return request.get('/action/resource/base_components', params)
  },
  // 获取行动节点列表
  getNodes(params = {}) {
    return request.get('/action/resource/nodes', params)
  },
  // 创建行动节点
  createNode(data) {
    return request.post('/action/resource/nodes', data)
  },
  // 获取行动节点详情
  getNodeDetail(nodeId) {
    return request.get(`/action/resource/nodes/${nodeId}`)
  },
  // 获取封装节点资源族列表
  getEncapsulatedNodes(params = {}) {
    return request.get('/action/resource/encapsulated-nodes', params)
  },
  // 获取封装节点版本详情
  getEncapsulatedNodeDetail(nodeId) {
    return request.get(`/action/resource/encapsulated-nodes/${nodeId}`)
  },
  // 删除封装节点版本；最后一个有效版本会清理整个资源族
  deleteEncapsulatedNode(nodeId, config = {}) {
    return request.delete(`/action/resource/encapsulated-nodes/${nodeId}`, config)
  },
  // 更新行动节点
  updateNode(nodeId, data) {
    return request.put(`/action/resource/nodes/${nodeId}`, data)
  },
  // 删除行动节点（逻辑删除）
  deleteNode(nodeId) {
    return request.delete(`/action/resource/nodes/${nodeId}`)
  },
  // 启用或禁用后端原生节点
  setNativeNodeEnabled(nodeId, enabled) {
    return request.patch(`/action/resource/nodes/${nodeId}/enabled`, { enabled })
  },
  // 创建行动蓝图
  createActionBlueprint(data) {
    return request.post('/action/blueprint', data)
  },
  // 更新行动蓝图
  updateActionBlueprint(id, data) {
    return request.put(`/action/blueprint/${id}`, data)
  },
  // 获取行动蓝图详情
  getBlueprint(id) {
    return request.get(`/action/blueprint/detail/${id}`)
  },
  // 获取行动蓝图列表
  getBlueprintsBaseInfo(params = {page: 1, page_size: 10}) {
    return request.get('/action/blueprint/list', params)
  },
  // 校验蓝图执行图
  validateBlueprint(id) {
    return request.post(`/action/blueprint/${id}/validate`)
  },
  // 发布不可变蓝图版本
  publishBlueprint(id) {
    return request.post(`/action/blueprint/${id}/publish`)
  },
  // 封装蓝图为节点
  encapsulateBlueprint(id, data) {
    return request.post(`/action/blueprint/${id}/encapsulate`, data)
  },
  // 获取蓝图版本列表
  getBlueprintRevisions(id) {
    return request.get(`/action/blueprint/${id}/revisions`)
  },
  // 获取不可变蓝图版本
  getBlueprintRevision(revisionId) {
    return request.get(`/action/blueprint/revisions/${revisionId}`)
  },
  // 删除行动蓝图及其历史行动
  deleteBlueprint(id) {
    return request.delete(`/action/blueprint/${id}`)
  },
  // 获取行动历史列表
  getActionHistory(params = {page: 1, page_size: 10}) {
    return request.get('/action/list', params)
  },
  // 获取行动历史全量状态统计
  getActionHistorySummary(config = {}) {
    return request.get('/action/summary', undefined, config)
  },
  // 运行行动
  runAction(data) {
    return request.post(`/action/start`, data)
  },
  // 基于历史行动的冻结快照创建一次全新执行
  retryAction(id) {
    return request.post(`/action/${id}/retry`)
  },
  // 暂停行动
  pauseAction(id) {
    return request.post(`/action/${id}/pause`)
  },
  // 恢复行动
  resumeAction(id) {
    return request.post(`/action/${id}/resume`)
  },
  // 不可逆停止行动
  stopAction(id) {
    return request.post(`/action/${id}/stop`)
  },
  // 获取行动详情
  getActionDetail(id) {
    return request.get(`/action/detail/${id}`)
  },
  // 增量查询节点执行日志
  getNodeLogs(nodeInstanceId, params = {}) {
    return request.get(`/action/nodes/${nodeInstanceId}/logs`, params)
  },
  // 获取封装节点内部行动
  getEmbeddedAction(actionId, nodeId) {
    return request.get(`/action/instances/${actionId}/nodes/${nodeId}/embedded`)
  },
  // 聚合查询封装节点内部日志
  getEmbeddedActionLogs(actionId, nodeId, params = {}) {
    return request.get(`/action/instances/${actionId}/nodes/${nodeId}/embedded/logs`, params)
  },
  // 获取行动节点接口列表
  getNodeHandles(params = { page: 1, page_size: 10 }) {
    return request.get(`/action/configs/handles`, params)
  },
  // 创建行动节点接口
  createNodeHandle(data) {
    return request.post(`/action/configs/handles`, data)
  },
  // 获取所有节点接口列表
  getAllNodeHandles() {
    return request.get(`/action/configs/handles/all`)
  },
  // 获取资源统计数据
  getStatistics() {
    return request.get('/action/configs/statistics')
  },
  // 获取节点类型过滤列表（用于节点类型下拉）
  getNodeTypeFilter() {
    return request.get('/action/configs/filter/node_type')
  },
  getAccountList(params = { page: 1, page_size: 10 }) {
    return request.get('/action/accounts/list', params)
  },
  createAccount(data) {
    return request.post('/action/accounts', data)
  },
  getAccountDetail(accountId) {
    return request.get(`/action/accounts/detail/${accountId}`)
  },
  updateAccount(accountId, data) {
    return request.patch(`/action/accounts/${accountId}`, data)
  },
  deleteAccount(accountId) {
    return request.delete(`/action/accounts/${accountId}`)
  }
}
