<template>
    <div class="h-screen flex flex-col bg-white" :class="{ 'mobile-blueprint-page': isMobile }">
        <Header />

        <SimplePageHeader v-if="!isMobile" :title="pageTitle" />

        <MobileBlueprintEditor v-if="isMobile" ref="mobileEditorRef"
            :elements="elements" :configs="nodeTypeConfigs" :selected-id="selectedGraphNodeId"
            :title="actionForm.title" :editable="canEdit && pageActive" :dirty="draftDirty || Boolean(localDraftSignature)"
            :loading="loadingBlueprint || loadingNodeConfigs" :saving="saving" :error="editorError"
            :can-undo="historyStatus.canUndo" :can-redo="historyStatus.canRedo" :issues="mobileIssues"
            @select="selectedGraphNodeId = $event" @selection="mobileSelectedIds = $event" @mode="setMobileMode" @fit="fitMobileGraph" @fit-all="fitMobileGraph(true)"
            @save="handleSaveAction" @retry="initializeEditor" @undo="restoreHistory('undo')" @redo="restoreHistory('redo')"
            @add-node="addMobileNode" @connect="connectMobileNodes" @bind="bindMobileNodes"
            @unbind="confirmMobileUnbind" @remove="removeMobileElements" @position="moveMobileNode" @move-group="moveMobileGroup"
            @apply-layout="applyMobileLayout" @cancel-layout="cancelMobileLayout">
            <template #canvas>
                <VueFlow id="mobile-blueprint-flow" :nodes="mobileCanvasNodes" :edges="mobileCanvasEdges" :node-types="nodeTypes" :edge-types="edgeTypes" :min-zoom="0.05" :max-zoom="3"
                    :nodes-draggable="canEdit && !saving && mobileMode === 'move'" :nodes-connectable="false"
                    :elements-selectable="false" :delete-key-code="null" :zoom-on-double-click="false" class="h-full w-full"
                    @node-click="mobileEditorRef?.selectNode($event.node.id)"
                    @edge-click="handleMobileEdgeClick" @node-drag-stop="recordMobileDrag" @nodes-initialized="fitMobileGraph(false)">
                    <Background pattern-color="#cbd5e1" :gap="18" />
                    <Controls :show-interactive="false" />
                </VueFlow>
            </template>
            <template #fields="{ node }"><MobileBlueprintNodeFields :node="node" :disabled="!canEdit || saving" @field-change="updateMobileField(node.id, $event)" /></template>
            <template #settings>
                <el-form :model="actionForm" label-position="top" :disabled="!canEdit || saving">
                    <el-form-item label="蓝图标题" required><el-input v-model="actionForm.title" /></el-form-item>
                    <el-form-item label="版本号" required><el-input v-model="actionForm.version" /></el-form-item>
                    <el-form-item label="任务目标" required><el-input v-model="actionForm.target" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" /></el-form-item>
                    <el-form-item label="详细信息"><el-input v-model="actionForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" /></el-form-item>
                    <el-form-item label="执行期限（秒，0 为不限制）"><el-input-number v-model="actionForm.implementation_period" :min="0" /></el-form-item>
                    <el-form-item label="默认异步执行"><el-switch :model-value="actionForm.default_scheduling_mode === 'streaming'" @update:model-value="actionForm.default_scheduling_mode = $event ? 'streaming' : 'barrier'" /></el-form-item>
                    <el-form-item label="模板蓝图"><el-switch v-model="isTemplate" /></el-form-item>
                    <el-form-item label="资源配置"><el-switch v-model="resourceConfigEnabled" /></el-form-item>
                </el-form>
            </template>
            <template #template><TemplateParamsManager v-if="isTemplate" embedded :resizable="false" :disabled="!canEdit || saving" v-model:params="templateParams" v-model:bindings="templateBindings" /><p v-else class="text-sm text-gray-500">请先在蓝图设置中启用模板蓝图。</p></template>
            <template #resource><ResourceConfigPanel v-if="resourceConfigEnabled" :show-top-divider="false" /><p v-else class="text-sm text-gray-500">尚未启用资源配置。</p></template>
            <template #interfaces><BlueprintInterfacePanel :ports="publicInterfaces" :disabled="!canEdit || saving" @unbind="confirmMobileUnbind" /></template>
            <template #upgrade><el-button v-if="selectedEncapsulatedUpgrade" :disabled="!canEdit || saving" @click="upgradeSelectedEncapsulatedNode">升级到 v{{ selectedEncapsulatedUpgrade.definition_version }} 并按稳定端口重连</el-button></template>
            <template #publish><div v-if="isEditMode" class="flex flex-wrap gap-2 mt-4"><el-button v-if="hasPerm(PERM.operations.action.blueprint.publish)" :disabled="!canEdit || saving || mobileMode === 'move'" @click="publishDialogVisible = true">发布版本</el-button><el-button v-if="canEncapsulate" :disabled="!canEdit || saving || mobileMode === 'move'" @click="encapsulateDialogVisible = true">封装为节点</el-button></div></template>
        </MobileBlueprintEditor>

        <div v-else
            v-loading="loadingBlueprint"
            element-loading-text="加载行动蓝图中..."
            class="flex-1 flex overflow-hidden"
        >
            <!-- 左侧边栏 -->
            <div class="bg-white flex flex-col border-r border-white relative shrink-0 group"
                :style="{ width: sidebarWidth + 'px' }">
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">节点列表</h3>
                </div>
                <div class="flex flex-col select-none overflow-y-auto flex-1 overflow-x-hidden min-h-0"
                    v-loading="loadingNodeConfigs" :element-loading-text="'加载节点配置中...'">
                    <div v-for="category in nodeCategories" :key="category.type"
                        class="border-b border-gray-100 last:border-b-0">
                        <div class="px-4 py-2 bg-gray-50 hover:bg-gray-100 cursor-pointer flex items-center justify-between transition-colors"
                            @click="toggleCategory(category.type)">
                            <div class="flex items-center gap-2">
                                <Icon
                                    :icon="categoryCollapsed[category.type] === true ? 'mdi:chevron-right' : 'mdi:chevron-down'"
                                    class="text-gray-500 text-sm transition-transform" />
                                <span class="text-sm font-medium text-gray-700">{{ category.label }}</span>
                                <span class="text-xs text-gray-400">({{ category.nodes.length }})</span>
                            </div>
                        </div>
                        <div v-show="!(categoryCollapsed[category.type] === true)" class="p-4 flex flex-col gap-3">
                            <el-tooltip v-for="node in category.nodes" :key="node.key" :content="node.description"
                                placement="right" :show-after="300">
                                <div class="cursor-grab active:cursor-grabbing origin-top-left transition-transform duration-75"
                                    draggable="true"
                                    @dragstart="onDragStart($event, node.key)"
                                    @dragend="clearBindingCandidate"
                                    :style="getNodeWrapperStyle">
                                    <div class="pointer-events-none w-full">
                                        <div v-if="isCompact"
                                            class="flex items-center p-3 bg-white rounded-lg border border-gray-200 shadow-sm hover:border-blue-400 transition-colors">
                                            <div class="w-1.5 h-3 rounded-full mr-2"
                                                :style="{ backgroundColor: node.color || '#909399' }"></div>
                                            <span class="text-sm text-gray-700 font-medium truncate">{{ node.label
                                                }}</span>
                                        </div>

                                        <component v-else :is="node.component" :id="`sidebar-${node.key}-preview`"
                                            :data="node.data" :show-handle="false" />
                                    </div>
                                </div>
                            </el-tooltip>
                        </div>
                    </div>
                </div>

                <div class="absolute top-0 bottom-0 -right-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startLeftResize">
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors"
                        :class="{ 'bg-blue-600!': isResizing }"></div>
                </div>
            </div>

            <!-- 流程图 -->
            <div class="flex-1 h-full relative bg-gray-50" @drop="onDrop" @dragover="onDragOver">
                <div
                    v-if="pendingOutputBindingNodeId"
                    class="absolute left-1/2 top-3 z-50 -translate-x-1/2 rounded-full bg-violet-600 px-4 py-2 text-xs font-medium text-white shadow-lg"
                >
                    已选择蓝图输出，请点击结束节点顶部的绑定 Handle；按 Esc 取消
                </div>
                <VueFlow id="desktop-blueprint-flow" :model-value="elements" @update:model-value="acceptDesktopElements" :node-types="nodeTypes" :edge-types="edgeTypes" :default-zoom="1.5" :min-zoom="0.2" :max-zoom="4"
                    fit-view-on-init class="h-full w-full"
                    @node-click="selectedGraphNodeId = $event.node.id"
                    @pane-click="handlePaneClick">
                    <Background pattern-color="#aaa" :gap="18" />
                    <Controls />
                </VueFlow>
            </div>

            <!-- 右侧边栏 -->
            <div class="bg-white flex flex-col border-l border-gray-200 relative shrink-0 group"
                :style="{ width: rightSidebarWidth + 'px' }">
                <div class="px-4 pt-4 pb-2 border-b border-gray-200 shrink-0">
                    <h3 class="text-base font-semibold text-gray-800 text-center">行动属性</h3>
                </div>
                <el-form ref="actionFormRef" :model="actionForm" :rules="actionFormRules"
                    class="p-4 flex flex-col gap-4 flex-1 overflow-y-auto min-h-0" label-width="auto" label-position="top">
                    <!-- 标题输入框 -->
                    <el-form-item prop="title" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">标题</span>
                        </template>
                        <el-input v-model="actionForm.title" placeholder="请输入行动标题" clearable />
                    </el-form-item>

                    <!-- 版本号输入框 -->
                    <el-form-item prop="version" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">版本号</span>
                        </template>
                        <el-input v-model="actionForm.version" placeholder="请输入版本号" clearable />
                    </el-form-item>

                    <!-- 执行期限输入框 -->
                    <el-form-item prop="implementation_period" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">执行期限(秒)</span>
                        </template>
                        <el-input-number v-model="actionForm.implementation_period" :min="0" placeholder="请输入执行期限" class="w-full" />
                        <div class="text-xs text-gray-400 mt-1">设置为 0 时不限制行动执行时间</div>
                    </el-form-item>

                    <el-form-item class="shrink-0 mb-0 -mt-2">
                        <template #label>
                            <div class="flex items-center justify-between w-full">
                                <span class="text-sm font-medium text-gray-700">默认异步执行</span>
                                <el-tooltip content="作为立即执行、调试运行、定时任务和未显式指定模式的 API 调用默认值；立即执行可在下拉菜单切换" placement="top">
                                    <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help" />
                                </el-tooltip>
                            </div>
                        </template>
                        <el-switch
                            :model-value="actionForm.default_scheduling_mode === 'streaming'"
                            active-text="启用"
                            inactive-text="禁用"
                            @update:model-value="actionForm.default_scheduling_mode = $event ? 'streaming' : 'barrier'"
                        />
                    </el-form-item>

                    <!-- 详细信息输入框 -->
                    <el-form-item prop="description" class="shrink-0 mb-0">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">详细信息</span>
                        </template>
                        <el-input v-model="actionForm.description" type="textarea" placeholder="请输入行动详细信息"
                            resize="vertical" :autosize="{ minRows: 3, maxRows: 10 }" />
                    </el-form-item>

                    <!-- 任务目标输入框 -->
                    <el-form-item prop="target" class="shrink-0 mb-0 -mt-2">
                        <template #label>
                            <span class="text-sm font-medium text-gray-700">任务目标</span>
                        </template>
                        <el-input v-model="actionForm.target" type="textarea" placeholder="请输入任务目标" resize="vertical"
                            :autosize="{ minRows: 3, maxRows: 10 }" />
                    </el-form-item>

                    <!-- 模板蓝图开关 -->
                    <el-form-item class="shrink-0 mb-0 -mt-2">
                        <template #label>
                            <div class="flex items-center justify-between w-full">
                                <span class="text-sm font-medium text-gray-700">模板蓝图</span>
                                <el-tooltip content="启用后可使用参数占位符，在运行时注入实际数据" placement="top">
                                    <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help" />
                                </el-tooltip>
                            </div>
                        </template>
                        <el-switch 
                            v-model="isTemplate" 
                            active-text="启用"
                            inactive-text="禁用"
                        />
                    </el-form-item>

                    <!-- 资源配置开关 -->
                    <el-form-item class="shrink-0 mb-0 -mt-2">
                        <template #label>
                            <div class="flex items-center justify-between w-full">
                                <span class="text-sm font-medium text-gray-700">资源配置</span>
                                <el-tooltip content="启用后可在此配置行动所需资源" placement="top">
                                    <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help" />
                                </el-tooltip>
                            </div>
                        </template>
                        <el-switch
                            v-model="resourceConfigEnabled"
                            active-text="启用"
                            inactive-text="禁用"
                        />
                    </el-form-item>
                </el-form>

                <!-- 右侧底部折叠菜单 -->
                <div
                    v-if="isTemplate || resourceConfigEnabled"
                    class="shrink-0 flex flex-col border-t border-gray-200 mt-4 max-h-[45vh] overflow-y-auto"
                >
                    <TemplateParamsManager
                        v-if="isTemplate"
                        embedded
                        :resizable="false"
                        v-model:params="templateParams"
                        v-model:bindings="templateBindings"
                    />
                    <ResourceConfigPanel
                        v-if="resourceConfigEnabled"
                        :show-top-divider="isTemplate"
                    />
                </div>

                <BlueprintInterfacePanel
                    :ports="publicInterfaces"
                    @unbind="handleUnbindBoundary"
                />
                <div
                    v-if="selectedEncapsulatedUpgrade"
                    class="mx-4 mb-3 rounded-lg border border-teal-200 bg-teal-50 p-3"
                >
                    <p class="text-sm font-medium text-teal-900">发现新的封装节点版本</p>
                    <p class="mt-1 text-xs text-teal-700">
                        当前 v{{ selectedNodeConfig.definition_version }}，可显式升级到
                        v{{ selectedEncapsulatedUpgrade.definition_version }}。
                    </p>
                    <el-button class="mt-2" size="small" type="success" @click="upgradeSelectedEncapsulatedNode">
                        升级并按稳定端口重连
                    </el-button>
                </div>

                <!-- 底部保存按钮 -->
                <div class="p-4 border-t border-gray-200 shrink-0 space-y-2">
                    <div v-if="isEditMode" class="grid grid-cols-2 gap-2">
                        <el-button
                            v-if="hasPerm(PERM.operations.action.blueprint.publish)"
                            class="w-full"
                            @click="publishDialogVisible = true"
                        >
                            发布版本
                        </el-button>
                        <el-button
                            v-if="canEncapsulate"
                            class="w-full"
                            type="success"
                            plain
                            @click="encapsulateDialogVisible = true"
                        >
                            封装为节点
                        </el-button>
                    </div>
                    <el-button
                        type="primary"
                        class="w-full"
                        :loading="saving"
                        :disabled="loadingBlueprint"
                        @click="handleSaveAction"
                    >
                        {{ saveButtonText }}
                    </el-button>
                </div>

                <!-- 调整大小手柄 -->
                <div class="absolute top-0 bottom-0 -left-1 w-2 cursor-col-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
                    @mousedown.prevent="startRightResize">
                    <div class="w-px h-full bg-gray-200 group-hover:bg-blue-400 transition-colors"
                        :class="{ 'bg-blue-600!': isRightResizing }"></div>
                </div>
            </div>
        </div>

        <BoundaryBindingDialog
            v-model="bindingDialogVisible"
            :boundary-node="pendingBoundaryNode"
            :target-node="pendingTargetNode"
            :available-handles="pendingBindableHandles"
            @confirm="handleConfirmBinding"
            @cancel="handleCancelBinding"
        />
        <BlueprintPublishDialog
            v-model="publishDialogVisible"
            :submitting="publishing"
            @submit="handlePublishBlueprint"
        />
        <BlueprintEncapsulateDialog
            v-model="encapsulateDialogVisible"
            :interfaces="publicInterfaces"
            :target-nodes="encapsulatedTargetNodes"
            :submitting="encapsulating"
            @submit="handleEncapsulateBlueprint"
        />
    </div>
