import { ref, onMounted, onUnmounted } from 'vue'

const LG_QUERY = '(min-width: 1024px)'

/**
 * @returns {import('vue').Ref<boolean>}
 */
export function useMinLg() {
    const isLgUp = ref(false)
    let mediaQuery = null

    const sync = () => {
        isLgUp.value = mediaQuery?.matches ?? false
    }

    onMounted(() => {
        mediaQuery = window.matchMedia(LG_QUERY)
        sync()
        mediaQuery.addEventListener('change', sync)
    })

    onUnmounted(() => {
        mediaQuery?.removeEventListener('change', sync)
    })

    return { isLgUp }
}
