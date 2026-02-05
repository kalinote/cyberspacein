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
                <Icon icon="mdi:alert-circle" class="text-red-500 text-5xl mb-4" />
                <h2 class="text-xl font-bold text-gray-900 mb-2">加载失败</h2>
                <p class="text-gray-600 mb-4">{{ error }}</p>
                <el-button type="primary" @click="$router.back()">返回</el-button>
            </div>
        </div>

        <template v-else-if="articleData">
            <DetailPageHeader
                :title="articleData.title || '无标题'"
                :subtitle="articleData.uuid"
            >
                <template #tags>
                    <el-tag v-if="articleData.spider_name" type="primary" size="default">
                        {{ articleData.spider_name }}
                    </el-tag>
                    <el-tag v-if="articleData.section" type="info" size="default">
                        {{ articleData.section }}
                    </el-tag>
                    <el-tag v-if="articleData.entity_type" type="" size="default">
                        {{ articleData.entity_type }}
                    </el-tag>
                    <el-tag v-if="articleData.nsfw" type="danger" size="default">
                        NSFW
                    </el-tag>
                    <el-tag v-if="articleData.aigc" type="warning" size="default">
                        AIGC
                    </el-tag>
                </template>
                <template #extra>
                    <el-link v-if="articleData.url" :href="articleData.url" target="_blank" type="primary" class="text-sm">
                        <template #icon>
                            <Icon icon="mdi:open-in-new" />
                        </template>
                        查看原文
                    </el-link>
                </template>
            </DetailPageHeader>

            <section class="py-8 bg-white">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 gap-6" :class="(articleData.likes != null && articleData.likes !== -1) ? 'md:grid-cols-5' : 'md:grid-cols-4'">
                        <div class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:account" class="text-blue-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">作者</p>
                                <p class="text-lg font-bold text-gray-900 truncate">
                                    {{ articleData.author_name || articleData.author_id || '未知' }}
                                </p>
                            </div>
                        </div>

                        <div class="bg-linear-to-br from-purple-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:web" class="text-purple-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">来源平台</p>
                                <p class="text-base font-bold text-gray-900 truncate">
                                    {{ articleData.platform || '未知' }}
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
                                    {{ formatDateTime(articleData.publish_at) }}
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
                                    {{ formatDateTime(articleData.crawled_at) }}
                                </p>
                            </div>
                        </div>

                        <div v-if="articleData.likes !== null && articleData.likes !== -1" class="bg-linear-to-br from-pink-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                            <div class="w-12 h-12 bg-pink-100 rounded-xl flex items-center justify-center">
                                <Icon icon="mdi:thumb-up" class="text-pink-600 text-2xl" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-500">点赞数</p>
                                <p class="text-2xl font-bold text-gray-900">
                                    {{ articleData.likes.toLocaleString() }}
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
                            <KeywordConnector
                                :selected-keywords="selectedKeywords"
                                :keyword-tag-refs="keywordTagRefs"
                                :keyword-colors="keywordColors"
                                :active-tab="activeTab"
                            />
                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div class="flex items-center justify-between mb-4">
                                    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
                                        <Icon icon="mdi:text-box" class="text-blue-600 mr-2" />
                                        文章<span class="text-blue-500">内容</span>
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
                                <el-tabs v-model="activeTab" class="article-tabs">
                                    <el-tab-pane v-if="articleData.clean_content" label="纯文本内容" name="clean">
                                        <div
                                            ref="cleanContentRef"
                                            class="prose max-w-none select-text"
                                            @mouseup="handleCleanContentMouseUp"
                                        >
                                            <pre class="whitespace-pre-wrap wrap-break-word text-gray-700 leading-relaxed" v-html="highlightedCleanContent"></pre>
                                        </div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="!articleData.clean_content" label="内容" name="empty">
                                        <div class="text-center py-12 text-gray-400 flex flex-col items-center">
                                            <Icon icon="mdi:text-box-remove-outline" class="text-5xl mb-2" />
                                            <p>暂无内容，点击开始分析以分析实体内容</p>
                                        </div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="articleData.safe_raw_content" label="安全渲染内容" name="rendered">
                                        <div
                                            ref="renderedContentRef"
                                            class="prose max-w-none article-content marking-content select-text"
                                            v-html="editableSafeRawContent"
                                            @mouseup="handleRenderedContentMouseUp"
                                        ></div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="articleData.translate_content" label="翻译内容" name="translate">
                                        <div
                                            ref="translateContentRef"
                                            class="prose max-w-none select-text"
                                            @mouseup="handleTranslateContentMouseUp"
                                        >
                                            <pre class="whitespace-pre-wrap wrap-break-word text-gray-700 leading-relaxed" v-html="highlightedTranslateContent"></pre>
                                        </div>
                                    </el-tab-pane>
                                    <el-tab-pane v-if="articleData.raw_content" label="原始源代码" name="raw">
                                        <MonacoEditor
                                            ref="rawEditorRef"
                                            :model-value="articleData.raw_content"
                                            :read-only="true"
                                            language="html"
                                        />
                                    </el-tab-pane>
                                    <el-tab-pane v-if="articleData.safe_raw_content" label="安全内容代码" name="safe-raw">
                                        <MonacoEditor
                                            ref="safeRawEditorRef"
                                            v-model="editableSafeRawContent"
                                            :read-only="false"
                                            language="html"
                                        />
                                    </el-tab-pane>
                                </el-tabs>
                            </div>

                            <div v-if="articleData.emotion !== null && articleData.emotion !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:emoticon-happy-outline" class="text-amber-600 mr-2" />
                                    情感<span class="text-blue-500">分析</span>
                                </h3>
                                <div class="space-y-4">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">情感分数</span>
                                        <span class="text-2xl font-bold" :class="getEmotionColor(articleData.emotion)">
                                            {{ articleData.emotion.toFixed(2) }}
                                        </span>
                                    </div>
                                    <div class="relative h-4 bg-gray-200 rounded-full overflow-hidden">
                                        <div class="absolute inset-0 flex">
                                            <div class="w-1/2 bg-red-200"></div>
                                            <div class="w-1/2 bg-green-200"></div>
                                        </div>
                                        <div 
                                            class="absolute top-0 bottom-0 w-1 bg-gray-800 transition-all duration-300"
                                            :style="{ left: `${(articleData.emotion + 1) * 50}%` }"
                                        ></div>
                                    </div>
                                    <div class="flex justify-between text-sm text-gray-500">
                                        <span>消极（-1）</span>
                                        <span>中性（0）</span>
                                        <span>积极（1）</span>
                                    </div>
                                </div>
                            </div>

                            <div v-if="articleData.political_bias && articleData.political_bias.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:scale-balance" class="text-purple-600 mr-2" />
                                    政治<span class="text-blue-500">倾向</span>
                                </h3>
                                <div class="flex flex-wrap gap-2">
                                    <el-tag v-for="bias in articleData.political_bias" :key="bias" type="warning" size="large">
                                        {{ bias }}
                                    </el-tag>
                                </div>
                            </div>

                            <div v-if="articleData.confidence !== null && articleData.confidence !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:shield-check" class="text-green-600 mr-2" />
                                    置信<span class="text-blue-500">度</span>
                                </h3>
                                <div v-if="articleData.confidence === -1" class="flex items-center space-x-3 p-4 bg-red-50 rounded-lg border border-red-200">
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
                                            {{ (articleData.confidence * 100).toFixed(0) }}%
                                        </span>
                                    </div>
                                    <div class="h-4 bg-gray-200 rounded-full overflow-hidden">
                                        <div 
                                            class="h-full bg-linear-to-r from-green-500 to-emerald-400 rounded-full transition-all duration-300"
                                            :style="{ width: `${articleData.confidence * 100}%` }"
                                        ></div>
                                    </div>
                                </div>
                            </div>

                            <div v-if="articleData.subjective_rating !== null && articleData.subjective_rating !== undefined" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                                    <Icon icon="mdi:star" class="text-amber-600 mr-2" />
                                    主观<span class="text-blue-500">评分</span>
                                </h3>
                                <div class="flex items-center space-x-4">
                                    <el-rate 
                                        v-model="articleData.subjective_rating" 
                                        disabled 
                                        show-score
                                        :max="10"
                                        size="large"
                                    />
                                    <span class="text-3xl font-bold text-gray-900">{{ articleData.subjective_rating }}/10</span>
                                </div>
                            </div>
                        </div>

                        <div class="space-y-6">
                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-lg font-bold text-gray-900 mb-4">
                                    文章<span class="text-blue-500">信息</span>
                                </h3>
                                <div class="space-y-4">
                                    <div v-if="articleData.author_name || articleData.author_id">
                                        <p class="text-sm text-gray-500 mb-1">作者</p>
                                        <router-link
                                            v-if="articleData.author_uuid"
                                            :to="`/user/${articleData.author_uuid}`"
                                            class="font-medium text-blue-600 hover:text-blue-800 underline"
                                        >
                                            {{ articleData.author_name || articleData.author_id }}
                                        </router-link>
                                        <p v-else class="font-medium text-gray-900">
                                            {{ articleData.author_name || articleData.author_id }}
                                        </p>
                                    </div>
                                    <div v-if="articleData.platform">
                                        <p class="text-sm text-gray-500 mb-1">平台</p>
                                        <router-link
                                            v-if="articleData.platform_uuid"
                                            :to="`/details/platform/${articleData.platform_uuid}`"
                                            class="font-medium text-blue-600 hover:text-blue-800 underline"
                                        >
                                            {{ articleData.platform }}
                                        </router-link>
                                        <p v-else class="font-medium text-gray-900">
                                            {{ articleData.platform }}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div v-if="articleData.keywords && articleData.keywords.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
                                    关键词<span class="text-blue-500">提取</span>
                                </h3>
                                <div class="flex flex-wrap gap-2">
                                    <el-tag
                                        v-for="keyword in articleData.keywords"
                                        :key="keyword"
                                        :type="selectedKeywords.includes(keyword) ? 'success' : 'primary'"
                                        size="large"
                                        class="cursor-pointer"
                                        :style="selectedKeywords.includes(keyword) && keywordColors[keyword] ? { borderColor: keywordColors[keyword], backgroundColor: keywordColors[keyword] + '22' } : undefined"
                                        :ref="(el) => setKeywordRef(keyword, el)"
                                        @click="toggleKeyword(keyword)"
                                    >
                                        {{ keyword }}
                                    </el-tag>
                                </div>
                            </div>

                            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 class="text-lg font-bold text-gray-900 mb-4">
                                    元数据<span class="text-blue-500">信息</span>
                                </h3>
                                <div class="space-y-4">
                                    <div v-if="articleData.tags && articleData.tags.length > 0">
                                        <p class="text-sm text-gray-500 mb-2">标签</p>
                                        <div class="flex flex-wrap gap-2">
                                            <el-tag v-for="tag in articleData.tags" :key="tag" type="info" size="small">
                                                {{ tag }}
                                            </el-tag>
                                        </div>
                                    </div>
                                    <div v-if="articleData.language">
                                        <p class="text-sm text-gray-500 mb-1">语言</p>
                                        <p class="font-medium text-gray-900">{{ articleData.language }}</p>
                                    </div>
                                    <div v-if="articleData.entity_type">
                                        <p class="text-sm text-gray-500 mb-1">实体类型</p>
                                        <p class="font-medium text-gray-900">{{ articleData.entity_type }}</p>
                                    </div>
                                    <div v-if="articleData.data_version">
                                        <p class="text-sm text-gray-500 mb-1">数据版本</p>
                                        <p class="font-medium text-gray-900">v{{ articleData.data_version }}</p>
                                    </div>
                                    <div v-if="articleData.source_id">
                                        <p class="text-sm text-gray-500 mb-1">来源ID</p>
                                        <p class="font-medium text-gray-900 break-all text-sm">{{ articleData.source_id }}</p>
                                    </div>
                                    <div v-if="articleData.last_edit_at">
                                        <p class="text-sm text-gray-500 mb-1">最后编辑</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(articleData.last_edit_at) }}</p>
                                    </div>
                                    <div v-if="articleData.update_at">
                                        <p class="text-sm text-gray-500 mb-1">更新时间</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(articleData.update_at) }}</p>
                                    </div>
                                    <div v-if="articleData.highlighted_at">
                                        <p class="text-sm text-gray-500 mb-1">标记时间</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ formatDateTime(articleData.highlighted_at) }}</p>
                                    </div>
                                    <div v-if="articleData.highlight_reason">
                                        <p class="text-sm text-gray-500 mb-1">标记理由</p>
                                        <p class="font-medium text-gray-900 text-sm">{{ articleData.highlight_reason }}</p>
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
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import SplitButton from '@/components/SplitButton.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkingSidebar from '@/components/marking/MarkingSidebar.vue'
import MarkingToolbar from '@/components/marking/MarkingToolbar.vue'
import MarkingConnector from '@/components/marking/MarkingConnector.vue'
import KeywordConnector from '@/components/keyword/KeywordConnector.vue'
import { articleApi } from '@/api/article'
import { agentApi } from '@/api/agent'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/action'
import { convertRelativeLinks } from '@/utils/linkProcessor'
import { useMarkingHandler } from '@/composables/useMarkingHandler'
import { useHighlight } from '@/composables/useHighlight'
import { useKeywordHighlight } from '@/composables/useKeywordHighlight'

