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

        <div v-else-if="articleData" class="flex flex-col">
            <div>
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

            <section v-if="articleInfoItems.length || hasArticleInfoTags" class="py-6 bg-white">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="rounded-xl border border-gray-200 bg-gray-50/60 p-4 sm:p-5 shadow-sm">
                        <dl
                            v-if="articleInfoItems.length"
                            class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-x-5 gap-y-3.5"
                        >
                            <div
                                v-for="item in articleInfoItems"
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
                            v-if="hasArticleInfoTags"
                            :class="articleInfoItems.length ? 'mt-4 pt-4 border-t border-gray-200' : ''"
                        >
                            <p class="text-xs text-gray-500 mb-2">标签</p>
                            <div class="flex flex-wrap gap-1.5">
                                <el-tag
                                    v-for="tag in articleData.tags"
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

            <div class="shrink-0 lg:min-h-[calc(100dvh-4rem)]">
            <section
                class="shrink-0 py-6 bg-gray-50 flex flex-col overflow-hidden lg:h-[calc(100dvh-4rem)] lg:max-h-[calc(100dvh-4rem)] lg:min-h-120"
            >
                <div class="w-full h-full min-h-0 px-4 sm:px-6 lg:px-8 flex flex-col">
                    <ArticleDetailWorkbench
                        class="flex-1 min-h-0"
                        :constrain-height="workbenchHeightEnabled"
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
                                <el-tabs v-model="activeTab" class="article-tabs min-h-0 flex-1 flex flex-col">
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
                                    <el-tab-pane v-if="articleData.snapshot" label="页面快照" name="snapshot">
                                        <div v-if="snapshotLoading" class="flex flex-col items-center justify-center py-16 text-gray-500">
                                            <Icon icon="mdi:loading" class="text-4xl text-blue-500 animate-spin mb-2" />
                                            <p>快照加载中...</p>
                                        </div>
                                        <div v-else-if="snapshotError" class="flex flex-col items-center justify-center py-16 text-gray-500">
                                            <Icon icon="mdi:alert-circle-outline" class="text-5xl text-red-400 mb-2" />
                                            <p class="mb-4 text-center max-w-md">{{ snapshotError }}</p>
                                            <el-button type="primary" @click="loadSnapshot">重试</el-button>
                                        </div>
                                        <div v-else-if="snapshotBlobUrl" class="space-y-2">
                                            <div class="flex justify-end">
                                                <el-link
                                                    :href="snapshotBlobUrl"
                                                    target="_blank"
                                                    type="primary"
                                                    class="text-sm"
                                                >
                                                    <template #icon>
                                                        <Icon icon="mdi:open-in-new" />
                                                    </template>
                                                    新窗口打开
                                                </el-link>
                                            </div>
                                            <iframe
                                                :src="snapshotBlobUrl"
                                                sandbox="allow-same-origin"
                                                class="w-full min-h-128 border-0 rounded-lg bg-white ring-1 ring-gray-200"
                                                title="页面快照"
                                            />
                                        </div>
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
                                v-if="showArticleTimeline"
                                :fill-height="!hasCenterBottomExtraCards && workbenchHeightEnabled"
                                :entity-type="articleData.entity_type"
                                :source-id="articleData.source_id"
                                :current-uuid="articleData.uuid"
                                :current-raw-content="articleData.raw_content || ''"
                                :current-title="articleData.title || ''"
                                :current-last-edit-at="articleData.last_edit_at || ''"
                            />

                            <div v-if="articleData.emotion !== null && articleData.emotion !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                            <div v-if="articleData.political_bias && articleData.political_bias.length > 0" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                            <div v-if="articleData.confidence !== null && articleData.confidence !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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

                            <div v-if="articleData.subjective_rating !== null && articleData.subjective_rating !== undefined" class="shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
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
                        </template>

                        <template #right>
                        <div class="flex min-w-0 gap-0 h-full min-h-0 w-full">
                            <div
                                class="flex-1 min-w-0 flex flex-col min-h-0 h-full bg-white rounded-l-xl shadow-sm border border-gray-200 border-r-0 overflow-hidden"
                            >
                                <ArticleDetailInfoPanel
                                    v-show="rightPanel === 'info'"
                                    :keywords="articleData.keywords"
                                    :entities="articleData.entities"
                                    :agent-options="analyzeOptions"
                                    :default-injection-param="defaultInjectionParam"
                                    :analyzing="analyzing"
                                    :is-priority-target="isPriorityTarget"
                                    :selected-keywords="selectedKeywords"
                                    :keyword-colors="keywordColors"
                                    :selected-entity-keys="selectedEntityKeys"
                                    :entity-colors="entityColors"
                                    :set-keyword-ref="setKeywordRef"
                                    :set-entity-ref="setEntityRef"
                                    @started="handleAgentStarted"
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
                                    :history-loading="historyLoading"
                                    :has-more-history="hasMoreHistory"
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
import MarkingToolbar from '@/components/marking/MarkingToolbar.vue'
import MarkingConnector from '@/components/marking/MarkingConnector.vue'
import KeywordConnector from '@/components/keyword/KeywordConnector.vue'
import Timeline from '@/components/Timeline.vue'
import DetailRightActivityRail from '@/components/detail/DetailRightActivityRail.vue'
import ArticleDetailInfoPanel from '@/components/detail/ArticleDetailInfoPanel.vue'
import ArticleDetailAnalysisPanel from '@/components/detail/ArticleDetailAnalysisPanel.vue'
import AgentApprovalPanel from '@/components/agent/approval/AgentApprovalPanel.vue'
import { useAgentSessionStream } from '@/composables/useAgentSessionStream'
import { articleApi } from '@/api/article'
import { agentApi } from '@/api/agent'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/action'
import { convertRelativeLinks } from '@/utils/linkProcessor'
import { useMarkingHandler } from '@/composables/useMarkingHandler'
import { useHighlight } from '@/composables/useHighlight'
import { useKeywordHighlight } from '@/composables/useKeywordHighlight'
import { useEntityHighlight } from '@/composables/useEntityHighlight'
import { hasEntities } from '@/utils/entityDisplay'
import { loadMhtmlSnapshot, revokeBlobUrl, resolveSnapshotUrl } from '@/utils/mhtmlSnapshot'
import { useMinLg } from '@/composables/useMinLg'
const route = useRoute()
const router = useRouter()
const uuid = computed(() => route.params.uuid)

