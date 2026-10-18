/** """仅接受绝对 HTTP/HTTPS 地址，供贴文媒体与来源链接共同使用。""" */
export function safePostUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return ''
  try {
    const url = new URL(value.trim())
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch {
    return ''
  }
}

/**
 * 依照媒体处理器的清单优先级解析可展示资源，归档地址优先于来源地址。
 * @param {object} post 贴文中的媒体清单和可选封面。
 * @returns {Array<object>} 已校验地址、确定类型并关联视频封面的媒体项。
 */
export function normalizePostMedia(post = {}) {
  const resources = post.media_resources ?? post.files_urls ?? (post.cover_image ? [post.cover_image] : [])
  if (!Array.isArray(resources)) return []
  const seen = new Set()
  const media = []
  for (const [index, resource] of resources.entries()) {
    const item = typeof resource === 'string' ? { source_url: resource } : resource
    if (!item || typeof item !== 'object') continue
    const url = safePostUrl(item.stored_url) || safePostUrl(item.source_url)
    if (!url || seen.has(url)) continue
    seen.add(url)
    const mime = String(item.content_type || '').toLowerCase().split(';')[0]
    const extension = new URL(url).pathname.split('.').pop().toLowerCase()
    let type = 'file'
    if (/^(image|video|audio)\//.test(mime)) type = mime.split('/')[0]
    else if (mime && mime !== 'application/octet-stream') type = 'file'
    else if (['image', 'video', 'audio', 'file'].includes(item.type)) type = item.type
    else if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'avif', 'svg', 'bmp'].includes(extension)) type = 'image'
    else if (['mp4', 'webm', 'ogv', 'mov', 'm4v'].includes(extension)) type = 'video'
    else if (['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac', 'opus'].includes(extension)) type = 'audio'
    // 播放清单不作为可直接播放的完整视频。
    if (['m3u8', 'mpd'].includes(extension)) type = 'file'
    media.push({
      ...item, url, type, key: `${index}:${url}`,
      name: item.name || item.filename || ({ image: '图片', video: '视频', audio: '音频', file: '附件' })[type] + ` ${index + 1}`,
      poster: safePostUrl(item.poster_url),
    })
  }
  const attachedPosters = new Set()
  for (const video of media.filter(item => item.type === 'video')) {
    const poster = media.find(item => item.type === 'image' && item.role === 'poster'
      && item.media_id && item.media_id === video.media_id)
    if (poster) {
      video.poster ||= poster.url
      attachedPosters.add(poster.key)
    }
  }
  return media.filter(item => !attachedPosters.has(item.key))
}
