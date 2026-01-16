/**
 * COS 对象存储 URL 工具函数
 */

/**
 * 获取 COS 对象的完整 URL
 * @param {string} objectKey - COS 对象名（如：logo/xxx.ico）
 * @returns {string} 完整的 COS URL，如果 objectKey 为空或已经是完整 URL 则直接返回
 */
export function getCosUrl(objectKey) {
  if (!objectKey) {
    return ''
  }

  // 如果已经是完整的 URL（以 http:// 或 https:// 开头），直接返回
  if (objectKey.startsWith('http://') || objectKey.startsWith('https://')) {
    return objectKey
  }

  const endpoint = import.meta.env.VITE_COS_ENDPOINT
  const bucket = import.meta.env.VITE_COS_BUCKET

  if (!endpoint || !bucket) {
    console.warn('COS 配置未找到，请检查环境变量 VITE_COS_ENDPOINT 和 VITE_COS_BUCKET')
    return objectKey
  }

  // 移除 endpoint 末尾的斜杠
  const cleanEndpoint = endpoint.replace(/\/+$/, '')
  // 移除 objectKey 开头的斜杠
  const cleanObjectKey = objectKey.replace(/^\/+/, '')

  return `${cleanEndpoint}/${bucket}/${cleanObjectKey}`
}
