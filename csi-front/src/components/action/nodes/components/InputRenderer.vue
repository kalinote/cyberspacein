<template>
    <div 
        class="input-renderer-wrapper nodrag" 
        :class="[positionClass, { 'multi-line-layout': isMultiLineLayout }]"
        :style="isMobile ? undefined : inputConfig.custom_style"
    >
        <div v-if="isMobile" class="mobile-blueprint-input">
            <div class="mobile-input-heading"><span>{{ inputConfig.label || inputConfig.name }}<strong v-if="inputConfig.required"> *</strong></span><el-button v-if="isTemplateMode && nodeId && inputConfig.type !== 'comment'" :disabled="disabled" :type="currentMode === PARAM_MODE.PARAM ? 'primary' : 'default'" plain @click="toggleMode">{{ currentMode === PARAM_MODE.PARAM ? '参数注入' : '固定值' }}</el-button></div>
            <p v-if="inputConfig.description" class="mobile-input-description">{{ inputConfig.description }}</p>
            <template v-if="inputConfig.type !== 'comment'">
                <ParamSelector v-if="isTemplateMode && currentMode === PARAM_MODE.PARAM" :model-value="boundParamName" :input-type="inputConfig.type" :available-params="availableParams" :disabled="disabled" @update:model-value="handleParamChange" />
                <component v-else :is="componentType" :model-value="normalizedModelValue" v-bind="computedProps" :disabled="disabled" :placeholder="inputConfig.placeholder || `请输入${inputConfig.label || inputConfig.name}`" :aria-label="inputConfig.label || inputConfig.name" @update:model-value="handleUpdate">
                    <template v-if="componentType === 'el-select'"><el-option v-for="option in inputConfig.options || []" :key="option.value" :label="option.label" :value="option.value" /></template>
                    <template v-else-if="componentType === 'el-checkbox-group'"><el-checkbox v-for="option in inputConfig.options || []" :key="option.value" :label="option.value">{{ option.label }}</el-checkbox></template>
                    <template v-else-if="componentType === 'el-radio-group'"><el-radio v-for="option in inputConfig.options || []" :key="option.value" :label="option.value">{{ option.label }}</el-radio></template>
                </component>
            </template>
        </div>
        <!-- 注释型输入项：仅展示文本 -->
        <template v-else-if="inputConfig.type === 'comment'">
            <div class="comment-display">
                <div class="divider-line"></div>
                <div class="comment-content">
                    <div class="flex items-start gap-2">
                        <Icon icon="mdi:information-outline" class="text-blue-500 text-base mt-0.5 shrink-0" />
                        <div class="flex-1">
                            <div v-if="inputConfig.label" class="text-xs font-medium text-gray-700 mb-1">
                                {{ inputConfig.label }}
                            </div>
                            <div class="text-xs text-gray-600 whitespace-pre-wrap leading-relaxed">
                                {{ inputConfig.description || '暂无说明' }}
                            </div>
                        </div>
                    </div>
                </div>
                <div class="divider-line"></div>
            </div>
        </template>
        
        <!-- 多行布局：带分隔线 -->
        <template v-else-if="isMultiLineLayout">
            <div class="divider-line"></div>
            <div class="multi-line-content">
                <div v-if="inputConfig.label" class="label-with-tooltip mb-2 flex items-center justify-between">
                    <div class="flex items-center">
                        <span class="text-xs text-gray-600 font-medium">{{ inputConfig.label }}</span>
                        <el-tooltip 
                            v-if="inputConfig.description" 
                            :content="inputConfig.description" 
                            placement="top"
                        >
                            <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help ml-1" />
                        </el-tooltip>
                    </div>
                    
                    <el-tooltip 
                        v-if="isTemplateMode" 
                        :content="currentMode === PARAM_MODE.PARAM ? '切换为固定值' : '切换为参数注入'"
                        placement="top"
                    >
                        <el-button
                            size="small"
                            :type="currentMode === PARAM_MODE.PARAM ? 'primary' : 'default'"
                            :icon="currentMode === PARAM_MODE.PARAM ? Link : Edit"
                            circle
                            @click="toggleMode"
                            class="mode-toggle-btn"
                        />
                    </el-tooltip>
                </div>
                
                <ParamSelector
                    v-if="isTemplateMode && currentMode === PARAM_MODE.PARAM"
                    v-model="boundParamName"
                    :input-type="inputConfig.type"
                    :available-params="availableParams"
                    :disabled="disabled"
                    @update:model-value="handleParamChange"
                    class="w-full"
                />
                
                <component 
                    v-else
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
                
                <el-tooltip 
                    v-if="isTemplateMode" 
                    :content="currentMode === PARAM_MODE.PARAM ? '切换为固定值' : '切换为参数注入'"
                    placement="top"
                >
                    <el-button
                        size="small"
                        :type="currentMode === PARAM_MODE.PARAM ? 'primary' : 'default'"
                        :icon="currentMode === PARAM_MODE.PARAM ? Link : Edit"
                        circle
                        @click="toggleMode"
                        class="mode-toggle-btn shrink-0"
                    />
                </el-tooltip>
                
                <ParamSelector
                    v-if="isTemplateMode && currentMode === PARAM_MODE.PARAM"
                    v-model="boundParamName"
                    :input-type="inputConfig.type"
                    :available-params="availableParams"
                    :disabled="disabled"
                    @update:model-value="handleParamChange"
                    class="flex-1"
                />
                
                <component 
                    v-else
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
import { computed, inject, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Link, Edit } from '@element-plus/icons-vue'
import TagInput from './TagInput.vue'
import ConditionInput from './ConditionInput.vue'
import KeyValueEditor from './KeyValueEditor.vue'
import ParamSelector from '@/components/action/template/ParamSelector.vue'
import { PARAM_MODE } from '@/utils/action/constants'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileBlueprintStructuredField from '@/components/action/mobile/MobileBlueprintStructuredField.vue'
const { isMobile } = useMobileViewport()

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
    'conditions': ConditionInput,
    'key-value': KeyValueEditor,
    'comment': 'comment-display'
}

