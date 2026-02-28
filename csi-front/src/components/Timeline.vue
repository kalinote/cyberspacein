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
                                    @contextmenu.prevent="onCardContextMenu($event, item)"
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

        <div
            v-show="contextMenu.visible"
            class="context-menu-floating rounded-lg shadow-lg border border-gray-200 bg-white py-1 min-w-[120px]"
            :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        >
            <button
                v-for="entry in contextMenuItems"
                :key="entry.key"
                type="button"
                class="w-full px-4 py-2 text-left text-sm transition-colors flex items-center gap-2"
                :class="isContextMenuEntryDisabled(entry) ? 'text-gray-400 cursor-not-allowed' : 'text-gray-700 hover:bg-gray-50 cursor-pointer'"
                :disabled="isContextMenuEntryDisabled(entry)"
                @click.stop="onContextMenuAction(entry.key)"
            >
                <Icon v-if="entry.icon" :icon="entry.icon" class="shrink-0 text-base" :class="isContextMenuEntryDisabled(entry) ? 'text-gray-400' : 'text-gray-500'" />
                {{ entry.label }}
            </button>
        </div>

        <el-dialog
            v-model="diffDialog.visible"
            title="溯源对比"
            width="calc(100vw - 64px)"
            top="32px"
            :destroy-on-close="true"
            class="diff-dialog"
        >
            <div v-if="diffDialog.loading" class="flex justify-center py-20">
                <Icon icon="mdi:loading" class="animate-spin text-4xl text-blue-500" />
            </div>
            <template v-else-if="diffDialog.visible">
                <div class="flex mb-3 text-sm text-gray-600 font-mono">
                    <div class="flex-1">UUID: {{ diffDialog.originalUuid }}</div>
                    <div class="flex-1 text-right">UUID: {{ diffDialog.modifiedUuid }}</div>
                </div>
                <MonacoDiffEditor
                    :original="diffDialog.original"
                    :modified="diffDialog.modified"
                    :min-height="diffEditorHeight"
                />
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, watch, onMounted, computed, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { timelineApi } from '@/api/timeline'
import { formatDateTime } from '@/utils/action'
import MonacoDiffEditor from '@/components/MonacoDiffEditor.vue'

const contextMenuItems = [
    { label: '溯源比对', key: 'trace-compare', icon: 'mdi:file-compare' }
]

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
    },
    currentRawContent: {
        type: String,
        default: ''
    },
    currentTitle: {
        type: String,
        default: ''
    },
    currentLastEditAt: {
        type: String,
        default: ''
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
const contextMenu = ref({ visible: false, x: 0, y: 0, item: null })
const diffDialog = ref({ visible: false, loading: false, original: '', modified: '', originalUuid: '', modifiedUuid: '' })
const diffEditorHeight = computed(() => Math.max(400, window.innerHeight - 160))

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

const closeContextMenu = () => {
    contextMenu.value.visible = false
}

const onCardContextMenu = (e, item) => {
    e.stopPropagation()
    contextMenu.value = { visible: true, x: e.clientX, y: e.clientY, item }
}

const isContextMenuEntryDisabled = (entry) => {
    if (entry.key === 'trace-compare') {
        return contextMenu.value.item?.uuid === props.currentUuid
    }
    return false
}

const wrapContent = (rawContent, title, lastEditAt) => {
    return [
        `<!-- 实体标题: ${title || 'null'} -->`,
        `<!-- 最后修改时间: ${lastEditAt || 'null'} -->`,
        '',
        '<!-- 原始源代码内容开始 -->',
        rawContent,
        '<!-- 原始源代码内容结束 -->'
    ].join('\n')
}

const onContextMenuAction = async (key) => {
    const item = contextMenu.value.item
    if (key === 'trace-compare' && item?.uuid === props.currentUuid) {
        closeContextMenu()
        return
    }
    closeContextMenu()
    if (key === 'trace-compare') {
        diffDialog.value = { visible: true, loading: true, original: '', modified: '', originalUuid: '', modifiedUuid: '' }
        try {
            const res = await timelineApi.getDiffCompare(props.entityType, item.uuid)
            if (res.code !== 0) {
                ElMessage.error(res.message || '获取对比数据失败')
                diffDialog.value.visible = false
                return
            }
            const targetRaw = res.data?.raw_content || ''
            const currentRaw = props.currentRawContent || ''
            const targetWrapped = wrapContent(targetRaw, res.data?.title, res.data?.last_edit_at)
            const currentWrapped = wrapContent(currentRaw, props.currentTitle, props.currentLastEditAt)

            if (!targetRaw || !currentRaw) {
                diffDialog.value.original = currentWrapped
                diffDialog.value.modified = targetWrapped
                diffDialog.value.originalUuid = props.currentUuid
                diffDialog.value.modifiedUuid = item.uuid
            } else {
                const currentItem = timelineItems.value.find(t => t.uuid === props.currentUuid)
                const currentTime = currentItem ? new Date(currentItem.crawled_at).getTime() : null
                const targetTime = res.data?.last_edit_at ? new Date(res.data.last_edit_at).getTime() : null

                if (currentTime && targetTime && targetTime < currentTime) {
                    diffDialog.value.original = targetWrapped
                    diffDialog.value.modified = currentWrapped
                    diffDialog.value.originalUuid = item.uuid
                    diffDialog.value.modifiedUuid = props.currentUuid
                } else {
                    diffDialog.value.original = currentWrapped
                    diffDialog.value.modified = targetWrapped
                    diffDialog.value.originalUuid = props.currentUuid
                    diffDialog.value.modifiedUuid = item.uuid
                }
            }
        } catch {
            ElMessage.error('获取对比数据失败')
            diffDialog.value.visible = false
            return
        } finally {
            diffDialog.value.loading = false
        }
    }
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
    document.addEventListener('click', closeContextMenu)
})

onUnmounted(() => {
    if (scrollTimeout) {
        clearTimeout(scrollTimeout)
    }
    if (resizeObserver) {
        resizeObserver.disconnect()
    }
    document.removeEventListener('click', closeContextMenu)
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

.context-menu-floating {
    position: fixed;
    z-index: 1000;
}
</style>
