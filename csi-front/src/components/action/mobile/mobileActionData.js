/**
 * 读取行动分页并保留接口错误，避免手机将加载失败展示为空列表。
 * @param {Function} api 请求分页数据的既有接口。
 * @param {object} params 查询参数。
 * @returns {Promise<object>} 列表及与桌面一致的分页信息。
 */
export async function fetchMobileActionPage(api, params) {
  const response = await api(params)
  if (typeof response?.code === 'number' && response.code !== 0) throw new Error(response.message || '列表请求失败，请重试')
  const page = response?.code === 0 ? response.data : response
  if (!Array.isArray(page?.items) || typeof page.total !== 'number') throw new Error(response?.message || '列表数据暂不可用，请重试')
  return {
    items: page.items,
    pagination: { total: page.total, page: page.page ?? params.page ?? 1, pageSize: page.page_size ?? params.page_size ?? 10, totalPages: page.total_pages ?? 0 }
  }
}
