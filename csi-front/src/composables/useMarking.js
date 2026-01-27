import { ref, computed, nextTick } from 'vue'
import { annotate } from 'rough-notation'
import { createSpanWrapper, serializeTextSelection, serializeHtmlSelection } from '@/utils/textSelection'
import { getStyleColor, createMarkingConfig } from '@/utils/markingStyles'

export function useMarking() {
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
        region,
        ...target
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
    if (marking.target.region === 'clean') {
      applyTextHighlight(element, marking)
    } else {
      applyHtmlHighlight(element, marking)
    }
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
      while (node = walker.nextNode()) {
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

  function applyHtmlHighlight(element, marking) {
    const { spanId } = marking.target
    if (!spanId) return

    nextTick(() => {
      setTimeout(() => {
        const highlightElement = document.getElementById(spanId)
        if (highlightElement) {
          const range = document.createRange()
          range.selectNodeContents(highlightElement)
          const isMultiline = checkIfMultiline(range)
          const config = createMarkingConfig(marking.style, isMultiline)
          const instance = annotate(highlightElement, config)
          instance.show()
          markingInstances.value.set(marking.id, instance)
          updateMarkingPosition(marking)
        }
      }, 50)
    })
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

    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      null
    )

    let currentOffset = 0
    let startOffset = 0
    let endOffset = 0
    let foundStart = false

    let node
    while (node = walker.nextNode()) {
      const nodeLength = node.textContent.length
      
      if (!foundStart && range.startContainer === node) {
        startOffset = currentOffset + range.startOffset
        foundStart = true
      }
      
      if (range.endContainer === node) {
        endOffset = currentOffset + range.endOffset
        break
      }
      
      currentOffset += nodeLength
    }

    if (!foundStart) {
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

    selectedText.value = {
      range: range.cloneRange(),
      text: selectedTextValue
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

  function createMarkingFromSelection(element, region, style) {
    if (!selectedText.value) return null

    let target = null
    let rangeToUse = null

    if (region === 'clean') {
      target = serializeTextSelection(element, selectedText.value)
      rangeToUse = selectedText.value.range
    } else {
      rangeToUse = selectedText.value.range
      const spanId = `marking-span-${generateId()}`
      const span = createSpanWrapper(rangeToUse.cloneRange(), spanId)
      if (span) {
        target = serializeHtmlSelection(element, span)
      }
    }

    if (!target) return null

    const marking = createMarking(element, region, target, style)
    applyHighlight(element, marking)
    
    window.getSelection()?.removeAllRanges()
    hideToolbar()

    return marking
  }

  function updateMarkingContent(id, content) {
    const marking = markings.value.find(a => a.id === id)
    if (marking) {
      marking.content = content
      marking.updatedAt = new Date()
    }
  }

  function deleteMarking(id) {
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
        const element = region === 'clean' 
          ? document.querySelector(`[data-marking-id="${marking.id}"]`)?.closest('pre')
          : document.getElementById(marking.target.spanId)?.closest('.marking-content')
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
    hideToolbar
  }
}
