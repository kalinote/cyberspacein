export function convertRelativeLinks(htmlContent, baseUrl) {
  if (!htmlContent || !baseUrl) {
    return htmlContent
  }

  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlContent, 'text/html')
    const base = new URL(baseUrl)

    const links = doc.querySelectorAll('a[href]')
    links.forEach(link => {
      const href = link.getAttribute('href')
      if (href && !isAbsoluteUrl(href) && !isMailtoOrTel(href)) {
        try {
          const absoluteUrl = new URL(href, base.origin + base.pathname)
          link.setAttribute('href', absoluteUrl.href)
          link.setAttribute('target', '_blank')
          link.setAttribute('rel', 'noopener noreferrer')
        } catch (e) {
          console.warn('无法转换链接:', href, e)
        }
      } else if (href && isAbsoluteUrl(href)) {
        link.setAttribute('target', '_blank')
        link.setAttribute('rel', 'noopener noreferrer')
      }
    })

    const images = doc.querySelectorAll('img[src]')
    images.forEach(img => {
      const src = img.getAttribute('src')
      if (src && !isAbsoluteUrl(src)) {
        try {
          const absoluteUrl = new URL(src, base.origin + base.pathname)
          img.setAttribute('src', absoluteUrl.href)
        } catch (e) {
          console.warn('无法转换图片链接:', src, e)
        }
      }
    })

    return doc.body.innerHTML
  } catch (error) {
    console.error('处理HTML链接失败:', error)
    return htmlContent
  }
}

function isAbsoluteUrl(url) {
  return /^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(url) || url.startsWith('data:')
}

function isMailtoOrTel(url) {
  return url.startsWith('mailto:') || url.startsWith('tel:')
}
