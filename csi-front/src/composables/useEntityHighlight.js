import { ref } from 'vue'
import { entityRefKey } from '@/utils/entityDisplay'
import { getRandomKeywordColor } from '@/utils/keywordHighlight'

export function useEntityHighlight() {
  const selectedEntityKeys = ref([])
  const entityTagRefs = ref({})
  const entityColors = ref({})

  function setEntityRef(key, el) {
    if (el) entityTagRefs.value[key] = el
  }

  function toggleEntity(category, name) {
    const key = entityRefKey(category, name)
    const idx = selectedEntityKeys.value.indexOf(key)
    if (idx >= 0) {
      selectedEntityKeys.value = selectedEntityKeys.value.filter((k) => k !== key)
    } else {
      selectedEntityKeys.value = [...selectedEntityKeys.value, key]
      if (!entityColors.value[key]) {
        entityColors.value = { ...entityColors.value, [key]: getRandomKeywordColor() }
      }
    }
  }

  function buildEntityHighlightLayer() {
    if (!selectedEntityKeys.value.length) return null
    return {
      terms: selectedEntityKeys.value.map((key) => ({
        matchText: key.includes(':') ? key.slice(key.indexOf(':') + 1) : key,
        dataValue: key,
        colorKey: key,
      })),
      colors: entityColors.value,
      dataAttr: 'data-entity',
      highlightClass: 'entity-highlight',
    }
  }

  return {
    selectedEntityKeys,
    entityTagRefs,
    entityColors,
    setEntityRef,
    toggleEntity,
    buildEntityHighlightLayer,
  }
}
