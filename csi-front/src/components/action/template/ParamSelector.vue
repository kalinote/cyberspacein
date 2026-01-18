<template>
    <div class="param-selector-wrapper">
        <el-select
            :model-value="modelValue"
            @update:model-value="handleChange"
            :disabled="disabled"
            placeholder="选择参数"
            filterable
            clearable
            size="small"
            class="w-full"
        >
            <template #prefix>
                <Icon icon="mdi:link-variant" class="text-blue-500" />
            </template>
            
            <el-option
                v-for="param in filteredParams"
                :key="param.name"
                :label="param.label || param.name"
                :value="param.name"
            >
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span>{{ param.label || param.name }}</span>
                        <el-tag size="small" :type="getParamTypeTagType(param.type)">
                            {{ param.type }}
                        </el-tag>
                    </div>
                    <span v-if="param.required" class="text-red-500 text-xs">*</span>
                </div>
                <div v-if="param.description" class="text-xs text-gray-400 mt-1">
                    {{ param.description }}
                </div>
            </el-option>
            
            <template v-if="filteredParams.length === 0" #empty>
                <div class="text-center py-2 text-gray-400 text-sm">
                    <Icon icon="mdi:alert-circle-outline" class="text-lg mb-1" />
                    <p>暂无匹配类型的参数</p>
                    <p class="text-xs mt-1">请在参数管理区添加 {{ inputType }} 类型的参数</p>
                </div>
            </template>
        </el-select>
        
        <el-tooltip content="当前输入项已绑定到参数，将在运行时注入实际值" placement="top">
            <Icon icon="mdi:information-outline" class="text-blue-400 text-sm ml-2 cursor-help" />
        </el-tooltip>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
    inputType: {
        type: String,
        required: true
    },
    modelValue: {
        type: String,
        default: null
    },
    availableParams: {
        type: Array,
        default: () => []
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['update:modelValue'])

const filteredParams = computed(() => {
    return props.availableParams.filter(param => param.type === props.inputType)
})

const getParamTypeTagType = (type) => {
    const typeMap = {
        'int': 'warning',
        'string': '',
        'textarea': '',
        'select': 'info',
        'checkbox': 'success',
        'checkbox-group': 'success',
        'radio-group': 'info',
        'boolean': 'success',
        'datetime': 'warning',
        'tags': 'danger',
        'conditions': 'danger'
    }
    return typeMap[type] || ''
}

const handleChange = (value) => {
    emit('update:modelValue', value)
}
</script>

<style scoped>
.param-selector-wrapper {
    display: flex;
    align-items: center;
    width: 100%;
}

:deep(.el-select) {
    flex: 1;
}
</style>
