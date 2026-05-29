<template>
    <div
        v-if="showSection"
        data-forum-comments-section
        class="w-full space-y-6"
    >
        <div
            v-if="featuredComments.length > 0"
            class="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
            v-loading="featuredLoading"
        >
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-2xl font-bold text-gray-900 flex items-center">
                    <Icon icon="mdi:star" class="text-blue-600 mr-2" />
                    贴文<span class="text-blue-500">点评</span>
                </h2>
                <span class="text-sm text-gray-500">共 {{ featuredTotal }} 条</span>
            </div>
            <div class="space-y-2">
                <router-link
                    v-for="item in featuredComments"
                    :key="item.uuid"
                    :to="`/details/forum/${item.uuid}`"
                    class="flex items-center gap-2 px-3 py-2 border border-gray-100 rounded hover:border-blue-200 hover:bg-blue-50 transition-all cursor-pointer"
                >
                    <Icon icon="mdi:account-circle" class="text-blue-600 text-base shrink-0" />
                    <span class="font-medium text-gray-900 shrink-0">{{ item.author_name || '匿名用户' }}:</span>
                    <span class="text-gray-700 flex-1 min-w-0 truncate">{{ item.clean_content || '暂无分析内容' }}</span>
                    <span class="text-sm text-gray-500 shrink-0 ml-auto">点评于 {{ formatDateTime(item.publish_at || item.update_at) }}</span>
                </router-link>
            </div>
            <div v-if="featuredTotal > pageSize" class="flex justify-center mt-6">
                <el-pagination
                    :current-page="featuredPage"
                    :page-size="pageSize"
                    :total="featuredTotal"
                    layout="prev, pager, next"
                    background
                    @update:current-page="emit('update:featuredPage', $event)"
                />
            </div>
        </div>

        <div
            v-if="commentList.length > 0"
            class="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
            v-loading="commentLoading"
        >
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-2xl font-bold text-gray-900 flex items-center">
                    <Icon icon="mdi:comment" class="text-blue-600 mr-2" />
                    <span class="text-blue-500">评论区</span>板块
                </h2>
                <span class="text-sm text-gray-500">共 {{ commentTotal }} 条</span>
            </div>
            <div class="space-y-4">
                <div
                    v-for="item in commentList"
                    :key="item.uuid"
                    class="relative flex gap-4 p-4 border border-gray-100 rounded-lg hover:border-blue-200 hover:shadow-sm transition-all"
                >
                    <div class="absolute top-4 right-4">
                        <span v-if="item.floor" class="text-sm text-gray-400">#{{ item.floor }}</span>
                    </div>
                    <div class="shrink-0">
                        <div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                            <Icon icon="mdi:account-circle" class="text-blue-600 text-3xl" />
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="font-medium text-gray-900">{{ item.author_name || '匿名用户' }}</span>
                            <span class="text-sm text-gray-500">{{ formatDateTime(item.publish_at || item.update_at) }}</span>
                        </div>
                        <p class="text-gray-700 mb-3 line-clamp-3">{{ item.clean_content || '暂无分析内容' }}</p>
                        <div class="flex flex-wrap items-center gap-2 mb-2">
                            <el-tag
                                v-if="item.confidence !== null && item.confidence !== undefined"
                                :type="getConfidenceInfo(item.confidence).type"
                                size="small"
                            >
                                {{ getConfidenceInfo(item.confidence).text }}
                            </el-tag>
                            <el-tag v-if="item.nsfw" type="danger" size="small">NSFW</el-tag>
                            <el-tag v-if="item.aigc" type="warning" size="small">AIGC</el-tag>
                        </div>
                        <div v-if="item.keywords && item.keywords.length > 0" class="flex flex-wrap gap-1">
                            <el-tag
                                v-for="keyword in item.keywords"
                                :key="keyword"
                                size="small"
                                type="info"
                                effect="plain"
                            >
                                {{ keyword }}
                            </el-tag>
                        </div>
                    </div>
                    <div class="absolute bottom-4 right-4">
                        <router-link
                            :to="`/details/forum/${item.uuid}`"
                            class="text-blue-600 hover:text-blue-800 flex items-center text-sm"
                        >
                            查看详情
                            <Icon icon="mdi:arrow-right" class="ml-1" />
                        </router-link>
                    </div>
                </div>
            </div>
            <div v-if="commentTotal > pageSize" class="flex justify-center mt-6">
                <el-pagination
                    :current-page="commentPage"
                    :page-size="pageSize"
                    :total="commentTotal"
                    layout="prev, pager, next"
                    background
                    @update:current-page="emit('update:commentPage', $event)"
                />
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { formatDateTime } from '@/utils/action'

const props = defineProps({
    featuredComments: {
        type: Array,
        default: () => [],
    },
    featuredTotal: {
        type: Number,
        default: 0,
    },
    featuredLoading: {
        type: Boolean,
        default: false,
    },
    featuredPage: {
        type: Number,
        default: 1,
    },
    commentList: {
        type: Array,
        default: () => [],
    },
    commentTotal: {
        type: Number,
        default: 0,
    },
    commentLoading: {
        type: Boolean,
        default: false,
    },
    commentPage: {
        type: Number,
        default: 1,
    },
    pageSize: {
        type: Number,
        default: 10,
    },
    getConfidenceInfo: {
        type: Function,
        required: true,
    },
})

const emit = defineEmits(['update:featuredPage', 'update:commentPage'])

const showSection = computed(
    () => props.featuredComments.length > 0 || props.commentList.length > 0,
)
</script>
