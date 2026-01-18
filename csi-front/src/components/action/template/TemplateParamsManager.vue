<template>
    <div class="template-params-manager border-t border-gray-200 mt-4">
        <div 
            class="flex items-center justify-between py-3 px-2 cursor-pointer hover:bg-gray-50"
            @click="collapsed = !collapsed"
        >
            <div class="flex items-center gap-2">
                <Icon 
                    :icon="collapsed ? 'mdi:chevron-right' : 'mdi:chevron-down'" 
                    class="text-gray-500 text-lg transition-transform"
                />
                <span class="text-sm font-semibold text-gray-800">模板参数</span>
                <el-tag size="small" type="info">{{ params.length }}</el-tag>
            </div>
            <el-button 
                v-if="!collapsed"
                type="primary" 
                size="small" 
                :icon="Plus"
                @click.stop="showAddDialog = true"
            >
                添加参数
            </el-button>
        </div>

        <div v-show="!collapsed" class="params-content px-2 pb-4">
            <div v-if="params.length === 0" class="text-center py-8 text-gray-400">
                <Icon icon="mdi:package-variant" class="text-4xl mb-2" />
                <p class="text-sm">暂无参数</p>
                <p class="text-xs mt-1">点击上方按钮添加模板参数</p>
            </div>

            <div v-else class="space-y-2 mt-3">
                <div
                    v-for="param in params"
                    :key="param.id"
                    class="param-item bg-gray-50 rounded-lg p-3 border border-gray-200 hover:border-blue-300 transition-colors"
                >
                    <div class="flex items-start justify-between mb-2">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-sm font-medium text-gray-900">{{ param.label || param.name }}</span>
                                <el-tag size="small" :type="getParamTypeTagType(param.type)">
                                    {{ param.type }}
                                </el-tag>
                                <el-tag v-if="param.required" size="small" type="danger">必填</el-tag>
                            </div>
                            <div class="text-xs text-gray-500">
                                <span class="font-mono bg-gray-100 px-1 py-0.5 rounded">{{ param.name }}</span>
                            </div>
                            <div v-if="param.description" class="text-xs text-gray-600 mt-1">
                                {{ param.description }}
                            </div>
                        </div>
                        <div class="flex items-center gap-1 ml-2">
                            <el-tooltip content="编辑参数" placement="top">
                                <el-button
                                    size="small"
                                    :icon="Edit"
                                    circle
                                    @click="editParam(param)"
                                />
                            </el-tooltip>
                            <el-tooltip content="删除参数" placement="top">
                                <el-button
                                    size="small"
                                    :icon="Delete"
                                    type="danger"
                                    circle
                                    @click="confirmDeleteParam(param)"
                                />
                            </el-tooltip>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-2 text-xs text-gray-500 mt-2 pt-2 border-t border-gray-200">
                        <Icon icon="mdi:link-variant" />
                        <span>引用次数: {{ getParamRefCount(param.name) }}</span>
                    </div>
                </div>
            </div>
        </div>

        <el-dialog
            v-model="showAddDialog"
            :title="editingParam ? '编辑参数' : '添加参数'"
            width="500px"
            :close-on-click-modal="false"
        >
            <el-form
                ref="paramFormRef"
                :model="paramForm"
                :rules="paramFormRules"
                label-width="80px"
                label-position="left"
            >
                <el-form-item label="参数名" prop="name">
                    <el-input
                        v-model="paramForm.name"
                        placeholder="字母/数字/下划线，不能以数字开头"
                        clearable
                    />
                    <div class="text-xs text-gray-500 mt-1">
                        用于标识参数的唯一名称，建议使用小写字母和下划线
                    </div>
                </el-form-item>

                <el-form-item label="显示名称" prop="label">
                    <el-input
                        v-model="paramForm.label"
                        placeholder="参数的显示名称"
                        clearable
                    />
                </el-form-item>

                <el-form-item label="参数类型" prop="type">
                    <el-select
                        v-model="paramForm.type"
                        placeholder="选择参数类型"
                        class="w-full"
                    >
                        <el-option
                            v-for="type in INPUT_TYPES"
                            :key="type"
                            :label="type"
                            :value="type"
                        >
                            <div class="flex items-center justify-between">
                                <span>{{ type }}</span>
                                <el-tag size="small" :type="getParamTypeTagType(type)">
                                    {{ type }}
                                </el-tag>
                            </div>
                        </el-option>
                    </el-select>
                </el-form-item>

                <el-form-item label="描述" prop="description">
                    <el-input
                        v-model="paramForm.description"
                        type="textarea"
                        :rows="2"
                        placeholder="参数的详细描述"
                    />
                </el-form-item>

                <el-form-item label="必填" prop="required">
                    <el-switch v-model="paramForm.required" />
                </el-form-item>
            </el-form>

            <template #footer>
                <el-button @click="cancelParamDialog">取消</el-button>
                <el-button type="primary" @click="saveParam">
                    {{ editingParam ? '保存' : '添加' }}
                </el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { INPUT_TYPES } from '@/utils/action/constants'