</template>

<script setup>
import {
    ref,
    computed,
    onMounted,
    onBeforeUnmount,
    markRaw,
    nextTick,
    provide,
    watch
} from 'vue'
import { onActivated, onDeactivated, reactive } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from "@/components/Header.vue"
import SimplePageHeader from "@/components/page-header/SimplePageHeader.vue"
import { VueFlow, useVueFlow } from "@vue-flow/core"
import { Background } from "@vue-flow/background"
import { Controls } from "@vue-flow/controls"
import GenericNode from "@/components/action/nodes/GenericNode.vue"
import SubflowNode from "@/components/action/nodes/SubflowNode.vue"
import BoundaryBindingEdge from "@/components/action/edges/BoundaryBindingEdge.vue"
import { resolveNativeNodeRenderer } from "@/components/action/nodes/nativeNodeRendererRegistry"
import BlueprintInterfacePanel from "@/components/action/BlueprintInterfacePanel.vue"
import BoundaryBindingDialog from "@/components/action/BoundaryBindingDialog.vue"
import BlueprintPublishDialog from "@/components/action/BlueprintPublishDialog.vue"
import BlueprintEncapsulateDialog from "@/components/action/BlueprintEncapsulateDialog.vue"
import TemplateParamsManager from "@/components/action/template/TemplateParamsManager.vue"
import ResourceConfigPanel from "@/components/action/ResourceConfigPanel.vue"
import { actionApi } from '@/api/action'
import { ElMessage, ElNotification, ElMessageBox } from 'element-plus'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileBlueprintEditor from '@/components/action/mobile/MobileBlueprintEditor.vue'
import MobileBlueprintNode from '@/components/action/mobile/MobileBlueprintNode.vue'
import MobileBlueprintNodeFields from '@/components/action/mobile/MobileBlueprintNodeFields.vue'
import { captureBlueprintDraft, createBlueprintHistory, blueprintConnectionIssue, collectBlueprintGraphIssues, blueprintRemovalImpact, projectMobileBlueprint } from '@/utils/action/mobileGraph'
import { hasAll, hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import {
    getDefaultData,
    getNodeColor,
    normalizeDefaultValue
} from '@/utils/action'
import {
    BINDING_SOURCE_HANDLE_ID,
    BINDING_TARGET_HANDLE_ID,
    buildBindingDisplay,
    buildBindingRelationEdges,
    collectBindingTargetKinds,
    getBoundaryDirection,
    getBoundaryExposedHandles,
    getBoundaryInitialPosition,
    isBindingProtocolHandle,
    isBoundaryConfig,
    resolveBindingTargetStates,
    validateBindingCandidate,
    validateBoundaryBindings
} from '@/utils/action/boundaryBinding'
import {
    acceptsHandleDataType,
    allowsMultipleHandleInputs,
    areHandleInterfacesCompatible,
    isDuplicateHandleConnection
} from '@/utils/action/handleConnection'
import { useSidebarResize } from '@/utils/action/useSidebarResize'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const router = useRouter()
const route = useRoute()
const { isMobile } = useMobileViewport()
const mobileEditorRef = ref(null)
const blueprintLocalDrafts = reactive(new Map())
provide('blueprintLocalDrafts', blueprintLocalDrafts)
const localDraftSignature = computed(() => {
    const drafts = [...blueprintLocalDrafts.values()].filter(Boolean)
    return drafts.length ? JSON.stringify(drafts) : ''
})
const mobileMode = ref('browse')
const mobileSelectedIds = ref([])
const pageActive = ref(true)
const editorError = ref('')
let editorEpoch = 0
let nodeRequest = 0
const canLoad = computed(() => hasPerm(PERM.operations.action.node.read) && (!blueprintId.value || hasPerm(PERM.operations.action.blueprint.read)))
const canEdit = computed(() => canLoad.value && hasPerm(blueprintId.value ? PERM.operations.action.blueprint.update : PERM.operations.action.blueprint.create))
const savedViewport = ref({ x: 0, y: 0, zoom: 1 })
const createdBlueprintId = ref(null)
const blueprintId = computed(() => route.params.blueprintId || createdBlueprintId.value || null)
const isEditMode = computed(() => Boolean(blueprintId.value))
const pageTitle = computed(() => isEditMode.value ? '编辑标准行动蓝图' : '创建标准行动蓝图')
const saveButtonText = computed(() => isEditMode.value ? '保存蓝图修改' : '保存行动蓝图')
const loadingBlueprint = ref(false)
const saving = ref(false)
const canEncapsulate = computed(() => hasAll([
    PERM.operations.action.blueprint.read,
    PERM.operations.action.blueprint.publish,
    PERM.operations.action.node.create
]))

const nodeTypeConfigs = ref([])
const loadingNodeConfigs = ref(false)

const fetchNodeConfigs = async () => {
    const request = ++nodeRequest
    const epoch = editorEpoch
    if (!pageActive.value || !canLoad.value) return false
    loadingNodeConfigs.value = true
    try {
        const response = await actionApi.getNodes()
        if (request !== nodeRequest || epoch !== editorEpoch || !pageActive.value || !canLoad.value) return false
        if (response.code === 0) {
            const nodes = response.data || []
            nodeTypeConfigs.value = nodes.map(node => {
                const processedNode = { ...node }

                if (processedNode.handles) {
                    processedNode.handles = processedNode.handles.map(handle => ({
                        ...handle,
                        id: handle.id || handle.name
                    }))
                }

                if (processedNode.inputs) {
                    processedNode.inputs = processedNode.inputs.map(input => ({
                        ...input,
                        id: input.id || input.name
                    }))
                }
                processedNode.rendererUnsupported = (
                    processedNode.node_kind === 'backend_native'
                    && !resolveNativeNodeRenderer(processedNode)
                )

                return processedNode
            })
            return true
        } else throw new Error(response.message || '获取节点配置失败')
    } catch (error) {
        if (request !== nodeRequest || epoch !== editorEpoch || !pageActive.value) return false
        ElMessage.error('获取节点配置失败')
        editorError.value = '节点定义加载失败，现有草稿已保留，请重试。'
        return false
    } finally {
        if (request === nodeRequest && epoch === editorEpoch) loadingNodeConfigs.value = false
    }
}

const componentForConfig = (config) => {
    if (config.node_kind === 'encapsulated') return markRaw(SubflowNode)
    if (config.node_kind === 'backend_native') {
        return resolveNativeNodeRenderer(config)
    }
    return markRaw(GenericNode)
}

const sidebarNodes = computed(() => {
    return nodeTypeConfigs.value.filter(config => (
        !config.rendererUnsupported && config.enabled && config.is_latest
    )).map(config => ({
        key: config.id,
        label: config.name,
        type: config.type,
        color: getNodeColor(config),
        description: config.description,
        component: componentForConfig(config),
        data: getDefaultData(config)
    }))
})

const nodeCategories = computed(() => {
    const categories = {}

    sidebarNodes.value.forEach(node => {
        if (!categories[node.type]) {
            categories[node.type] = {
                type: node.type,
                label: node.type,
                nodes: []
            }
        }
        categories[node.type].nodes.push(node)
    })

    return Object.values(categories)
})

const categoryCollapsed = ref({})

const toggleCategory = (type) => {
    categoryCollapsed.value[type] = !(categoryCollapsed.value[type] === true)
}

const nodeTypes = computed(() => {
    const types = {}
    nodeTypeConfigs.value.forEach(config => {
        const component = isMobile.value ? markRaw(MobileBlueprintNode) : componentForConfig(config)
        if (component) types[config.id] = component
    })
    return types
})
const edgeTypes = {
    boundaryBinding: markRaw(BoundaryBindingEdge)
}

const elements = ref([])
const desktopSyncReady = ref(!isMobile.value)
const selectedGraphNodeId = ref(null)
const {
    addEdges: addDesktopEdges,
    addNodes,
    onConnect,
    screenToFlowCoordinate,
    onNodesInitialized,
    updateNodeInternals,
    updateNode: updateDesktopNode,
    updateNodeData: updateDesktopNodeData,
    onNodeDrag,
    onNodeDragStop,
    isValidConnection,
    getNodes: desktopNodes,
    getEdges: desktopEdges,
    getViewport,
    setViewport,
    setElements: setDesktopElements,
    fitView
} = useVueFlow('desktop-blueprint-flow')
const mobileFlow = useVueFlow('mobile-blueprint-flow')
const mobileDisplayPositions = ref({})
const mobileProjection = computed(() => projectMobileBlueprint(elements.value, mobileDisplayPositions.value))
const mobileCanvasNodes = computed(() => mobileProjection.value.filter(item => !item.source).map(node => ({ ...node, selected: mobileMode.value === 'select' ? mobileSelectedIds.value.includes(node.id) : node.id === selectedGraphNodeId.value })))
const mobileCanvasEdges = computed(() => mobileProjection.value.filter(item => item.source))
const getNodes = computed(() => isMobile.value ? elements.value.filter(item => !item.source) : desktopNodes.value)
const getEdges = computed(() => isMobile.value ? elements.value.filter(item => item.source) : desktopEdges.value)

/** """桌面重新挂载完成后才接受其图状态，避免旧画布覆盖当前草稿。""" */
const acceptDesktopElements = value => {
    if (!isMobile.value && desktopSyncReady.value && pageActive.value) elements.value = value
}

/** """手机操作只修改原始图，独立画布的测量与临时坐标不参与保存。""" */
const updateNode = (id, patch) => {
    if (!isMobile.value) return updateDesktopNode(id, patch)
    const node = elements.value.find(item => !item.source && item.id === id)
    if (node) Object.assign(node, typeof patch === 'function' ? patch(node) : patch)
}
/** """更新原节点参数，并让手机投影重新读取显示数据。""" */
const updateNodeData = (id, patch) => {
    if (!isMobile.value) return updateDesktopNodeData(id, patch)
    const node = elements.value.find(item => !item.source && item.id === id)
    if (node) node.data = { ...node.data, ...patch }
}
/** """新增边始终写入业务图，手机投影只负责展示。""" */
const addEdges = edges => {
    if (!isMobile.value) return addDesktopEdges(edges)
    elements.value = [...elements.value, ...(Array.isArray(edges) ? edges : [edges])]
}

const getDataEdges = () => getEdges.value.filter(
    edge => edge.data?.relationKind !== 'boundary-binding'
)

const resolveBindingDisplay = (boundaryNode, graphNodes = elements.value) => {
    const binding = boundaryNode?.data?.boundaryBinding
    if (!binding?.bound_node_id) return null
    const targetNode = graphNodes.find(node => node.id === binding.bound_node_id)
    if (!targetNode) return null
    return buildBindingDisplay(
        boundaryNode,
        targetNode,
        (binding.port_mappings || []).map(mapping => mapping.target_port_id)
    )
}

const publicInterfaces = computed(() => {
    const graphNodes = elements.value.filter(element => !element.source)
    const graphEdges = elements.value.filter(element => (
        element.source && element.data?.relationKind !== 'boundary-binding'
    ))
    return graphNodes
        .filter(node => isBoundaryConfig(node.data?.config))
        .map(node => {
            const config = node.data.config
            const nameInput = (config.inputs || []).find(input => input.name === 'interface_name')
            const handleInput = (config.inputs || []).find(
                input => input.custom_props?.option_metadata
            )
            const direction = getBoundaryDirection(node)
            const selectedHandleId = handleInput ? node.data[handleInput.id] : ''
            const selectedHandle = (
                handleInput?.custom_props?.option_metadata?.[selectedHandleId]
            )
            const exposedHandles = getBoundaryExposedHandles(
                node,
                graphNodes,
                graphEdges
            )
            const handle = exposedHandles[0] || selectedHandle || null
            const bindingDisplay = resolveBindingDisplay(node)
            return {
                nodeId: node.id,
                name: nameInput ? node.data[nameInput.id] : '',
                direction,
                handleConfigId: handle?.handle_config_id || handle?.id || null,
                interfaceTypeId: handle?.interface_type_id
                    || handle?.id
                    || null,
                dataType: handle?.data_type || 'value',
                boundNodeId: node.data.boundaryBinding?.bound_node_id || null,
                bindingDisplay
            }
        })
})

const refreshBindingDerivedState = (rebuildRelations = true) => {
    const graphNodes = getNodes.value
    const graphEdges = getDataEdges()
    const kindsByTarget = collectBindingTargetKinds(graphNodes)
    const statesByTarget = resolveBindingTargetStates(graphNodes, graphEdges)
    const bindingIssues = validateBoundaryBindings(graphNodes, graphEdges)
    graphNodes
        .filter(node => !isBoundaryConfig(node.data?.config))
        .forEach(node => {
            const nextKinds = kindsByTarget[node.id] || []
            const currentKinds = node.data?.bindingTargetKinds || []
            const nextState = statesByTarget[node.id]
            const currentState = node.data?.bindingTargetState || null
            if (
                nextKinds.join('|') !== currentKinds.join('|')
                || JSON.stringify(nextState) !== JSON.stringify(currentState)
            ) {
                updateNodeData(node.id, {
                    bindingTargetKinds: nextKinds,
                    bindingTargetState: nextState
                })
            }
        })
    graphNodes
        .filter(node => isBoundaryConfig(node.data?.config))
        .forEach(node => {
            const nextDisplay = resolveBindingDisplay(node, graphNodes)
            const nextIssues = bindingIssues.filter(issue => issue.nodeId === node.id)
            if (
                JSON.stringify(nextDisplay) !== JSON.stringify(node.data?.bindingDisplay || null)
                || JSON.stringify(nextIssues) !== JSON.stringify(
                    node.data?.bindingValidationIssues || []
                )
            ) {
                updateNodeData(node.id, {
                    bindingDisplay: nextDisplay,
                    bindingValidationIssues: nextIssues
                })
            }
        })

    if (!rebuildRelations) return
    const relationEdges = buildBindingRelationEdges(graphNodes, statesByTarget)
    const currentRelationEdges = getEdges.value.filter(
        edge => edge.data?.relationKind === 'boundary-binding'
    )
    const relationSignature = edges => edges
        .map(edge => [
            edge.id,
            edge.source,
            edge.sourceHandle,
            edge.target,
            edge.targetHandle,
            edge.style?.stroke
        ].join(':'))
        .sort()
        .join('|')
    if (relationSignature(relationEdges) !== relationSignature(currentRelationEdges)) {
        elements.value = [
            ...elements.value.filter(
                element => element.data?.relationKind !== 'boundary-binding'
            ),
            ...relationEdges
        ]
    }
}

watch(
    () => JSON.stringify({
        nodes: elements.value
            .filter(element => !element.source)
            .map(node => ({
                id: node.id,
                definitionId: node.data?.config?.id,
                handles: (node.data?.config?.handles || []).map(handle => (
                    handle.port_id || handle.id
                ))
            }))
            .sort((left, right) => left.id.localeCompare(right.id)),
        bindings: elements.value
            .filter(element => !element.source && isBoundaryConfig(element.data?.config))
            .map(node => ({
                id: node.id,
                binding: node.data?.boundaryBinding || null
            }))
            .sort((left, right) => left.id.localeCompare(right.id)),
        edges: elements.value
            .filter(element => (
                element.source
                && element.data?.relationKind !== 'boundary-binding'
            ))
            .map(edge => ({
                id: edge.id,
                source: edge.source,
                sourceHandle: edge.sourceHandle,
                target: edge.target,
                targetHandle: edge.targetHandle
            }))
            .sort((left, right) => left.id.localeCompare(right.id))
    }),
    () => refreshBindingDerivedState(),
    { flush: 'post' }
)

const restoreBindingRelations = async () => {
    refreshBindingDerivedState(false)
    await nextTick()
    const relationNodeIds = getNodes.value
        .filter(node => (
            node.data?.boundaryBinding?.bound_node_id
            || node.data?.bindingTargetState?.relationCount > 0
        ))
        .map(node => node.id)
    if (relationNodeIds.length > 0 && !isMobile.value) {
        updateNodeInternals(relationNodeIds)
    }
    await nextTick()
    refreshBindingDerivedState()
}

const encapsulatedTargetNodes = computed(() => nodeTypeConfigs.value.filter(config => (
    config.node_kind === 'encapsulated'
    && config.source_blueprint_id === blueprintId.value
    && config.is_latest
)))
const selectedGraphNode = computed(() => (
    elements.value.find(element => !element.source && element.id === selectedGraphNodeId.value)
    || null
))
const selectedNodeConfig = computed(() => selectedGraphNode.value?.data?.config || null)
const selectedEncapsulatedUpgrade = computed(() => {
    const current = selectedNodeConfig.value
    if (current?.node_kind !== 'encapsulated' || !current.node_family_id) return null
    return nodeTypeConfigs.value
        .filter(config => (
            config.node_family_id === current.node_family_id
            && config.definition_version > current.definition_version
            && config.enabled
        ))
        .sort((left, right) => right.definition_version - left.definition_version)[0] || null
})

const upgradeSelectedEncapsulatedNode = () => {
    if (isMobile.value && (!canEdit.value || saving.value)) return
    const node = selectedGraphNode.value
    const oldConfig = selectedNodeConfig.value
    const newConfig = selectedEncapsulatedUpgrade.value
    if (!node || !oldConfig || !newConfig) return
    const newData = getDefaultData(newConfig)
    for (const oldInput of oldConfig.inputs || []) {
        const newInput = (newConfig.inputs || []).find(item => item.name === oldInput.name)
        if (newInput && node.data[oldInput.id] !== undefined) {
            newData[newInput.id] = node.data[oldInput.id]
        }
    }
    const newHandleByPort = Object.fromEntries(
        (newConfig.handles || []).map(handle => [handle.port_id || handle.id, handle])
    )
    const oldHandleById = Object.fromEntries(
        (oldConfig.handles || []).map(handle => [handle.id, handle])
    )
    elements.value = elements.value.map(element => {
        if (!element.source && element.id === node.id) {
            return {
                ...element,
                type: newConfig.id,
                data: {
                    ...newData,
                    interfacePortId: element.data.interfacePortId || null,
                    boundaryBinding: element.data.boundaryBinding || null
                }
            }
        }
        if (!element.source) return element
        const updated = { ...element }
        if (element.source === node.id) {
            const oldHandle = oldHandleById[element.sourceHandle]
            const replacement = newHandleByPort[oldHandle?.port_id || oldHandle?.id]
            if (replacement) updated.sourceHandle = replacement.id
        }
        if (element.target === node.id) {
            const oldHandle = oldHandleById[element.targetHandle]
            const replacement = newHandleByPort[oldHandle?.port_id || oldHandle?.id]
            if (replacement) updated.targetHandle = replacement.id
        }
        return updated
    })
    ElMessage.success(`封装节点已升级到 v${newConfig.definition_version}`)
}

const bindingDialogVisible = ref(false)
const pendingBoundaryNode = ref(null)
const pendingTargetNode = ref(null)
const pendingBindableHandles = ref([])
const pendingOutputBindingNodeId = ref(null)
const publishDialogVisible = ref(false)
const encapsulateDialogVisible = ref(false)
const publishing = ref(false)
const encapsulating = ref(false)

/**
 * 验证节点连接是否有效
 * 规则：
 * 1. source handle 只能连接 target handle
 * 2. target handle 默认只能接受一个上游连接，可由节点契约声明允许多连接
 * 3. 每个 source handle 可以连接多个下游 target handle
 * 4. handle 的传输类型和业务接口必须同时兼容
 */
isValidConnection.value = (connection) => {
    // 已有关系的画布水合不属于新建连接，不能因自身端口占用而被过滤。
    if (connection.id && elements.value.some(edge => edge.source && edge.id === connection.id && edge.source === connection.source && edge.target === connection.target && edge.sourceHandle === connection.sourceHandle && edge.targetHandle === connection.targetHandle)) return true
    // 1. 基础验证：节点是否存在
    const sourceNode = elements.value.find(el => el.id === connection.source)
    const targetNode = elements.value.find(el => el.id === connection.target)

    if (!sourceNode || !targetNode) return false
    if (connection.targetHandle === BINDING_TARGET_HANDLE_ID) {
        return (
            isBoundaryConfig(sourceNode.data?.config)
            && getBoundaryDirection(sourceNode) === 'input'
            && validateBindingCandidate(
                sourceNode,
                targetNode,
                getNodes.value,
                getDataEdges()
            ).valid
        )
    }
    if (connection.sourceHandle === BINDING_SOURCE_HANDLE_ID) {
        return (
            isBoundaryConfig(targetNode.data?.config)
            && getBoundaryDirection(targetNode) === 'output'
            && validateBindingCandidate(
                targetNode,
                sourceNode,
                getNodes.value,
                getDataEdges()
            ).valid
        )
    }
    if (
        isBindingProtocolHandle(connection.sourceHandle)
        || isBindingProtocolHandle(connection.targetHandle)
    ) {
        return false
    }
    if (
        sourceNode.data?.boundaryBinding
        || targetNode.data?.boundaryBinding
    ) {
        return false
    }

    // 2. 获取节点配置
    const sourceConfig = nodeTypeConfigs.value.find(c => c.id === sourceNode.type)
    const targetConfig = nodeTypeConfigs.value.find(c => c.id === targetNode.type)

    if (!sourceConfig || !targetConfig) return false

    // 3. 获取 handle 配置
    const sourceHandle = sourceConfig.handles.find(h => h.id === connection.sourceHandle)
    const targetHandle = targetConfig.handles.find(h => h.id === connection.targetHandle)

    if (!sourceHandle || !targetHandle) return false

    // 4. 类型验证：source 只能连接 target
    if (sourceHandle.type !== 'source' || targetHandle.type !== 'target') {
        return false
    }

    // 5. 完全相同的端口连接始终拒绝，多输入能力由节点契约声明
    const dataEdges = getDataEdges()
    if (isDuplicateHandleConnection(dataEdges, connection)) {
        return false
    }
    const existingConnection = dataEdges.find(el =>
        el.id !== connection.id &&
        el.target === connection.target && 
        el.targetHandle === connection.targetHandle
    )

    const allowsMultipleInputs = allowsMultipleHandleInputs(targetConfig, targetHandle)
    if (existingConnection && !allowsMultipleInputs) {
        return false // target handle 已有连接，不允许重复连接
    }

    // 6. 通配业务接口不能绕过 Value/Reference 传输类型校验
    return acceptsHandleDataType(sourceHandle, targetHandle)
        && areHandleInterfacesCompatible(sourceHandle, targetHandle)
}

const createNodeFromConfig = (configId, position) => {
    const config = nodeTypeConfigs.value.find(c => c.id === configId)
    if (!config) return null

    const data = getDefaultData(config)
    if (isBoundaryConfig(config)) {
        data.interfacePortId = globalThis.crypto?.randomUUID?.()
            || `interface-${Date.now()}-${Math.random().toString(16).slice(2)}`
        data.boundaryBinding = null
    }
    return {
        id: `node-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`,
        type: config.id,
        position: position,
        data
    }
}

// 左侧边栏调整
const { 
  sidebarWidth, 
  isResizing, 
  startResize: startLeftResize 
} = useSidebarResize(400, 150, 600, 'left')

// 右侧边栏调整
const { 
  sidebarWidth: rightSidebarWidth, 
  isResizing: isRightResizing, 
  startResize: startRightResize 
} = useSidebarResize(400, 300, 800, 'right')

// 行动表单数据
const actionFormRef = ref(null)
const actionForm = ref({
    title: '',
    version: '1.0.0',
    implementation_period: 0,
    description: '',
    target: '',
    default_scheduling_mode: 'barrier'
})

const actionFormRules = {
    title: [
        { required: true, message: '请输入行动标题', trigger: 'blur' }
    ],
    version: [
        { required: true, message: '请输入版本号', trigger: 'blur' }
    ],
    target: [
        { required: true, message: '请输入任务目标', trigger: 'blur' }
    ]
}

const isTemplate = ref(false)
const resourceConfigEnabled = ref(false)
const resourceData = ref({})
const templateParams = ref([])
const templateBindings = ref({})

const history = createBlueprintHistory()
const historyStatus = ref({ canUndo: false, canRedo: false })
const historyReady = ref(false)
const savedDraftSignature = ref('')
let historyTimer = null
let restoringDraft = false
let layoutBefore = null
let layoutProjectionBefore = null
const pendingConfirmations = new Set()
const draftSnapshot = computed(() => captureBlueprintDraft({ elements: elements.value, form: actionForm.value, template: isTemplate.value, params: templateParams.value, bindings: templateBindings.value, resource: resourceData.value, resourceEnabled: resourceConfigEnabled.value }))
const draftSignature = computed(() => JSON.stringify(draftSnapshot.value))
const draftDirty = computed(() => historyReady.value && draftSignature.value !== savedDraftSignature.value)
const mobileIssues = computed(() => {
    const issues = []
    for (const [field, label] of [['title', '蓝图标题'], ['version', '版本号'], ['target', '任务目标']]) {
        if (!String(actionForm.value[field] || '').trim()) issues.push({ message: `请填写${label}` })
    }
    return [...issues, ...collectBlueprintGraphIssues(elements.value.filter(item => !item.source), elements.value.filter(item => item.source && item.data?.relationKind !== 'boundary-binding'), publicInterfaces.value)]
})

/** """合并连续字段输入为一个撤销步骤，并刷新工具栏状态。""" */
const recordHistory = () => {
    clearTimeout(historyTimer)
    if (!historyReady.value || restoringDraft || layoutBefore || !pageActive.value) return
    history.commit(draftSnapshot.value)
    historyStatus.value = { canUndo: history.canUndo, canRedo: history.canRedo }
}
watch(draftSignature, () => {
    if (!historyReady.value || restoringDraft || layoutBefore) return
    clearTimeout(historyTimer)
    historyTimer = setTimeout(recordHistory, 350)
})

/** """恢复语义快照，保留手机浏览视口并重建派生绑定状态。""" */
const restoreHistory = async (direction) => {
    if (!canEdit.value || saving.value || layoutBefore || !pageActive.value) return
    recordHistory()
    const snapshot = history[direction]()
    if (!snapshot) return
    restoringDraft = true
    if (isMobile.value) {
        const positions = { ...mobileDisplayPositions.value }
        for (const restored of snapshot.elements.filter(item => !item.source)) {
            const previous = elements.value.find(item => !item.source && item.id === restored.id)
            const displayed = mobileCanvasNodes.value.find(item => item.id === restored.id)
            if (previous && displayed && (previous.position.x !== restored.position.x || previous.position.y !== restored.position.y)) positions[restored.id] = { x: displayed.position.x + restored.position.x - previous.position.x, y: displayed.position.y + restored.position.y - previous.position.y }
        }
        mobileDisplayPositions.value = positions
    }
    elements.value = snapshot.elements
    actionForm.value = snapshot.form
    isTemplate.value = snapshot.template
    templateParams.value = snapshot.params
    templateBindings.value = snapshot.bindings
    resourceData.value = snapshot.resource
    resourceConfigEnabled.value = snapshot.resourceEnabled
    if (!elements.value.some(node => node.id === selectedGraphNodeId.value)) selectedGraphNodeId.value = null
    await nextTick()
    await restoreBindingRelations()
    restoringDraft = false
    historyStatus.value = { canUndo: history.canUndo, canRedo: history.canRedo }
}

/** """手机拟合只改变浏览视口，保存仍使用已载入的桌面视口。""" */
const fitMobileGraph = async (all = false) => {
    const epoch = editorEpoch
    await nextTick()
    const focus = selectedGraphNodeId.value || mobileCanvasNodes.value[0]?.id
    if (isMobile.value && pageActive.value && epoch === editorEpoch) mobileFlow.fitView({ ...(all === true ? {} : { nodes: focus ? [focus] : [] }), padding: 0.2, minZoom: all === true ? 0.05 : 0.8, maxZoom: 1, duration: 0 })
}

/** """添加节点后转到参数编辑；默认坐标不重排任何已有节点。""" */
const addMobileNode = async (configId) => {
    if (!canEdit.value || saving.value || !pageActive.value || layoutBefore) return
    const config = nodeTypeConfigs.value.find(item => item.id === configId)
    if (!config?.enabled || !config.is_latest || config.rendererUnsupported) return
    recordHistory()
    const nodes = elements.value.filter(item => !item.source)
    const node = createNodeFromConfig(configId, { x: nodes.length ? Math.max(...nodes.map(item => item.position.x)) + 240 : 60, y: 100 })
    elements.value = [...elements.value, node]
    selectedGraphNodeId.value = node.id
    recordHistory()
    await nextTick()
    mobileEditorRef.value?.showFields()
}

/** """固定值字段通过原节点字段 ID 更新，不修改定义或模板绑定。""" */
const updateMobileField = (nodeId, { inputId, value }) => {
    if (!canEdit.value || saving.value || !pageActive.value) return
    const node = elements.value.find(item => !item.source && item.id === nodeId)
    if (!node?.data.config?.inputs?.some(input => input.id === inputId)) return
    updateNodeData(nodeId, { [inputId]: value })
}

/** """提交前重新校验两端口，防止向导打开后图已改变。""" */
const connectMobileNodes = (connection) => {
    if (!canEdit.value || saving.value || !pageActive.value) return
    const nodes = getNodes.value
    const issue = blueprintConnectionIssue(nodes, getDataEdges(), connection)
    if (issue || !isValidConnection.value(connection)) { ElMessage.warning(issue || '当前端口连接无效'); return }
    recordHistory()
    const handle = nodes.find(node => node.id === connection.source)?.data.config?.handles?.find(item => item.id === connection.sourceHandle)
    addEdges([{ ...connection, id: `edge-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`, style: { stroke: handle?.color || '#909399', strokeWidth: 3 } }])
    nextTick(recordHistory)
}

/** """公开 IO 向导使用既有候选校验和绑定对话框。""" */
const bindMobileNodes = ({ boundaryId, targetId }) => {
    if (!canEdit.value || saving.value || !pageActive.value) return
    const boundary = getNodes.value.find(node => node.id === boundaryId)
    const target = getNodes.value.find(node => node.id === targetId)
    if (boundary && target) openBoundaryBinding(boundary, target)
}

/** """数据边打开连接详情，派生边则定位所属公开 IO。""" */
const handleMobileEdgeClick = ({ edge }) => {
    if (edge.data?.relationKind === 'boundary-binding') {
        const boundary = getNodes.value.find(node => (node.id === edge.source || node.id === edge.target) && isBoundaryConfig(node.data.config))
        if (boundary) mobileEditorRef.value?.selectNode(boundary.id)
    } else mobileEditorRef.value?.openEdge(edge)
}

/** """记录移动前坐标，浏览和连线模式都不能直接拖动节点。""" */
const setMobileMode = (mode) => {
    if (mode !== 'browse' && (!canEdit.value || saving.value)) return
    if (mode === 'move' && !layoutBefore) {
        recordHistory()
        layoutBefore = new Map(getNodes.value.map(node => [node.id, { ...node.position }]))
        layoutProjectionBefore = Object.fromEntries(mobileCanvasNodes.value.map(node => [node.id, { ...node.position }]))
        mobileDisplayPositions.value = { ...layoutProjectionBefore }
    }
    mobileMode.value = mode
}
/** """拖动仅记录浏览投影，点击应用布局前不修改原坐标。""" */
const recordMobileDrag = ({ node }) => {
    if (!layoutBefore || !canEdit.value || saving.value || !pageActive.value || mobileMode.value !== 'move') return
    mobileDisplayPositions.value = { ...mobileDisplayPositions.value, [node.id]: { ...node.position } }
}
/** """取消尚未应用的位置变化，不触碰任何连接或参数。""" */
const cancelMobileLayout = () => {
    if (layoutProjectionBefore) mobileDisplayPositions.value = { ...layoutProjectionBefore }
    layoutBefore = null
    layoutProjectionBefore = null
    mobileMode.value = 'browse'
}
/** """明确应用移动后的坐标，再形成可撤销的布局操作。""" */
const applyMobileLayout = async () => {
    if (!canEdit.value || saving.value || !pageActive.value) { cancelMobileLayout(); return }
    if (layoutBefore && layoutProjectionBefore) for (const node of getNodes.value) {
        const original = layoutBefore.get(node.id), before = layoutProjectionBefore[node.id], after = mobileDisplayPositions.value[node.id]
        if (original && before && after) updateNode(node.id, { position: { x: original.x + after.x - before.x, y: original.y + after.y - before.y } })
    }
    layoutBefore = null
    layoutProjectionBefore = null
    mobileMode.value = 'browse'
    await nextTick()
    recordHistory()
}
/** """数值坐标编辑也只改变位置，不改变端口或业务连接。""" */
const moveMobileNode = async ({ nodeId, x, y }) => {
    if (!canEdit.value || saving.value || !pageActive.value || !Number.isFinite(x) || !Number.isFinite(y)) return
    const node = getNodes.value.find(item => item.id === nodeId)
    const display = mobileCanvasNodes.value.find(item => item.id === nodeId)
    if (!node || !display) return
    const original = layoutBefore?.get(nodeId) || node.position
    const projection = layoutProjectionBefore?.[nodeId] || display.position
    mobileDisplayPositions.value = { ...mobileDisplayPositions.value, [nodeId]: { x: projection.x + x - original.x, y: projection.y + y - original.y } }
    if (layoutBefore) return
    recordHistory()
    updateNode(nodeId, { position: { x, y } })
    await nextTick()
    recordHistory()
}

/** """多选统一平移只改变坐标，形成一次可撤销的布局操作。""" */
const moveMobileGroup = async ({ nodeIds, x, y }) => {
    if (!canEdit.value || saving.value || !pageActive.value || layoutBefore || !Number.isFinite(x) || !Number.isFinite(y)) return
    recordHistory()
    const positions = { ...mobileDisplayPositions.value }
    for (const node of getNodes.value.filter(item => nodeIds.includes(item.id))) {
        const display = mobileCanvasNodes.value.find(item => item.id === node.id)
        if (display) positions[node.id] = { x: display.position.x + x, y: display.position.y + y }
        updateNode(node.id, { position: { x: node.position.x + x, y: node.position.y + y } })
    }
    mobileDisplayPositions.value = positions
    await nextTick()
    recordHistory()
}

/**
 * 确认期间重新检查页面、权限与草稿，拒绝过期的移除操作。
 * @param {object} selection 待删除的节点或普通数据边。
 */
const removeMobileElements = async ({ nodeIds = [], edgeIds = [] }) => {
    if (!canEdit.value || saving.value || !pageActive.value || layoutBefore) return
    const epoch = editorEpoch, signature = draftSignature.value
    const ids = nodeIds.filter(id => elements.value.some(node => !node.source && node.id === id))
    const impact = blueprintRemovalImpact(elements.value, ids, edgeIds, templateBindings.value)
    if (!ids.length && !impact.edgeIds.length) return
    const token = Symbol()
    pendingConfirmations.add(token)
    try {
        await ElMessageBox.confirm(`将移除 ${ids.length} 个节点和 ${impact.edgeIds.length} 条数据连接；${impact.boundaryIds.length} 个 IO 将解除绑定，清理 ${impact.templateCount} 项模板字段绑定。其余 IO 端口覆盖会重新校验，可通过撤销恢复。`, '确认移除', { type: 'warning', confirmButtonText: '移除', cancelButtonText: '保留' })
        if (epoch !== editorEpoch || !pageActive.value || !canEdit.value || saving.value || signature !== draftSignature.value) return
        recordHistory()
        elements.value = elements.value.filter(item => !ids.includes(item.id) && !impact.edgeIds.includes(item.id) && item.data?.relationKind !== 'boundary-binding').map(item => impact.boundaryIds.includes(item.id) ? { ...item, data: { ...item.data, boundaryBinding: null, bindingDisplay: null } } : item)
        const bindings = { ...templateBindings.value }
        for (const id of ids) delete bindings[id]
        templateBindings.value = bindings
        if (ids.includes(selectedGraphNodeId.value)) selectedGraphNodeId.value = null
        await nextTick()
        recordHistory()
    } catch { /* 用户取消时保留完整草稿。 */ }
    finally { pendingConfirmations.delete(token) }
}

/** """解绑保留公开 IO 节点及稳定接口 ID，并可撤销。""" */
const confirmMobileUnbind = async (nodeId) => {
    if (!canEdit.value || saving.value || !pageActive.value) return
    const epoch = editorEpoch, signature = draftSignature.value, token = Symbol()
    pendingConfirmations.add(token)
    try {
        await ElMessageBox.confirm('解除替代关系后，公开 IO 节点仍然保留。保存前需检查接口类型和数据连接。', '解除 IO 绑定', { confirmButtonText: '解除绑定', cancelButtonText: '保留' })
        if (epoch !== editorEpoch || !pageActive.value || !canEdit.value || saving.value || signature !== draftSignature.value) return
        recordHistory()
        handleUnbindBoundary(nodeId)
        await nextTick()
        recordHistory()
    } catch { /* 取消不改变绑定。 */ }
    finally { pendingConfirmations.delete(token) }
}

provide('templateContext', {
    isTemplateMode: computed(() => isTemplate.value),
    availableParams: computed(() => templateParams.value),
    bindings: templateBindings,
    updateBinding: (nodeId, fieldName, paramName) => {
        if (isMobile.value && (!canEdit.value || saving.value || !pageActive.value)) return
        if (!templateBindings.value[nodeId]) {
            templateBindings.value[nodeId] = {}
        }
        if (paramName) {
            templateBindings.value[nodeId][fieldName] = paramName
        } else {
            delete templateBindings.value[nodeId][fieldName]
            if (Object.keys(templateBindings.value[nodeId]).length === 0) {
                delete templateBindings.value[nodeId]
            }
        }
    }
})

// 配置常量
const BASE_NODE_WIDTH = 300   // 节点组件的最小设计宽度
const MAX_NODE_WIDTH = 400    // 与 GenericNode 的最大宽度保持一致
const SIDEBAR_PADDING = 32    // p-4 * 2
const COMPACT_THRESHOLD = 240 // 低于此宽度切换为标题模式

// 是否处于紧凑模式
const isCompact = computed(() => sidebarWidth.value < COMPACT_THRESHOLD)

// 动态计算节点容器样式
const getNodeWrapperStyle = computed(() => {
    if (isCompact.value) {
        return { width: '100%', marginBottom: '0px' }
    }

    const availableWidth = sidebarWidth.value - SIDEBAR_PADDING

    //节点拉伸
    if (availableWidth >= BASE_NODE_WIDTH) {
        return {
            width: `${Math.min(availableWidth, MAX_NODE_WIDTH)}px`,
            transform: 'scale(1)',
            marginBottom: '0px'
        }
    }

    // 侧边栏介于 240px - 300px 之间需要缩放
    // 强制容器宽度为 300px 并整体缩小
    const scale = availableWidth / BASE_NODE_WIDTH
    const marginBottom = `-${(1 - scale) * 120}px` // 补偿缩放产生的底部空白

    return {
        width: `${BASE_NODE_WIDTH}px`, // 锁定渲染宽度，防止被压扁
        transform: `scale(${scale})`,
        marginBottom: marginBottom
    }
})

const resetEditor = () => {
    clearBindingCandidate()
    draggedSidebarBoundaryNode.value = null
    pendingOutputBindingNodeId.value = null
    actionForm.value = {
        title: '',
        version: '1.0.0',
        implementation_period: 0,
        description: '',
        target: '',
        default_scheduling_mode: 'barrier'
    }
    isTemplate.value = false
    resourceConfigEnabled.value = false
    resourceData.value = {}
    templateParams.value = []
    templateBindings.value = {}
    elements.value = []
    selectedGraphNodeId.value = null
}

const findNodeConfig = (node) => {
    const definitionId = node.data?.definition_id
    if (definitionId) {
        const definition = nodeTypeConfigs.value.find(config => config.id === definitionId)
        if (definition) return definition
    }

    const directMatch = nodeTypeConfigs.value.find(config => config.id === node.type)
    if (directMatch) return directMatch

    const candidates = nodeTypeConfigs.value.filter(config => config.type === node.type)
    if (candidates.length === 1) return candidates[0]

    const formDataKeys = Object.keys(node.data?.form_data || {})
    return candidates
        .map(config => ({
            config,
            matches: formDataKeys.filter(key =>
                (config.inputs || []).some(input => (input.name || input.id) === key)
            ).length
        }))
        .sort((left, right) => right.matches - left.matches)[0]?.config || null
}

const loadBlueprintForEdit = async (epoch = editorEpoch) => {
    if (!blueprintId.value) return
    const id = blueprintId.value

    loadingBlueprint.value = true
    try {
        const response = await actionApi.getBlueprint(id)
        if (epoch !== editorEpoch || !pageActive.value || !canLoad.value || id !== blueprintId.value) return false
        const blueprint = response.data
        if (response.code !== 0 || !blueprint) {
            throw new Error(response.message || '获取行动蓝图失败')
        }

        actionForm.value = {
            title: blueprint.name,
            version: blueprint.version,
            implementation_period: blueprint.implementation_period ?? 0,
            description: blueprint.description || '',
            target: blueprint.target,
            default_scheduling_mode: blueprint.default_scheduling_mode === 'streaming' ? 'streaming' : 'barrier'
        }
        isTemplate.value = Boolean(blueprint.is_template)
        templateParams.value = (blueprint.template?.params || []).map(param => ({ ...param }))
        templateBindings.value = JSON.parse(JSON.stringify(blueprint.template?.bindings || {}))
        resourceData.value = blueprint.resource ?? null
        resourceConfigEnabled.value = Boolean(
            blueprint.resource && Object.keys(blueprint.resource).length > 0
        )

        const processedNodes = (blueprint.graph?.nodes || []).map(node => {
            const config = findNodeConfig(node)
            if (!config) {
                throw new Error(`节点定义不存在，无法编辑：${node.data?.definition_id || node.type}`)
            }
            if (config.rendererUnsupported) {
                throw new Error(`当前前端不支持节点渲染器：${config.extension?.renderer_key || config.id}`)
            }

            const nodeData = getDefaultData(config)
            nodeData.interfacePortId = node.data?.interface_port_id || null
            nodeData.boundaryBinding = node.data?.boundary_binding || null
            for (const input of config.inputs || []) {
                const fieldName = input.name || input.id
                const value = node.data?.form_data?.[fieldName]
                if (value !== undefined && value !== null) {
                    nodeData[input.id] = normalizeDefaultValue(input.type, value)
                }
            }

            return {
                id: node.id,
                type: config.id,
                position: { ...node.position },
                data: nodeData,
                selected: false
            }
        })
        processedNodes.forEach(node => {
            if (isBoundaryConfig(node.data?.config)) {
                node.data.bindingDisplay = resolveBindingDisplay(node, processedNodes)
            }
        })

        const processedEdges = (blueprint.graph?.edges || []).map(edge => {
            const sourceNode = processedNodes.find(node => node.id === edge.source)
            const sourceHandle = sourceNode?.data?.config?.handles?.find(
                handle => handle.id === edge.sourceHandle || (edge.source_port_id && (handle.port_id || handle.id) === edge.source_port_id)
            )
            const targetHandle = processedNodes.find(node => node.id === edge.target)?.data?.config?.handles?.find(handle => handle.id === edge.targetHandle || (edge.target_port_id && (handle.port_id || handle.id) === edge.target_port_id))
            return {
                id: edge.id,
                source: edge.source,
                sourceHandle: sourceHandle?.id || edge.sourceHandle || edge.source_port_id,
                target: edge.target,
                targetHandle: targetHandle?.id || edge.targetHandle || edge.target_port_id,
                style: {
                    stroke: sourceHandle?.color || '#909399',
                    strokeWidth: 3
                }
            }
        })

        const { off: stopRestoreListener } = onNodesInitialized(() => {
            stopRestoreListener()
            if (epoch === editorEpoch && pageActive.value) restoreBindingRelations()
        })
        elements.value = [...processedNodes, ...processedEdges]
        await restoreBindingRelations()
        if (epoch !== editorEpoch || !pageActive.value || !canLoad.value) return false
        savedViewport.value = { ...(blueprint.graph?.viewport || { x: 0, y: 0, zoom: 1 }) }
        if (isMobile.value) await fitMobileGraph()
        else if (blueprint.graph?.viewport) setTimeout(() => { if (epoch === editorEpoch && pageActive.value && !isMobile.value) setViewport(blueprint.graph.viewport) }, 0)
        return true
    } catch (error) {
        if (epoch !== editorEpoch || !pageActive.value) return false
        console.error('加载行动蓝图失败:', error)
        if (!error?.code) {
            ElMessage.error(error.message || '加载行动蓝图失败')
        }
        editorError.value = error.message || '加载行动蓝图失败，请重试'
        return false
    } finally {
        if (epoch === editorEpoch) loadingBlueprint.value = false
    }
}

const initializeEditor = async () => {
    const epoch = ++editorEpoch
    historyReady.value = false
    clearTimeout(historyTimer)
    mobileEditorRef.value?.closeSheets()
    bindingDialogVisible.value = false
    editorError.value = ''
    saving.value = false
    savedViewport.value = { x: 0, y: 0, zoom: 1 }
    mobileDisplayPositions.value = {}
    layoutBefore = null
    layoutProjectionBefore = null
    mobileMode.value = 'browse'
    resetEditor()
    if (!pageActive.value || !canLoad.value) { editorError.value = '需要蓝图读取与节点读取权限才能载入编辑器'; return }
    if (!await fetchNodeConfigs() || epoch !== editorEpoch || !pageActive.value) return
    if (isEditMode.value) {
        if (!await loadBlueprintForEdit(epoch)) return
    }
    await nextTick()
    if (epoch !== editorEpoch || !pageActive.value) return
    history.reset(draftSnapshot.value)
    savedDraftSignature.value = draftSignature.value
    historyStatus.value = { canUndo: false, canRedo: false }
    historyReady.value = true
}

const handleBindingKeydown = (event) => {
    if (event.key === 'Escape') {
        pendingOutputBindingNodeId.value = null
        clearBindingCandidate()
    }
}

onMounted(() => {
    window.addEventListener('keydown', handleBindingKeydown)
    window.addEventListener('beforeunload', handleDraftBeforeUnload)
    initializeEditor()
})
onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleBindingKeydown)
    window.removeEventListener('beforeunload', handleDraftBeforeUnload)
    deactivateEditor()
})
watch(() => route.params.blueprintId, (id) => {
    if (createdBlueprintId.value && id === createdBlueprintId.value) return
    createdBlueprintId.value = null
    initializeEditor()
})

