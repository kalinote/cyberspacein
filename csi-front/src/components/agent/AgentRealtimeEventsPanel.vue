<template>
    <div class="agent-events-panel flex flex-col min-h-0 flex-1 min-w-0" :class="{ 'agent-events-panel--mobile': isMobile }">
        <div
            v-if="showHeader"
            class="shrink-0 flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100"
        >
            <h3 class="text-lg font-bold text-gray-900 flex items-center min-w-0">
                <Icon icon="mdi:timeline-text" class="text-blue-600 mr-2 shrink-0" />
                <span v-if="isMobile" class="truncate">分析会话</span>
                <span v-else class="truncate">实时<span class="text-blue-500">事件</span></span>
            </h3>
            <slot name="header-extra" />
        </div>
        <div
            ref="scrollEl"
            class="flex-1 min-h-0 overflow-y-auto px-4 pb-5"
            :class="scrollClass"
            @scroll="onScroll"
        >
            <div
                v-if="!timelineItems.length"
                class="flex flex-col items-center justify-center h-full min-h-32 text-gray-400 py-8"
            >
                <Icon icon="mdi:access-point" class="text-2xl text-blue-500 mb-2" />
                <p class="text-sm font-medium text-gray-500 text-center">{{ emptyText }}</p>
            </div>
            <div v-else class="mx-auto w-full max-w-3xl pt-3">
                <div v-if="hasMoreHistory" class="text-center py-1">
                    <button
                        type="button"
                        class="text-xs text-blue-500 hover:text-blue-600 disabled:text-gray-400 disabled:cursor-wait"
                        :disabled="historyLoading"
                        :aria-busy="historyLoading"
                        title="点击加载更早事件，也可向上滚动加载"
                        @click="emit('load-older')"
                    >
                        {{ historyLoading ? '正在加载更早事件...' : '加载更早事件' }}
                    </button>
                </div>
                <AgentSseTimelineItem v-if="runDetails" :item="runDetails" class="mb-6" />
                <div class="space-y-6 min-w-0">
                    <template v-for="ev in visibleItems" :key="ev.displayKey || ev.id">
                        <details v-if="ev.kind === 'process_group'" class="agent-process-group">
                            <summary><Icon icon="mdi:progress-wrench" /> 过程记录 · {{ ev.items.length }} 项 <span>展开</span></summary>
                            <div class="space-y-5 pt-4"><AgentSseTimelineItem v-for="entry in ev.items" :key="entry.displayKey || entry.id" :item="entry" /></div>
                        </details>
                        <div v-else>
                            <p v-if="isMobile && ev.kind === 'tool_activity' && (ev.error || (ev.toolEvents || []).some(event => event.status === 'error' || event.error))" class="mb-2 text-xs text-red-700">工具执行出现错误，展开记录可查看详情。</p>
                            <AgentSseTimelineItem :item="ev" />
                        </div>
                    </template>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import AgentSseTimelineItem from '@/components/agent/AgentSseTimelineItem.vue'
import { buildAgentTimelineDisplay } from '@/utils/agentTimelineDisplay'
import { groupMobileTimeline } from './mobileTimeline'
import { useMobileViewport } from '@/composables/useMobileViewport'

const props = defineProps({
    timelineItems: {
        type: Array,
        default: () => [],
    },
    emptyText: {
        type: String,
        default: '等待事件推送',
    },
    showHeader: {
        type: Boolean,
        default: true,
    },
    scrollClass: {
        type: String,
        default: '',
    },
    historyLoading: {
        type: Boolean,
        default: false,
    },
    hasMoreHistory: {
        type: Boolean,
        default: false,
    },
    registerEventsScrollEl: {
        type: Function,
        default: undefined,
    },
    onEventsScroll: {
        type: Function,
        default: undefined,
    },
})

const emit = defineEmits(['load-older'])
const scrollEl = ref(null)
const displayTimeline = computed(() => buildAgentTimelineDisplay(props.timelineItems))
const activityItems = computed(() => displayTimeline.value.activityItems)
const runDetails = computed(() => displayTimeline.value.runDetails)
const { isMobile } = useMobileViewport()
const visibleItems = computed(() => isMobile.value ? groupMobileTimeline(activityItems.value) : activityItems.value)

watch(
    scrollEl,
    (el) => {
        props.registerEventsScrollEl?.(el ?? null)
    },
    { immediate: true }
)

onUnmounted(() => {
    props.registerEventsScrollEl?.(null)
})

function onScroll() {
    props.onEventsScroll?.()
}
</script>

<style scoped>
.agent-process-group { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.agent-process-group summary { display: flex; align-items: center; gap: 6px; min-height: 40px; color: #64748b; font-size: 13px; cursor: pointer; }
.agent-process-group summary > span { margin-left: auto; color: #2563eb; }
.agent-process-group[open] summary > span { display: none; }
.agent-events-panel--mobile :deep(article > button) { min-height: 44px; }
.agent-events-panel--mobile :deep(pre) { overflow-wrap: anywhere; }
.agent-events-panel--mobile :deep(table) { display: block; max-width: 100%; overflow-x: auto; }
</style>
