<template>
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-xl font-bold text-gray-900 flex items-center">
                <Icon icon="mdi:timeline-clock" class="text-blue-600 mr-2" />
                实体变更<span class="text-blue-500">溯源</span>
            </h3>
            <span v-if="total > 0" class="text-sm text-gray-500">
                共 {{ total }} 条记录
            </span>
        </div>

        <div v-if="initialLoading" class="flex items-center justify-center py-12">
            <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin" />
        </div>

        <div v-else-if="error" class="text-center py-12">
            <Icon icon="mdi:alert-circle" class="text-red-500 text-4xl mb-2" />
            <p class="text-gray-600">{{ error }}</p>
        </div>

        <div v-else-if="timelineItems.length === 0" class="text-center py-12">
            <Icon icon="mdi:timeline-alert" class="text-gray-400 text-4xl mb-2" />
            <p class="text-gray-500">暂无历史记录</p>
        </div>

        <div v-else class="relative">
            <div class="flex items-center gap-3">
                <button
                    v-if="timelineItems.length > 0"
                    @click="scrollByDistance(-600)"
                    class="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center transition-colors bg-blue-50 text-blue-600 hover:bg-blue-100"
                >
                    <Icon icon="mdi:chevron-left" class="text-2xl" />
                </button>

                <div 
                    ref="scrollContainer"
                    class="flex-1 overflow-x-auto scroll-smooth timeline-scroll"
                    @scroll="handleScroll"
                >
                    <div ref="timelineContent" class="relative inline-flex pb-2" style="min-width: 100%;">
                        <svg
                            class="absolute inset-0 pointer-events-none z-0"
                            :width="svgWidth"
                            :height="svgHeight"
                        >
                            <defs>
                                <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="0%">
                                    <stop offset="0%" stop-color="#93c5fd" />
                                    <stop offset="50%" stop-color="#3b82f6" />
                                    <stop offset="100%" stop-color="#93c5fd" />
                                </linearGradient>
                            </defs>
                            <path
                                v-if="linePath"
                                :d="linePath"
                                fill="none"
                                :stroke="`url(#${gradientId})`"
                                stroke-width="3"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                        </svg>

                        <div class="flex gap-6 relative z-10">
                            <div
                                v-for="(item, index) in timelineItems"
                                :key="item.uuid"
                                class="relative flex flex-col items-center"
                                style="min-width: 280px; max-width: 280px;"
                            >
                                <div
                                    @click="handleCardClick(item)"
                                    class="p-4 rounded-lg border-2 transition-all mb-4"
                                    :class="getCardClass(item)"
                                    style="width: 280px;"
                                >
                                    <div class="flex items-start justify-between mb-2">
                                        <h4 class="text-sm font-bold text-gray-900 line-clamp-2 flex-1">
                                            {{ item.title || '无标题' }}
                                        </h4>
                                        <Icon
                                            v-if="item.is_highlighted"
                                            icon="mdi:star"
                                            class="text-red-500 text-lg shrink-0 ml-2"
                                        />
                                        <Icon
                                            v-else-if="item.uuid === currentUuid"
                                            icon="mdi:check-circle"
                                            class="text-green-500 text-lg shrink-0 ml-2"
                                        />
                                    </div>

                                    <p class="text-sm text-gray-700 line-clamp-3">
                                        {{ getContentPreview(item.clean_content) }}
                                    </p>

                                    <div v-if="item.uuid === currentUuid" class="mt-3 text-xs text-green-600 font-medium">
                                        当前页面
                                    </div>
                                    <div v-else-if="item.is_highlighted && item.highlight_reason" class="mt-3 text-xs text-red-600 font-medium">
                                        {{ item.highlight_reason }}
                                    </div>
                                </div>

                                <div class="relative flex flex-col items-center">
                                    <div 
                                        :ref="el => setDotRef(index, el)"
                                        class="w-4 h-4 rounded-full border-4"
                                        :class="getTimeNodeClass(item)"
                                    ></div>
                                    <div class="w-0.5 h-6 bg-blue-300"></div>
                                    <div 
                                        class="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap"
                                        :class="getTimeLabelClass(item)"
                                    >
                                        {{ formatDateTime(item.crawled_at) }}
                                    </div>
                                </div>
                            </div>

                            <div
                                v-if="loadingMore"
                                class="relative flex flex-col items-center"
                                style="min-width: 280px; max-width: 280px;"
                            >
                                <div class="p-4 rounded-lg border-2 border-gray-200 bg-gray-50 flex items-center justify-center mb-4" style="width: 280px; height: 120px;">
                                    <Icon icon="mdi:loading" class="text-3xl text-blue-500 animate-spin" />
                                </div>
                                <div 
                                    :ref="el => setDotRef(timelineItems.length, el)"
                                    class="w-4 h-4 rounded-full bg-gray-300 border-4 border-white"
                                ></div>
                                <div class="w-0.5 h-6 bg-blue-300"></div>
                                <div class="px-3 py-1.5 rounded-full text-xs font-medium text-gray-500 bg-gray-100">
                                    加载中...
                                </div>
                            </div>

                            <div
                                v-else-if="hasMore"
                                class="relative flex flex-col items-center"
                                style="min-width: 280px; max-width: 280px;"
                            >
                                <div class="p-4 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 flex items-center justify-center text-gray-400 mb-4" style="width: 280px; height: 120px;">
                                    <div class="text-center">
                                        <Icon icon="mdi:arrow-right" class="text-2xl mb-1" />
                                        <p class="text-xs">向右滚动加载更多</p>
                                    </div>
                                </div>
                                <div 
                                    :ref="el => setDotRef(timelineItems.length, el)"
                                    class="w-4 h-4 rounded-full bg-gray-200 border-4 border-white"
                                ></div>
                                <div class="w-0.5 h-6 bg-blue-300"></div>
                                <div class="px-3 py-1.5 rounded-full text-xs font-medium text-gray-400 bg-gray-100">
                                    更多记录
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <button
                    v-if="timelineItems.length > 0"
                    @click="scrollByDistance(600)"
                    class="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center transition-colors bg-blue-50 text-blue-600 hover:bg-blue-100"
                >
                    <Icon icon="mdi:chevron-right" class="text-2xl" />
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, onMounted, computed, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { timelineApi } from '@/api/timeline'
import { formatDateTime } from '@/utils/action'

