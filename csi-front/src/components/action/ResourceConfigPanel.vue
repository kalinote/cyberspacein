<template>
    <div
        class="resource-config-panel relative group flex flex-col"
        :class="showTopDivider ? 'border-t border-gray-200' : ''"
    >
        <section v-if="isMobile" class="mobile-blueprint-resources"><Icon icon="mdi:cog-outline" /><h3>资源配置</h3><p>此蓝图尚无独立的资源配置项。</p><p>节点使用的参数可在节点详情中维护。</p></section>
        <template v-else>
        <div
            class="flex items-center justify-between py-3 px-2 cursor-pointer hover:bg-gray-50 shrink-0"
            @click="collapsed = !collapsed"
        >
            <div class="flex items-center gap-2">
                <Icon
                    :icon="collapsed ? 'mdi:chevron-right' : 'mdi:chevron-down'"
                    class="text-gray-500 text-lg transition-transform"
                />
                <span class="text-sm font-semibold text-gray-800">资源配置</span>
            </div>
        </div>

        <div v-show="!collapsed" class="px-2 pb-4 overflow-y-auto max-h-60">
            <div class="text-center py-8 text-gray-400">
                <Icon icon="mdi:cog-outline" class="text-4xl mb-2 block mx-auto" />
                <p class="text-sm">暂无资源配置</p>
                <p class="text-xs mt-1">具体编辑能力将后续提供</p>
            </div>
        </div>
        </template>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
const { isMobile } = useMobileViewport()

defineProps({
    /** 为 true 时在顶部绘制分割线（接在模板参数等其它折叠块下方时） */
    showTopDivider: {
        type: Boolean,
        default: false
    }
})

const collapsed = ref(false)
</script>

<style scoped>
.resource-config-panel {
    width: 100%;
}
.mobile-blueprint-resources { padding: 24px 12px; text-align: center; }.mobile-blueprint-resources svg { margin: 0 auto 12px; color: #94a3b8; font-size: 36px; }.mobile-blueprint-resources h3 { font-size: 16px; font-weight: 650; }.mobile-blueprint-resources p { color: #64748b; font-size: 13px; line-height: 1.8; margin-top: 8px; }
</style>