/** """离页先确认未保存草稿，不让保存中的请求悄悄切换目标。""" */
const confirmDraftLeave = async () => {
    if (saving.value || publishing.value || encapsulating.value) { ElMessage.warning('正在保存，请等待操作完成'); return false }
    if (!draftDirty.value && !layoutBefore && !localDraftSignature.value) return true
    const epoch = editorEpoch, signature = draftSignature.value, localSignature = localDraftSignature.value, token = Symbol()
    pendingConfirmations.add(token)
    try {
        await ElMessageBox.confirm('当前蓝图有未保存修改，离开将丢弃这些草稿。', '离开编辑器', { confirmButtonText: '丢弃并离开', cancelButtonText: '继续编辑', type: 'warning' })
        return epoch === editorEpoch && pageActive.value && signature === draftSignature.value && localSignature === localDraftSignature.value && !saving.value
    } catch { return false }
    finally { pendingConfirmations.delete(token) }
}
onBeforeRouteLeave(confirmDraftLeave)
onBeforeRouteUpdate((to, from) => to.params.blueprintId !== from.params.blueprintId ? confirmDraftLeave() : true)

/** """浏览器关闭提示只作用于当前编辑器的未保存草稿。""" */
const handleDraftBeforeUnload = event => {
    if (pageActive.value && (draftDirty.value || saving.value || layoutBefore || localDraftSignature.value)) { event.preventDefault(); event.returnValue = '' }
}
/** """失活时使请求与确认失效，关闭所有传送到 body 的面板。""" */
const deactivateEditor = () => {
    if (!pageActive.value) return
    pageActive.value = false
    editorEpoch++
    nodeRequest++
    clearTimeout(historyTimer)
    cancelMobileLayout()
    mobileEditorRef.value?.closeSheets()
    bindingDialogVisible.value = false
    publishDialogVisible.value = false
    encapsulateDialogVisible.value = false
    if (pendingConfirmations.size) { ElMessageBox.close(); pendingConfirmations.clear() }
}
onDeactivated(deactivateEditor)
onActivated(() => { if (!pageActive.value) { pageActive.value = true; if (!historyReady.value) initializeEditor() } })
watch(canLoad, allowed => {
    if (!allowed) {
        editorEpoch++
        nodeRequest++
        loadingBlueprint.value = false
        loadingNodeConfigs.value = false
        historyReady.value = false
        elements.value = []
        nodeTypeConfigs.value = []
        actionForm.value = { title: '', version: '1.0.0', target: '', description: '', implementation_period: 0, default_scheduling_mode: 'barrier' }
        templateParams.value = []
        templateBindings.value = {}
        resourceData.value = {}
        mobileEditorRef.value?.closeSheets()
        bindingDialogVisible.value = false
        editorError.value = '编辑器读取权限已撤销'
    } else if (pageActive.value && !historyReady.value) initializeEditor()
}, { flush: 'sync' })
watch(canEdit, allowed => {
    if (!allowed) {
        editorEpoch++
        saving.value = false
        publishing.value = false
        encapsulating.value = false
        loadingBlueprint.value = false
        loadingNodeConfigs.value = false
        cancelMobileLayout()
        mobileEditorRef.value?.closeSheets()
        bindingDialogVisible.value = false
        publishDialogVisible.value = false
        encapsulateDialogVisible.value = false
        if (pendingConfirmations.size) { ElMessageBox.close(); pendingConfirmations.clear() }
    } else if (pageActive.value && !historyReady.value && canLoad.value) initializeEditor()
}, { flush: 'sync' })
watch(isMobile, async (mobile, wasMobile) => {
    desktopSyncReady.value = false
    if (wasMobile) { cancelMobileLayout(); mobileEditorRef.value?.closeSheets() }
    else savedViewport.value = { ...getViewport() }
    if (!mobile) setDesktopElements(elements.value)
    await nextTick()
    if (mobile !== isMobile.value || !pageActive.value) return
    if (mobile) fitMobileGraph()
    else {
        setDesktopElements(elements.value)
        setViewport(savedViewport.value)
        desktopSyncReady.value = true
    }
}, { flush: 'sync' })


