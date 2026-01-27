<template>
  <svg
    class="marking-connector absolute inset-0 pointer-events-none z-10"
    :style="{ width: '100%', height: '100%' }"
  >
    <path
      v-for="path in connectionPaths"
      :key="path.id"
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
import { getStyleColor } from '@/utils/markingStyles'

const props = defineProps({
  markings: {
    type: Array,
    default: () => []
  },
  activeMarkingId: {
    type: String,
    default: null
  }
})

const connectionPaths = ref([])

function calculatePath(marking, index) {
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

  if (!targetElement) return null

  const container = targetElement.closest('.marking-container')
  if (!container) return null

  const targetRect = targetElement.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()
  const sidebar = container.previousElementSibling
  const sidebarRect = sidebar?.getBoundingClientRect()

  if (!sidebarRect) return null

  const targetX = targetRect.left - containerRect.left
  const targetY = targetRect.top + targetRect.height / 2 - containerRect.top

  const sidebarX = sidebarRect.right - containerRect.left

  let cardY = targetY
  const markingCard = sidebar.querySelector(`[data-marking-id="${marking.id}"]`) ||
    sidebar.querySelectorAll('.marking-card')[index]
  
  if (markingCard) {
    const cardRect = markingCard.getBoundingClientRect()
    cardY = cardRect.top + cardRect.height / 2 - containerRect.top
  } else if (marking.position?.top) {
    cardY = marking.position.top
  }

  const startX = targetX
  const startY = targetY
  const endX = sidebarX
  const endY = cardY

  const controlX1 = startX - Math.abs(endX - startX) * 0.4
  const controlY1 = startY
  const controlX2 = endX + Math.abs(endX - startX) * 0.4
  const controlY2 = endY

  const d = `M ${startX} ${startY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${endX} ${endY}`

  const isActive = props.activeMarkingId === marking.id

  return {
    id: marking.id,
    d,
    color: getStyleColor(marking.style, isActive),
    width: isActive ? 2.5 : 1.5
  }
}

function updatePaths() {
  nextTick(() => {
    setTimeout(() => {
      const sortedMarkings = [...props.markings].sort((a, b) => {
        const topA = a.position?.top || 0
        const topB = b.position?.top || 0
        return topA - topB
      })

      const paths = sortedMarkings
        .map((marking, index) => calculatePath(marking, index))
        .filter(path => path !== null)
      
      connectionPaths.value = paths
    }, 100)
  })
}

let updateTimer = null

function scheduleUpdate() {
  if (updateTimer) {
    clearTimeout(updateTimer)
  }
  updateTimer = setTimeout(updatePaths, 50)
}

watch(() => props.markings, updatePaths, { deep: true })
watch(() => props.activeMarkingId, updatePaths)

onMounted(() => {
  updatePaths()
  
  window.addEventListener('scroll', scheduleUpdate, true)
  window.addEventListener('resize', scheduleUpdate)
})

onUnmounted(() => {
  if (updateTimer) {
    clearTimeout(updateTimer)
  }
  window.removeEventListener('scroll', scheduleUpdate, true)
  window.removeEventListener('resize', scheduleUpdate)
})
</script>

<style scoped>
.marking-connector {
  overflow: visible;
}
</style>
