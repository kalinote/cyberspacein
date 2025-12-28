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
  // 创建行动蓝图
  createActionBlueprint(data) {
    return request.post('/action/blueprint', data)
  },
  // 获取行动蓝图详情
  getBlueprint(id) {
    return request.get(`/action/blueprint/detail/${id}`)
  },
  // 获取行动蓝图列表
  getBlueprintsBaseInfo(params = {page: 1, page_size: 10}) {
    return request.get('/action/blueprint/list', params)
  },
  // 获取行动历史列表
  getActionHistory(params = {page: 1, page_size: 10}) {
    return request.get('/action/list', params)
  },
  // 运行行动
  runAction(data) {
    return request.post(`/action/start`, data)
  },
  // 获取行动详情
  getActionDetail(id) {
    return request.get(`/action/detail/${id}`)
  },
  // 获取行动节点接口列表
  getNodeHandles(params = { page: 1, page_size: 10 }) {
    return request.get(`/action/configs/handles`, params)
  },
  // 创建行动节点接口
  createNodeHandle(data) {
    return request.post(`/action/configs/handles`, data)
  }
}
