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
            class="flex-1 min-h-0 overflow-y-auto px-3 pb-3"
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
            <div v-else class="space-y-2 pt-2">
                <div
                    v-for="ev in timelineItems"
                    :key="ev.id"
                    class="rounded-lg border border-gray-100 bg-gray-50/80 p-2.5 min-w-0"
                >
                    <AgentSseTimelineItem :item="ev" />
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import AgentSseTimelineItem from '@/components/agent/AgentSseTimelineItem.vue'

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
    eventsScrollEl: {
        type: Object,
        default: null,
    },
    onEventsScroll: {
        type: Function,
        default: undefined,
    },
})

const scrollEl = ref(null)

watch(
    scrollEl,
    (el) => {
        if (props.eventsScrollEl && el) {
            props.eventsScrollEl.value = el
        }
    },
    { immediate: true }
)

function onScroll() {
    props.onEventsScroll?.()
}
</script>
