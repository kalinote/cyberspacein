<template>
    <div
        data-article-detail-workbench
        class="article-detail-workbench w-full overflow-hidden"
        :class="constrainHeight ? 'h-full max-h-full min-h-0' : isMobile ? 'mobile-reading-workbench' : 'min-h-120'"
    >
        <Splitpanes
            v-if="isLgUp"
            class="default-theme article-detail-splitpanes h-full max-h-full min-h-0"
            @resized="onHorizontalResized"
        >
            <Pane :size="sizes.horizontal[0]" :min-size="12">
                <div
                    data-marking-sidebar
                    class="flex h-full min-h-0 flex-col overflow-hidden p-1"
                >
                    <MarkingSidebar
                        class="h-full min-h-0"
                        :sorted-markings="sortedMarkings"
                        :active-marking-id="activeMarkingId"
                        @update="(id, content) => emit('marking-update', id, content)"
                        @delete="(id) => emit('marking-delete', id)"
                        @hover="(id) => emit('marking-hover', id)"
                    />
                </div>
            </Pane>

            <Pane :size="sizes.horizontal[1]" :min-size="28">
                <Splitpanes
                    horizontal
                    class="default-theme article-detail-splitpanes article-detail-splitpanes--vertical h-full"
                    @resized="onCenterVerticalResized"
                >
                    <Pane :size="sizes.centerVertical[0]" :min-size="25">
                        <div class="relative marking-container flex h-full min-h-0 flex-col overflow-hidden p-1">
                            <slot name="center-top" />
                        </div>
                    </Pane>
                    <Pane :size="sizes.centerVertical[1]" :min-size="15">
                        <div class="flex h-full min-h-0 flex-col overflow-hidden p-1">
                            <slot name="center-bottom" />
                        </div>
                    </Pane>
                </Splitpanes>
            </Pane>

            <Pane :size="sizes.horizontal[2]" :min-size="18">
                <div class="h-full min-h-0 flex min-w-0 gap-0 overflow-hidden p-1">
                    <slot name="right" />
                </div>
            </Pane>
        </Splitpanes>

        <div v-else-if="isMobile" class="mobile-reading-layout">
            <div class="relative marking-container min-w-0">
                <slot name="center-top" />
            </div>
            <nav class="mobile-reading-tools" aria-label="材料补充信息">
                <button type="button" aria-haspopup="dialog" :aria-expanded="mobilePanel === 'analysis'" @click="emit('update:mobilePanel', 'analysis')"><Icon icon="mdi:brain" /> 分析与研判</button>
                <button type="button" aria-haspopup="dialog" :aria-expanded="mobilePanel === 'markings'" @click="emit('update:mobilePanel', 'markings')"><Icon icon="mdi:comment-text-outline" /> 批注 {{ sortedMarkings.length }}</button>
                <button type="button" aria-haspopup="dialog" :aria-expanded="mobilePanel === 'versions'" @click="emit('update:mobilePanel', 'versions')"><Icon icon="mdi:history" /> 版本与附件</button>
            </nav>
            <MobileSheet :model-value="mobilePanel === 'analysis'" title="分析与研判" @update:model-value="!$event && emit('update:mobilePanel', '')">
                <div class="mobile-analysis-sheet"><slot name="right" /></div>
            </MobileSheet>
            <MobileSheet :model-value="mobilePanel === 'markings'" title="正文批注" @update:model-value="!$event && emit('update:mobilePanel', '')">
                <div data-marking-sidebar>
                    <MarkingSidebar
                        :sorted-markings="sortedMarkings"
                        :active-marking-id="activeMarkingId"
                        @update="(id, content) => emit('marking-update', id, content)"
                        @delete="(id) => emit('marking-delete', id)"
                        @hover="(id, hovering) => emit('marking-hover', id, hovering)"
                    />
                </div>
            </MobileSheet>
            <MobileSheet :model-value="mobilePanel === 'versions'" title="版本与补充资料" @update:model-value="!$event && emit('update:mobilePanel', '')">
                <div class="mobile-version-sheet"><slot name="center-bottom" /></div>
            </MobileSheet>
        </div>

        <div v-else class="grid grid-cols-1 gap-4">
            <div data-marking-sidebar class="min-w-0">
                <MarkingSidebar
                    class="h-full"
                    :sorted-markings="sortedMarkings"
                    :active-marking-id="activeMarkingId"
                    @update="(id, content) => emit('marking-update', id, content)"
                    @delete="(id) => emit('marking-delete', id)"
                    @hover="(id) => emit('marking-hover', id)"
                />
            </div>
            <div class="relative marking-container min-w-0 space-y-6">
                <slot name="center-top" />
                <slot name="center-bottom" />
            </div>
            <div class="min-w-0">
                <slot name="right" />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import MarkingSidebar from '@/components/marking/MarkingSidebar.vue'
import { useMinLg } from '@/composables/useMinLg'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import {
    ARTICLE_DETAIL_PANE_DEFAULTS,
    ARTICLE_DETAIL_PANE_STORAGE_KEY,
    loadPaneSizes,
    savePaneSizes,
    paneSizesFromResizedPayload,
} from '@/utils/useSplitpanesPersistence'