const route = useRoute()
const router = useRouter()
const uuid = computed(() => route.params.uuid)

const articleData = ref(null)
const loading = ref(false)
const error = ref(null)
const activeTab = ref('clean')
const analyzing = ref(false)
const editableSafeRawContent = ref('')
const rawEditorRef = ref(null)
const safeRawEditorRef = ref(null)
const cleanContentRef = ref(null)
const renderedContentRef = ref(null)
const translateContentRef = ref(null)

const {
  selectedKeywords,
  keywordTagRefs,
  keywordColors,
  highlightedCleanContent,
  highlightedTranslateContent,
  setKeywordRef,
  toggleKeyword,
  applyRenderedKeywordHighlight
} = useKeywordHighlight({
  getCleanContent: () => articleData.value?.clean_content,
  getTranslateContent: () => articleData.value?.translate_content,
  renderedContentRef,
  activeTab
})

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
    handleTranslateContentMouseUp,
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
    translateContentRef,
    activeTab
})

const analyzeOptions = ref([])

const loadAnalyzeOptions = async () => {
    try {
        const res = await agentApi.getAgentsConfigList()
        const list = res?.data || []
        analyzeOptions.value = list.map(item => ({ label: item.name, value: item.id }))
    } catch (e) {
        analyzeOptions.value = []
    }
}

