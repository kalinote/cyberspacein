<template>
  <svg
    class="annotation-connector absolute inset-0 pointer-events-none z-10"
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
import { getStyleColor } from '@/utils/annotationStyles'

const props = defineProps({
  annotations: {
    type: Array,
    default: () => []
  },
  activeAnnotationId: {
    type: String,
    default: null
  }
})

const connectionPaths = ref([])

function calculatePath(annotation, index) {
  const { spanId, textOffset } = annotation.target
  let targetElement = null

  if (spanId) {
    targetElement = document.getElementById(spanId)
  } else if (textOffset) {
    const elements = document.querySelectorAll(`[data-annotation-id="${annotation.id}"]`)
    if (elements.length > 0) {
      targetElement = elements[0]
    }
  }

  if (!targetElement) return null

  const container = targetElement.closest('.annotation-container')
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
  const annotationCard = sidebar.querySelector(`[data-annotation-id="${annotation.id}"]`) ||
    sidebar.querySelectorAll('.annotation-card')[index]
  
  if (annotationCard) {
    const cardRect = annotationCard.getBoundingClientRect()
    cardY = cardRect.top + cardRect.height / 2 - containerRect.top
  } else if (annotation.position?.top) {
    cardY = annotation.position.top
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

  const isActive = props.activeAnnotationId === annotation.id

  return {
    id: annotation.id,
    d,
    color: getStyleColor(annotation.style, isActive),
    width: isActive ? 2.5 : 1.5
  }
}

function updatePaths() {
  nextTick(() => {
    setTimeout(() => {
      const sortedAnnotations = [...props.annotations].sort((a, b) => {
        const topA = a.position?.top || 0
        const topB = b.position?.top || 0
        return topA - topB
      })

      const paths = sortedAnnotations
        .map((annotation, index) => calculatePath(annotation, index))
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

watch(() => props.annotations, updatePaths, { deep: true })
watch(() => props.activeAnnotationId, updatePaths)

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
.annotation-connector {
  overflow: visible;
}
</style>
