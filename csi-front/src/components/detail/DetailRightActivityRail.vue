<template>
    <nav
        class="shrink-0 flex flex-col gap-1 py-2 px-1 border-l border-gray-100 bg-gray-50/80 rounded-r-xl self-stretch"
        aria-label="详情侧栏切换"
    >
        <button
            v-for="item in items"
            :key="item.key"
            type="button"
            :title="item.label"
            class="flex items-center justify-center w-10 h-10 rounded-lg transition-all"
            :class="
                modelValue === item.key
                    ? 'bg-blue-50 text-blue-600 shadow-sm border border-blue-200'
                    : 'text-gray-500 hover:bg-white hover:text-gray-700'
            "
            @click="emit('update:modelValue', item.key)"
        >
            <Icon :icon="item.icon" class="text-xl" />
        </button>
    </nav>
</template>

<script setup>
import { Icon } from '@iconify/vue'

defineProps({
    items: {
        type: Array,
        default: () => [],
    },
    modelValue: {
        type: String,
        default: 'info',
    },
})

const emit = defineEmits(['update:modelValue'])
</script>