const props = defineProps({
    entityType: {
        type: String,
        required: true
    },
    sourceId: {
        type: [String, Number],
        required: true
    },
    currentUuid: {
        type: String,
        required: true
    }
})

const router = useRouter()

const scrollContainer = ref(null)
const timelineContent = ref(null)
const initialLoading = ref(false)
const loadingMore = ref(false)
const error = ref(null)
const timelineItems = ref([])
const currentPage = ref(1)
const pageSize = ref(5)
const total = ref(0)
const hasMore = computed(() => timelineItems.value.length < total.value)

const linePath = ref('')
const svgWidth = ref(0)
const svgHeight = ref(0)
const dotElements = ref({})
const gradientId = ref(`timeline-gradient-${Math.random().toString(36).substr(2, 9)}`)

let scrollTimeout = null
let resizeObserver = null

const setDotRef = (index, el) => {
    if (el) {
        dotElements.value[index] = el
    } else {
        delete dotElements.value[index]
    }
}

const updateLinePath = () => {
    const container = timelineContent.value
    if (!container) return

    const containerRect = container.getBoundingClientRect()
    svgWidth.value = container.scrollWidth
    svgHeight.value = container.scrollHeight

    const indices = Object.keys(dotElements.value).map(Number).sort((a, b) => a - b)
    const points = []

    for (const idx of indices) {
        const dot = dotElements.value[idx]
        if (!dot) continue
        const dotRect = dot.getBoundingClientRect()
        points.push({
            x: dotRect.left + dotRect.width / 2 - containerRect.left,
            y: dotRect.top + dotRect.height / 2 - containerRect.top
        })
    }

    if (points.length < 2) {
        linePath.value = ''
        return
    }

    let d = `M ${points[0].x},${points[0].y}`
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1]
        const curr = points[i]
        const cpx = (prev.x + curr.x) / 2
        d += ` C ${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`
    }

    linePath.value = d
}

const scheduleLineUpdate = () => {
    nextTick(() => {
        requestAnimationFrame(updateLinePath)
    })
}