const articleData = ref(null)
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

const articleEntityUuid = computed(() => articleData.value?.uuid || '')
const articleEntityType = computed(() => articleData.value?.entity_type || '')

const agentStream = useAgentSessionStream({
    sessionId: activeSessionId,
    agentId: activeAgentId,
    entityUuid: articleEntityUuid,
    entityType: articleEntityType,
})

const {
    userPrompt,
    sendLoading,
    cancelLoading,
    todos,
    timelineItems,
    hasMoreHistory,
    historyLoading,
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
const snapshotLoading = ref(false)
const snapshotError = ref('')
const snapshotBlobUrl = ref('')

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
  getCleanContent: () => articleData.value?.clean_content,
  getTranslateContent: () => articleData.value?.translate_content,
  renderedContentRef,
  activeTab
})

const entityHighlightLayers = computed(() => {
  const layer = buildEntityHighlightLayer()
  return layer ? [layer] : []
})

const highlightedCleanContent = computed(() =>
  getHighlightedPlainText(() => articleData.value?.clean_content, entityHighlightLayers.value)
)

const highlightedTranslateContent = computed(() =>
  getHighlightedPlainText(() => articleData.value?.translate_content, entityHighlightLayers.value)
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
    entityType: 'article'
})

const analyzeOptions = ref([])

const defaultInjectionParam = computed(() => ({
    entity_uuid: articleData.value?.uuid || '',
    entity_type: articleData.value?.entity_type || '',
}))

