<template>
    <div class="min-h-screen bg-gray-50 flex flex-col">
        <Header />

        <div v-if="loading" class="flex items-center justify-center h-96">
            <div class="text-center">
                <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                <p class="text-gray-600">加载中...</p>
            </div>
        </div>

        <div v-else-if="error" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div class="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
                <Icon icon="mdi:alert-circle" class="block mx-auto text-red-500 text-5xl mb-4" />
                <h2 class="text-xl font-bold text-gray-900 mb-2">加载失败</h2>
                <p class="text-gray-600 mb-4">{{ error }}</p>
                <el-button type="primary" @click="$router.back()">返回</el-button>
            </div>
        </div>

        <div v-else-if="forumData" class="flex flex-col forum-detail-page">
            <div class="snap-start scroll-mt-16">
            <DetailPageHeader
                :title="forumData.title || '无标题'"
                :subtitle="forumData.uuid"
            >
                <template #tags>
                    <el-tag v-if="forumData.spider_name" type="primary" size="default">
                        {{ forumData.spider_name }}
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
                    <el-tag v-for="flag in forumData.status_flags" :key="flag" type="primary" size="default">
                        {{ getStatusFlagText(flag) }}
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
                    <router-link v-if="forumData.topic_thread_uuid && forumData.thread_type !== 'thread'" :to="`/details/forum/${forumData.topic_thread_uuid}`" class="text-sm text-blue-600 hover:text-blue-800 flex items-center">
                        <Icon icon="mdi:forum" class="mr-1" />
                        查看主贴
                    </router-link>
                </template>
            </DetailPageHeader>

            <section v-if="forumInfoItems.length || hasForumInfoTags" class="py-6 bg-white">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="rounded-xl border border-gray-200 bg-gray-50/60 p-4 sm:p-5 shadow-sm">
                        <dl
                            v-if="forumInfoItems.length"
                            class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-x-5 gap-y-3.5"
                        >
                            <div
                                v-for="item in forumInfoItems"
                                :key="item.key"
                                class="min-w-0"
                            >
                                <dt class="text-xs text-gray-500 leading-tight">{{ item.label }}</dt>
                                <dd
                                    class="mt-0.5 text-sm font-medium text-gray-900"
                                    :class="{
                                        'font-mono text-xs': item.mono,
                                        'break-all': item.breakAll,
                                    }"
                                >
                                    <router-link
                                        v-if="item.to"
                                        :to="item.to"
                                        class="text-blue-600 hover:text-blue-800 inline-flex items-center gap-0.5 max-w-full"
                                    >
                                        <span class="truncate">{{ item.value }}</span>
                                        <Icon icon="mdi:chevron-right" class="shrink-0 text-base" />
                                    </router-link>
                                    <span
                                        v-else
                                        class="block truncate"
                                        :title="item.value"
                                    >{{ item.value }}</span>
                                </dd>
                            </div>
                        </dl>
                        <div
                            v-if="hasForumInfoTags"
                            :class="forumInfoItems.length ? 'mt-4 pt-4 border-t border-gray-200' : ''"
                        >
                            <p class="text-xs text-gray-500 mb-2">标签</p>
                            <div class="flex flex-wrap gap-1.5">
                                <el-tag
                                    v-for="tag in forumData.tags"
                                    :key="tag"
                                    type="info"
                                    size="small"
                                >
                                    {{ tag }}
                                </el-tag>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            </div>

            <div class="shrink-0 snap-start snap-always scroll-mt-16 lg:min-h-[calc(100dvh-4rem)]">
            <section
                class="shrink-0 py-6 bg-gray-50 flex flex-col overflow-hidden lg:h-[calc(100dvh-4rem)] lg:max-h-[calc(100dvh-4rem)] lg:min-h-120"
            >
                <div class="w-full h-full min-h-0 px-4 sm:px-6 lg:px-8 flex flex-col">
                    <ArticleDetailWorkbench
                        class="flex-1 min-h-0"
                        :constrain-height="workbenchHeightEnabled"
                        :pane-storage-key="FORUM_DETAIL_PANE_STORAGE_KEY"
                        :pane-defaults="FORUM_DETAIL_PANE_DEFAULTS"
                        :sorted-markings="getSortedMarkingsByRegion(currentRegion)"
                        :active-marking-id="activeMarkingId"
                        @marking-update="handleUpdateMarking"
                        @marking-delete="handleDeleteMarking"
                        @marking-hover="handleMarkingHover"
                        @pane-resized="handlePaneResized"
                    >
                        <template #center-top>
                            <div class="absolute inset-0 pointer-events-none z-10" aria-hidden="true">
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
                                <KeywordConnector
                                    :selected-keywords="selectedEntityKeys"
                                    :keyword-tag-refs="entityTagRefs"
                                    :keyword-colors="entityColors"
                                    data-attribute="data-entity"
                                    highlight-selector=".entity-highlight"
                                    :active-tab="activeTab"
                                />
                            </div>
                            <div class="flex h-full min-h-0 flex-1 flex-col bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div class="mb-4 flex shrink-0 items-center justify-between">
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
                                <el-tabs v-model="activeTab" class="forum-tabs min-h-0 flex-1 flex flex-col">
                                    <el-tab-pane v-if="forumData.clean_content" label="纯文本内容" name="clean">
                                        <div
                                            ref="cleanContentRef"
                                            class="prose max-w-none select-text"
                                            @mouseup="handleCleanContentMouseUp"
                                        >
                                            <pre class="whitespace-pre-wrap wrap-break-word text-gray-700 leading-relaxed" v-html="highlightedCleanContent"></pre>
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
                                    <el-tab-pane v-if="forumData.translate_content" label="翻译内容" name="translate">
                                        <div
                                            ref="translateContentRef"
                                            class="prose max-w-none select-text"
                                            @mouseup="handleTranslateContentMouseUp"
                                        >
                                            <pre class="whitespace-pre-wrap wrap-break-word text-gray-700 leading-relaxed" v-html="highlightedTranslateContent"></pre>
                                        </div>
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
                        </template>

                        <template #center-bottom>
                            <div
                                class="flex h-full min-h-0 flex-col gap-6"
                                :class="hasCenterBottomExtraCards ? 'overflow-y-auto overflow-x-hidden' : 'overflow-hidden'"
                            >
                                <Timeline
                                    v-if="showForumTimeline"
                                    :fill-height="!hasCenterBottomExtraCards && workbenchHeightEnabled"
                                    :entity-type="forumData.entity_type"
                                    :source-id="forumData.source_id"
                                    :current-uuid="forumData.uuid"
                                    :current-raw-content="forumData.raw_content || ''"
                                    :current-title="forumData.title || ''"
                                    :current-last-edit-at="forumData.last_edit_at || ''"
                                />

                                <div v-if="forumData.files_urls && forumData.files_urls.length > 0" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                                <div v-if="forumData.emotion !== null && forumData.emotion !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                                <div v-if="forumData.political_bias && forumData.political_bias.length > 0" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                                <div v-if="forumData.confidence !== null && forumData.confidence !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                                <div v-if="forumData.subjective_rating !== null && forumData.subjective_rating !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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
                        </template>

                        <template #right>
                            <div class="flex min-w-0 gap-0 h-full min-h-0 w-full">
                                <div
                                    class="flex-1 min-w-0 flex flex-col min-h-0 h-full bg-white rounded-l-xl shadow-sm border border-gray-200 border-r-0 overflow-hidden"
                                >
                                    <ArticleDetailInfoPanel
                                        v-show="rightPanel === 'info'"
                                        :keywords="forumData.keywords"
                                        :entities="forumData.entities"
                                        :analyze-options="analyzeOptions"
                                        :analyzing="analyzing"
                                        :is-priority-target="isPriorityTarget"
                                        :selected-keywords="selectedKeywords"
                                        :keyword-colors="keywordColors"
                                        :selected-entity-keys="selectedEntityKeys"
                                        :entity-colors="entityColors"
                                        :set-keyword-ref="setKeywordRef"
                                        :set-entity-ref="setEntityRef"
                                        @analyze-main="handleAnalyze"
                                        @analyze-option="handleAnalyzeOption"
                                        @export="handleExport"
                                        @toggle-priority="togglePriorityTarget"
                                        @toggle-keyword="toggleKeyword"
                                        @toggle-entity="toggleEntity"
                                    />
                                    <ArticleDetailAnalysisPanel
                                        v-show="rightPanel === 'analysis'"
                                        :session-id="activeSessionId"
                                        :timeline-items="timelineItems"
                                        :register-events-scroll-el="registerEventsScrollEl"
                                        :on-events-scroll="onEventsScroll"
                                        v-model:user-prompt="userPrompt"
                                        :send-loading="sendLoading"
                                        :cancel-loading="cancelLoading"
                                        :can-send-message="canSendMessage"
                                        :can-cancel="canCancel"
                                        :sse-connected="sseConnected"
                                        :status-label="agentStatusLabel"
                                        :status-tag-type="agentStatusTagType"
                                        :todos="todos"
                                        :todo-status-icon="todoStatusIcon"
                                        :todo-status-icon-color="todoStatusIconColor"
                                        @open-fullscreen="openAnalysisFullscreen"
                                        @send="sendMessage"
                                        @cancel="cancelAgentTask"
                                    />
                                </div>
                                <DetailRightActivityRail
                                    v-model="rightPanel"
                                    :items="rightRailItems"
                                    class="h-full shrink-0"
                                />
                            </div>
                        </template>
                    </ArticleDetailWorkbench>
                </div>
            </section>
            </div>

            <section
                v-if="forumData.thread_type === 'thread'"
                class="shrink-0 bg-gray-50 pb-6 snap-start scroll-mt-16"
            >
                <div class="w-full px-4 sm:px-6 lg:px-8">
                    <ForumDetailCommentsSection
                        :featured-comments="featuredComments"
                        :featured-total="featuredTotal"
                        :featured-loading="featuredLoading"
                        v-model:featured-page="featuredPage"
                        :comment-list="commentList"
                        :comment-total="commentTotal"
                        :comment-loading="commentLoading"
                        v-model:comment-page="commentPage"
                        :get-confidence-info="getConfidenceInfo"
                    />
                </div>
            </section>
        </div>

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

        <el-dialog
            v-model="showApprovalDialog"
            :title="approvalDialogTitle"
            width="760px"
            :close-on-click-modal="false"
            :show-close="false"
            @closed="onApprovalDialogClosed"
        >
            <div v-if="pendingApproval">
                <p class="text-gray-600 mb-4">Agent 请求执行以下操作，请选择批准或拒绝：</p>
                <AgentApprovalPanel :approval="pendingApproval" />
                <div v-if="showRejectReason" class="mt-4 pt-4 border-t border-gray-100">
                    <p class="text-sm text-gray-600 mb-2">拒绝理由（可选）</p>
                    <el-input
                        v-model="approvalReason"
                        type="textarea"
                        :autosize="{ minRows: 2, maxRows: 4 }"
                        placeholder="请填写拒绝原因"
                        resize="none"
                    />
                </div>
            </div>
            <template #footer>
                <template v-if="showRejectReason">
                    <el-button @click="cancelRejectFlow" :disabled="approvalLoading">返回</el-button>
                    <el-button type="danger" @click="submitApprovalDecision('reject')" :loading="approvalLoading">确认拒绝</el-button>
                </template>
                <template v-else>
                    <el-button type="danger" @click="showRejectReason = true" :loading="approvalLoading">拒绝</el-button>
                    <el-button type="primary" @click="submitApprovalDecision('approve')" :loading="approvalLoading">批准</el-button>
                </template>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import DetailPageHeader from '@/components/page-header/DetailPageHeader.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import ArticleDetailWorkbench from '@/components/detail/ArticleDetailWorkbench.vue'
