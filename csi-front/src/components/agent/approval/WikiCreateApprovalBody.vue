<template>
    <div class="space-y-4">
        <div class="rounded-lg border border-gray-200 bg-gray-50/80 p-4">
            <p class="text-xs font-medium text-gray-700 mb-2">新建页面</p>
            <p class="text-lg font-semibold text-gray-900 wrap-break-word">{{ payload?.title || '—' }}</p>
        </div>

        <div v-if="categories.length" class="rounded-lg border border-gray-200 bg-white p-4">
            <p class="text-xs font-medium text-gray-700 mb-2">分类</p>
            <div class="flex flex-wrap gap-1.5">
                <el-tag
                    v-for="tag in categories"
                    :key="tag"
                    size="small"
                    type="info"
                    effect="plain"
                >
                    {{ tag }}
                </el-tag>
            </div>
        </div>

        <div v-if="payload?.source_note" class="rounded-lg border border-gray-200 bg-white p-4">
            <p class="text-xs font-medium text-gray-700 mb-1">来源说明</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload.source_note }}</p>
        </div>

        <div v-if="payload?.reason" class="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3">
            <p class="text-xs font-medium text-blue-800 mb-1">操作说明</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload.reason }}</p>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
    payload: {
        type: Object,
        default: null,
    },
})

const categories = computed(() => {
    const list = props.payload?.categories
    return Array.isArray(list) ? list.map((v) => String(v)).filter(Boolean) : []
})
</script>