const loadAnalyzeOptions = async () => {
    try {
        const res = await agentApi.getAgentsConfigList()
        const list = res?.data || []
        analyzeOptions.value = list.map(item => ({ label: item.name, value: item.id }))
    } catch (e) {
        analyzeOptions.value = []
    }
}

function revokeSnapshotBlob() {
    revokeBlobUrl(snapshotBlobUrl.value)
    snapshotBlobUrl.value = ''
}

async function loadSnapshot() {
    const url = resolveSnapshotUrl(articleData.value?.snapshot)
    if (!url) {
        snapshotError.value = '快照地址无效'
        return
    }
    snapshotLoading.value = true
    snapshotError.value = ''
    try {
        const { blobUrl } = await loadMhtmlSnapshot(url)
        revokeSnapshotBlob()
        snapshotBlobUrl.value = blobUrl
    } catch (err) {
        snapshotError.value = err?.message || '快照加载失败'
    } finally {
        snapshotLoading.value = false
    }
}

const loadArticleDetail = async () => {
    loading.value = true
    error.value = null
    revokeSnapshotBlob()
    snapshotError.value = ''
    
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

            await nextTick()
            loadMarkings()
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

const isValidMetric = (value) => value !== null && value !== undefined && value !== -1

const hasArticleInfoTags = computed(() => {
    const tags = articleData.value?.tags
    return Array.isArray(tags) && tags.length > 0
})

const showArticleTimeline = computed(
    () => Boolean(articleData.value?.entity_type && articleData.value?.source_id),
)

const hasCenterBottomExtraCards = computed(() => {
    const d = articleData.value
    if (!d) return false
    if (d.emotion !== null && d.emotion !== undefined) return true
    if (d.political_bias?.length) return true
    if (d.confidence !== null && d.confidence !== undefined) return true
    if (d.subjective_rating !== null && d.subjective_rating !== undefined) return true
    return false
})

const articleInfoItems = computed(() => {
    const d = articleData.value
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
    if (isValidMetric(d.likes)) {
        push({ key: 'likes', label: '点赞', value: d.likes.toLocaleString() })
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

const getEmotionColor = (emotion) => {
    if (emotion < -0.3) return 'text-red-600'
    if (emotion > 0.3) return 'text-green-600'
    return 'text-gray-600'
}

async function handleAgentStarted({ agentId, sessionId }) {
    analyzing.value = true
    try {
        activeSessionId.value = String(sessionId)
        activeAgentId.value = String(agentId)
        rightPanel.value = 'analysis'
        syncAgentSessionQuery()
        await startStreamForSession({ loadDetail: true })
    } finally {
        analyzing.value = false
    }
}

const handleExport = () => {
    ElMessage.info('导出功能开发中')
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
                entity_uuid: articleData.value?.uuid || '',
                entity_type: articleData.value?.entity_type || '',
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
    loadArticleDetail()
}, { immediate: false })

watch(activeTab, async (newTab, oldTab) => {
    if (newTab === 'snapshot' && !snapshotBlobUrl.value && !snapshotLoading.value) {
        loadSnapshot()
    }
    if (newTab === 'raw' && rawEditorRef.value && articleData.value?.raw_content) {
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

onMounted(() => {
    loadArticleDetail()
    loadAnalyzeOptions()
    setupEventListeners()
    restoreAgentSessionFromQuery()
})

onUnmounted(() => {
    revokeSnapshotBlob()
    cleanupEventListeners()
    disconnectSSE()
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

.article-tabs {
    display: flex;
    flex-direction: column;
}

.article-tabs :deep(.el-tabs__header) {
    flex-shrink: 0;
}

.article-tabs :deep(.el-tabs__content) {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
}

.article-tabs :deep(.el-tab-pane) {
    height: 100%;
    overflow-y: auto;
}

.article-tabs :deep(.monaco-editor-container) {
    min-height: 20rem;
    height: 100%;
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

.marking-container :deep(.entity-highlight) {
    background-color: rgba(16, 185, 129, 0.25);
    border-radius: 2px;
}
</style>
