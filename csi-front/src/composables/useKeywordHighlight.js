import { ref, computed, nextTick } from 'vue'
import {
  buildHighlightedPlainTextHtmlMulti,
  wrapKeywordInRenderedElementMulti,
  unwrapKeywordHighlights,
  getRandomKeywordColor
} from '@/utils/keywordHighlight'

export function useKeywordHighlight(options = {}) {
  const { getCleanContent, getTranslateContent, renderedContentRef, activeTab } = options

  const selectedKeywords = ref([])
  const keywordTagRefs = ref({})
  const keywordColors = ref({})

  const highlightedCleanContent = computed(() => {
    const content = getCleanContent?.()
    if (content == null || content === '') return ''
    return buildHighlightedPlainTextHtmlMulti(content, selectedKeywords.value, keywordColors.value)
  })

  const highlightedTranslateContent = computed(() => {
    const content = getTranslateContent?.()
    if (content == null || content === '') return ''
    return buildHighlightedPlainTextHtmlMulti(content, selectedKeywords.value, keywordColors.value)
  })

  function setKeywordRef(keyword, el) {
    if (el) keywordTagRefs.value[keyword] = el
  }

  function toggleKeyword(keyword) {
    const idx = selectedKeywords.value.indexOf(keyword)
    if (idx >= 0) {
      selectedKeywords.value = selectedKeywords.value.filter((k) => k !== keyword)
    } else {
      selectedKeywords.value = [...selectedKeywords.value, keyword]
      if (!keywordColors.value[keyword]) {
        keywordColors.value = { ...keywordColors.value, [keyword]: getRandomKeywordColor() }
      }
    }
  }

  function applyRenderedKeywordHighlight() {
    nextTick(() => {
      const container = renderedContentRef?.value
      if (!container) return
      if (activeTab?.value !== 'rendered') {
        unwrapKeywordHighlights(container)
        return
      }
      if (!selectedKeywords.value.length) {
        unwrapKeywordHighlights(container)
        return
      }
      wrapKeywordInRenderedElementMulti(container, selectedKeywords.value, keywordColors.value)
    })
  }

  return {
    selectedKeywords,
    keywordTagRefs,
    keywordColors,
    highlightedCleanContent,
    highlightedTranslateContent,
    setKeywordRef,
    toggleKeyword,
    applyRenderedKeywordHighlight
  }
}
