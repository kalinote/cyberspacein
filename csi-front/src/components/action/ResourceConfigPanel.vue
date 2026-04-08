<template>
    <div
        class="resource-config-panel relative group flex flex-col"
        :class="showTopDivider ? 'border-t border-gray-200' : ''"
    >
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
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

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
</style>
