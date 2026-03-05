import { request } from '@/utils/request'

const BASE = '/action/task-configs'

function normalizeListResponse(res) {
  const data = res.data ?? res
  return {
    data: {
      items: data.items ?? [],
      total: data.total ?? 0,
      page: data.page ?? 1,
      page_size: data.page_size ?? 10,
      total_pages: data.total_pages ?? 0
    }
  }
}

export const taskConfigApi = {
  getConfigList(params = {}) {
    return request.get(BASE, {
      page: params.page ?? 1,
      page_size: params.page_size ?? 10,
      keyword: params.keyword || undefined
    }).then(res => normalizeListResponse(res))
  },

  getConfigDetail(configId) {
    return request.get(`${BASE}/detail/${configId}`)
  },

  createConfig(data) {
    return request.post(BASE, {
      name: data.name,
      description: data.description ?? '',
      type: data.type,
      version: data.version ?? '1.0.0',
      config_data: data.config_data
    })
  },

  updateConfig(configId, data) {
    return request.patch(`${BASE}/${configId}`, {
      name: data.name,
      description: data.description ?? '',
      type: data.type,
      version: data.version ?? '1.0.0',
      config_data: data.config_data
    })
  },

  deleteConfig(configId) {
    return request.delete(`${BASE}/${configId}`)
  }
}