// 流程图逻辑
onConnect((params) => {
    const sourceNode = elements.value.find(el => el.id === params.source)
    const targetNode = elements.value.find(el => el.id === params.target)
    if (params.targetHandle === BINDING_TARGET_HANDLE_ID) {
        if (
            sourceNode
            && targetNode
            && isBoundaryConfig(sourceNode.data?.config)
            && getBoundaryDirection(sourceNode) === 'input'
        ) {
            openBoundaryBinding(sourceNode, targetNode)
        }
        return
    }
    if (params.sourceHandle === BINDING_SOURCE_HANDLE_ID) {
        if (
            sourceNode
            && targetNode
            && isBoundaryConfig(targetNode.data?.config)
            && getBoundaryDirection(targetNode) === 'output'
        ) {
            openBoundaryBinding(targetNode, sourceNode)
        }
        return
    }
    if (
        isBindingProtocolHandle(params.sourceHandle)
        || isBindingProtocolHandle(params.targetHandle)
    ) {
        ElMessage.warning('绑定 Handle 只能连接方向匹配的蓝图 IO 节点')
        return
    }
    if (
        sourceNode?.data?.boundaryBinding
        || targetNode?.data?.boundaryBinding
    ) {
        ElMessage.warning('已绑定 IO 节点不能创建普通数据边，请先解绑')
        return
    }
    if (!sourceNode) {
        addEdges(params)
        return
    }

    const sourceConfig = nodeTypeConfigs.value.find(c => c.id === sourceNode.type)
    if (!sourceConfig) {
        addEdges(params)
        return
    }

    const sourceHandle = sourceConfig.handles.find(h => h.id === params.sourceHandle)
    if (!sourceHandle) {
        addEdges(params)
        return
    }

    const edgeColor = sourceHandle.color || '#909399'

    const edgeWithStyle = {
        ...params,
        style: {
            stroke: edgeColor,
            strokeWidth: 3
        }
    }

    addEdges([edgeWithStyle])
})

