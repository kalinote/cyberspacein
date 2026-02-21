import { ref, computed, nextTick } from 'vue'
import { annotate } from 'rough-notation'
import { createSpanWrapper, serializeTextSelection, serializeHtmlSelection, computeTextOffsetFromRange } from '@/utils/textSelection'
import { getStyleColor, createMarkingConfig } from '@/utils/markingStyles'
import { annotationApi } from '@/api/annotation'

export function useMarking({ entityUuid, entityType } = {}) {
  const markings = ref([])
  const selectedText = ref(null)
  const selectedStyle = ref('highlight')
  const toolbarVisible = ref(false)
  const toolbarPosition = ref({ top: 0, left: 0 })
  const toolbarRange = ref(null)
  const markingInstances = ref(new Map())
  const originalTexts = ref(new Map())
  const isMultilineSelection = ref(false)

  const markingStyles = [
    { value: 'underline', label: '下划线', icon: 'mdi:format-underline', supportsMultiline: false },
    { value: 'highlight', label: '高亮', icon: 'mdi:format-color-highlight', supportsMultiline: true },
    { value: 'box', label: '边框', icon: 'mdi:border-all', supportsMultiline: true },
    { value: 'bracket', label: '括号', icon: 'mdi:code-brackets', supportsMultiline: true },
    { value: 'circle', label: '圆圈', icon: 'mdi:circle-outline', supportsMultiline: true },
    { value: 'strike-through', label: '删除线', icon: 'mdi:format-strikethrough', supportsMultiline: false }
  ]

  function checkIfMultiline(range) {
    if (!range) return false
    try {
      const rects = range.getClientRects()
      return rects.length > 1
    } catch (e) {
      return false
    }
  }

  function generateId() {
    return `marking-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  function createMarking(element, region, target, style) {
    const id = generateId()
    const now = new Date()

    const marking = {
      id,
      type: 'marking',
      content: '',
      style: style || selectedStyle.value,
      target: {
        ...target,
        region
      },
      position: {
        top: 0,
        left: 0
      },
      createdAt: now,
      updatedAt: now
    }

    markings.value.push(marking)
    return marking
  }

  function applyHighlight(element, marking) {
    applyTextHighlight(element, marking)
  }

  function applyTextHighlight(element, marking) {
    const { textOffset } = marking.target
    if (!textOffset) return

    const elementId = element.id || `text-element-${Date.now()}`
    if (!element.id) {
      element.id = elementId
    }

    let originalText = originalTexts.value.get(elementId)
    if (!originalText) {
      originalText = element.textContent || ''
      originalTexts.value.set(elementId, originalText)
    }

    if (textOffset.start >= originalText.length || textOffset.end > originalText.length) {
      console.error('文本偏移量超出范围', { start: textOffset.start, end: textOffset.end, length: originalText.length })
      return
    }

    const selectedText = originalText.substring(textOffset.start, textOffset.end)
    if (!selectedText.trim()) return

    const spanId = `marking-span-${marking.id}`
    marking.target.spanId = spanId
    
    try {
      const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null
      )

      let currentOffset = 0
      let startNode = null
      let startOffset = 0
      let endNode = null
      let endOffset = 0

      let node
      while ((node = walker.nextNode())) {
        const nodeLength = node.textContent.length
        
        if (!startNode && currentOffset + nodeLength > textOffset.start) {
          startNode = node
          startOffset = textOffset.start - currentOffset
        }
        
        if (currentOffset + nodeLength >= textOffset.end) {
          endNode = node
          endOffset = textOffset.end - currentOffset
          break
        }
        
        currentOffset += nodeLength
      }

      if (!startNode || !endNode) {
        console.error('无法找到文本节点')
        return
      }

      const range = document.createRange()
      range.setStart(startNode, startOffset)
      range.setEnd(endNode, endOffset)

      const span = document.createElement('span')
      span.id = spanId
      span.className = 'marking-target'
      span.setAttribute('data-marking-id', marking.id)
      
      try {
        range.surroundContents(span)
      } catch (e) {
        const contents = range.extractContents()
        span.appendChild(contents)
        range.insertNode(span)
      }

      nextTick(() => {
        setTimeout(() => {
          const highlightElement = document.getElementById(spanId)
          if (highlightElement) {
            const isMultiline = checkIfMultiline(range.cloneRange())
            const config = createMarkingConfig(marking.style, isMultiline)
            const instance = annotate(highlightElement, config)
            instance.show()
            markingInstances.value.set(marking.id, instance)
            updateMarkingPosition(marking)
          }
        }, 50)
      })
    } catch (e) {
      console.error('应用文本高亮失败:', e)
    }
  }

  function updateMarkingPosition(marking) {
    nextTick(() => {
      const { spanId, textOffset } = marking.target
      let targetElement = null

      if (spanId) {
        targetElement = document.getElementById(spanId)
      } else if (textOffset) {
        const elements = document.querySelectorAll(`[data-marking-id="${marking.id}"]`)
        if (elements.length > 0) {
          targetElement = elements[0]
        }
      }

      if (targetElement) {
        const rect = targetElement.getBoundingClientRect()
        const container = targetElement.closest('.marking-container')
        if (container) {
          const containerRect = container.getBoundingClientRect()
          marking.position = {
            top: rect.top - containerRect.top + container.scrollTop,
            left: rect.left - containerRect.left
          }
        }
      }
    })
  }

  function updateAllPositions() {
    markings.value.forEach(marking => {
      updateMarkingPosition(marking)
    })
    if (toolbarVisible.value) {
      updateToolbarPosition()
    }
  }

  function handleTextSelection(element, region) {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      hideToolbar()
      return
    }

    const range = selection.getRangeAt(0)
    
    if (!element.contains(range.commonAncestorContainer)) {
      hideToolbar()
      return
    }

    const selectedTextValue = range.toString().trim()
    if (!selectedTextValue) {
      hideToolbar()
      return
    }

    const elementId = element.id || `text-element-${Date.now()}`
    if (!element.id) {
      element.id = elementId
    }

    let originalText = originalTexts.value.get(elementId)
    if (!originalText) {
      originalText = element.textContent || ''
      originalTexts.value.set(elementId, originalText)
    }

    const { start: startOffset, end: endOffset } = computeTextOffsetFromRange(element, range)

    if (startOffset === 0 && endOffset === 0 && selectedTextValue) {
      hideToolbar()
      return
    }

    const textSelection = {
      start: startOffset,
      end: endOffset,
      text: selectedTextValue,
      range: range.cloneRange()
    }

    selectedText.value = textSelection
    showToolbar(range)
  }

  function handleHtmlSelection(element) {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      hideToolbar()
      return
    }

    const range = selection.getRangeAt(0)
    
    if (!element.contains(range.commonAncestorContainer)) {
      hideToolbar()
      return
    }

    const selectedTextValue = range.toString().trim()
    
    if (!selectedTextValue) {
      hideToolbar()
      return
    }

    const { start, end } = computeTextOffsetFromRange(element, range)

    selectedText.value = {
      range: range.cloneRange(),
      text: selectedTextValue,
      start,
      end
    }

    showToolbar(range)
  }

  function showToolbar(range) {
    if (!range) return

    try {
      toolbarRange.value = range.cloneRange()
      isMultilineSelection.value = checkIfMultiline(range)
      
      if (isMultilineSelection.value) {
        const currentStyle = markingStyles.find(s => s.value === selectedStyle.value)
        if (currentStyle && !currentStyle.supportsMultiline) {
          const multilineStyle = markingStyles.find(s => s.supportsMultiline)
          if (multilineStyle) {
            selectedStyle.value = multilineStyle.value
          }
        }
      }
      
      updateToolbarPosition()
      toolbarVisible.value = true
    } catch (e) {
      console.error('显示工具栏失败:', e)
    }
  }

  function updateToolbarPosition() {
    if (!toolbarRange.value) return

    try {
      const rect = toolbarRange.value.getBoundingClientRect()
      if (rect.width === 0 && rect.height === 0) {
        return
      }
      
      toolbarPosition.value = {
        top: rect.top - 50,
        left: rect.left + rect.width / 2
      }
    } catch (e) {
      console.error('更新工具栏位置失败:', e)
    }
  }

  function hideToolbar() {
    toolbarVisible.value = false
    selectedText.value = null
    toolbarRange.value = null
    isMultilineSelection.value = false
  }

  async function createMarkingFromSelection(element, region, style) {
    if (!selectedText.value) return null

    let target = null

    if (region === 'clean' || region === 'translate') {
      target = serializeTextSelection(element, selectedText.value)
    } else {
      // rendered 区域：使用偏移量（与纯文本区域统一），span 注入仅用于当次视觉渲染
      target = serializeHtmlSelection(element, selectedText.value)
      if (target && selectedText.value.range) {
        const spanId = `marking-span-${generateId()}`
        createSpanWrapper(selectedText.value.range.cloneRange(), spanId)
      }
    }

    if (!target) return null

    const marking = createMarking(element, region, target, style)

    // 对 rendered 区域，applyHighlight 使用 applyTextHighlight，需要先确保 spanId 未被设置
    // （spanId 在 applyTextHighlight 内部生成）
    if (region === 'rendered') {
      // 清除临时注入的 span（applyTextHighlight 会自行注入）
      const tmpSpan = element.querySelector(`[data-marking-id^="marking-span-"]`)
      if (tmpSpan && tmpSpan.id.startsWith('marking-span-marking-')) {
        const parent = tmpSpan.parentNode
        if (parent) {
          while (tmpSpan.firstChild) {
            parent.insertBefore(tmpSpan.firstChild, tmpSpan)
          }
          parent.removeChild(tmpSpan)
        }
      }
    }

    applyHighlight(element, marking)
    
    window.getSelection()?.removeAllRanges()
    hideToolbar()

    // 持久化到后端
    if (entityUuid?.value || entityUuid) {
      try {
        const uuid = typeof entityUuid === 'object' ? entityUuid.value : entityUuid
        const type = typeof entityType === 'object' ? entityType.value : entityType
        const res = await annotationApi.create({
          entity_uuid: uuid,
          entity_type: type,
          annotation_type: 'text',
          style: marking.style,
          content: marking.content,
          target: {
            region: marking.target.region,
            text_offset: {
              start: marking.target.textOffset.start,
              end: marking.target.textOffset.end,
              text: marking.target.textOffset.text
            }
          },
          meta: {}
        })
        if (res.code === 0 && res.data?.id) {
          marking.id = res.data.id
        }
      } catch (e) {
        console.error('保存批注失败:', e)
      }
    }

    return marking
  }

  async function updateMarkingContent(id, content) {
    const marking = markings.value.find(a => a.id === id)
    if (marking) {
      marking.content = content
      marking.updatedAt = new Date()

      try {
        await annotationApi.update(id, { content })
      } catch (e) {
        console.error('更新批注失败:', e)
      }
    }
  }

  async function deleteMarking(id) {
    const index = markings.value.findIndex(a => a.id === id)
    if (index > -1) {
      const marking = markings.value[index]
      const instance = markingInstances.value.get(id)
      if (instance) {
        instance.remove()
        markingInstances.value.delete(id)
      }

      if (marking.target.spanId) {
        const element = document.getElementById(marking.target.spanId)
        if (element) {
          const parent = element.parentNode
          if (parent) {
            while (element.firstChild) {
              parent.insertBefore(element.firstChild, element)
            }
            parent.removeChild(element)
          }
        }
      } else {
        const element = document.querySelector(`[data-marking-id="${id}"]`)
        if (element) {
          const parent = element.parentNode
          if (parent) {
            while (element.firstChild) {
              parent.insertBefore(element.firstChild, element)
            }
            parent.removeChild(element)
          }
        }
      }

      markings.value.splice(index, 1)

      try {
        await annotationApi.delete(id)
      } catch (e) {
        console.error('删除批注失败:', e)
      }
    }
  }

  function clearAllMarkings() {
    markings.value.forEach(marking => {
      const instance = markingInstances.value.get(marking.id)
      if (instance) {
        instance.remove()
      }
    })
    markingInstances.value.clear()
    markings.value = []
  }

  function getMarkingById(id) {
    return markings.value.find(a => a.id === id)
  }

  function getMarkingsByRegion(region) {
    return markings.value.filter(a => a.target.region === region)
  }

  function getSortedMarkingsByRegion(region) {
    return [...getMarkingsByRegion(region)].sort((a, b) => {
      return a.position.top - b.position.top
    })
  }

  const sortedMarkings = computed(() => {
    return [...markings.value].sort((a, b) => {
      return a.position.top - b.position.top
    })
  })

  function showMarkingsByRegion(region) {
    const regionMarkings = getMarkingsByRegion(region)
    regionMarkings.forEach(marking => {
      const instance = markingInstances.value.get(marking.id)
      if (instance) {
        instance.show()
      } else {
        let element = null
        if (region === 'clean' || region === 'translate') {
          element = document.querySelector(`[data-marking-id="${marking.id}"]`)?.closest('pre')
        } else {
          element = document.querySelector(`[data-marking-id="${marking.id}"]`)?.closest('.marking-content')
        }
        if (element) {
          applyHighlight(element, marking)
        }
      }
    })
  }

  function hideMarkingsByRegion(region) {
    const regionMarkings = getMarkingsByRegion(region)
    regionMarkings.forEach(marking => {
      const instance = markingInstances.value.get(marking.id)
      if (instance) {
        instance.hide()
      }
    })
  }

  const availableStyles = computed(() => {
    if (!isMultilineSelection.value) {
      return markingStyles
    }
    return markingStyles.filter(style => style.supportsMultiline)
  })

  /**
   * 从后端加载批注列表并在 DOM 上恢复高亮
   */
  async function loadAndRestoreMarkings(cleanEl, renderedEl, translateEl) {
    const uuid = typeof entityUuid === 'object' ? entityUuid?.value : entityUuid
    const type = typeof entityType === 'object' ? entityType?.value : entityType
    if (!uuid || !type) return

    try {
      const res = await annotationApi.list(uuid, type)
      if (res.code !== 0 || !res.data) return

      const regionElMap = {
        clean: cleanEl instanceof HTMLElement ? cleanEl.querySelector('pre') : null,
        translate: translateEl instanceof HTMLElement ? translateEl.querySelector('pre') : null,
        rendered: renderedEl instanceof HTMLElement ? renderedEl : null
      }

      for (const item of res.data) {
        const marking = {
          id: item.id,
          type: 'marking',
          content: item.content,
          style: item.style,
          target: {
            region: item.target.region,
            textOffset: {
              start: item.target.text_offset.start,
              end: item.target.text_offset.end,
              text: item.target.text_offset.text
            }
          },
          position: { top: 0, left: 0 },
          createdAt: new Date(item.created_at),
          updatedAt: new Date(item.updated_at)
        }
        markings.value.push(marking)

        const el = regionElMap[item.target.region]
        if (el) {
          applyTextHighlight(el, marking)
        }
      }
    } catch (e) {
      console.error('加载批注失败:', e)
    }
  }

  return {
    markings,
    selectedText,
    selectedStyle,
    toolbarVisible,
    toolbarPosition,
    markingStyles,
    availableStyles,
    isMultilineSelection,
    handleTextSelection,
    handleHtmlSelection,
    createMarkingFromSelection,
    updateMarkingContent,
    deleteMarking,
    clearAllMarkings,
    getMarkingById,
    updateMarkingPosition,
    updateAllPositions,
    updateToolbarPosition,
    getMarkingsByRegion,
    getSortedMarkingsByRegion,
    showMarkingsByRegion,
    hideMarkingsByRegion,
    sortedMarkings,
    hideToolbar,
    loadAndRestoreMarkings
  }
}