import ForumDetailCommentsSection from '@/components/detail/ForumDetailCommentsSection.vue'
import MarkingToolbar from '@/components/marking/MarkingToolbar.vue'
import MarkingConnector from '@/components/marking/MarkingConnector.vue'
import KeywordConnector from '@/components/keyword/KeywordConnector.vue'
import Timeline from '@/components/Timeline.vue'
import DetailRightActivityRail from '@/components/detail/DetailRightActivityRail.vue'
import ArticleDetailInfoPanel from '@/components/detail/ArticleDetailInfoPanel.vue'
import ArticleDetailAnalysisPanel from '@/components/detail/ArticleDetailAnalysisPanel.vue'
import AgentApprovalPanel from '@/components/agent/approval/AgentApprovalPanel.vue'
import { useAgentSessionStream } from '@/composables/useAgentSessionStream'
import { getAgentAutoApproveValue } from '@/composables/useAgentAutoApprove'
import { forumApi } from '@/api/forum'
import { agentApi } from '@/api/agent'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/action'
import { convertRelativeLinks } from '@/utils/linkProcessor'
import { useMarkingHandler } from '@/composables/useMarkingHandler'
import { useHighlight } from '@/composables/useHighlight'
import { useKeywordHighlight } from '@/composables/useKeywordHighlight'
import { useEntityHighlight } from '@/composables/useEntityHighlight'
import { useMinLg } from '@/composables/useMinLg'
import {
    FORUM_DETAIL_PANE_DEFAULTS,
    FORUM_DETAIL_PANE_STORAGE_KEY,
} from '@/utils/useSplitpanesPersistence'
import { setDetailPageScrollSnap } from '@/utils/detailPageScrollSnap'

