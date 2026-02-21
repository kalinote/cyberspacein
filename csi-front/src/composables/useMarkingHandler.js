import { ref, computed, nextTick, watch } from 'vue'
import { useMarking } from './useMarking'

export function useMarkingHandler(options = {}) {
  const { cleanContentRef, renderedContentRef, translateContentRef, activeTab, entityUuid, entityType } = options

  const marking = useMarking({ entityUuid, entityType })
  const activeMarkingId = ref(null)
  const pendingLoadMarkings = ref(false)

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

  async function handleCreateMarking() {
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
      const newMarking = await marking.createMarkingFromSelection(element, region, marking.selectedStyle.value)
      if (newMarking) {
        nextTick(() => {
          marking.updateMarkingPosition(newMarking)
        })
      }
    }
  }

  async function handleUpdateMarking(id, content) {
    await marking.updateMarkingContent(id, content)
  }

  async function handleDeleteMarking(id) {
    await marking.deleteMarking(id)
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

  async function loadMarkings() {
    await nextTick()
    const cleanEl = cleanContentRef?.value
    const renderedEl = renderedContentRef?.value
    const translateEl = translateContentRef?.value
    const hasAnyEl = (cleanEl instanceof HTMLElement && cleanEl.querySelector('pre')) || (renderedEl instanceof HTMLElement) || (translateEl instanceof HTMLElement && translateEl.querySelector('pre'))
    if (hasAnyEl) {
      await marking.loadAndRestoreMarkings(cleanEl, renderedEl, translateEl)
    } else {
      pendingLoadMarkings.value = true
    }
  }

  watch(
    () => [cleanContentRef?.value, renderedContentRef?.value, translateContentRef?.value],
    () => {
      if (!pendingLoadMarkings.value) return
      const cleanEl = cleanContentRef?.value
      const renderedEl = renderedContentRef?.value
      const translateEl = translateContentRef?.value
      const hasAnyEl = (cleanEl instanceof HTMLElement && cleanEl.querySelector('pre')) || (renderedEl instanceof HTMLElement) || (translateEl instanceof HTMLElement && translateEl.querySelector('pre'))
      if (hasAnyEl) {
        pendingLoadMarkings.value = false
        nextTick(() => {
          marking.loadAndRestoreMarkings(cleanEl, renderedEl, translateEl)
        })
      }
    },
    { flush: 'post' }
  )

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
    loadMarkings,
    setupEventListeners,
    cleanupEventListeners
  }
}
