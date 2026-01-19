import { ref, onUnmounted } from 'vue'

/**
 * 可复用的垂直方向调整大小组合函数
 * @param {number} initialHeight - 初始高度
 * @param {number} minHeight - 最小高度
 * @param {number} maxHeight - 最大高度
 * @returns {object} { height, isResizing, startResize }
 */
export function useVerticalResize(initialHeight, minHeight, maxHeight) {
  const height = ref(initialHeight)
  const isResizing = ref(false)
  let startY = 0
  let startHeight = 0

  const startResize = (event) => {
    isResizing.value = true
    startY = event.clientY
    startHeight = height.value
    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onResize)
    window.addEventListener('mouseup', stopResize)
  }

  const onResize = (event) => {
    if (!isResizing.value) return
    
    const deltaY = event.clientY - startY
    const newHeight = startHeight - deltaY
    
    if (newHeight < minHeight) {
      height.value = minHeight
    } else if (newHeight > maxHeight) {
      height.value = maxHeight
    } else {
      height.value = newHeight
    }
  }

  const stopResize = () => {
    isResizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onResize)
    window.removeEventListener('mouseup', stopResize)
  }

  onUnmounted(() => {
    window.removeEventListener('mousemove', onResize)
    window.removeEventListener('mouseup', stopResize)
  })

  return {
    height,
    isResizing,
    startResize
  }
}
