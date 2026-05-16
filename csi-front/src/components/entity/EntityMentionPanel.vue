<template>
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
            提及<span class="text-blue-500">实体</span>
        </h3>
        <div class="space-y-4">
            <div v-for="group in groups" :key="group.key">
                <p class="text-sm text-gray-500 mb-2">{{ group.label }}</p>
                <div class="flex flex-wrap gap-2">
                    <el-tag
                        v-for="name in group.items"
                        :key="entityRefKey(group.key, name)"
                        :type="isSelected(group.key, name) ? 'success' : 'primary'"
                        size="large"
                        class="cursor-pointer"
                        :style="tagStyle(group.key, name)"
                        :ref="(el) => setRef(entityRefKey(group.key, name), el)"
                        @click="emit('toggle', group.key, name)"
                    >
                        {{ name }}
                    </el-tag>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { getEntityGroups, entityRefKey } from '@/utils/entityDisplay'

const props = defineProps({
    entities: {
        type: Object,
        default: null,
    },
    selectedKeys: {
        type: Array,
        default: () => [],
    },
    colors: {
        type: Object,
        default: () => ({}),
    },
    setRef: {
        type: Function,
        default: () => {},
    },
})

const emit = defineEmits(['toggle'])

const groups = computed(() => getEntityGroups(props.entities))

function isSelected(category, name) {
    return props.selectedKeys.includes(entityRefKey(category, name))
}

function tagStyle(category, name) {
    const key = entityRefKey(category, name)
    if (!isSelected(category, name) || !props.colors[key]) return undefined
    const color = props.colors[key]
    return { borderColor: color, backgroundColor: color + '22' }
}
</script>