import { 
    validateParamName, 
    generateParamId, 
    isParamNameExists,
    getParamReferenceCount,
    removeParamBindings,
    updateParamBindingsName
} from '@/utils/action/template'

const props = defineProps({
    params: {
        type: Array,
        default: () => []
    },
    bindings: {
        type: Object,
        default: () => ({})
    }
})

const emit = defineEmits(['update:params', 'update:bindings'])

const collapsed = ref(false)
const showAddDialog = ref(false)
const paramFormRef = ref(null)
const editingParam = ref(null)

const paramForm = ref({
    name: '',
    label: '',
    type: 'string',
    description: '',
    required: false
})

const paramFormRules = {
    name: [
        { required: true, message: '请输入参数名', trigger: 'blur' },
        { 
            validator: (rule, value, callback) => {
                if (!validateParamName(value)) {
                    callback(new Error('参数名只能包含字母、数字和下划线，且不能以数字开头'))
                } else if (isParamNameExists(value, props.params, editingParam.value?.id)) {
                    callback(new Error('参数名已存在'))
                } else {
                    callback()
                }
            },
            trigger: 'blur'
        }
    ],
    label: [
        { required: true, message: '请输入显示名称', trigger: 'blur' }
    ],
    type: [
        { required: true, message: '请选择参数类型', trigger: 'change' }
    ]
}

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

const getParamRefCount = (paramName) => {
    return getParamReferenceCount(paramName, props.bindings)
}

const editParam = (param) => {
    editingParam.value = param
    paramForm.value = {
        name: param.name,
        label: param.label,
        type: param.type,
        description: param.description || '',
        required: param.required
    }
    showAddDialog.value = true
}

const confirmDeleteParam = (param) => {
    const refCount = getParamRefCount(param.name)
    
    const message = refCount > 0
        ? `该参数被 ${refCount} 个字段引用，删除后这些字段将恢复为固定值模式。确认删除？`
        : '确认删除该参数？'
    
    ElMessageBox.confirm(message, '警告', {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消'
    }).then(() => {
        deleteParam(param)
    }).catch(() => {})
}

const deleteParam = (param) => {
    const newParams = props.params.filter(p => p.id !== param.id)
    emit('update:params', newParams)
    
    const newBindings = { ...props.bindings }
    removeParamBindings(param.name, newBindings)
    emit('update:bindings', newBindings)
    
    ElMessage.success('参数删除成功')
}

const saveParam = async () => {
    if (!paramFormRef.value) return
    
    try {
        await paramFormRef.value.validate()
        
        if (editingParam.value) {
            const index = props.params.findIndex(p => p.id === editingParam.value.id)
            if (index !== -1) {
                const newParams = [...props.params]
                const oldName = newParams[index].name
                
                newParams[index] = {
                    ...newParams[index],
                    ...paramForm.value
                }
                
                emit('update:params', newParams)
                
                if (oldName !== paramForm.value.name) {
                    const newBindings = { ...props.bindings }
                    updateParamBindingsName(oldName, paramForm.value.name, newBindings)
                    emit('update:bindings', newBindings)
                }
                
                ElMessage.success('参数更新成功')
            }
        } else {
            const newParam = {
                id: generateParamId(),
                ...paramForm.value
            }
            
            emit('update:params', [...props.params, newParam])
            ElMessage.success('参数添加成功')
        }
        
        cancelParamDialog()
    } catch (error) {
        console.error('表单验证失败:', error)
    }
}

const cancelParamDialog = () => {
    showAddDialog.value = false
    editingParam.value = null
    paramForm.value = {
        name: '',
        label: '',
        type: 'string',
        description: '',
        required: false
    }
    if (paramFormRef.value) {
        paramFormRef.value.resetFields()
    }
}
</script>

<style scoped>
.template-params-manager {
    width: 100%;
}

.params-content {
    max-height: 400px;
    overflow-y: auto;
}

.param-item {
    transition: all 0.2s ease;
}

.param-item:hover {
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
</style>
