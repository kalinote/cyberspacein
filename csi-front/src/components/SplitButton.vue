<!--
    分割按钮组件 (SplitButton)
    
    一个带下拉菜单的组合按钮组件，主按钮和下拉菜单按钮组合在一起。
    
    使用方法：
    <template>
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
    </template>
    
    <script setup>
    import SplitButton from '@/components/SplitButton.vue'
    import { ElMessage } from 'element-plus'
    
    const analyzing = ref(false)
    
    // 下拉选项配置
    const analyzeOptions = [
        { label: '共识分析', icon: 'mdi:account-group', value: 'consensus' },
        { label: '情感分析', icon: 'mdi:emoticon-happy-outline', value: 'emotion' },
        { label: '传播路径分析', icon: 'mdi:share-variant', value: 'propagation' },
        { label: '证据链溯源分析', icon: 'mdi:link-variant', value: 'evidence' }
    ]
    
    // 主按钮点击事件
    const handleAnalyze = async () => {
        analyzing.value = true
        try {
            // 执行分析逻辑
            ElMessage.success('分析任务已提交')
        } finally {
            analyzing.value = false
        }
    }
    
    // 下拉选项点击事件
    const handleAnalyzeOption = (option) => {
        // option 包含 { label, icon, value }
        ElMessage.info(`${option.label}功能开发中`)
    }
    </script>
    
    Props:
    - mainButtonText (String, 必需): 主按钮显示的文本
    - loadingText (String, 默认: '处理中...'): 加载状态时显示的文本
    - disabled (Boolean, 默认: false): 是否禁用按钮
    - loading (Boolean, 默认: false): 是否处于加载状态
    - options (Array, 默认: []): 下拉菜单选项数组，每个选项格式为：
        { label: String, icon: String, value: Any }
    - mainButtonIcon (String, 可选): 主按钮图标（Iconify 图标名称）
    
    Events:
    - main-click: 主按钮点击时触发
    - option-click: 下拉选项点击时触发，参数为选中的选项对象 { label, icon, value }
-->
<template>
    <div ref="menuRef" class="relative">
        <div class="flex">
            <button 
                @click.stop="handleMainClick"
                :disabled="disabled"
                class="flex-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white py-3 rounded-l-lg font-medium transition-colors flex items-center justify-center space-x-2"
            >
                <Icon v-if="mainButtonIcon" :icon="loading ? 'mdi:loading' : mainButtonIcon" :class="{ 'animate-spin': loading }" />
                <span>{{ loading ? loadingText : mainButtonText }}</span>
            </button>
            <button
                @click.stop="toggleMenu"
                :disabled="disabled"
                class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white py-3 px-3 rounded-r-lg border-l border-blue-400 transition-colors flex items-center justify-center"
            >
                <Icon icon="mdi:chevron-down" :class="{ 'rotate-180': showMenu }" class="transition-transform" />
            </button>
        </div>
        <div 
            v-if="showMenu && options && options.length > 0"
            class="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden z-10"
        >
            <button
                v-for="option in options"
                :key="option.value"
                @click.stop="handleOptionClick(option)"
                class="w-full text-left px-4 py-3 text-gray-700 hover:bg-gray-50 transition-colors flex items-center space-x-2"
            >
                <Icon v-if="option.icon" :icon="option.icon" class="text-blue-500" />
                <span>{{ option.label }}</span>
            </button>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'

// Props 定义
const props = defineProps({
    mainButtonText: {
        type: String,
        required: true
    },
    loadingText: {
        type: String,
        default: '处理中...'
    },
    disabled: {
        type: Boolean,
        default: false
    },
    loading: {
        type: Boolean,
        default: false
    },
    options: {
        type: Array,
        default: () => []
    },
    mainButtonIcon: {
        type: String,
        default: null
    }
})

// Events 定义
const emit = defineEmits(['main-click', 'option-click'])

// 内部状态
const showMenu = ref(false)
const menuRef = ref(null)

// 切换下拉菜单显示/隐藏
const toggleMenu = () => {
    showMenu.value = !showMenu.value
}

// 处理主按钮点击
const handleMainClick = () => {
    showMenu.value = false
    emit('main-click')
}

// 处理下拉选项点击
const handleOptionClick = (option) => {
    showMenu.value = false
    emit('option-click', option)
}

// 处理点击外部区域关闭菜单
const handleClickOutside = (event) => {
    if (showMenu.value && menuRef.value && !menuRef.value.contains(event.target)) {
        showMenu.value = false
    }
}

onMounted(() => {
    document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
})
</script>
