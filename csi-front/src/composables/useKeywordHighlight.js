import { ref, computed, nextTick } from 'vue'
import {
  buildHighlightedPlainTextHtmlLayers,
  applyRenderedHighlightsMulti,
  getRandomKeywordColor,
} from '@/utils/keywordHighlight'

export function useKeywordHighlight(options = {}) {
  const { getCleanContent, getTranslateContent, renderedContentRef, activeTab } = options

  const selectedKeywords = ref([])
  const keywordTagRefs = ref({})
  const keywordColors = ref({})

  function buildKeywordHighlightLayer() {
    if (!selectedKeywords.value.length) return null
    return {
      items: selectedKeywords.value,
      colors: keywordColors.value,
      dataAttr: 'data-keyword',
      highlightClass: 'keyword-highlight',
    }
  }

  function buildHighlightLayers(extraLayers = []) {
    const layers = []
    const kw = buildKeywordHighlightLayer()
    if (kw) layers.push(kw)
    for (const layer of extraLayers) {
      if (layer) layers.push(layer)
    }
    return layers
  }

  function getHighlightedPlainText(getContent, extraLayers = []) {
    const content = getContent?.()
    if (content == null || content === '') return ''
    return buildHighlightedPlainTextHtmlLayers(content, buildHighlightLayers(extraLayers))
  }

  const highlightedCleanContent = computed(() => getHighlightedPlainText(getCleanContent))

  const highlightedTranslateContent = computed(() => getHighlightedPlainText(getTranslateContent))

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

  function applyRenderedKeywordHighlight(extraLayers = []) {
    nextTick(() => {
      const container = renderedContentRef?.value
      if (!container) return
      if (activeTab?.value !== 'rendered') {
        applyRenderedHighlightsMulti(container, [])
        return
      }
      const layers = buildHighlightLayers(extraLayers)
      if (!layers.length) {
        applyRenderedHighlightsMulti(container, [])
        return
      }
      applyRenderedHighlightsMulti(container, layers)
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
    applyRenderedKeywordHighlight,
    buildKeywordHighlightLayer,
    getHighlightedPlainText,
    buildHighlightLayers,
  }
}