const route = useRoute()
const router = useRouter()
const uuid = computed(() => route.params.uuid)

const forumData = ref(null)
const loading = ref(false)
const error = ref(null)
const { isLgUp: workbenchHeightEnabled } = useMinLg()

const rightPanel = ref('info')
const rightRailItems = [
    { key: 'info', icon: 'mdi:information-outline', label: '信息栏' },
    { key: 'analysis', icon: 'mdi:brain', label: '分析框' },
]

const activeSessionId = ref('')
const activeAgentId = ref('')

const forumEntityUuid = computed(() => forumData.value?.uuid || '')
const forumEntityType = computed(() => forumData.value?.entity_type || '')

const agentStream = useAgentSessionStream({
    sessionId: activeSessionId,
    agentId: activeAgentId,
    entityUuid: forumEntityUuid,
    entityType: forumEntityType,
})

const {
    userPrompt,
    sendLoading,
    cancelLoading,
    todos,
    timelineItems,
    sseConnected,
    showApprovalDialog,
    pendingApproval,
    approvalReason,
    showRejectReason,
    approvalLoading,
    approvalDialogTitle,
    registerEventsScrollEl,
    scrollEventsToBottom,
    onEventsScroll,
    statusLabel: agentStatusLabel,
    statusTagType: agentStatusTagType,
    canSendMessage,
    canCancel,
    todoStatusIcon,
    todoStatusIconColor,
    disconnectSSE,
    startStreamForSession,
    sendMessage,
    cancel: cancelAgentTask,
    cancelRejectFlow,
    submitApprovalDecision,
    onApprovalDialogClosed,
} = agentStream