const draggedSidebarBoundaryNode = ref(null)
const bindingCandidate = ref(null)

const clearBindingCandidate = () => {
    if (bindingCandidate.value) {
        updateNode(bindingCandidate.value.nodeId, {
            class: bindingCandidate.value.originalClass
        })
    }
    bindingCandidate.value = null
}

const setBindingCandidate = (boundaryNode, targetNode) => {
    const validation = validateBindingCandidate(
        boundaryNode,
        targetNode,
        getNodes.value,
        getDataEdges()
    )
    if (!validation.valid) {
        clearBindingCandidate()
        return
    }
    const direction = getBoundaryDirection(boundaryNode)
    if (
        bindingCandidate.value?.nodeId === targetNode.id
        && bindingCandidate.value?.direction === direction
    ) {
        return
    }
    clearBindingCandidate()
    const originalClass = targetNode.class
    const classList = Array.isArray(originalClass)
        ? [...originalClass]
        : originalClass ? [originalClass] : []
    updateNode(targetNode.id, {
        class: [
            ...classList,
            'boundary-binding-candidate',
            `boundary-binding-candidate-${direction}`
        ]
    })
    bindingCandidate.value = {
        nodeId: targetNode.id,
        direction,
        originalClass
    }
}

const onDragStart = (event, nodeType) => {
    clearBindingCandidate()
    if (event.dataTransfer) {
        event.dataTransfer.setData('application/vueflow', nodeType)
        event.dataTransfer.effectAllowed = 'move'
    }
    const config = nodeTypeConfigs.value.find(node => node.id === nodeType)
    draggedSidebarBoundaryNode.value = isBoundaryConfig(config)
        ? {
            id: 'sidebar-boundary-preview',
            data: getDefaultData(config)
        }
        : null
}

