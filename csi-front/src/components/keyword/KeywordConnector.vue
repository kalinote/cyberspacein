<template>
  <svg
    ref="svgRef"
    class="keyword-connector absolute inset-0 pointer-events-none z-10"
    :style="{ width: '100%', height: '100%' }"
  >
    <path
      v-for="(path, index) in connectionPaths"
      :key="index"
      :d="path.d"
      :stroke="path.color"
      :stroke-width="path.width"
      fill="none"
      class="transition-all duration-200"
    />
  </svg>
</template>

<script setup>
import { watch, ref, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  selectedKeywords: {
    type: Array,
    default: () => []
  },
  keywordTagRefs: {
    type: Object,
    default: () => ({})
  },
  keywordColors: {
    type: Object,
    default: () => ({})
  },
  activeTab: {
    type: String,
    default: ''
  }
})

const DEFAULT_LINE_COLOR = '#3b82f6'

const svgRef = ref(null)
const connectionPaths = ref([])

function getTagEl(refVal) {
  return refVal?.$el ?? refVal
}

function calculatePaths() {
  const container = svgRef.value?.closest('.marking-container')
  if (!container || !props.selectedKeywords?.length) {
    connectionPaths.value = []
    return
  }
  const containerRect = container.getBoundingClientRect()
  const allPaths = []
  const allHighlights = container.querySelectorAll('.keyword-highlight')
  for (const keyword of props.selectedKeywords) {
    const tagEl = getTagEl(props.keywordTagRefs?.[keyword])
    if (!tagEl) continue
    const highlights = Array.from(allHighlights).filter((el) => el.getAttribute('data-keyword') === keyword)
    const visibleHighlights = highlights.filter((el) => {
      const r = el.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    })
    if (!visibleHighlights.length) continue
    const tagRect = tagEl.getBoundingClientRect()
    const startX = tagRect.left - containerRect.left
    const startY = tagRect.top + tagRect.height / 2 - containerRect.top
    const color = props.keywordColors?.[keyword] || DEFAULT_LINE_COLOR
    visibleHighlights.forEach((el) => {
      const r = el.getBoundingClientRect()
      const endX = r.right - containerRect.left
      const endY = r.top - containerRect.top + r.height / 2
      const delta = Math.abs(startX - endX)
      const controlX1 = startX - delta * 0.4
      const controlY1 = startY
      const controlX2 = endX + delta * 0.4
      const controlY2 = endY
      const d = `M ${startX} ${startY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${endX} ${endY}`
      allPaths.push({ d, color, width: 1.5 })
    })
  }
  connectionPaths.value = allPaths
}

function updatePaths() {
  nextTick(() => {
    setTimeout(calculatePaths, 100)
  })
}

let updateTimer = null

function scheduleUpdate() {
  if (updateTimer) clearTimeout(updateTimer)
  updateTimer = setTimeout(updatePaths, 50)
}

watch(() => props.selectedKeywords, updatePaths, { deep: true })
watch(() => props.keywordTagRefs, updatePaths, { deep: true })
watch(() => props.keywordColors, updatePaths, { deep: true })
watch(() => props.activeTab, updatePaths)

onMounted(() => {
  updatePaths()
  window.addEventListener('scroll', scheduleUpdate, true)
  window.addEventListener('resize', scheduleUpdate)
})

onUnmounted(() => {
  if (updateTimer) clearTimeout(updateTimer)
  window.removeEventListener('scroll', scheduleUpdate, true)
  window.removeEventListener('resize', scheduleUpdate)
})
</script>

<style scoped>
.keyword-connector {
  overflow: visible;
}
</style>
