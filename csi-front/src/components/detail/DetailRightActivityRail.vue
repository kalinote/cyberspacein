<template>
    <nav
        class="detail-activity-rail shrink-0 flex flex-col gap-1 py-2 px-1 border-l border-gray-100 bg-gray-50/80 rounded-r-xl self-stretch"
        aria-label="详情侧栏切换"
    >
        <button
            v-for="item in items"
            :key="item.key"
            type="button"
            :title="item.label"
            :aria-label="item.label"
            :aria-pressed="modelValue === item.key"
            class="flex items-center justify-center w-10 h-10 rounded-lg transition-all"
            :class="
                modelValue === item.key
                    ? 'bg-blue-50 text-blue-600 shadow-sm border border-blue-200'
                    : 'text-gray-500 hover:bg-white hover:text-gray-700'
            "
            @click="emit('update:modelValue', item.key)"
        >
            <Icon :icon="item.icon" class="text-xl" />
            <span class="detail-activity-label">{{ item.label }}</span>
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

<style scoped>
.detail-activity-label { display: none; }
@media (max-width: 767px) {
    .detail-activity-rail { flex-direction: row; width: 100%; height: auto; border: 0; border-radius: 10px; padding: 4px; }
    .detail-activity-rail button { width: auto; min-height: 44px; flex: 1; gap: 8px; font-size: 14px; }
    .detail-activity-label { display: inline; }
}
</style>
