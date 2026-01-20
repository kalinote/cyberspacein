<template>
    <div ref="menuRef" class="relative">
        <div class="flex">
            <button 
                @click.stop="handleMainClick"
                :disabled="disabled"
                class="flex-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white py-3 rounded-l-lg font-medium transition-colors flex items-center justify-center space-x-2"
            >
                <Icon v-if="mainButtonIcon" :icon="loading ? 'mdi:loading' : mainButtonIcon" :class="{ 'animate-spin': loading }" />
                <span>{{ loading ? loadingText : mainButtonText }}</span>
            </button>
            <button
                @click.stop="toggleMenu"
                :disabled="disabled"
                class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white py-3 px-3 rounded-r-lg border-l border-blue-400 transition-colors flex items-center justify-center"
            >
                <Icon icon="mdi:chevron-down" :class="{ 'rotate-180': showMenu }" class="transition-transform" />
            </button>
        </div>
        <div 
            v-if="showMenu && options && options.length > 0"
            class="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden z-10"
        >
            <button
                v-for="option in options"
                :key="option.value"
                @click.stop="handleOptionClick(option)"
                class="w-full text-left px-4 py-3 text-gray-700 hover:bg-gray-50 transition-colors flex items-center space-x-2"
            >
                <Icon v-if="option.icon" :icon="option.icon" class="text-blue-500" />
                <span>{{ option.label }}</span>
            </button>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
    mainButtonText: {
        type: String,
        required: true
    },
    loadingText: {
        type: String,
        default: '处理中...'
    },
    disabled: {
        type: Boolean,
        default: false
    },
    loading: {
        type: Boolean,
        default: false
    },
    options: {
        type: Array,
        default: () => []
    },
    mainButtonIcon: {
        type: String,
        default: null
    }
})

const emit = defineEmits(['main-click', 'option-click'])

const showMenu = ref(false)
const menuRef = ref(null)

const toggleMenu = () => {
    showMenu.value = !showMenu.value
}

const handleMainClick = () => {
    showMenu.value = false
    emit('main-click')
}

const handleOptionClick = (option) => {
    showMenu.value = false
    emit('option-click', option)
}

const handleClickOutside = (event) => {
    if (showMenu.value && menuRef.value && !menuRef.value.contains(event.target)) {
        showMenu.value = false
    }
}

onMounted(() => {
    document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
})
</script>
