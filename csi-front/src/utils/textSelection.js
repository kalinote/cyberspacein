export function createSpanWrapper(range, spanId) {
  try {
    if (range.collapsed) {
      return null
    }

    const span = document.createElement('span')
    span.id = spanId
    span.className = 'annotation-target'
    span.setAttribute('data-annotation-id', spanId)

    try {
      range.surroundContents(span)
      return span
    } catch (e) {
      const contents = range.extractContents()
      span.appendChild(contents)
      range.insertNode(span)
      return span
    }
  } catch (error) {
    console.error('创建span包裹失败:', error)
    return null
  }
}

export function getXPath(element) {
  if (element.id) {
    return `//*[@id="${element.id}"]`
  }

  const parts = []
  let current = element

  while (current && current.nodeType === Node.ELEMENT_NODE) {
    let index = 1
    let sibling = current.previousElementSibling

    while (sibling) {
      if (sibling.nodeName === current.nodeName) {
        index++
      }
      sibling = sibling.previousElementSibling
    }

    const tagName = current.nodeName.toLowerCase()
    const pathIndex = index > 1 ? `[${index}]` : ''
    parts.unshift(`${tagName}${pathIndex}`)
    current = current.parentElement
  }

  return parts.length ? `/${parts.join('/')}` : null
}

export function getElementByXPath(xpath) {
  const result = document.evaluate(
    xpath,
    document,
    null,
    XPathResult.FIRST_ORDERED_NODE_TYPE,
    null
  )
  return result.singleNodeValue
}

export function serializeTextSelection(element, selection) {
  if (!selection) return null

  return {
    region: 'clean',
    textOffset: {
      start: selection.start,
      end: selection.end,
      text: selection.text
    }
  }
}

export function serializeHtmlSelection(element, span) {
  if (!span) return null

  const xpath = getXPath(span)
  const html = span.outerHTML

  return {
    region: 'rendered',
    spanId: span.id,
    xpath: xpath,
    html: html
  }
}
