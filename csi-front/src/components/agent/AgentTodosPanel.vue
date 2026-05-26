<template>
    <div class="shrink-0 w-full border-t border-gray-100 bg-white">
        <button
            type="button"
            class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 transition-colors"
            @click="expanded = !expanded"
        >
            <Icon icon="mdi:format-list-checks" class="shrink-0 text-base text-blue-600" />
            <span class="text-sm font-medium text-gray-900 flex-1 min-w-0 truncate">任务列表</span>
            <span
                v-if="todos.length"
                class="shrink-0 text-xs font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded"
            >
                {{ todos.length }}
            </span>
            <Icon
                :icon="expanded ? 'mdi:chevron-down' : 'mdi:chevron-up'"
                class="shrink-0 text-lg text-gray-400"
            />
        </button>
        <div
            v-show="expanded"
            class="border-t border-gray-100 max-h-40 overflow-y-auto"
        >
            <div
                v-if="!todos.length"
                class="flex items-center justify-center gap-1.5 py-3 text-gray-400"
            >
                <Icon icon="mdi:playlist-remove" class="text-base" />
                <p class="text-xs text-gray-500">暂无任务</p>
            </div>
            <ul v-else class="py-1 min-w-0">
                <li
                    v-for="(todo, index) in todos"
                    :key="index"
                    class="flex items-center gap-2 px-3 py-1.5 min-w-0"
                >
                    <Icon
                        :icon="todoStatusIcon(todo?.status)"
                        :class="['shrink-0 text-base', todoStatusIconColor(todo?.status)]"
                    />
                    <p class="text-xs text-gray-900 break-all min-w-0 leading-snug flex-1">
                        {{ todo?.content || '-' }}
                    </p>
                </li>
            </ul>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

defineProps({
    todos: {
        type: Array,
        default: () => [],
    },
    todoStatusIcon: {
        type: Function,
        required: true,
    },
    todoStatusIconColor: {
        type: Function,
        required: true,
    },
})

const expanded = ref(false)
</script>