const onDragOver = (event) => {
    event.preventDefault()
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
    if (!draggedSidebarBoundaryNode.value) return
    setBindingCandidate(
        draggedSidebarBoundaryNode.value,
        findDropTargetNode(event.clientX, event.clientY)
    )
}

const findDropTargetNode = (clientX, clientY, excludedNodeId = null) => {
    const nodeElement = document
        .elementsFromPoint(clientX, clientY)
        .map(element => element.closest?.('.vue-flow__node'))
        .find(element => {
            const nodeId = element?.dataset?.id || element?.getAttribute?.('data-id')
            return nodeId && nodeId !== excludedNodeId
        })
    const nodeId = nodeElement?.dataset?.id || nodeElement?.getAttribute?.('data-id')
    return elements.value.find(element => !element.source && element.id === nodeId) || null
}

const openBoundaryBinding = (boundaryNode, targetNode) => {
    const validation = validateBindingCandidate(
        boundaryNode,
        targetNode,
        getNodes.value,
        getDataEdges()
    )
    if (!validation.valid) {
        ElMessage.warning(
            validation.issues[0]?.message || '当前节点不能建立该绑定关系'
        )
        return
    }
    pendingBoundaryNode.value = boundaryNode
    pendingTargetNode.value = targetNode
    pendingBindableHandles.value = validation.bindableHandles
    bindingDialogVisible.value = true
}

