<template>
    <div class="flex flex-col min-h-0 flex-1 min-w-0">
        <div
            v-if="showHeader"
            class="shrink-0 flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100"
        >
            <h3 class="text-lg font-bold text-gray-900 flex items-center min-w-0">
                <Icon icon="mdi:timeline-text" class="text-blue-600 mr-2 shrink-0" />
                <span class="truncate">实时<span class="text-blue-500">事件</span></span>
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
                <div v-if="historyLoading" class="text-center text-xs text-gray-400 py-2">
                    加载更早事件...
                </div>
                <div
                    v-else-if="hasMoreHistory && timelineItems.length"
                    class="text-center text-xs text-gray-400 py-1"
                >
                    向上滚动加载更多
                </div>
                <AgentSseTimelineItem v-if="runDetails" :item="runDetails" class="mb-6" />
                <div class="space-y-6 min-w-0">
                    <AgentSseTimelineItem
                        v-for="ev in activityItems"
                        :key="ev.displayKey || ev.id"
                        :item="ev"
                    />
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

const scrollEl = ref(null)
const displayTimeline = computed(() => buildAgentTimelineDisplay(props.timelineItems))
const activityItems = computed(() => displayTimeline.value.activityItems)
const runDetails = computed(() => displayTimeline.value.runDetails)

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
