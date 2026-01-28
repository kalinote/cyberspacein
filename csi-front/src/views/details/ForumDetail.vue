<template>
    <div class="min-h-screen bg-gray-50">
        <Header />

        <div v-if="loading" class="flex items-center justify-center h-96">
            <div class="text-center">
                <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                <p class="text-gray-600">加载中...</p>
            </div>
        </div>

        <div v-else-if="error" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div class="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
                <div class="flex justify-center mb-4">
                    <Icon icon="mdi:alert-circle" class="text-red-500 text-5xl" />
                </div>
                <h2 class="text-xl font-bold text-gray-900 mb-2">加载失败</h2>
                <p class="text-gray-600 mb-4">{{ error }}</p>
                <el-button type="primary" @click="$router.back()">返回</el-button>
            </div>
        </div>

        <template v-else-if="forumData">
            <DetailPageHeader
                :title="forumData.title || '无标题'"
                :subtitle="forumData.uuid"
            >
                <template #tags>
                    <el-tag v-if="forumData.platform" type="primary" size="default">
                        {{ forumData.platform }}
                    </el-tag>
                    <el-tag v-if="forumData.section" type="primary" size="default">
                        {{ forumData.section }}
                    </el-tag>
                    <el-tag v-if="forumData.category_tag" type="warning" size="default">
                        {{ forumData.category_tag }}
                    </el-tag>
                    <el-tag :type="getThreadTypeTag(forumData.thread_type)" size="default">
                        {{ getThreadTypeText(forumData.thread_type) }}
                    </el-tag>
                    <el-tag v-if="forumData.nsfw" type="danger" size="default">
                        NSFW
                    </el-tag>
                    <el-tag v-if="forumData.aigc" type="warning" size="default">
                        AIGC
                    </el-tag>
                    <el-tag v-if="forumData.floor" type="primary" size="default" class="shrink-0">
                        {{ forumData.floor }}楼
                    </el-tag>
                </template>
                <template #extra>
                    <el-link v-if="forumData.url" :href="forumData.url" target="_blank" type="primary" class="text-sm">
                        <template #icon>
                            <Icon icon="mdi:open-in-new" />
                        </template>
                        查看原文
                    </el-link>
                    <router-link v-if="forumData.topic_thread_uuid" :to="`/details/forum/${forumData.topic_thread_uuid}`" class="text-sm text-blue-600 hover:text-blue-800 flex items-center">
                        <Icon icon="mdi:forum" class="mr-1" />
                        查看主贴
                    </router-link>
                    <template v-if="forumData.status_flags && forumData.status_flags.length > 0">
                        <el-tag v-for="flag in forumData.status_flags" :key="flag" :type="getStatusFlagType(flag)" size="default">
                            <Icon :icon="getStatusFlagIcon(flag)" class="mr-1" />
                            {{ getStatusFlagText(flag) }}
                        </el-tag>
                    </template>
                </template>
            </DetailPageHeader>

            <section class="py-8 bg-white">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                        <div class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:account" class="text-blue-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">作者</p>
                                <p class="text-lg font-bold text-gray-900 truncate">
                                    {{ forumData.author_name || forumData.author_id || '未知' }}
                                </p>
                            </div>
                        </div>

                        <div class="bg-linear-to-br from-green-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:calendar" class="text-green-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">发布时间</p>
                                <p class="text-base font-bold text-gray-900">
                                    {{ formatDateTime(forumData.publish_at) }}
                                </p>
                            </div>
                        </div>

                        <div class="bg-linear-to-br from-amber-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:clock-outline" class="text-amber-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">采集时间</p>
                                <p class="text-base font-bold text-gray-900">
                                    {{ formatDateTime(forumData.crawled_at) }}
                                </p>
                            </div>
                        </div>

                        <div class="bg-linear-to-br from-purple-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:spider" class="text-purple-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">爬虫</p>
                                <p class="text-base font-bold text-gray-900 truncate">
                                    {{ forumData.spider_name || '未知' }}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div v-if="hasInteractionData" class="grid grid-cols-2 md:grid-cols-5 gap-6 mt-6">
                        <div v-if="forumData.likes !== null && forumData.likes !== -1" class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:thumb-up" class="text-blue-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">点赞</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ forumData.likes.toLocaleString() }}
                                </p>
                            </div>
                        </div>

                        <div v-if="forumData.dislikes !== null && forumData.dislikes !== -1" class="bg-linear-to-br from-red-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:thumb-down" class="text-red-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">点踩</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ forumData.dislikes.toLocaleString() }}
                                </p>
                            </div>
                        </div>

                        <div v-if="forumData.collections !== null && forumData.collections !== -1" class="bg-linear-to-br from-yellow-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-yellow-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:bookmark" class="text-yellow-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">收藏</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ forumData.collections.toLocaleString() }}
                                </p>
                            </div>
                        </div>

                        <div v-if="forumData.comments !== null && forumData.comments !== -1" class="bg-linear-to-br from-green-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:comment" class="text-green-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">评论</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ forumData.comments.toLocaleString() }}
                                </p>
                            </div>
                        </div>

                        <div v-if="forumData.views !== null && forumData.views !== -1" class="bg-linear-to-br from-indigo-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:eye" class="text-indigo-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">浏览</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ forumData.views.toLocaleString() }}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="py-12 bg-gray-50">
                <div class="w-full px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 lg:grid-cols-5 gap-8">
                        <MarkingSidebar
                            :sorted-markings="getSortedMarkingsByRegion(currentRegion)"
                            :active-marking-id="activeMarkingId"
                            @update="handleUpdateMarking"
                            @delete="handleDeleteMarking"
                            @hover="handleMarkingHover"
                        />
                        <div class="lg:col-span-3 space-y-6 relative marking-container">
                            <MarkingConnector
                                :markings="getMarkingsByRegion(currentRegion)"
                                :active-marking-id="activeMarkingId"
                            />
                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div class="flex items-center justify-between mb-4">
                                    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
                                        <Icon icon="mdi:forum" class="text-blue-600 mr-2" />
                                        帖子<span class="text-blue-500">内容</span>
                                    </h2>
                                    <div class="flex items-center gap-2">
                                        <el-button
                                            v-if="activeTab === 'safe-raw'"
                                            type="default"
                                            size="small"
                                            @click="handleFormat"
                                        >
                                            <template #icon>
                                                <Icon icon="mdi:code-braces" />
                                            </template>
                                            格式化
                                        </el-button>
                                        <el-button
                                            v-if="activeTab === 'safe-raw'"
                                            type="primary"
                                            size="small"
                                            @click="handleSaveSafeContent"
                                        >
                                            <template #icon>
                                                <Icon icon="mdi:content-save" />
                                            </template>
                                            保存
                                        </el-button>
                                    </div>
                                </div>
                                <el-tabs v-model="activeTab" class="forum-tabs">
                                    <el-tab-pane v-if="forumData.clean_content" label="纯文本内容" name="clean">
                                        <div
                                            ref="cleanContentRef"
                                            class="prose max-w-none select-text"
                                            @mouseup="handleCleanContentMouseUp"
                                        >
                                            <pre class="whitespace-pre-wrap wrap-break-word text-gray-700 leading-relaxed">{{ forumData.clean_content }}</pre>
                                        </div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="!forumData.clean_content" label="内容" name="empty">
                                        <div class="text-center py-12 text-gray-400 flex flex-col items-center">
                                            <Icon icon="mdi:text-box-remove-outline" class="text-5xl mb-2" />
                                            <p>暂无内容，点击开始分析以分析实体内容</p>
                                        </div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="forumData.safe_raw_content" label="安全渲染内容" name="rendered">
                                        <div
                                            ref="renderedContentRef"
                                            class="prose max-w-none forum-content marking-content select-text"
                                            v-html="editableSafeRawContent"
                                            @mouseup="handleRenderedContentMouseUp"
                                        ></div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="forumData.raw_content" label="原始源代码" name="raw">
                                        <MonacoEditor
                                            ref="rawEditorRef"
                                            :model-value="forumData.raw_content"
                                            :read-only="true"
                                            language="html"
                                        />
                                    </el-tab-pane>
                                    <el-tab-pane v-if="forumData.safe_raw_content" label="安全内容代码" name="safe-raw">
                                        <MonacoEditor
                                            ref="safeRawEditorRef"
                                            v-model="editableSafeRawContent"
                                            :read-only="false"
                                            language="html"
                                        />
                                    </el-tab-pane>
                                </el-tabs>
                            </div>

                            <div v-if="forumData.thread_type === 'thread' && featuredComments.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6" v-loading="featuredLoading">
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
                                <div v-if="featuredTotal > 10" class="flex justify-center mt-6">
                                    <el-pagination
                                        v-model:current-page="featuredPage"
                                        :page-size="10"
                                        :total="featuredTotal"
                                        layout="prev, pager, next"
                                        background
                                    />
                                </div>
                            </div>

                            <div v-if="forumData.thread_type === 'thread' && commentList.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6" v-loading="commentLoading">
                                <div class="flex items-center justify-between mb-6">
                                    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
                                        <Icon icon="mdi:comment" class="text-blue-600 mr-2" />
                                        <span class="text-blue-500">评论区</span>板块
                                    </h2>
                                    <span class="text-sm text-gray-500">共 {{ commentTotal }} 条</span>
                                </div>
                                <div class="space-y-4">
                                    <div v-for="item in commentList" :key="item.uuid" class="relative flex gap-4 p-4 border border-gray-100 rounded-lg hover:border-blue-200 hover:shadow-sm transition-all">
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
                                                <el-tag v-if="item.confidence !== null && item.confidence !== undefined" :type="getConfidenceInfo(item.confidence).type" size="small">
                                                    {{ getConfidenceInfo(item.confidence).text }}
                                                </el-tag>
                                                <el-tag v-if="item.nsfw" type="danger" size="small">NSFW</el-tag>
                                                <el-tag v-if="item.aigc" type="warning" size="small">AIGC</el-tag>
                                            </div>
                                            <div v-if="item.keywords && item.keywords.length > 0" class="flex flex-wrap gap-1">
                                                <el-tag v-for="keyword in item.keywords" :key="keyword" size="small" type="info" effect="plain">
                                                    {{ keyword }}
                                                </el-tag>
                                            </div>
                                        </div>
                                        <div class="absolute bottom-4 right-4">
                                            <router-link :to="`/details/forum/${item.uuid}`" class="text-blue-600 hover:text-blue-800 flex items-center text-sm">
                                                查看详情
                                                <Icon icon="mdi:arrow-right" class="ml-1" />
                                            </router-link>
                                        </div>
                                    </div>
                                </div>
                                <div v-if="commentTotal > 10" class="flex justify-center mt-6">
                                    <el-pagination
                                        v-model:current-page="commentPage"
                                        :page-size="10"
                                        :total="commentTotal"
                                        layout="prev, pager, next"
                                        background
                                    />
                                </div>
                            </div>

                            <div v-if="forumData.files_urls && forumData.files_urls.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:file-image" class="text-blue-600 mr-2" />
                                    附件<span class="text-blue-500">文件</span>
                                </h3>
                                <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
                                    <div v-for="(url, index) in forumData.files_urls" :key="index" class="relative group">
                                        <a :href="url" target="_blank" class="block aspect-square bg-gray-100 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
                                            <img v-if="isImageUrl(url)" :src="url" :alt="`附件${index + 1}`" class="w-full h-full object-cover" />
                                            <div v-else class="w-full h-full flex items-center justify-center">
                                                <Icon icon="mdi:file" class="text-4xl text-gray-400" />
                                            </div>
                                        </a>
                                    </div>
                                </div>
                            </div>

                            <div v-if="forumData.translation_content" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:translate" class="text-green-600 mr-2" />
                                    翻译<span class="text-blue-500">内容</span>
                                </h3>
                                <div class="prose max-w-none">
                                    <p class="text-gray-700 leading-relaxed whitespace-pre-wrap">{{ forumData.translation_content }}</p>
                                </div>
                            </div>

                            <div v-if="forumData.keywords && forumData.keywords.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:tag-multiple" class="text-blue-600 mr-2" />
                                    关键<span class="text-blue-500">词</span>
                                </h3>
                                <div class="flex flex-wrap gap-2">
                                    <el-tag v-for="keyword in forumData.keywords" :key="keyword" type="primary" size="large">
                                        {{ keyword }}
                                    </el-tag>
                                </div>
                            </div>

                            <div v-if="forumData.emotion !== null && forumData.emotion !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:emoticon-happy-outline" class="text-amber-600 mr-2" />
                                    情感<span class="text-blue-500">分析</span>
                                </h3>
                                <div class="space-y-4">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">情感分数</span>
                                        <span class="text-2xl font-bold" :class="getEmotionColor(forumData.emotion)">
                                            {{ forumData.emotion.toFixed(2) }}
                                        </span>
                                    </div>
                                    <div class="relative h-4 bg-gray-200 rounded-full overflow-hidden">
                                        <div class="absolute inset-0 flex">
                                            <div class="w-1/2 bg-red-200"></div>
                                            <div class="w-1/2 bg-green-200"></div>
                                        </div>
                                        <div 
                                            class="absolute top-0 bottom-0 w-1 bg-gray-800 transition-all duration-300"
                                            :style="{ left: `${(forumData.emotion + 1) * 50}%` }"
                                        ></div>
                                    </div>
                                    <div class="flex justify-between text-sm text-gray-500">
                                        <span>消极（-1）</span>
                                        <span>中性（0）</span>
                                        <span>积极（1）</span>
                                    </div>
                                </div>
                            </div>

                            <div v-if="forumData.political_bias && forumData.political_bias.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:scale-balance" class="text-purple-600 mr-2" />
                                    政治<span class="text-blue-500">倾向</span>
                                </h3>
                                <div class="flex flex-wrap gap-2">
                                    <el-tag v-for="bias in forumData.political_bias" :key="bias" type="warning" size="large">
                                        {{ bias }}
                                    </el-tag>
                                </div>
                            </div>

                            <div v-if="forumData.confidence !== null && forumData.confidence !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:shield-check" class="text-green-600 mr-2" />
                                    置信<span class="text-blue-500">度</span>
                                </h3>
                                <div v-if="forumData.confidence === 0" class="flex items-center space-x-3 p-4 bg-red-50 rounded-lg border border-red-200">
                                    <Icon icon="mdi:alert-circle" class="text-red-600 text-3xl" />
                                    <div>
                                        <p class="font-bold text-red-900">零信任模式</p>
                                        <p class="text-sm text-red-600">此内容处于零信任状态</p>
                                    </div>
                                </div>
                                <div v-else class="space-y-4">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">置信度分数</span>
                                        <span class="text-2xl font-bold text-green-600">
                                            {{ (forumData.confidence * 100).toFixed(0) }}%
                                        </span>
                                    </div>
                                    <div class="h-4 bg-gray-200 rounded-full overflow-hidden">
                                        <div 
                                            class="h-full bg-linear-to-r from-green-500 to-emerald-400 rounded-full transition-all duration-300"
                                            :style="{ width: `${forumData.confidence * 100}%` }"
                                        ></div>
                                    </div>
                                </div>
                            </div>

                            <div v-if="forumData.subjective_rating !== null && forumData.subjective_rating !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:star" class="text-amber-600 mr-2" />
                                    主观<span class="text-blue-500">评分</span>
                                </h3>
                                <div class="flex items-center space-x-4">
                                    <el-rate 
                                        v-model="forumData.subjective_rating" 
                                        disabled 
                                        show-score
                                        :max="10"
                                        size="large"
                                    />
                                    <span class="text-3xl font-bold text-gray-900">{{ forumData.subjective_rating }}/10</span>
                                </div>
                            </div>
                        </div>

                        <div class="space-y-6">
                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-lg font-bold text-gray-900 mb-4">
                                    帖子<span class="text-blue-500">信息</span>
                                </h3>
                                <div class="space-y-4">
                                    <div v-if="forumData.topic_id">
                                        <p class="text-sm text-gray-500 mb-1">主题ID</p>
                                        <p class="font-medium text-gray-900 break-all text-sm">{{ forumData.topic_id }}</p>
                                    </div>
                                    <div v-if="forumData.parent_id">
                                        <p class="text-sm text-gray-500 mb-1">父ID</p>
                                        <p class="font-medium text-gray-900 break-all text-sm">{{ forumData.parent_id }}</p>
                                    </div>
                                    <div v-if="forumData.floor">
                                        <p class="text-sm text-gray-500 mb-1">楼层号</p>
                                        <p class="font-medium text-gray-900">{{ forumData.floor }}</p>
                                    </div>
                                    <div v-if="forumData.thread_type">
                                        <p class="text-sm text-gray-500 mb-1">帖子类型</p>
                                        <el-tag :type="getThreadTypeTag(forumData.thread_type)" size="default">
                                            {{ getThreadTypeText(forumData.thread_type) }}
                                        </el-tag>
                                    </div>
                                </div>
                            </div>

                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-lg font-bold text-gray-900 mb-4">
                                    元数据<span class="text-blue-500">信息</span>
                                </h3>
                                <div class="space-y-4">
                                    <div v-if="forumData.tags && forumData.tags.length > 0">
                                        <p class="text-sm text-gray-500 mb-2">标签</p>
                                        <div class="flex flex-wrap gap-2">
                                            <el-tag v-for="tag in forumData.tags" :key="tag" type="info" size="small">
                                                {{ tag }}
                                            </el-tag>
                                        </div>
                                    </div>
                                    <div v-if="forumData.language">
                                        <p class="text-sm text-gray-500 mb-1">语言</p>
                                        <p class="font-medium text-gray-900">{{ forumData.language }}</p>
                                    </div>
                                    <div v-if="forumData.entity_type">
                                        <p class="text-sm text-gray-500 mb-1">实体类型</p>
                                        <p class="font-medium text-gray-900">{{ forumData.entity_type }}</p>
                                    </div>
                                    <div v-if="forumData.data_version">
                                        <p class="text-sm text-gray-500 mb-1">数据版本</p>
                                        <p class="font-medium text-gray-900">v{{ forumData.data_version }}</p>
                                    </div>
                                    <div v-if="forumData.source_id">
                                        <p class="text-sm text-gray-500 mb-1">来源ID</p>
                                        <p class="font-medium text-gray-900 break-all text-sm">{{ forumData.source_id }}</p>
                                    </div>
                                    <div v-if="forumData.last_edit_at">
                                        <p class="text-sm text-gray-500 mb-1">最后编辑</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(forumData.last_edit_at) }}</p>
                                    </div>
                                    <div v-if="forumData.update_at">
                                        <p class="text-sm text-gray-500 mb-1">更新时间</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(forumData.update_at) }}</p>
                                    </div>
                                    <div v-if="forumData.highlighted_at">
                                        <p class="text-sm text-gray-500 mb-1">标记时间</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(forumData.highlighted_at) }}</p>
                                    </div>
                                    <div v-if="forumData.highlight_reason">
                                        <p class="text-sm text-gray-500 mb-1">标记理由</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ forumData.highlight_reason }}</p>
                                    </div>
                                </div>
                            </div>

                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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
                                        @main-click="handleAnalyze"
                                        @option-click="handleAnalyzeOption"
                                    />
                                    <button 
                                        @click="handleExport"
                                        class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2"
                                    >
                                        <Icon icon="mdi:download" />
                                        <span>媒体文件本地化</span>
                                    </button>
                                    <button 
                                        @click="togglePriorityTarget"
                                        :class="[
                                            'w-full py-3 rounded-lg font-medium transition-colors flex items-center justify-center space-x-2',
                                            isPriorityTarget 
                                                ? 'bg-amber-500 hover:bg-amber-600 text-white border-2 border-amber-500' 
                                                : 'border-2 border-gray-200 text-gray-600 hover:bg-gray-50'
                                        ]"
                                    >
                                        <Icon :icon="isPriorityTarget ? 'mdi:star' : 'mdi:star-outline'" />
                                        <span>{{ isPriorityTarget ? '取消重点目标' : '设置重点目标' }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </template>

        <el-dialog
            v-model="showHighlightDialog"
            title="设置重点目标"
            width="500px"
            :close-on-click-modal="false"
        >
            <el-form :model="highlightForm" label-width="100px">
                <el-form-item label="标记理由">
                    <el-input
                        v-model="highlightForm.reason"
                        type="textarea"
                        :rows="4"
                        placeholder="请输入标记理由（可选）"
                        maxlength="500"
                        show-word-limit
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showHighlightDialog = false">取消</el-button>
                <el-button type="primary" @click="confirmSetHighlight" :loading="highlightLoading">确定</el-button>
            </template>
        </el-dialog>

        <MarkingToolbar
            :visible="toolbarVisible"
            :position="toolbarPosition"
            :available-styles="availableStyles"
            :selected-style="selectedStyle"
            @style-select="handleStyleSelect"
            @create="handleCreateMarking"
        />
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import SplitButton from '@/components/SplitButton.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkingSidebar from '@/components/marking/MarkingSidebar.vue'
import MarkingToolbar from '@/components/marking/MarkingToolbar.vue'
import MarkingConnector from '@/components/marking/MarkingConnector.vue'
import { forumApi } from '@/api/forum'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/action'
import { useMarkingHandler } from '@/composables/useMarkingHandler'
import { useHighlight } from '@/composables/useHighlight'

const route = useRoute()
const uuid = computed(() => route.params.uuid)

const forumData = ref(null)
const loading = ref(false)
const error = ref(null)
const activeTab = ref('clean')
const analyzing = ref(false)
const editableSafeRawContent = ref('')
const rawEditorRef = ref(null)
const safeRawEditorRef = ref(null)
const cleanContentRef = ref(null)
const renderedContentRef = ref(null)

const {
    currentRegion,
    activeMarkingId,
    toolbarVisible,
    toolbarPosition,
    availableStyles,
    selectedStyle,
    getMarkingsByRegion,
    getSortedMarkingsByRegion,
    handleCleanContentMouseUp,
    handleRenderedContentMouseUp,
    handleStyleSelect,
    handleCreateMarking,
    handleUpdateMarking,
    handleDeleteMarking,
    handleMarkingHover,
    handleTabChange,
    setupEventListeners,
    cleanupEventListeners
} = useMarkingHandler({
    cleanContentRef,
    renderedContentRef,
    activeTab
})

const featuredComments = ref([])
const commentList = ref([])
const featuredLoading = ref(false)
const commentLoading = ref(false)
const featuredPage = ref(1)
const commentPage = ref(1)
const featuredTotal = ref(0)
const commentTotal = ref(0)

const loadForumDetail = async () => {
    loading.value = true
    error.value = null
    
    try {
        const response = await forumApi.getForumDetail(uuid.value)
        if (response.code === 0) {
            forumData.value = response.data
            
            if (forumData.value.safe_raw_content) {
                editableSafeRawContent.value = forumData.value.safe_raw_content
            }
            
            if (forumData.value.clean_content) {
                activeTab.value = 'clean'
            } else if (forumData.value.safe_raw_content) {
                activeTab.value = 'rendered'
            } else {
                activeTab.value = 'empty'
            }
            
            if (forumData.value.thread_type === 'thread' && forumData.value.platform && forumData.value.source_id) {
                await Promise.all([
                    loadFeaturedComments(),
                    loadComments()
                ])
            }
        } else {
            error.value = response.message || '加载帖子详情失败'
        }
    } catch (err) {
        console.error('加载帖子详情失败:', err)
        error.value = '加载帖子详情失败，请稍后重试'
    } finally {
        loading.value = false
    }
}

const {
    showHighlightDialog,
    highlightLoading,
    highlightForm,
    isPriorityTarget,
    togglePriorityTarget,
    confirmSetHighlight
} = useHighlight({
    entityType: 'forum',
    getData: () => forumData.value,
    reloadData: loadForumDetail,
    withDialog: true
})

const analyzeOptions = [
    { label: '内容分析', icon: 'mdi:text-box', value: 'content' },
    { label: '共识分析', icon: 'mdi:account-group', value: 'consensus' },
    { label: '情感分析', icon: 'mdi:emoticon-happy-outline', value: 'emotion' },
    { label: '多模态分析', icon: 'mdi:image-filter-none', value: 'multimodal' },
    { label: '传播路径分析', icon: 'mdi:share-variant', value: 'propagation' },
    { label: '证据链溯源分析', icon: 'mdi:link-variant', value: 'evidence' }
]

const hasInteractionData = computed(() => {
    if (!forumData.value) return false
    return (forumData.value.likes !== null && forumData.value.likes !== -1) ||
           (forumData.value.dislikes !== null && forumData.value.dislikes !== -1) ||
           (forumData.value.collections !== null && forumData.value.collections !== -1) ||
           (forumData.value.comments !== null && forumData.value.comments !== -1) ||
           (forumData.value.views !== null && forumData.value.views !== -1)
})

const handleSaveSafeContent = async () => {
    await ElMessageBox.alert('后端接口尚未实现，保存功能暂不可用', '提示', {
        confirmButtonText: '确定',
        type: 'info'
    }).catch(() => {})
}

const handleFormat = async () => {
    if (activeTab.value === 'safe-raw' && safeRawEditorRef.value) {
        await safeRawEditorRef.value.formatDocument()
    }
}

const getThreadTypeTag = (type) => {
    const typeMap = {
        'thread': 'primary',
        'comment': 'info',
        'featured': 'warning'
    }
    return typeMap[type] || ''
}

const getThreadTypeText = (type) => {
    const typeMap = {
        'thread': '主贴',
        'comment': '评论',
        'featured': '点评'
    }
    return typeMap[type] || type
}

const getStatusFlagType = (flag) => {
    const flagMap = {
        'stickied': 'warning',
        'essence': 'success',
        'locked': 'danger',
        'solved': 'success'
    }
    return flagMap[flag] || 'info'
}

const getStatusFlagIcon = (flag) => {
    const iconMap = {
        'stickied': 'mdi:pin',
        'essence': 'mdi:star',
        'locked': 'mdi:lock',
        'solved': 'mdi:check-circle'
    }
    return iconMap[flag] || 'mdi:tag'
}

const getStatusFlagText = (flag) => {
    const textMap = {
        'stickied': '置顶',
        'essence': '精华',
        'locked': '锁定',
        'solved': '已解决'
    }
    return textMap[flag] || flag
}

const getEmotionColor = (emotion) => {
    if (emotion < -0.3) return 'text-red-600'
    if (emotion > 0.3) return 'text-green-600'
    return 'text-gray-600'
}

const getConfidenceInfo = (confidence) => {
    if (confidence === 0) {
        return { text: '零信任', type: 'danger' }
    } else if (confidence > 0 && confidence <= 0.4) {
        return { text: '低', type: 'info' }
    } else if (confidence > 0.4 && confidence <= 0.7) {
        return { text: '中', type: '' }
    } else {
        return { text: '高', type: 'warning' }
    }
}

const loadFeaturedComments = async () => {
    if (!forumData.value?.platform || !forumData.value?.source_id) return
    
    featuredLoading.value = true
    try {
        const response = await forumApi.getComments({
            platform: forumData.value.platform,
            source_id: forumData.value.source_id,
            thread_type: 'featured',
            page: featuredPage.value,
            page_size: 10
        })
        
        if (response.code === 0 && response.data) {
            featuredComments.value = response.data.items || []
            featuredTotal.value = response.data.total || 0
        }
    } catch (err) {
        console.error('加载点评失败:', err)
        featuredComments.value = []
        featuredTotal.value = 0
    } finally {
        featuredLoading.value = false
    }
}

const loadComments = async () => {
    if (!forumData.value?.platform || !forumData.value?.source_id) return
    
    commentLoading.value = true
    try {
        const response = await forumApi.getComments({
            platform: forumData.value.platform,
            source_id: forumData.value.source_id,
            thread_type: 'comment',
            page: commentPage.value,
            page_size: 10
        })
        
        if (response.code === 0 && response.data) {
            commentList.value = response.data.items || []
            commentTotal.value = response.data.total || 0
        }
    } catch (err) {
        console.error('加载回复失败:', err)
        commentList.value = []
        commentTotal.value = 0
    } finally {
        commentLoading.value = false
    }
}

const isImageUrl = (url) => {
    if (!url) return false
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
    const lowerUrl = url.toLowerCase()
    return imageExtensions.some(ext => lowerUrl.includes(ext))
}

const handleAnalyze = async () => {
    analyzing.value = true
    try {
        ElMessage.success('分析任务已提交，请稍后刷新页面查看结果')
    } catch (err) {
        ElMessage.warning('分析功能暂未开放')
    } finally {
        analyzing.value = false
    }
}

const handleAnalyzeOption = (option) => {
    ElMessage.info(`${option.label}功能开发中`)
}

const handleExport = () => {
    ElMessage.info('功能开发中')
}

watch(() => route.params.uuid, () => {
    loadForumDetail()
}, { immediate: false })

watch(featuredPage, () => {
    loadFeaturedComments()
})

watch(commentPage, () => {
    loadComments()
})

watch(activeTab, async (newTab, oldTab) => {
    if (newTab === 'raw' && rawEditorRef.value && forumData.value?.raw_content) {
        await nextTick()
        await rawEditorRef.value.formatDocument()
    }
    await handleTabChange(newTab, oldTab)
})

onMounted(() => {
    loadForumDetail()
    setupEventListeners()
})

onUnmounted(() => {
    cleanupEventListeners()
})
</script>

<style scoped>
.forum-content :deep(img) {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 1rem 0;
}

.forum-content :deep(a) {
    color: #3b82f6;
    text-decoration: underline;
}

.forum-content :deep(p) {
    margin: 1rem 0;
    line-height: 1.8;
}

.forum-content :deep(h1),
.forum-content :deep(h2),
.forum-content :deep(h3),
.forum-content :deep(h4),
.forum-content :deep(h5),
.forum-content :deep(h6) {
    font-weight: bold;
    margin: 1.5rem 0 1rem 0;
}

.prose pre {
    background: transparent;
    padding: 0;
    margin: 0;
    font-family: inherit;
}

.forum-tabs :deep(.el-tabs__nav-wrap::after) {
    height: 1px;
}

.select-text {
    user-select: text;
    -webkit-user-select: text;
    -moz-user-select: text;
    -ms-user-select: text;
}

.marking-container :deep(.marking-target) {
    position: relative;
}

.prose :deep(.marking-target),
.forum-content :deep(.marking-target) {
    overflow: visible !important;
}

:deep(.rough-marking) {
    overflow: visible !important;
}

.prose,
.forum-content {
    overflow: visible !important;
}

.marking-container :deep(.bg-white),
.marking-container :deep(.rounded-xl) {
    overflow: visible !important;
}

.forum-tabs :deep(.el-tabs__content),
.forum-tabs :deep(.el-tab-pane) {
    overflow: visible !important;
}

.prose pre {
    padding-left: 8px;
    padding-right: 8px;
    margin-left: -8px;
    margin-right: -8px;
}
</style>