const props = defineProps({
    mobilePanel: { type: String, default: '' },
    sortedMarkings: {
        type: Array,
        default: () => [],
    },
    activeMarkingId: {
        type: String,
        default: null,
    },
    /** 大屏下由父级传入视口剩余高度，限制 splitpanes 不随内容撑开 */
    constrainHeight: {
        type: Boolean,
        default: false,
    },
    paneStorageKey: {
        type: String,
        default: ARTICLE_DETAIL_PANE_STORAGE_KEY,
    },
    paneDefaults: {
        type: Object,
        default: () => ARTICLE_DETAIL_PANE_DEFAULTS,
    },
})

const emit = defineEmits([
    'marking-update',
    'marking-delete',
    'marking-hover',
    'pane-resized',
    'update:mobilePanel',
])

const { isLgUp } = useMinLg()
const { isMobile } = useMobileViewport()
const sizes = ref(loadPaneSizes(props.paneStorageKey, props.paneDefaults))

let saveTimer = null

function debouncedSave() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
        savePaneSizes(props.paneStorageKey, sizes.value)
    }, 150)
}

function onHorizontalResized(payload) {
    const next = paneSizesFromResizedPayload(payload, 3)
    if (next) {
        sizes.value = { ...sizes.value, horizontal: next }
        debouncedSave()
    }
    emit('pane-resized')
}

function onCenterVerticalResized(payload) {
    const next = paneSizesFromResizedPayload(payload, 2)
    if (next) {
        sizes.value = { ...sizes.value, centerVertical: next }
        debouncedSave()
    }
    emit('pane-resized')
}

onUnmounted(() => {
    if (saveTimer) clearTimeout(saveTimer)
})
</script>

<style scoped>
.mobile-reading-layout { display: flex; flex-direction: column; }
.mobile-reading-tools { order: -1; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; padding: 0 16px 12px; background: #fff; }
.mobile-reading-tools button { display: flex; align-items: center; justify-content: center; gap: 4px; min-height: 44px; border: 1px solid #e2e8f0; border-radius: 10px; color: #475569; font-size: 12px; }
.mobile-analysis-sheet { height: min(70dvh, 700px); min-height: 280px; }
.mobile-version-sheet { min-width: 0; overflow-x: hidden; }
.mobile-version-sheet :deep(.p-6) { padding: 16px; }
.mobile-version-sheet :deep(.space-x-4) { flex-wrap: wrap; gap: 12px; }
@media (max-width: 767px) {
    .mobile-analysis-sheet :deep(.detail-right-panels) { flex-direction: column-reverse; gap: 12px; }
    .mobile-analysis-sheet :deep(.detail-right-panel-content) { border: 0; border-radius: 0; }
}

.article-detail-workbench :deep(.splitpanes) {
    height: 100%;
    max-height: 100%;
}

.article-detail-workbench :deep(.default-theme.splitpanes .splitpanes__pane) {
    background-color: transparent;
}

.article-detail-workbench :deep(.splitpanes__pane) {
    overflow: hidden;
}

/* 对齐 splitpanes 官方 default-theme：窄白条 + 双竖线/双横线把手 */
.article-detail-workbench :deep(.splitpanes__splitter) {
    box-sizing: border-box;
    flex-shrink: 0;
    position: relative;
    background-color: rgb(249 250 251);
}

.article-detail-workbench :deep(.splitpanes--vertical > .splitpanes__splitter) {
    width: 7px;
    min-width: 7px;
    margin-left: -1px;
    border-left: 1px solid rgb(243 244 246);
    cursor: col-resize;
}

.article-detail-workbench :deep(.splitpanes--horizontal > .splitpanes__splitter) {
    height: 7px;
    min-height: 7px;
    margin-top: -1px;
    border-top: 1px solid rgb(243 244 246);
    cursor: row-resize;
}

.article-detail-workbench :deep(.splitpanes__splitter::before),
.article-detail-workbench :deep(.splitpanes__splitter::after) {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    background-color: rgb(0 0 0 / 0.15);
    transition: background-color 0.2s;
}

.article-detail-workbench :deep(.splitpanes--vertical > .splitpanes__splitter::before),
.article-detail-workbench :deep(.splitpanes--vertical > .splitpanes__splitter::after) {
    width: 1px;
    height: 30px;
    transform: translateY(-50%);
}

.article-detail-workbench :deep(.splitpanes--vertical > .splitpanes__splitter::before) {
    margin-left: -2px;
}

.article-detail-workbench :deep(.splitpanes--vertical > .splitpanes__splitter::after) {
    margin-left: 1px;
}

.article-detail-workbench :deep(.splitpanes--horizontal > .splitpanes__splitter::before),
.article-detail-workbench :deep(.splitpanes--horizontal > .splitpanes__splitter::after) {
    width: 30px;
    height: 1px;
    transform: translateX(-50%);
}

.article-detail-workbench :deep(.splitpanes--horizontal > .splitpanes__splitter::before) {
    margin-top: -2px;
}

.article-detail-workbench :deep(.splitpanes--horizontal > .splitpanes__splitter::after) {
    margin-top: 1px;
}

.article-detail-workbench :deep(.splitpanes__splitter:hover::before),
.article-detail-workbench :deep(.splitpanes__splitter:hover::after) {
    background-color: rgb(0 0 0 / 0.28);
}

.article-detail-workbench :deep(.splitpanes__splitter:focus-visible) {
    outline: 2px solid rgb(59 130 246);
    outline-offset: -2px;
}
</style>
