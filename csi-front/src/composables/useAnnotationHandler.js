import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useAnnotation } from './useAnnotation'

export function useAnnotationHandler(options = {}) {
  const { cleanContentRef, renderedContentRef, activeTab } = options

  const annotation = useAnnotation()
  const activeAnnotationId = ref(null)

  const currentRegion = computed(() => {
    if (activeTab?.value === 'clean') return 'clean'
    if (activeTab?.value === 'rendered') return 'rendered'
    return ''
  })

  function handleCleanContentMouseUp() {
    if (activeTab?.value !== 'clean' || !cleanContentRef?.value) return

    setTimeout(() => {
      const selection = window.getSelection()
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        return
      }

      const preElement = cleanContentRef.value.querySelector('pre')
      if (preElement) {
        annotation.handleTextSelection(preElement, 'clean')
      }
    }, 50)
  }

  function handleRenderedContentMouseUp() {
    if (activeTab?.value !== 'rendered' || !renderedContentRef?.value) return

    setTimeout(() => {
      const selection = window.getSelection()
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        return
      }
      annotation.handleHtmlSelection(renderedContentRef.value)
    }, 50)
  }

  function handleStyleSelect(style) {
    annotation.selectedStyle.value = style
  }

  function handleCreateAnnotation() {
    if (!annotation.selectedText.value) return

    let element = null
    let region = null

    if (activeTab?.value === 'clean' && cleanContentRef?.value) {
      const preElement = cleanContentRef.value.querySelector('pre')
      if (preElement) {
        element = preElement
        region = 'clean'
      }
    } else if (activeTab?.value === 'rendered' && renderedContentRef?.value) {
      element = renderedContentRef.value
      region = 'rendered'
    }

    if (element && region) {
      const newAnnotation = annotation.createAnnotationFromSelection(element, region, annotation.selectedStyle.value)
      if (newAnnotation) {
        nextTick(() => {
          annotation.updateAnnotationPosition(newAnnotation)
        })
      }
    }
  }

  function handleCancelAnnotation() {
    annotation.hideToolbar()
    window.getSelection()?.removeAllRanges()
  }

  function handleUpdateAnnotation(id, content) {
    annotation.updateAnnotationContent(id, content)
  }

  function handleDeleteAnnotation(id) {
    annotation.deleteAnnotation(id)
    if (activeAnnotationId.value === id) {
      activeAnnotationId.value = null
    }
  }

  function handleAnnotationHover(id, isHovering) {
    activeAnnotationId.value = isHovering ? id : null
  }

  function handleClick(e) {
    if (e.target.closest('.annotation-toolbar')) {
      return
    }

    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
      return
    }

    if (!e.target.closest('.annotation-target') &&
        !e.target.closest('.annotation-container')) {
      annotation.hideToolbar()
    }
  }

  function handleScroll() {
    annotation.updateAllPositions()
  }

  async function handleTabChange(newTab, oldTab) {
    annotation.hideToolbar()

    if (oldTab === 'clean' || oldTab === 'rendered') {
      const oldRegion = oldTab === 'clean' ? 'clean' : 'rendered'
      annotation.hideAnnotationsByRegion(oldRegion)
    }

    if (newTab === 'clean' || newTab === 'rendered') {
      const newRegion = newTab === 'clean' ? 'clean' : 'rendered'
      await nextTick()
      if (newTab === 'clean' && cleanContentRef?.value) {
        const preElement = cleanContentRef.value.querySelector('pre')
        if (preElement && !preElement.id) {
          preElement.id = `clean-content-${Date.now()}`
        }
      }
      annotation.showAnnotationsByRegion(newRegion)
    }
  }

  function setupEventListeners() {
    document.addEventListener('click', handleClick)
    window.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', handleScroll)
  }

  function cleanupEventListeners() {
    document.removeEventListener('click', handleClick)
    window.removeEventListener('scroll', handleScroll, true)
    window.removeEventListener('resize', handleScroll)
  }

  return {
    ...annotation,
    activeAnnotationId,
    currentRegion,
    handleCleanContentMouseUp,
    handleRenderedContentMouseUp,
    handleStyleSelect,
    handleCreateAnnotation,
    handleCancelAnnotation,
    handleUpdateAnnotation,
    handleDeleteAnnotation,
    handleAnnotationHover,
    handleTabChange,
    setupEventListeners,
    cleanupEventListeners
  }
}