const activeTab = ref('clean')
const analyzing = ref(false)
const editableSafeRawContent = ref('')
const rawEditorRef = ref(null)
const safeRawEditorRef = ref(null)
const cleanContentRef = ref(null)
const renderedContentRef = ref(null)
const translateContentRef = ref(null)

const {
  selectedEntityKeys,
  entityTagRefs,
  entityColors,
  setEntityRef,
  toggleEntity,
  buildEntityHighlightLayer,
} = useEntityHighlight()

const {
  selectedKeywords,
  keywordTagRefs,
  keywordColors,
  setKeywordRef,
  toggleKeyword,
  applyRenderedKeywordHighlight,
  getHighlightedPlainText,
} = useKeywordHighlight({
  getCleanContent: () => forumData.value?.clean_content,
  getTranslateContent: () => forumData.value?.translate_content,
  renderedContentRef,
  activeTab
})

const entityHighlightLayers = computed(() => {
  const layer = buildEntityHighlightLayer()
  return layer ? [layer] : []
})

const highlightedCleanContent = computed(() =>
  getHighlightedPlainText(() => forumData.value?.clean_content, entityHighlightLayers.value)
)

const highlightedTranslateContent = computed(() =>
  getHighlightedPlainText(() => forumData.value?.translate_content, entityHighlightLayers.value)
)

function applyContentHighlights() {
  applyRenderedKeywordHighlight(entityHighlightLayers.value)
}

