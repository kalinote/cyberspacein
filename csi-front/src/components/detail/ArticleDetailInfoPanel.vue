<template>
    <div class="flex-1 min-h-0 h-full overflow-y-auto p-4 space-y-5">
        <section>
            <h3 class="text-lg font-bold text-gray-900 mb-4">
                快速<span class="text-blue-500">操作</span>
            </h3>
            <div class="space-y-3">
                <SplitButton
                    :main-button-text="'分析此实体'"
                    :loading-text="'分析实体中...'"
                    :disabled="analyzing"
                    :loading="analyzing"
                    :options="analyzeOptions"
                    main-button-icon="mdi:brain"
                    @main-click="emit('analyze-main')"
                    @option-click="emit('analyze-option', $event)"
                />
                <button
                    type="button"
                    class="w-full border-2 border-blue-200 text-blue-600 py-2.5 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center gap-2 text-sm"
                    @click="emit('export')"
                >
                    <Icon icon="mdi:download" />
                    <span>媒体文件本地化</span>
                </button>
                <button
                    type="button"
                    :class="[
                        'w-full py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 text-sm',
                        isPriorityTarget
                            ? 'bg-amber-500 hover:bg-amber-600 text-white border-2 border-amber-500'
                            : 'border-2 border-gray-200 text-gray-600 hover:bg-gray-50',
                    ]"
                    @click="emit('toggle-priority')"
                >
                    <Icon :icon="isPriorityTarget ? 'mdi:star' : 'mdi:star-outline'" />
                    <span>{{ isPriorityTarget ? '取消重点目标' : '设置重点目标' }}</span>
                </button>
            </div>
        </section>

        <section
            v-if="keywords && keywords.length > 0"
            class="pt-4 border-t border-gray-100"
        >
            <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
                关键词<span class="text-blue-500">提取</span>
            </h3>
            <div class="flex flex-wrap gap-2">
                <el-tag
                    v-for="keyword in keywords"
                    :key="keyword"
                    :type="selectedKeywords.includes(keyword) ? 'success' : 'primary'"
                    size="default"
                    class="cursor-pointer"
                    :style="
                        selectedKeywords.includes(keyword) && keywordColors[keyword]
                            ? {
                                  borderColor: keywordColors[keyword],
                                  backgroundColor: keywordColors[keyword] + '22',
                              }
                            : undefined
                    "
                    :ref="(el) => setKeywordRef(keyword, el)"
                    @click="emit('toggle-keyword', keyword)"
                >
                    {{ keyword }}
                </el-tag>
            </div>
        </section>

        <section
            v-if="hasEntities(entities)"
            class="pt-4 border-t border-gray-100"
        >
            <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
                提及<span class="text-blue-500">实体</span>
            </h3>
            <EntityMentionPanel
                embedded
                :entities="entities"
                :selected-keys="selectedEntityKeys"
                :colors="entityColors"
                :set-ref="setEntityRef"
                @toggle="emit('toggle-entity', $event)"
            />
        </section>
    </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import SplitButton from '@/components/SplitButton.vue'
import EntityMentionPanel from '@/components/entity/EntityMentionPanel.vue'
import { hasEntities } from '@/utils/entityDisplay'

defineProps({
    keywords: {
        type: Array,
        default: () => [],
    },
    entities: {
        type: Object,
        default: null,
    },
    analyzeOptions: {
        type: Array,
        default: () => [],
    },
    analyzing: {
        type: Boolean,
        default: false,
    },
    isPriorityTarget: {
        type: Boolean,
        default: false,
    },
    selectedKeywords: {
        type: Array,
        default: () => [],
    },
    keywordColors: {
        type: Object,
        default: () => ({}),
    },
    selectedEntityKeys: {
        type: Array,
        default: () => [],
    },
    entityColors: {
        type: Object,
        default: () => ({}),
    },
    setKeywordRef: {
        type: Function,
        default: () => {},
    },
    setEntityRef: {
        type: Function,
        default: () => {},
    },
})

const emit = defineEmits([
    'analyze-main',
    'analyze-option',
    'export',
    'toggle-priority',
    'toggle-keyword',
    'toggle-entity',
])
</script>
