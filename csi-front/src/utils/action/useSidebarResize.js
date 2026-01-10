import { ref, onUnmounted } from 'vue'

/**
 * 可复用的侧边栏调整大小组合函数
 * @param {number} initialWidth - 初始宽度
 * @param {number} minWidth - 最小宽度
 * @param {number} maxWidth - 最大宽度
 * @param {string} direction - 调整方向 'left' 或 'right'
 * @returns {object} { sidebarWidth, isResizing, startResize }
 */
export function useSidebarResize(initialWidth, minWidth, maxWidth, direction = 'right') {
  const sidebarWidth = ref(initialWidth)
  const isResizing = ref(false)

  const startResize = () => {
    isResizing.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onResize)
    window.addEventListener('mouseup', stopResize)
  }

  const onResize = (event) => {
    if (!isResizing.value) return
    
    let newWidth
    if (direction === 'right') {
      newWidth = window.innerWidth - event.clientX
    } else {
      newWidth = event.clientX
    }
    
    if (newWidth < minWidth) {
      sidebarWidth.value = minWidth
    } else if (newWidth > maxWidth) {
      sidebarWidth.value = maxWidth
    } else {
      sidebarWidth.value = newWidth
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
    sidebarWidth,
    isResizing,
    startResize
  }
}