function handlePaneResized() {
    nextTick(() => {
        rawEditorRef.value?.layout?.()
        safeRawEditorRef.value?.layout?.()
    })
}

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
    loadMarkings,
    setupEventListeners,
    cleanupEventListeners
} = useMarkingHandler({
    cleanContentRef,
    renderedContentRef,
    translateContentRef,
    activeTab,
    entityUuid: uuid,
    entityType: 'forum'
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

            if (forumData.value.safe_raw_content && forumData.value.url) {
                editableSafeRawContent.value = convertRelativeLinks(
                    forumData.value.safe_raw_content,
                    forumData.value.url
                )
            } else if (forumData.value.safe_raw_content) {
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

            await nextTick()
            loadMarkings()
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

const isValidMetric = (value) => value !== null && value !== undefined && value !== -1

const hasForumInfoTags = computed(() => {
    const tags = forumData.value?.tags
    return Array.isArray(tags) && tags.length > 0
})

const showForumTimeline = computed(
    () => Boolean(forumData.value?.entity_type && forumData.value?.source_id),
)

const hasCenterBottomExtraCards = computed(() => {
    const d = forumData.value
    if (!d) return false
    if (d.files_urls?.length) return true
    if (d.emotion !== null && d.emotion !== undefined) return true
    if (d.political_bias?.length) return true
    if (d.confidence !== null && d.confidence !== undefined) return true
    if (d.subjective_rating !== null && d.subjective_rating !== undefined) return true
    return false
})

const forumInfoItems = computed(() => {
    const d = forumData.value
    if (!d) return []

    /** @type {{ key: string, label: string, value: string, to?: string, mono?: boolean, breakAll?: boolean }[]} */
    const items = []

    const push = (item) => {
        if (item.value !== undefined && item.value !== null && item.value !== '') {
            items.push(item)
        }
    }

    push({
        key: 'author',
        label: '作者',
        value: d.author_name || d.author_id || '未知',
        to: d.author_uuid ? `/user/${d.author_uuid}` : undefined,
    })
    push({
        key: 'platform',
        label: '来源平台',
        value: d.platform || '未知',
        to: d.platform_uuid ? `/details/platform/${d.platform_uuid}` : undefined,
    })
    if (d.publish_at) {
        push({ key: 'publish_at', label: '发布时间', value: formatDateTime(d.publish_at) })
    }
    if (d.crawled_at) {
        push({ key: 'crawled_at', label: '采集时间', value: formatDateTime(d.crawled_at) })
    }
    if (d.topic_id) {
        push({ key: 'topic_id', label: '主题ID', value: String(d.topic_id), mono: true, breakAll: true })
    }
    if (d.parent_id) {
        push({ key: 'parent_id', label: '父ID', value: String(d.parent_id), mono: true, breakAll: true })
    }
    if (isValidMetric(d.comments)) {
        push({ key: 'comments', label: '评论', value: d.comments.toLocaleString() })
    }
    if (isValidMetric(d.views)) {
        push({ key: 'views', label: '浏览', value: d.views.toLocaleString() })
    }
    if (d.topic_thread_uuid && d.thread_type !== 'thread') {
        push({
            key: 'topic_thread',
            label: '主贴',
            value: '查看主贴',
            to: `/details/forum/${d.topic_thread_uuid}`,
        })
    }
    if (isValidMetric(d.likes)) {
        push({ key: 'likes', label: '点赞', value: d.likes.toLocaleString() })
    }
    if (isValidMetric(d.dislikes)) {
        push({ key: 'dislikes', label: '点踩', value: d.dislikes.toLocaleString() })
    }
    if (isValidMetric(d.collections)) {
        push({ key: 'collections', label: '收藏', value: d.collections.toLocaleString() })
    }
    if (d.language) {
        push({ key: 'language', label: '语言', value: d.language })
    }
    if (d.entity_type) {
        push({ key: 'entity_type', label: '实体类型', value: d.entity_type })
    }
    if (d.data_version) {
        push({ key: 'data_version', label: '数据版本', value: `v${d.data_version}` })
    }
    if (d.source_id) {
        push({ key: 'source_id', label: '来源ID', value: String(d.source_id), mono: true, breakAll: true })
    }
    if (d.last_edit_at) {
        push({ key: 'last_edit_at', label: '最后编辑', value: formatDateTime(d.last_edit_at) })
    }
    if (d.update_at) {
        push({ key: 'update_at', label: '更新时间', value: formatDateTime(d.update_at) })
    }
    if (d.highlighted_at) {
        push({ key: 'highlighted_at', label: '标记时间', value: formatDateTime(d.highlighted_at) })
    }
    if (d.highlight_reason) {
        push({ key: 'highlight_reason', label: '标记理由', value: d.highlight_reason, breakAll: true })
    }

    return items
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
            agent_id: option.value,
            injection_param: {
                entity_uuid: forumData.value.uuid,
                entity_type: forumData.value.entity_type,
            },
            debug: true,
            auto_approve: getAgentAutoApproveValue(),
        })

        if (response.code === 0 && response.data?.agent_id) {
            ElMessage.success('分析任务已启动')
            const sid = response.data.session_id
            if (!sid) {
                ElMessage.error('未返回 session_id，无法开始分析')
                return
            }
            activeSessionId.value = String(sid)
            activeAgentId.value = String(response.data.agent_id)
            rightPanel.value = 'analysis'
            syncAgentSessionQuery()
            await startStreamForSession({ loadDetail: true })
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
    ElMessage.info('功能开发中')
}

function syncAgentSessionQuery() {
    const q = { ...route.query }
    if (activeSessionId.value) {
        q.agent_session = activeSessionId.value
        q.agent_id = activeAgentId.value
    } else {
        delete q.agent_session
        delete q.agent_id
    }
    router.replace({ query: q })
}

function restoreAgentSessionFromQuery() {
    const sid = route.query.agent_session
    const aid = route.query.agent_id
    if (!sid || !aid) return
    activeSessionId.value = String(sid)
    activeAgentId.value = String(aid)
    rightPanel.value = 'analysis'
    startStreamForSession({ loadDetail: true })
}

watch(rightPanel, async (panel) => {
    if (panel === 'analysis') {
        await nextTick()
        scrollEventsToBottom(true)
    }
})

function openAnalysisFullscreen() {
    if (!activeSessionId.value) return
    router.push({
        path: `/agent/analysis/${activeSessionId.value}`,
        query: {
            agent_id: activeAgentId.value,
            injection_param: JSON.stringify({
                entity_uuid: forumData.value?.uuid || '',
                entity_type: forumData.value?.entity_type || '',
            }),
        },
    })
}

watch(() => route.params.uuid, () => {
    disconnectSSE()
    activeSessionId.value = ''
    activeAgentId.value = ''
    rightPanel.value = 'info'
    syncAgentSessionQuery()
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

watch([activeTab, selectedKeywords, selectedEntityKeys], () => {
    applyContentHighlights()
}, { deep: true })
watch(editableSafeRawContent, () => {
    if (activeTab.value === 'rendered') applyContentHighlights()
})

watch(
    () => Boolean(forumData.value) && !loading.value,
    (enabled) => setDetailPageScrollSnap(enabled),
    { immediate: true },
)

onMounted(() => {
    loadForumDetail()
    loadAnalyzeOptions()
    setupEventListeners()
    restoreAgentSessionFromQuery()
})

onUnmounted(() => {
    setDetailPageScrollSnap(false)
    cleanupEventListeners()
    disconnectSSE()
})
</script>

<style scoped>
:global(html.detail-page-scroll-snap) {
    scroll-snap-type: y proximity;
}

@media (min-width: 1024px) {
    :global(html.detail-page-scroll-snap) {
        scroll-snap-type: y mandatory;
    }
}

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

.forum-tabs {
    display: flex;
    flex-direction: column;
}

.forum-tabs :deep(.el-tabs__header) {
    flex-shrink: 0;
}

.forum-tabs :deep(.el-tabs__content) {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
}

.forum-tabs :deep(.el-tab-pane) {
    height: 100%;
    overflow-y: auto;
}

.forum-tabs :deep(.monaco-editor-container) {
    min-height: 20rem;
    height: 100%;
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

.marking-container :deep(.keyword-highlight) {
    background-color: rgba(59, 130, 246, 0.25);
    border-radius: 2px;
}

.marking-container :deep(.entity-highlight) {
    background-color: rgba(16, 185, 129, 0.25);
    border-radius: 2px;
}

.prose pre {
    padding-left: 8px;
    padding-right: 8px;
    margin-left: -8px;
    margin-right: -8px;
}
</style>
