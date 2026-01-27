import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useMarking } from './useMarking'

export function useMarkingHandler(options = {}) {
  const { cleanContentRef, renderedContentRef, activeTab } = options

  const marking = useMarking()
  const activeMarkingId = ref(null)

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

  function handleCancelMarking() {
    marking.hideToolbar()
    window.getSelection()?.removeAllRanges()
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

  function handleClick(e) {
    if (e.target.closest('.marking-toolbar')) {
      return
    }

    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
      return
    }

    if (!e.target.closest('.marking-target') &&
        !e.target.closest('.marking-container')) {
      marking.hideToolbar()
    }
  }

  function handleScroll() {
    marking.updateAllPositions()
  }

  async function handleTabChange(newTab, oldTab) {
    marking.hideToolbar()

    if (oldTab === 'clean' || oldTab === 'rendered') {
      const oldRegion = oldTab === 'clean' ? 'clean' : 'rendered'
      marking.hideMarkingsByRegion(oldRegion)
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
      marking.showMarkingsByRegion(newRegion)
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
    ...marking,
    activeMarkingId,
    currentRegion,
    handleCleanContentMouseUp,
    handleRenderedContentMouseUp,
    handleStyleSelect,
    handleCreateMarking,
    handleCancelMarking,
    handleUpdateMarking,
    handleDeleteMarking,
    handleMarkingHover,
    handleTabChange,
    setupEventListeners,
    cleanupEventListeners
  }
}