const loadArticleDetail = async () => {
    loading.value = true
    error.value = null
    
    try {
        const response = await articleApi.getArticleDetail(uuid.value)
        if (response.code === 0) {
            articleData.value = response.data
            
            if (articleData.value.safe_raw_content && articleData.value.url) {
                editableSafeRawContent.value = convertRelativeLinks(
                    articleData.value.safe_raw_content,
                    articleData.value.url
                )
            } else if (articleData.value.safe_raw_content) {
                editableSafeRawContent.value = articleData.value.safe_raw_content
            }
            
            if (articleData.value.clean_content) {
                activeTab.value = 'clean'
            } else if (articleData.value.safe_raw_content) {
                activeTab.value = 'rendered'
            } else {
                activeTab.value = 'empty'
            }
        } else {
            error.value = response.message || '加载文章详情失败'
        }
    } catch (err) {
        console.error('加载文章详情失败:', err)
        error.value = '加载文章详情失败，请稍后重试'
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
    entityType: 'article',
    getData: () => articleData.value,
    reloadData: loadArticleDetail,
    withDialog: true
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

const getEmotionColor = (emotion) => {
    if (emotion < -0.3) return 'text-red-600'
    if (emotion > 0.3) return 'text-green-600'
    return 'text-gray-600'
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

const handleAnalyzeOption = async (option) => {
    try {
        await ElMessageBox.confirm(
            `确定要执行「${option.label}」分析任务吗？`,
            '确认分析',
            {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )
        
        analyzing.value = true
        
        const response = await agentApi.startAgent({
            entity_uuid: articleData.value.uuid,
            entity_type: articleData.value.entity_type,
            agent_id: option.value
        })
        
        if (response.code === 0 && response.data?.thread_id) {
            ElMessage.success('分析任务已启动')
            router.push(`/agent/analysis/${response.data.thread_id}`)
        } else {
            ElMessage.error(response.message || '启动分析任务失败')
        }
    } catch (err) {
        if (err !== 'cancel') {
            console.error('启动分析任务失败:', err)
            ElMessage.error('启动分析任务失败，请稍后重试')
        }
    } finally {
        analyzing.value = false
    }
}

const handleExport = () => {
    ElMessage.info('导出功能开发中')
}

watch(() => route.params.uuid, () => {
    loadArticleDetail()
}, { immediate: false })

watch(activeTab, async (newTab, oldTab) => {
    if (newTab === 'raw' && rawEditorRef.value && articleData.value?.raw_content) {
        await nextTick()
        await rawEditorRef.value.formatDocument()
    }
    await handleTabChange(newTab, oldTab)
})

watch([activeTab, selectedKeywords], () => {
    applyRenderedKeywordHighlight()
}, { deep: true })
watch(editableSafeRawContent, () => {
    if (activeTab.value === 'rendered') applyRenderedKeywordHighlight()
})

onMounted(() => {
    loadArticleDetail()
    loadAnalyzeOptions()
    setupEventListeners()
})

onUnmounted(() => {
    cleanupEventListeners()
})
</script>

<style scoped>
.article-content :deep(img) {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 1rem 0;
}

.article-content :deep(a) {
    color: #3b82f6;
    text-decoration: underline;
}

.article-content :deep(p) {
    margin: 1rem 0;
    line-height: 1.8;
}

.article-content :deep(h1),
.article-content :deep(h2),
.article-content :deep(h3),
.article-content :deep(h4),
.article-content :deep(h5),
.article-content :deep(h6) {
    font-weight: bold;
    margin: 1.5rem 0 1rem 0;
}

.prose pre {
    background: transparent;
    padding: 0;
    margin: 0;
    font-family: inherit;
}

.article-tabs :deep(.el-tabs__nav-wrap::after) {
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
.article-content :deep(.marking-target) {
    overflow: visible !important;
}

:deep(.rough-marking) {
    overflow: visible !important;
}

.prose,
.article-content {
    overflow: visible !important;
}

.marking-container :deep(.bg-white),
.marking-container :deep(.rounded-xl) {
    overflow: visible !important;
}

.article-tabs :deep(.el-tabs__content),
.article-tabs :deep(.el-tab-pane) {
    overflow: visible !important;
}

.prose pre {
    padding-left: 8px;
    padding-right: 8px;
    margin-left: -8px;
    margin-right: -8px;
}

.marking-container :deep(.keyword-highlight) {
    background-color: rgba(59, 130, 246, 0.25);
    border-radius: 2px;
}
</style>
