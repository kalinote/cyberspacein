<template>
    <div class="space-y-4">
        <div class="rounded-lg border border-gray-200 bg-gray-50/80 p-4">
            <p class="text-xs font-medium text-gray-700 mb-3">目标 Wiki 页面</p>
            <div class="grid gap-2 text-sm sm:grid-cols-2">
                <div class="flex flex-col gap-0.5 min-w-0 sm:col-span-2">
                    <span class="text-xs text-gray-500">页面 ID</span>
                    <router-link
                        v-if="detailRoute"
                        :to="detailRoute"
                        class="font-mono text-sm text-blue-600 hover:text-blue-800 hover:underline truncate"
                        target="_blank"
                    >
                        {{ payload?.wiki_id }}
                    </router-link>
                    <span v-else class="font-mono text-sm text-gray-900 break-all">{{ payload?.wiki_id || '—' }}</span>
                </div>
                <div class="flex flex-col gap-0.5 min-w-0">
                    <span class="text-xs text-gray-500">操作类型</span>
                    <span class="font-medium text-gray-900">
                        {{ operationLabel }}
                        <span v-if="payload?.operation" class="ml-1 font-mono text-xs text-gray-500">({{ payload.operation }})</span>
                    </span>
                </div>
                <div v-if="payload?.expected_revision != null" class="flex flex-col gap-0.5 min-w-0">
                    <span class="text-xs text-gray-500">期望修订版本</span>
                    <span class="font-mono text-gray-900">{{ payload.expected_revision }}</span>
                </div>
            </div>
        </div>

        <div v-if="payload?.change_summary" class="rounded-lg border border-gray-200 bg-white p-4">
            <p class="text-xs font-medium text-gray-700 mb-1">变更摘要</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload.change_summary }}</p>
        </div>

        <div v-if="payload?.reason" class="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3">
            <p class="text-xs font-medium text-blue-800 mb-1">操作说明</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload.reason }}</p>
        </div>

        <div v-if="paramRows.length" class="space-y-3">
            <p class="text-sm font-medium text-gray-900">变更参数</p>
            <div
                v-for="(row, index) in paramRows"
                :key="`${row.label}-${index}`"
                class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
                <p class="text-xs font-medium text-gray-700 mb-2">{{ row.label }}</p>

                <div v-if="row.kind === 'tags'" class="flex flex-wrap gap-1.5">
                    <el-tag
                        v-for="tag in row.tags"
                        :key="tag"
                        size="small"
                        type="info"
                        effect="plain"
                    >
                        {{ tag }}
                    </el-tag>
                </div>

                <ul v-else-if="row.kind === 'items'" class="space-y-2 text-sm text-gray-800">
                    <li
                        v-for="(item, itemIndex) in row.items"
                        :key="itemIndex"
                        class="rounded border border-gray-100 bg-gray-50/80 px-3 py-2"
                    >
                        <p class="wrap-break-word">{{ item.primary }}</p>
                        <p v-if="item.secondary" class="mt-1 text-xs text-blue-600 break-all">{{ item.secondary }}</p>
                    </li>
                </ul>

                <pre
                    v-else-if="row.kind === 'pre'"
                    class="max-h-48 overflow-auto rounded bg-gray-50 p-2 text-xs text-gray-800 ring-1 ring-gray-100 whitespace-pre-wrap"
                >{{ row.text }}</pre>

                <p v-else class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ row.text }}</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import {
    buildWikiEditParamRows,
    getWikiDetailRoute,
    getWikiEditOperationLabel,
} from '@/utils/agentApproval'

const props = defineProps({
    payload: {
        type: Object,
        default: null,
    },
})

const detailRoute = computed(() => getWikiDetailRoute(props.payload?.wiki_id))

const operationLabel = computed(() => getWikiEditOperationLabel(props.payload?.operation))

const paramRows = computed(() =>
    buildWikiEditParamRows(props.payload?.operation, props.payload?.params)
)
</script>