const startOutputBinding = (boundaryNodeId) => {
    const boundaryNode = getNodes.value.find(node => node.id === boundaryNodeId)
    if (
        !boundaryNode
        || !isBoundaryConfig(boundaryNode.data?.config)
        || getBoundaryDirection(boundaryNode) !== 'output'
    ) {
        return
    }
    const hasDataEdge = getDataEdges().some(
        edge => edge.source === boundaryNodeId || edge.target === boundaryNodeId
    )
    if (hasDataEdge) {
        ElMessage.warning('IO 节点已有普通数据连线，请先删除连线再建立绑定')
        return
    }
    pendingOutputBindingNodeId.value = boundaryNodeId
    ElMessage.info('请选择结束节点顶部的绑定 Handle')
}

const selectBindingTarget = (targetNodeId) => {
    if (!pendingOutputBindingNodeId.value) return
    const boundaryNode = getNodes.value.find(
        node => node.id === pendingOutputBindingNodeId.value
    )
    const targetNode = getNodes.value.find(node => node.id === targetNodeId)
    pendingOutputBindingNodeId.value = null
    if (boundaryNode && targetNode) {
        openBoundaryBinding(boundaryNode, targetNode)
    }
}

const handlePaneClick = () => {
    selectedGraphNodeId.value = null
    pendingOutputBindingNodeId.value = null
}

provide('boundaryBindingController', {
    startOutputBinding,
    selectBindingTarget
})

const onDrop = (event) => {
    event.preventDefault()
    const nodeKey = event.dataTransfer?.getData('application/vueflow')
    if (nodeKey) {
        const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
        const newNode = createNodeFromConfig(nodeKey, position)
        if (!newNode) return
        const candidateNodeId = bindingCandidate.value?.nodeId
        const targetNode = elements.value.find(element => element.id === candidateNodeId)
            || findDropTargetNode(event.clientX, event.clientY)
        clearBindingCandidate()
        draggedSidebarBoundaryNode.value = null
        const { off } = onNodesInitialized(() => {
            updateNode(newNode.id, (node) => ({
                position: {
                    x: node.position.x - node.dimensions.width / 2,
                    y: node.position.y - node.dimensions.height / 2
                },
            }))
            off()
        })
        addNodes([newNode])
        if (isBoundaryConfig(newNode.data?.config) && targetNode) {
            openBoundaryBinding(newNode, targetNode)
        }
    }
}

onNodeDrag(({ event, node }) => {
    if (isMobile.value) return
    if (isBoundaryConfig(node?.data?.config)) {
        setBindingCandidate(
            node,
            event ? findDropTargetNode(event.clientX, event.clientY, node.id) : null
        )
    }
})

onNodeDragStop(({ event, node }) => {
    if (isMobile.value) return
    if (!isBoundaryConfig(node?.data?.config)) return
    const candidateNodeId = bindingCandidate.value?.nodeId
    const targetNode = elements.value.find(element => element.id === candidateNodeId)
        || (
            event
                ? findDropTargetNode(event.clientX, event.clientY, node.id)
                : null
        )
    clearBindingCandidate()
    if (targetNode) {
        openBoundaryBinding(node, targetNode)
    }
})

const handleConfirmBinding = (binding) => {
    if (isMobile.value && (!canEdit.value || saving.value || !pageActive.value)) return
    const boundaryNode = pendingBoundaryNode.value
    const targetNode = pendingTargetNode.value
    if (!boundaryNode || !targetNode) return
    const candidate = validateBindingCandidate(boundaryNode, targetNode, getNodes.value, getDataEdges())
    if (!candidate.valid || !binding.interfaceName?.trim() || binding.interfacePortId !== boundaryNode.data.interfacePortId || !binding.targetPortIds?.length || binding.targetPortIds.some(id => !candidate.bindableHandles.some(handle => (handle.port_id || handle.id) === id))) { ElMessage.warning('绑定目标或端口已变化，请重新选择'); return }
    if (isMobile.value) recordHistory()
    const nameInput = (boundaryNode.data?.config?.inputs || []).find(
        input => input.name === 'interface_name'
    )
    const previousTargetId = boundaryNode.data?.boundaryBinding?.bound_node_id
    const boundaryBinding = {
        bound_node_id: targetNode.id,
        port_mappings: binding.targetPortIds.map(targetPortId => ({
            interface_port_id: binding.interfacePortId,
            target_port_id: targetPortId
        }))
    }
    updateNodeData(boundaryNode.id, {
        ...(nameInput ? { [nameInput.id]: binding.interfaceName } : {}),
        boundaryBinding,
        bindingDisplay: buildBindingDisplay(
            boundaryNode,
            targetNode,
            binding.targetPortIds
        )
    })
    if (previousTargetId !== targetNode.id) {
        const direction = getBoundaryDirection(boundaryNode)
        const siblingCount = getNodes.value.filter(node => (
            node.id !== boundaryNode.id
            && isBoundaryConfig(node.data?.config)
            && getBoundaryDirection(node) === direction
            && node.data?.boundaryBinding?.bound_node_id === targetNode.id
        )).length
        const position = getBoundaryInitialPosition(boundaryNode, targetNode)
        const boundaryWidth = boundaryNode?.dimensions?.width || 300
        position.x += (
            direction === 'input' ? -1 : 1
        ) * siblingCount * (boundaryWidth + 20)
        updateNode(boundaryNode.id, { position })
    }
    pendingBoundaryNode.value = null
    pendingTargetNode.value = null
    pendingBindableHandles.value = []
    if (isMobile.value) nextTick(recordHistory)
}

