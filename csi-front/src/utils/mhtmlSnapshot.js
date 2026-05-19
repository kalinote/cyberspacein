import { convert } from 'mhtml-to-html/browser'

/**
 * @param {string | null | undefined} snapshot
 * @returns {string}
 */
export function resolveSnapshotUrl(snapshot) {
  if (!snapshot || typeof snapshot !== 'string') {
    return ''
  }
  const trimmed = snapshot.trim()
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed
  }
  return ''
}

/**
 * @param {string} url
 * @returns {Promise<string>}
 */
export async function fetchMhtmlText(url) {
  let response
  try {
    response = await fetch(url, { credentials: 'omit' })
  } catch {
    throw new Error('快照下载失败，请检查网络或对象存储 CORS 配置')
  }
  if (!response.ok) {
    throw new Error(`快照下载失败（${response.status}）`)
  }
  return response.text()
}

/**
 * @param {string} mhtmlText
 * @returns {Promise<{ data: string, title?: string }>}
 */
export async function convertMhtmlToHtml(mhtmlText) {
  try {
    return await convert(mhtmlText, {
      enableScripts: false,
      fetchMissingResources: false,
    })
  } catch {
    throw new Error('快照解析失败，MHTML 格式可能不受支持')
  }
}

/**
 * @param {string} html
 * @returns {string}
 */
export function createHtmlBlobUrl(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  return URL.createObjectURL(blob)
}

/**
 * @param {string | null | undefined} url
 */
export function revokeBlobUrl(url) {
  if (url && url.startsWith('blob:')) {
    URL.revokeObjectURL(url)
  }
}

/**
 * @param {string} url
 * @returns {Promise<{ blobUrl: string, title?: string }>}
 */
export async function loadMhtmlSnapshot(url) {
  const resolved = resolveSnapshotUrl(url)
  if (!resolved) {
    throw new Error('快照地址无效')
  }
  const mhtmlText = await fetchMhtmlText(resolved)
  const { data, title } = await convertMhtmlToHtml(mhtmlText)
  const blobUrl = createHtmlBlobUrl(data)
  return { blobUrl, title }
}
