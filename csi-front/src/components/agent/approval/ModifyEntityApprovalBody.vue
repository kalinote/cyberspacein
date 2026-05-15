<template>
    <div class="space-y-4">
        <div class="rounded-lg border border-gray-200 bg-gray-50/80 p-4">
            <p class="text-xs font-medium text-gray-700 mb-3">目标实体</p>
            <div class="grid gap-2 text-sm sm:grid-cols-2">
                <div class="flex flex-col gap-0.5 min-w-0">
                    <span class="text-xs text-gray-500">类型</span>
                    <span class="font-medium text-gray-900">
                        {{ entityTypeLabel }}
                        <span v-if="payload?.entity_type" class="ml-1 font-mono text-xs text-gray-500">({{ payload.entity_type }})</span>
                    </span>
                </div>
                <div class="flex flex-col gap-0.5 min-w-0">
                    <span class="text-xs text-gray-500">UUID</span>
                    <router-link
                        v-if="detailRoute"
                        :to="detailRoute"
                        class="font-mono text-sm text-blue-600 hover:text-blue-800 hover:underline truncate"
                        target="_blank"
                    >
                        {{ payload?.entity_uuid }}
                    </router-link>
                    <span v-else class="font-mono text-sm text-gray-900 break-all">{{ payload?.entity_uuid || '—' }}</span>
                </div>
            </div>
        </div>

        <div v-if="payload?.reason" class="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3">
            <p class="text-xs font-medium text-blue-800 mb-1">修改说明</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload.reason }}</p>
        </div>

        <div v-if="modifications.length" class="space-y-3">
            <p class="text-sm font-medium text-gray-900">修改项（{{ modifications.length }}）</p>
            <div
                v-for="(mod, index) in modifications"
                :key="`${mod.field}-${index}`"
                class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
                <div class="flex flex-wrap items-center gap-2 mb-3">
                    <span class="text-sm font-medium text-gray-900">{{ getModificationFieldLabel(mod.field) }}</span>
                    <span class="font-mono text-xs text-gray-400">{{ mod.field }}</span>
                    <el-tag size="small" :type="actionTagType(mod.action)" effect="light">
                        {{ getActionLabel(mod.action) }}
                    </el-tag>
                </div>

                <div v-if="displays[index]?.kind === 'tags'" class="flex flex-wrap gap-1.5">
                    <el-tag
                        v-for="tag in displays[index].tags"
                        :key="tag"
                        size="small"
                        type="info"
                        effect="plain"
                    >
                        {{ tag }}
                    </el-tag>
                </div>

                <div v-else-if="displays[index]?.kind === 'entityGroups'">
                    <el-collapse class="border-0">
                        <el-collapse-item
                            v-for="group in displays[index].entityGroups"
                            :key="group.key"
                            :title="`${group.label}（${group.items.length}）`"
                            :name="group.key"
                        >
                            <div class="flex flex-wrap gap-1.5">
                                <el-tag
                                    v-for="item in group.items"
                                    :key="item"
                                    size="small"
                                    effect="plain"
                                >
                                    {{ item }}
                                </el-tag>
                            </div>
                        </el-collapse-item>
                    </el-collapse>
                </div>

                <div v-else-if="displays[index]?.kind === 'primitive'">
                    <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ displays[index].primitive }}</p>
                </div>

                <pre
                    v-else-if="displays[index]"
                    class="max-h-48 overflow-auto rounded bg-gray-50 p-2 text-xs text-gray-800 ring-1 ring-gray-100 whitespace-pre-wrap"
                >{{ displays[index].json }}</pre>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import {
    getActionLabel,
    getEntityDetailRoute,
    getEntityTypeLabel,
    getModificationFieldLabel,
    parseModificationValue,
} from '@/utils/agentApproval'

const props = defineProps({
    payload: {
        type: Object,
        default: null,
    },
})

const entityTypeLabel = computed(() => getEntityTypeLabel(props.payload?.entity_type))
const detailRoute = computed(() =>
    getEntityDetailRoute(props.payload?.entity_type, props.payload?.entity_uuid)
)
const modifications = computed(() => {
    const list = props.payload?.modifications
    return Array.isArray(list) ? list : []
})
const displays = computed(() => modifications.value.map(parseModificationValue))

const ACTION_TAG_TYPES = { set: 'primary', append: 'success', remove: 'danger' }

function actionTagType(action) {
    return ACTION_TAG_TYPES[action != null ? String(action) : ''] || 'info'
}
</script>