const handleCancelBinding = () => {
    pendingBoundaryNode.value = null
    pendingTargetNode.value = null
    pendingBindableHandles.value = []
}

const handleUnbindBoundary = (nodeId) => {
    updateNodeData(nodeId, {
        boundaryBinding: null,
        bindingDisplay: null
    })
    ElMessage.success('边界节点已解绑，将作为独立公开接口保留')
}

const persistBlueprint = async ({ navigate = true, notify = true } = {}) => {
    /** 校验并保存当前编辑器草稿，可供发布和封装流程复用。 */
    if (saving.value || !canEdit.value || !pageActive.value || editorError.value || loadingBlueprint.value || loadingNodeConfigs.value || layoutBefore) return false
    if (localDraftSignature.value) { ElMessage.warning('请先应用或取消当前面板中的修改，再保存蓝图'); return false }
    const epoch = editorEpoch
    const targetId = blueprintId.value
    const editing = Boolean(targetId)
    saving.value = true
    try {

    if (isMobile.value) {
        if (mobileIssues.value.length) { mobileEditorRef.value?.showIssues(); return false }
    } else {
        try {
            if (!actionFormRef.value) return false
            await actionFormRef.value.validate()
        } catch { return false }
    }
    if (epoch !== editorEpoch || !canEdit.value || !pageActive.value || targetId !== blueprintId.value) return false

    const nodes = getNodes.value
    const edges = getDataEdges()
    const viewport = isMobile.value ? savedViewport.value : getViewport()

    if (!nodes || nodes.length === 0) {
        ElMessage.error('请至少添加一个节点')
        return false
    }
    const unsupportedNode = nodes.find(node => node.data?.config?.rendererUnsupported)
    if (unsupportedNode) {
        ElMessage.error('蓝图包含当前前端不支持的原生节点版本，无法保存')
        return false
    }
    const bindingIssues = validateBoundaryBindings(nodes, edges)
    if (bindingIssues.length > 0) {
        selectedGraphNodeId.value = bindingIssues[0].nodeId || null
        ElMessage.error(bindingIssues[0].message)
        return false
    }
    const unnamedInterface = publicInterfaces.value.find(port => !port.name?.trim())
    if (unnamedInterface) {
        ElMessage.error('蓝图输入和输出节点必须填写接口名称')
        return false
    }
    const unresolvedInterface = publicInterfaces.value.find(
        port => !port.handleConfigId || !port.interfaceTypeId
    )
    if (unresolvedInterface) {
        selectedGraphNodeId.value = unresolvedInterface.nodeId
        ElMessage.error('未绑定且没有数据连线的 IO 节点必须选择接口类型')
        return false
    }
    for (const direction of ['input', 'output']) {
        const names = publicInterfaces.value
            .filter(port => port.direction === direction)
            .map(port => port.name.trim())
        if (names.length !== new Set(names).size) {
            ElMessage.error(`${direction === 'input' ? '输入' : '输出'}接口名称不能重复`)
            return false
        }
    }

    const processedNodes = nodes.map(node => {
        const config = node.data?.config
        if (!config) {
            return null
        }

        const formData = {}
        if (config.inputs && config.inputs.length > 0) {
            config.inputs.forEach(input => {
                formData[input.name] = node.data[input.id]
            })
        }

        return {
            id: node.id,
            type: config.type,
            position: {
                x: node.position.x,
                y: node.position.y
            },
            data: {
                definition_id: config.id,
                version: config.version,
                form_data: formData,
                node_definition_version: config.definition_version || 1,
                instance_config: formData,
                interface_port_id: node.data.interfacePortId || null,
                boundary_binding: node.data.boundaryBinding || null
            }
        }
    }).filter(node => node !== null)

    const processedEdges = edges.map(edge => {
        const sourceNode = nodes.find(node => node.id === edge.source)
        const targetNode = nodes.find(node => node.id === edge.target)
        const sourceHandle = sourceNode?.data?.config?.handles?.find(
            handle => handle.id === edge.sourceHandle
        )
        const targetHandle = targetNode?.data?.config?.handles?.find(
            handle => handle.id === edge.targetHandle
        )
        return {
            id: edge.id,
            source: edge.source,
            sourceHandle: edge.sourceHandle,
            source_port_id: sourceHandle?.port_id || edge.sourceHandle,
            target: edge.target,
            targetHandle: edge.targetHandle,
            target_port_id: targetHandle?.port_id || edge.targetHandle
        }
    })

    const actionData = {
        name: actionForm.value.title,
        version: actionForm.value.version,
        description: actionForm.value.description || '',
        target: actionForm.value.target,
        implementation_period: actionForm.value.implementation_period,
        default_scheduling_mode: actionForm.value.default_scheduling_mode === 'streaming' ? 'streaming' : 'barrier',
        resource: isEditMode.value ? resourceData.value : {},
        is_template: isTemplate.value,
        ...(isTemplate.value && {
            template: {
                params: templateParams.value.map(p => ({
                    id: p.id || p.name,
                    name: p.name,
                    type: p.type,
                    label: p.label,
                    required: p.required,
                    description: p.description,
                    default: p.default ?? null,
                    options: p.options || [],
                    validation: p.validation || {}
                })),
                bindings: templateBindings.value
            }
        }),
        graph: {
            nodes: processedNodes,
            edges: processedEdges,
            viewport: {
                x: viewport.x,
                y: viewport.y,
                zoom: viewport.zoom
            }
        }
    }

    const submittedSignature = draftSignature.value
    recordHistory()
    try {
        const payload = JSON.parse(JSON.stringify(actionData))
        const response = editing
            ? await actionApi.updateActionBlueprint(targetId, payload)
            : await actionApi.createActionBlueprint(payload)
        if (epoch !== editorEpoch || !pageActive.value || !canEdit.value || targetId !== blueprintId.value) return false

        if (response.code !== 0) {
            ElMessage.error(response.message || `${isEditMode.value ? '更新' : '新增'}行动蓝图失败`)
            return false
        }
        savedDraftSignature.value = submittedSignature
        savedViewport.value = { ...viewport }
        if (!editing && response.data?.id) createdBlueprintId.value = response.data.id

        if (notify) {
            ElMessage.success(isEditMode.value ? '行动蓝图更新成功' : '新增行动蓝图成功')
        }
        const disabledSchedules = response.data?.disabled_schedules || []
        if (disabledSchedules.length > 0) {
            ElNotification({
                title: '部分调度计划已停用',
                message: disabledSchedules
                    .map(schedule => `${schedule.name}：${schedule.reason}`)
                    .join('；'),
                type: 'warning',
                duration: 0
            })
        }
        if (navigate && !draftDirty.value) {
            saving.value = false
            await router.push('/action/blueprints')
        }
        return true
    } catch (error) {
        console.error(`${isEditMode.value ? '更新' : '新增'}行动蓝图失败:`, error)
        if (epoch === editorEpoch && pageActive.value) ElMessage.error('保存失败，草稿已保留，请检查后重试')
        return false
    }
    } finally { if (epoch === editorEpoch) saving.value = false }
}

const handleSaveAction = () => persistBlueprint({ navigate: !isMobile.value })

const handlePublishBlueprint = async () => {
    if (!blueprintId.value || publishing.value || !canEdit.value || !hasPerm(PERM.operations.action.blueprint.publish) || !pageActive.value) return
    const epoch = editorEpoch, id = blueprintId.value
    publishing.value = true
    try {
        if (!await persistBlueprint({ navigate: false, notify: false })) {
            return
        }
        if (epoch !== editorEpoch || !pageActive.value || !canEdit.value || !hasPerm(PERM.operations.action.blueprint.publish)) return
        const response = await actionApi.publishBlueprint(id)
        if (epoch !== editorEpoch || !pageActive.value || !hasPerm(PERM.operations.action.blueprint.publish)) return
        if (response.code !== 0) {
            ElMessage.error(response.message || '发布蓝图版本失败')
            return
        }
        publishDialogVisible.value = false
        ElMessage.success(`已发布 Revision ${response.data?.revision?.revision_number || ''}`)
    } catch (error) {
        console.error('发布蓝图版本失败:', error)
    } finally {
        publishing.value = false
    }
}

const handleEncapsulateBlueprint = async (payload) => {
    if (!blueprintId.value || encapsulating.value || !canEdit.value || !canEncapsulate.value || !pageActive.value) return
    const epoch = editorEpoch, id = blueprintId.value
    encapsulating.value = true
    try {
        if (!await persistBlueprint({ navigate: false, notify: false })) {
            return
        }
        if (epoch !== editorEpoch || !pageActive.value || !canEdit.value || !canEncapsulate.value) return
        const response = await actionApi.encapsulateBlueprint(id, payload)
        if (epoch !== editorEpoch || !pageActive.value || !canEncapsulate.value) return
        if (response.code !== 0) {
            ElMessage.error(response.message || '封装蓝图失败')
            return
        }
        encapsulateDialogVisible.value = false
        ElMessage.success('蓝图已封装为节点，可在其他蓝图中使用')
        await fetchNodeConfigs()
    } catch (error) {
        console.error('封装蓝图失败:', error)
    } finally {
        encapsulating.value = false
    }
}
</script>

<style scoped>
.mobile-blueprint-page { height: calc(var(--mobile-viewport-height, 100dvh) - var(--mobile-header-height, 56px) - var(--mobile-nav-height, 64px)); min-height: 0; overflow: hidden; }
:global(.mobile-keyboard-open) .mobile-blueprint-page { height: calc(var(--mobile-viewport-height, 100dvh) - var(--mobile-header-height, 56px)); }
:deep(.vue-flow__node.boundary-binding-candidate) {
    z-index: 1000 !important;
}

:deep(.vue-flow__node.boundary-binding-candidate .generic-node) {
    transform: translateY(-2px);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}

:deep(.vue-flow__node.boundary-binding-candidate-input .generic-node) {
    box-shadow: 0 0 0 3px rgb(96 165 250 / 65%), 0 12px 28px rgb(37 99 235 / 20%);
}

:deep(.vue-flow__node.boundary-binding-candidate-output .generic-node) {
    box-shadow: 0 0 0 3px rgb(167 139 250 / 65%), 0 12px 28px rgb(124 58 237 / 20%);
}

:deep(.vue-flow__node.boundary-binding-candidate::after) {
    position: absolute;
    top: -36px;
    left: 50%;
    z-index: 20;
    width: max-content;
    max-width: 240px;
    transform: translateX(-50%);
    border-radius: 9999px;
    padding: 6px 12px;
    color: white;
    font-size: 12px;
    font-weight: 500;
    pointer-events: none;
}

:deep(.vue-flow__node.boundary-binding-candidate-input::after) {
    background: #2563eb;
    content: '松开以绑定蓝图输入';
}

:deep(.vue-flow__node.boundary-binding-candidate-output::after) {
    background: #7c3aed;
    content: '松开以绑定蓝图输出';
}
</style>
