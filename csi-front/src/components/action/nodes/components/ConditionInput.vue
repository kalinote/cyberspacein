<template>
    <div class="condition-input-container">
        <div v-if="conditions.length > 0" class="conditions-display mb-3">
            <div
                v-for="(condition, index) in conditions"
                :key="index"
                class="condition-item mb-2"
            >
                <el-tag
                    closable
                    :disable-transitions="false"
                    @close="handleRemoveCondition(index)"
                    size="small"
                    class="condition-tag"
                >
                    {{ formatCondition(condition) }}
                </el-tag>
            </div>
        </div>
        
        <div class="add-condition-form">
            <div class="form-row flex gap-2 mb-2">
                <!-- TODO: 解决字段名不能带下划线的问题 -->
                <el-input
                    v-model="newCondition.field"
                    placeholder="字段名"
                    size="small"
                    clearable
                    :disabled="disabled"
                    class="flex-1"
                />
                <el-select
                    v-model="newCondition.operator"
                    placeholder="操作符"
                    size="small"
                    :disabled="disabled"
                    style="width: 140px"
                >
                    <el-option
                        v-for="op in OPERATORS"
                        :key="op.value"
                        :label="op.label"
                        :value="op.value"
                    />
                </el-select>
            </div>
            
            <div class="form-row flex gap-2 mb-2">
                <component
                    :is="valueInputComponent"
                    v-model="newCondition.value"
                    :placeholder="getValuePlaceholder()"
                    size="small"
                    :disabled="disabled"
                    class="flex-1"
                    v-bind="valueInputProps"
                />
                <el-button
                    size="small"
                    type="primary"
                    :icon="Plus"
                    @click="handleAddCondition"
                    :disabled="disabled || !canAddCondition"
                >
                    添加
                </el-button>
            </div>
        </div>
        
        <div v-if="showCount" class="text-xs text-gray-400 mt-1">
            已添加 {{ conditions.length }} 个条件
        </div>
    </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import TagInput from './TagInput.vue'

const OPERATORS = [
    { value: '=', label: '等于' },
    { value: '__ne', label: '不等于' },
    { value: '__gt', label: '大于' },
    { value: '__gte', label: '大于等于' },
    { value: '__lt', label: '小于' },
    { value: '__lte', label: '小于等于' },
    { value: '__contains', label: '包含于' },
    { value: '__icontains', label: '包含' },
    { value: '__in', label: '在列表中' },
    { value: '__startswith', label: '以...开始' },
    { value: '__endswith', label: '以...结束' }
]

const props = defineProps({
    modelValue: {
        type: Array,
        default: () => []
    },
    placeholder: {
        type: String,
        default: '输入内容后按回车或点击添加'
    },
    showCount: {
        type: Boolean,
        default: true
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['update:modelValue'])

const conditions = ref([])
const newCondition = ref({
    field: '',
    operator: '=',
    value: ''
})

watch(() => newCondition.value.operator, (newOp, oldOp) => {
    if (newOp === '__in' && !Array.isArray(newCondition.value.value)) {
        newCondition.value.value = []
    } else if (newOp !== '__in' && Array.isArray(newCondition.value.value)) {
        newCondition.value.value = ''
    }
})

const valueInputComponent = computed(() => {
    return newCondition.value.operator === '__in' ? TagInput : 'el-input'
})

const valueInputProps = computed(() => {
    if (newCondition.value.operator === '__in') {
        return {
            showCount: false
        }
    }
    return {
        clearable: true
    }
})

const canAddCondition = computed(() => {
    const field = newCondition.value.field?.trim()
    if (!field) return false
    
    if (newCondition.value.operator === '__in') {
        const value = newCondition.value.value
        return Array.isArray(value) && value.length > 0
    } else {
        const value = newCondition.value.value
        return value !== null && value !== undefined && String(value).trim() !== ''
    }
})

const getValuePlaceholder = () => {
    if (newCondition.value.operator === '__in') {
        return '输入值后按回车或点击添加'
    }
    return '输入值'
}

const formatCondition = (condition) => {
    const operatorLabel = OPERATORS.find(op => op.value === condition.operator)?.label || condition.operator
    let valueDisplay = condition.value
    
    if (condition.operator === '__in' && Array.isArray(condition.value)) {
        valueDisplay = condition.value.join(', ')
    }
    
    return `${condition.field} ${operatorLabel} ${valueDisplay}`
}

const parseConditionString = (str) => {
    const match = str.match(/^([^_=]+)(__\w+)?=(.+)$/)
    if (!match) return null
    
    const [, field, operator, value] = match
    return {
        field: field,
        operator: operator || '=',
        value: operator === '__in' ? value.split(',') : value
    }
}

const conditionToString = (condition) => {
    let value = condition.value
    if (condition.operator === '__in' && Array.isArray(value)) {
        value = value.join(',')
    }
    const operator = condition.operator === '=' ? '' : condition.operator
    return `${condition.field}${operator}=${value}`
}

const updateOutput = () => {
    const output = conditions.value.map(condition => conditionToString(condition))
    emit('update:modelValue', output)
}

const handleAddCondition = () => {
    if (!canAddCondition.value) return
    
    const condition = {
        field: newCondition.value.field.trim(),
        operator: newCondition.value.operator,
        value: newCondition.value.operator === '__in' 
            ? [...newCondition.value.value] 
            : String(newCondition.value.value).trim()
    }
    
    conditions.value.push(condition)
    updateOutput()
    
    newCondition.value = {
        field: '',
        operator: '=',
        value: newCondition.value.operator === '__in' ? [] : ''
    }
}

const handleRemoveCondition = (index) => {
    conditions.value.splice(index, 1)
    updateOutput()
}

watch(() => props.modelValue, (newVal) => {
    if (!Array.isArray(newVal)) {
        conditions.value = []
        return
    }
    
    conditions.value = newVal.map(str => {
        const parsed = parseConditionString(str)
        if (parsed) {
            return {
                field: parsed.field,
                operator: parsed.operator,
                value: parsed.operator === '__in' 
                    ? (Array.isArray(parsed.value) ? parsed.value : parsed.value.split(',').map(v => v.trim()))
                    : parsed.value
            }
        }
        return null
    }).filter(c => c !== null)
}, { immediate: true })
</script>

<style scoped>
.condition-input-container {
    width: 100%;
}

.conditions-display {
    display: flex;
    flex-direction: column;
    min-height: 28px;
    padding: 8px;
    background-color: #f5f7fa;
    border-radius: 4px;
}

.condition-item {
    display: flex;
    align-items: center;
}

.condition-tag {
    width: 100%;
    justify-content: space-between;
}

.add-condition-form {
    width: 100%;
}

.form-row {
    width: 100%;
    align-items: center;
}

:deep(.el-tag) {
    max-width: 100%;
}

:deep(.el-tag__content) {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
