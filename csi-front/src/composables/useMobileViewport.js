import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 跟踪手机断点和可见视口，让导航与面板避开软键盘。
 * @returns {{ isMobile: import('vue').Ref<boolean>, keyboardOpen: import('vue').Ref<boolean>, viewportHeight: import('vue').Ref<number>, viewportTop: import('vue').Ref<number>, keyboardOffset: import('vue').Ref<number> }}
 */
export function useMobileViewport() {
  const media = window.matchMedia('(max-width: 767px)')
  const isMobile = ref(media.matches)
  const keyboardOpen = ref(false)
  const viewportHeight = ref(window.visualViewport?.height ?? window.innerHeight)
  const viewportTop = ref(0)
  const keyboardOffset = ref(0)
  let fullHeight = window.innerHeight

  /** """同步可见视口，缩放页面时不误判为软键盘。""" */
  const sync = () => {
    isMobile.value = media.matches
    const viewport = window.visualViewport
    const editing = document.activeElement?.matches('input:not([type="checkbox"]):not([type="radio"]), textarea, [contenteditable="true"]')
    if (!editing) fullHeight = window.innerHeight
    viewportHeight.value = viewport?.height ?? window.innerHeight
    viewportTop.value = viewport?.offsetTop ?? 0
    keyboardOffset.value = Math.max(0, window.innerHeight - viewportHeight.value - viewportTop.value)
    keyboardOpen.value = isMobile.value && Boolean(editing) && (viewport?.scale ?? 1) === 1
      && Math.max(fullHeight, window.innerHeight) - viewportHeight.value > 120
  }

  onMounted(() => {
    sync()
    media.addEventListener('change', sync)
    window.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('scroll', sync)
    document.addEventListener('focusin', sync)
    document.addEventListener('focusout', sync)
  })
  onUnmounted(() => {
    media.removeEventListener('change', sync)
    window.removeEventListener('resize', sync)
    window.visualViewport?.removeEventListener('resize', sync)
    window.visualViewport?.removeEventListener('scroll', sync)
    document.removeEventListener('focusin', sync)
    document.removeEventListener('focusout', sync)
  })

  return { isMobile, keyboardOpen, viewportHeight, viewportTop, keyboardOffset }
}
