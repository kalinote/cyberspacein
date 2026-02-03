import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useMarking } from './useMarking'

export function useMarkingHandler(options = {}) {
  const { cleanContentRef, renderedContentRef, translateContentRef, activeTab } = options

  const marking = useMarking()
  const activeMarkingId = ref(null)

  const currentRegion = computed(() => {
    if (activeTab?.value === 'clean') return 'clean'
    if (activeTab?.value === 'rendered') return 'rendered'
    if (activeTab?.value === 'translate') return 'translate'
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
        marking.handleTextSelection(preElement, 'clean')
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
      marking.handleHtmlSelection(renderedContentRef.value)
    }, 50)
  }

  function handleTranslateContentMouseUp() {
    if (activeTab?.value !== 'translate' || !translateContentRef?.value) return

    setTimeout(() => {
      const selection = window.getSelection()
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        return
      }

      const preElement = translateContentRef.value.querySelector('pre')
      if (preElement) {
        marking.handleTextSelection(preElement, 'translate')
      }
    }, 50)
  }

  function handleStyleSelect(style) {
    marking.selectedStyle.value = style
  }

  function handleCreateMarking() {
    if (!marking.selectedText.value) return

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
    } else if (activeTab?.value === 'translate' && translateContentRef?.value) {
      const preElement = translateContentRef.value.querySelector('pre')
      if (preElement) {
        element = preElement
        region = 'translate'
      }
    }

    if (element && region) {
      const newMarking = marking.createMarkingFromSelection(element, region, marking.selectedStyle.value)
      if (newMarking) {
        nextTick(() => {
          marking.updateMarkingPosition(newMarking)
        })
      }
    }
  }

  function handleUpdateMarking(id, content) {
    marking.updateMarkingContent(id, content)
  }

  function handleDeleteMarking(id) {
    marking.deleteMarking(id)
    if (activeMarkingId.value === id) {
      activeMarkingId.value = null
    }
  }

  function handleMarkingHover(id, isHovering) {
    activeMarkingId.value = isHovering ? id : null
  }

  function handleMouseDown(e) {
    if (e.target.closest('.marking-toolbar')) {
      return
    }

    if (marking.toolbarVisible.value) {
      marking.hideToolbar()
      window.getSelection()?.removeAllRanges()
    }
  }

  function handleScroll() {
    marking.updateAllPositions()
  }

  async function handleTabChange(newTab, oldTab) {
    marking.hideToolbar()

    if (oldTab === 'clean' || oldTab === 'rendered' || oldTab === 'translate') {
      const oldRegion = oldTab === 'clean' ? 'clean' : oldTab === 'rendered' ? 'rendered' : 'translate'
      marking.hideMarkingsByRegion(oldRegion)
    }

    if (newTab === 'clean' || newTab === 'rendered' || newTab === 'translate') {
      const newRegion = newTab === 'clean' ? 'clean' : newTab === 'rendered' ? 'rendered' : 'translate'
      await nextTick()
      if (newTab === 'clean' && cleanContentRef?.value) {
        const preElement = cleanContentRef.value.querySelector('pre')
        if (preElement && !preElement.id) {
          preElement.id = `clean-content-${Date.now()}`
        }
      }
      if (newTab === 'translate' && translateContentRef?.value) {
        const preElement = translateContentRef.value.querySelector('pre')
        if (preElement && !preElement.id) {
          preElement.id = `translate-content-${Date.now()}`
        }
      }
      marking.showMarkingsByRegion(newRegion)
    }
  }

  function setupEventListeners() {
    document.addEventListener('mousedown', handleMouseDown)
    window.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', handleScroll)
  }

  function cleanupEventListeners() {
    document.removeEventListener('mousedown', handleMouseDown)
    window.removeEventListener('scroll', handleScroll, true)
    window.removeEventListener('resize', handleScroll)
  }

  return {
    ...marking,
    activeMarkingId,
    currentRegion,
    handleCleanContentMouseUp,
    handleRenderedContentMouseUp,
    handleTranslateContentMouseUp,
    handleStyleSelect,
    handleCreateMarking,
    handleUpdateMarking,
    handleDeleteMarking,
    handleMarkingHover,
    handleTabChange,
    setupEventListeners,
    cleanupEventListeners
  }
}
