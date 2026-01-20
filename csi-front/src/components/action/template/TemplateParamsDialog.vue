<template>
    <el-dialog
        v-model="dialogVisible"
        title="填写模板参数"
        width="600px"
        :close-on-click-modal="false"
        @close="handleClose"
    >
        <div v-loading="loading" :element-loading-text="'加载参数中...'" class="min-h-[200px]">
            <div v-if="!loading && inputConfigs.length === 0" class="text-center py-8 text-gray-400">
                <Icon icon="mdi:package-variant" class="text-4xl mb-2 block mx-auto" />
                <p class="text-sm">该模板没有参数</p>
            </div>

            <el-form
                v-else
                ref="formRef"
                :model="paramValues"
                :rules="formRules"
                label-position="top"
                :hide-required-asterisk="true"
                class="space-y-4"
            >
                <el-form-item
                    v-for="config in inputConfigs"
                    :key="config.name"
                    :prop="config.name"
                >
                    <template #label>
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium text-gray-700">
                                <span v-if="config.required" class="text-red-500 mr-1">*</span>{{ config.label }}
                            </span>
                            <el-tag v-if="config.required" size="small" type="danger">必填</el-tag>
                            <el-tag size="small" :type="getTypeTagType(config.type)">{{ config.type }}</el-tag>
                            <el-tooltip v-if="config.description" :content="config.description" placement="top">
                                <Icon icon="mdi:information-outline" class="text-gray-400 text-sm cursor-help" />
                            </el-tooltip>
                        </div>
                    </template>

                    <InputRenderer
                        :input-config="config"
                        v-model="paramValues[config.name]"
                        :node-id="null"
                    />
                </el-form-item>
            </el-form>
        </div>

        <template #footer>
            <el-button @click="handleClose">取消</el-button>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">
                确定运行
            </el-button>
        </template>
    </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import InputRenderer from '@/components/action/nodes/components/InputRenderer.vue'
import { actionApi } from '@/api/action'
import { INPUT_TYPE_DEFAULTS } from '@/utils/action/constants'

const props = defineProps({
    modelValue: {
        type: Boolean,
        default: false
    },
    blueprintId: {
        type: String,
        default: null
    }
})

const emit = defineEmits(['update:modelValue', 'submit'])

const dialogVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value)
})

const loading = ref(false)
const submitting = ref(false)
const blueprintData = ref(null)
const paramValues = ref({})
const formRef = ref(null)

const inputConfigs = computed(() => {
    return blueprintData.value?.template?.params.map(param => ({
        id: param.name,
        name: param.name,
        label: param.label,
        type: param.type,
        description: param.description,
        required: param.required,
        placeholder: `请输入${param.label}`,
        options: param.options
    })) || []
})

const formRules = computed(() => {
    const rules = {}
    inputConfigs.value.forEach(config => {
        if (config.required) {
            const configRules = []
            
            if (config.type === 'int') {
                configRules.push({
                    required: true,
                    type: 'number',
                    message: `${config.label}不能为空且必须是数字`,
                    trigger: 'blur'
                })
            } else if (['tags', 'conditions', 'checkbox-group'].includes(config.type)) {
                configRules.push({
                    required: true,
                    type: 'array',
                    min: 1,
                    message: `${config.label}至少需要一项`,
                    trigger: 'change'
                })
            } else if (config.type === 'boolean' || config.type === 'checkbox') {
                configRules.push({
                    validator: (rule, value, callback) => {
                        if (value === null || value === undefined) {
                            callback(new Error(`${config.label}不能为空`))
                        } else {
                            callback()
                        }
                    },
                    trigger: 'change'
                })
            } else {
                configRules.push({
                    required: true,
                    message: `${config.label}不能为空`,
                    trigger: 'blur'
                })
            }
            
            rules[config.name] = configRules
        }
    })
    return rules
})

const getTypeTagType = (type) => {
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

const initParamValues = () => {
    const values = {}
    inputConfigs.value.forEach(config => {
        values[config.name] = INPUT_TYPE_DEFAULTS[config.type]
    })
    paramValues.value = values
}

const fetchBlueprintData = async () => {
    if (!props.blueprintId) return
    
    loading.value = true
    try {
        const response = await actionApi.getBlueprint(props.blueprintId)
        if (response.code === 0 && response.data) {
            blueprintData.value = response.data
            initParamValues()
        } else {
            ElMessage.error(response.message || '获取蓝图详情失败')
        }
    } catch (error) {
        console.error('获取蓝图详情失败:', error)
        ElMessage.error('获取蓝图详情失败')
    } finally {
        loading.value = false
    }
}

const handleSubmit = async () => {
    if (!formRef.value) return
    
    try {
        await formRef.value.validate()
        emit('submit', paramValues.value)
    } catch (error) {
        console.error('表单验证失败:', error)
        ElMessage.warning('请检查必填项')
    }
}

const handleClose = () => {
    dialogVisible.value = false
    paramValues.value = {}
    blueprintData.value = null
    if (formRef.value) {
        formRef.value.resetFields()
    }
}

watch(() => props.modelValue, (newValue) => {
    if (newValue && props.blueprintId) {
        fetchBlueprintData()
    }
})
</script>

<style scoped>
:deep(.el-form-item) {
    margin-bottom: 20px;
}

:deep(.el-form-item__label) {
    margin-bottom: 8px;
}
</style>