const INPUT_DEFAULT_PROPS = {
    'int': { controlsPosition: 'right' },
    'string': { clearable: false },
    'textarea': { type: 'textarea', rows: 3 },
    'select': { clearable: true },
    'boolean': { activeValue: true, inactiveValue: false },
    'datetime': { type: 'datetime', valueFormat: 'YYYY-MM-DD HH:mm:ss' }
}

const MULTI_LINE_TYPES = ['textarea', 'checkbox-group', 'radio-group', 'tags', 'conditions', 'key-value']

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
    },
    nodeId: {
        type: String,
        default: null
    }
})

const emit = defineEmits(['update:modelValue'])

const templateContext = inject('templateContext', null)

const isTemplateMode = computed(() => {
    return templateContext?.isTemplateMode?.value || false
})

const availableParams = computed(() => {
    return templateContext?.availableParams?.value || []
})

const currentBinding = computed(() => {
    if (!templateContext || !props.nodeId || !props.inputConfig.name) {
        return null
    }
    const nodeBindings = templateContext.bindings.value[props.nodeId]
    return nodeBindings?.[props.inputConfig.name]
})

const currentMode = ref(PARAM_MODE.FIXED)
const boundParamName = ref(null)

watch(currentBinding, (paramName) => {
    if (paramName) {
        currentMode.value = PARAM_MODE.PARAM
        boundParamName.value = paramName
    } else {
        currentMode.value = PARAM_MODE.FIXED
        boundParamName.value = null
    }
}, { immediate: true })

const toggleMode = () => {
    if (props.disabled) return
    if (currentMode.value === PARAM_MODE.FIXED) {
        currentMode.value = PARAM_MODE.PARAM
    } else {
        currentMode.value = PARAM_MODE.FIXED
        updateBinding(null)
    }
}

const handleParamChange = (paramName) => {
    if (props.disabled) return
    boundParamName.value = paramName
    updateBinding(paramName)
}

const updateBinding = (paramName) => {
    if (props.disabled) return
    if (templateContext?.updateBinding && props.nodeId && props.inputConfig.name) {
        templateContext.updateBinding(props.nodeId, props.inputConfig.name, paramName)
    }
}

const componentType = computed(() => {
    if (isMobile.value && ['tags', 'conditions', 'key-value'].includes(props.inputConfig.type)) return MobileBlueprintStructuredField
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
        ...customProps,
        ...(isMobile.value && ['tags', 'conditions', 'key-value'].includes(props.inputConfig.type) ? { kind: props.inputConfig.type } : {})
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
    if (props.disabled) return
    emit('update:modelValue', value)
}
</script>

<style scoped>
.input-renderer-wrapper {
    width: 100%;
}
.mobile-blueprint-input { display: grid; gap: 8px; min-width: 0; width: 100%; }
.mobile-input-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: 14px; color: #334155; }
.mobile-input-heading > span { min-width: 0; overflow-wrap: anywhere; }.mobile-input-heading strong { color: #dc2626; }
.mobile-input-description { color: #64748b; font-size: 12px; line-height: 1.75; overflow-wrap: anywhere; white-space: pre-wrap; }
.mobile-blueprint-input :deep(.el-input__wrapper), .mobile-blueprint-input :deep(.el-select__wrapper), .mobile-blueprint-input :deep(.el-button) { min-height: 44px; }
.mobile-blueprint-input :deep(.el-checkbox), .mobile-blueprint-input :deep(.el-radio) { min-height: 44px; white-space: normal; margin: 0; height: auto; }
.mobile-blueprint-input :deep(.el-checkbox__label), .mobile-blueprint-input :deep(.el-radio__label) { white-space: normal; overflow-wrap: anywhere; }
.mobile-blueprint-input :deep(.el-date-editor), .mobile-blueprint-input :deep(.el-select) { width: 100%; min-width: 0; }.mobile-blueprint-input :deep(textarea) { font-size: 16px; }

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

.comment-display {
    margin: 12px 0;
}

.comment-content {
    padding: 10px 12px;
    background: #f0f9ff;
    border-radius: 6px;
    border-left: 3px solid #3b82f6;
}

.mode-toggle-btn {
    margin: 0 4px;
}

.mode-toggle-btn:hover {
    transform: scale(1.1);
    transition: transform 0.2s ease;
}
</style>
