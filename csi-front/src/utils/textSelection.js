export function createSpanWrapper(range, spanId) {
  try {
    if (range.collapsed) {
      return null
    }

    const span = document.createElement('span')
    span.id = spanId
    span.className = 'marking-target'
    span.setAttribute('data-marking-id', spanId)

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

/**
 * 从 Range 对象计算其在 element 的 textContent 中的字符偏移量。
 * 选区起点/终点在元素节点（如图片）时，用 comparePoint 判定位置，避免 start/end 错误为 0。
 * comparePoint: -1 点在 range 前，0 在边界上，1 在 range 后。
 */
export function computeTextOffsetFromRange(element, range) {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null)
  let currentOffset = 0
  let startOffset = 0
  let endOffset = 0
  let foundStart = false
  let foundEnd = false

  let node
  while ((node = walker.nextNode())) {
    const len = node.textContent.length

    if (!foundStart) {
      for (let i = 0; i <= len; i++) {
        if (range.comparePoint(node, i) >= 0) {
          startOffset = currentOffset + i
          foundStart = true
          break
        }
      }
    }
    if (!foundEnd) {
      for (let i = 0; i <= len; i++) {
        if (range.comparePoint(node, i) > 0) {
          endOffset = currentOffset + i
          foundEnd = true
          break
        }
      }
    }

    currentOffset += len
    if (foundStart && foundEnd) break
  }

  if (!foundEnd) {
    endOffset = currentOffset
  }
  return { start: startOffset, end: endOffset }
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

/**
 * 序列化 HTML 区域的选区，使用字符偏移量（与纯文本区域保持一致）
 * selection 需包含 start、end、text 字段
 */
export function serializeHtmlSelection(element, selection) {
  if (!selection) return null

  return {
    region: 'rendered',
    textOffset: {
      start: selection.start,
      end: selection.end,
      text: selection.text
    }
  }
}