const loadTimeline = async (append = false) => {
    if (append) {
        loadingMore.value = true
    } else {
        initialLoading.value = true
    }
    error.value = null

    try {
        const response = await timelineApi.getTimeline(
            props.entityType,
            props.sourceId,
            {
                page: currentPage.value,
                page_size: pageSize.value
            }
        )

        if (response.code === 0 && response.data) {
            const newItems = response.data.items || []
            if (append) {
                timelineItems.value = [...timelineItems.value, ...newItems]
            } else {
                timelineItems.value = newItems
            }
            total.value = response.data.total || 0
        } else {
            error.value = response.message || '加载时间线失败'
        }
    } catch (err) {
        console.error('加载时间线失败:', err)
        error.value = '加载时间线失败，请稍后重试'
    } finally {
        initialLoading.value = false
        loadingMore.value = false
        scheduleLineUpdate()
    }
}

const handleScroll = () => {
    if (!scrollContainer.value || loadingMore.value || !hasMore.value) return

    if (scrollTimeout) {
        clearTimeout(scrollTimeout)
    }

    scrollTimeout = setTimeout(() => {
        const container = scrollContainer.value
        const sl = container.scrollLeft
        const sw = container.scrollWidth
        const cw = container.clientWidth

        if (sl + cw >= sw - 100) {
            currentPage.value++
            loadTimeline(true)
        }
    }, 150)
}

const scrollByDistance = (distance) => {
    scrollContainer.value?.scrollBy({ left: distance, behavior: 'smooth' })
}

const getCardClass = (item) => {
    if (item.uuid === props.currentUuid) {
        return 'border-green-500 bg-green-50 cursor-not-allowed shadow-md'
    }
    if (item.is_highlighted) {
        return 'border-red-500 bg-white hover:bg-red-50 hover:shadow-lg cursor-pointer'
    }
    return 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50 hover:shadow-lg cursor-pointer'
}

const getTimeNodeClass = (item) => {
    if (item.uuid === props.currentUuid) {
        return 'bg-green-500 border-green-200'
    }
    if (item.is_highlighted) {
        return 'bg-red-500 border-red-200'
    }
    return 'bg-blue-500 border-blue-200'
}

const getTimeLabelClass = (item) => {
    if (item.uuid === props.currentUuid) {
        return 'bg-green-100 text-green-700'
    }
    if (item.is_highlighted) {
        return 'bg-red-100 text-red-700'
    }
    return 'bg-blue-100 text-blue-700'
}

const getContentPreview = (content) => {
    if (!content) return '暂无内容'
    const cleanContent = content.replace(/\s+/g, ' ').trim()
    return cleanContent.length > 80 ? cleanContent.substring(0, 80) + '...' : cleanContent
}

const handleCardClick = (item) => {
    if (item.uuid === props.currentUuid) return

    const routeMap = {
        'forum': `/details/forum/${item.uuid}`,
        'article': `/details/article/${item.uuid}`
    }

    const targetRoute = routeMap[item.entity_type] || `/details/${item.entity_type}/${item.uuid}`
    router.push(targetRoute)
}

watch([() => props.entityType, () => props.sourceId], () => {
    currentPage.value = 1
    timelineItems.value = []
    dotElements.value = {}
    loadTimeline()
})

onMounted(() => {
    loadTimeline()

    resizeObserver = new ResizeObserver(() => {
        scheduleLineUpdate()
    })
    if (timelineContent.value) {
        resizeObserver.observe(timelineContent.value)
    }
})

onUnmounted(() => {
    if (scrollTimeout) {
        clearTimeout(scrollTimeout)
    }
    if (resizeObserver) {
        resizeObserver.disconnect()
    }
})
</script>

<style scoped>
.line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.scroll-smooth {
    scroll-behavior: smooth;
}

.timeline-scroll {
    scrollbar-width: thin;
    padding-bottom: 8px;
}

.timeline-scroll::-webkit-scrollbar {
    height: 8px;
}

.timeline-scroll::-webkit-scrollbar-track {
    background: #f1f5f9;
    border-radius: 4px;
}

.timeline-scroll::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}

.timeline-scroll::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}
</style>
