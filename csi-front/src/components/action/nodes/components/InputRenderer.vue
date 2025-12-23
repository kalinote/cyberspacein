<template>
    <div 
        class="input-renderer-wrapper nodrag" 
        :class="[positionClass, { 'multi-line-layout': isMultiLineLayout }]"
        :style="inputConfig.custom_style"
    >
        <!-- 多行布局：带分隔线 -->
        <template v-if="isMultiLineLayout">
            <div class="divider-line"></div>
            <div class="multi-line-content">
                <div v-if="inputConfig.label" class="label-with-tooltip mb-2">
                    <span class="text-xs text-gray-600 font-medium">{{ inputConfig.label }}</span>
                    <el-tooltip 
                        v-if="inputConfig.description" 
                        :content="inputConfig.description" 
                        placement="top"
                    >
                        <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help ml-1" />
                    </el-tooltip>
                </div>
                
                <component 
                    :is="componentType"
                    :model-value="normalizedModelValue"
                    @update:model-value="handleUpdate"
                    v-bind="computedProps"
                    :disabled="disabled"
                    :placeholder="inputConfig.placeholder || `请输入${inputConfig.label}`"
                    size="small"
                    class="w-full"
                >
                    <template v-if="componentType === 'el-select' && inputConfig.options">
                        <el-option
                            v-for="option in inputConfig.options"
                            :key="option.value"
                            :label="option.label"
                            :value="option.value"
                        />
                    </template>
                    <template v-if="componentType === 'el-checkbox-group' && inputConfig.options">
                        <el-checkbox
                            v-for="option in inputConfig.options"
                            :key="option.value"
                            :label="option.value"
                        >
                            {{ option.label }}
                        </el-checkbox>
                    </template>
                    <template v-if="componentType === 'el-radio-group' && inputConfig.options">
                        <el-radio
                            v-for="option in inputConfig.options"
                            :key="option.value"
                            :label="option.value"
                        >
                            {{ option.label }}
                        </el-radio>
                    </template>
                </component>
            </div>
            <div class="divider-line"></div>
        </template>
        
        <!-- 单行布局：label 和控件在一行 -->
        <template v-else>
            <div class="single-line-content">
                <div v-if="inputConfig.label" class="label-with-tooltip">
                    <el-tooltip 
                        v-if="inputConfig.description" 
                        :content="inputConfig.description" 
                        placement="top"
                        :show-after="300"
                    >
                        <span class="text-xs text-gray-500 shrink-0 cursor-help">{{ inputConfig.label }}:</span>
                    </el-tooltip>
                    <span v-else class="text-xs text-gray-500 shrink-0">{{ inputConfig.label }}:</span>
                </div>
                
                <component 
                    :is="componentType"
                    :model-value="normalizedModelValue"
                    @update:model-value="handleUpdate"
                    v-bind="computedProps"
                    :disabled="disabled"
                    :placeholder="inputConfig.placeholder || `请输入${inputConfig.label}`"
                    size="small"
                    class="flex-1"
                >
                    <template v-if="componentType === 'el-select' && inputConfig.options">
                        <el-option
                            v-for="option in inputConfig.options"
                            :key="option.value"
                            :label="option.label"
                            :value="option.value"
                        />
                    </template>
                </component>
            </div>
        </template>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import TagInput from './TagInput.vue'
import ConditionInput from './ConditionInput.vue'

// TODO: 这里还需要优化规范一下，比如考虑是否把boolean和switch统一起来
const INPUT_TYPE_MAP = {
    'int': 'el-input-number',
    'string': 'el-input',
    'textarea': 'el-input',
    'select': 'el-select',
    'checkbox': 'el-checkbox',
    'checkbox-group': 'el-checkbox-group',
    'radio-group': 'el-radio-group',
    'boolean': 'el-switch',
    'datetime': 'el-date-picker',
    'tags': TagInput,
    'conditions': ConditionInput
}

const INPUT_DEFAULT_PROPS = {
    'int': { controlsPosition: 'right' },
    'string': { clearable: true },
    'textarea': { type: 'textarea', rows: 3 },
    'select': { clearable: true },
    'boolean': { activeValue: true, inactiveValue: false },
    'datetime': { type: 'datetime', valueFormat: 'YYYY-MM-DD HH:mm:ss' }
}

const MULTI_LINE_TYPES = ['textarea', 'checkbox-group', 'radio-group', 'tags', 'conditions']

const props = defineProps({
    inputConfig: {
        type: Object,
        required: true
    },
    modelValue: {
        type: [String, Number, Boolean, Array, Object],
        default: null
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['update:modelValue'])

const componentType = computed(() => {
    return INPUT_TYPE_MAP[props.inputConfig.type] || 'el-input'
})

const isMultiLineLayout = computed(() => {
    return MULTI_LINE_TYPES.includes(props.inputConfig.type)
})

const computedProps = computed(() => {
    const defaultProps = INPUT_DEFAULT_PROPS[props.inputConfig.type] || {}
    const customProps = props.inputConfig.custom_props || {}
    
    return {
        ...defaultProps,
        ...customProps
    }
})

const positionClass = computed(() => {
    const position = props.inputConfig.position || 'center'
    const classMap = {
        'center': 'mx-auto',
        'left': 'mr-auto',
        'right': 'ml-auto',
        'top': 'mb-auto',
        'bottom': 'mt-auto'
    }
    return classMap[position] || 'mx-auto'
})

const normalizedModelValue = computed(() => {
    if (props.inputConfig.type === 'int') {
        if (props.modelValue === null || props.modelValue === undefined || props.modelValue === '') {
            return null
        }
        const numValue = Number(props.modelValue)
        return isNaN(numValue) ? null : numValue
    }
    return props.modelValue
})

const handleUpdate = (value) => {
    emit('update:modelValue', value)
}
</script>

<style scoped>
.input-renderer-wrapper {
    width: 100%;
}

.single-line-content {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
}

.label-with-tooltip {
    display: flex;
    align-items: center;
    gap: 4px;
}

.multi-line-layout {
    margin: 12px 0;
}

.multi-line-content {
    padding: 12px 0;
}

.divider-line {
    height: 1px;
    background: linear-gradient(to right, transparent, #e5e7eb 20%, #e5e7eb 80%, transparent);
    margin: 0 -8px;
}

:deep(.el-input-number) {
    width: 100%;
}

:deep(.el-checkbox-group) {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

:deep(.el-radio-group) {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
</style>
