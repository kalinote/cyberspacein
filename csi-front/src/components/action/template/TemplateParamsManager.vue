<template>
    <div
        class="template-params-manager relative group flex flex-col"
        :class="embedded ? '' : 'border-t border-gray-200 mt-4'"
        :style="resizable && !isMobile ? { height: height + 'px' } : undefined"
    >
        <section v-if="isMobile" class="mobile-template-manager">
            <header><div><h3>模板参数</h3><p>{{ params.length }} 项参数 · 在节点字段中选择参数注入</p></div><el-button type="primary" :disabled="disabled" @click="showAddDialog = true">添加</el-button></header>
            <p v-if="!params.length" class="mobile-param-empty">先定义参数，再将节点字段绑定到对应参数。</p>
            <article v-for="param in params" :key="param.id" class="mobile-param-card"><h4>{{ param.label || param.name }}</h4><p class="param-code">{{ param.name }} · {{ param.type }}</p><p v-if="param.description">{{ param.description }}</p><div class="mobile-param-meta"><span>{{ param.required ? '必填' : '选填' }}</span><span>{{ getParamRefCount(param.name) }} 处引用</span></div><footer><el-button :disabled="disabled" @click="editParam(param)">编辑</el-button><el-button :disabled="disabled" type="danger" plain @click="confirmDeleteParam(param)">删除</el-button></footer></article>
        </section>
        <template v-else>
        <div
            v-if="resizable"
            class="absolute left-0 right-0 -top-1 h-2 cursor-row-resize z-10 flex justify-center hover:bg-blue-100/50 transition-colors"
            @mousedown.prevent="startResize"
        >
            <div class="h-px w-full bg-gray-200 group-hover:bg-blue-400 transition-colors"
                :class="{ 'bg-blue-600!': isResizing }"></div>
        </div>
        
        <div 
            class="flex items-center justify-between py-3 px-2 cursor-pointer hover:bg-gray-50 shrink-0"
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

        <div
            v-show="!collapsed"
            class="params-content px-2 pb-4 overflow-y-auto"
            :class="resizable ? 'flex-1 min-h-0' : 'max-h-80'"
        >
            <div v-if="params.length === 0" class="text-center py-8 text-gray-400">
                <Icon icon="mdi:package-variant" class="text-4xl mb-2 block mx-auto" />
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

        </template>
        <component :is="isMobile ? MobileSheet : 'el-dialog'"
            v-model="showAddDialog"
            :title="editingParam ? '编辑参数' : '添加参数'"
            width="500px"
            :close-on-click-modal="false"
            class="template-param-edit"
            @close="cancelParamDialog"
        >
            <nav v-if="isMobile" class="mobile-param-steps" aria-label="模板参数分组"><button type="button" :class="{ active: mobileStep === 0 }" @click="mobileStep = 0">名称与类型</button><button type="button" :class="{ active: mobileStep === 1 }" @click="mobileStep = 1">描述与要求</button></nav>
            <el-form
                ref="paramFormRef"
                :model="paramForm"
                :rules="paramFormRules"
                label-width="80px"
                :label-position="isMobile ? 'top' : 'left'"
                :disabled="disabled || saving"
            >
                <div v-show="!isMobile || mobileStep === 0">
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

                </div><div v-show="!isMobile || mobileStep === 1">
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
                </div>
            </el-form>

            <template #footer>
                <el-button @click="cancelParamDialog">取消</el-button>
                <el-button type="primary" :disabled="disabled" :loading="saving" @click="saveParam">
                    {{ editingParam ? '保存' : '添加' }}
                </el-button>
            </template>
        </component>
    </div>
</template>

<script setup>
import { ref, computed, inject, watch, onBeforeUnmount, onDeactivated, onActivated } from 'vue'
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
import { useVerticalResize } from '@/utils/action/useVerticalResize'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
const { isMobile } = useMobileViewport()
const mobileStep = ref(0), saving = ref(false)
let active = true, dialogGeneration = 0, confirming = false

const props = defineProps({
    disabled: { type: Boolean, default: false },
    params: {
        type: Array,
        default: () => []
    },
    bindings: {
        type: Object,
        default: () => ({})
    },
    /** 为 true 时不绘制顶部分割线与 mt-4，用于与其它折叠块同组叠放 */
    embedded: {
        type: Boolean,
        default: false
    },
    /** 为 true 时固定高度并提供拖拽调整；为 false 时高度随内容变化 */
    resizable: {
        type: Boolean,
        default: true
    }
})

const emit = defineEmits(['update:params', 'update:bindings'])

const { height, isResizing, startResize } = useVerticalResize(300, 200, 600)

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
    if (props.disabled || !active) return
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
    if (props.disabled || !active || confirming) return
    const generation = dialogGeneration
    confirming = true
    const refCount = getParamRefCount(param.name)
    
    const message = refCount > 0
        ? `该参数被 ${refCount} 个字段引用，删除后这些字段将恢复为固定值模式。确认删除？`
        : '确认删除该参数？'
    
    ElMessageBox.confirm(message, '警告', {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消'
    }).then(() => {
        if (!active || props.disabled || generation !== dialogGeneration) return
        deleteParam(param)
    }).catch(() => {}).finally(() => { if (generation === dialogGeneration) confirming = false })
}

const deleteParam = (param) => {
    if (props.disabled || !active) return
    const newParams = props.params.filter(p => p.id !== param.id)
    emit('update:params', newParams)
    
    const newBindings = Object.fromEntries(Object.entries(props.bindings).map(([id, bindings]) => [id, { ...bindings }]))
    removeParamBindings(param.name, newBindings)
    emit('update:bindings', newBindings)
    
    ElMessage.success('参数删除成功')
}

const saveParam = async () => {
    if (!paramFormRef.value || saving.value || props.disabled || !active || !showAddDialog.value) return
    const generation = dialogGeneration
    saving.value = true
    
    try {
        const valid = await paramFormRef.value.validate()
        if (valid === false) { mobileStep.value = 0; return }
        if (!active || props.disabled || generation !== dialogGeneration || !showAddDialog.value) return
        
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
                    const newBindings = Object.fromEntries(Object.entries(props.bindings).map(([id, bindings]) => [id, { ...bindings }]))
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
        if (!active || generation !== dialogGeneration) return
        mobileStep.value = 0
        console.error('表单验证失败:', error)
    } finally {
        if (generation === dialogGeneration) saving.value = false
    }
}

const cancelParamDialog = () => {
    dialogGeneration++
    saving.value = false
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
const localDrafts = inject('blueprintLocalDrafts', null), draftKeyId = Symbol('模板参数草稿'), initialDraft = ref('')
const draftSignature = computed(() => JSON.stringify(paramForm.value))
watch(showAddDialog, visible => { if (visible) { dialogGeneration++; mobileStep.value = 0; initialDraft.value = draftSignature.value } }, { flush: 'sync' })
watch([showAddDialog, draftSignature, isMobile], () => {
    if (isMobile.value && showAddDialog.value && draftSignature.value !== initialDraft.value) localDrafts?.set(draftKeyId, draftSignature.value)
    else localDrafts?.delete(draftKeyId)
}, { flush: 'sync' })
watch(() => props.disabled, value => { if (value) { if (confirming) ElMessageBox.close(); confirming = false; cancelParamDialog() } })
onActivated(() => { active = true })
onDeactivated(() => { active = false; if (confirming) ElMessageBox.close(); confirming = false; cancelParamDialog() })
onBeforeUnmount(() => { active = false; if (confirming) ElMessageBox.close(); confirming = false; dialogGeneration++; localDrafts?.delete(draftKeyId) })
</script>

<style scoped>
.template-params-manager {
    width: 100%;
}
.mobile-template-manager { display: grid; gap: 12px; }.mobile-template-manager header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }.mobile-template-manager h3 { font-weight: 650; font-size: 16px; }.mobile-template-manager p { font-size: 12px; color: #64748b; line-height: 1.75; overflow-wrap: anywhere; }.mobile-param-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; }.mobile-param-card h4 { font-size: 15px; font-weight: 600; overflow-wrap: anywhere; }.mobile-param-card .param-code { font-family: monospace; }.mobile-param-meta { display: flex; gap: 12px; color: #64748b; font-size: 12px; margin-top: 10px; }.mobile-param-card footer { display: flex; gap: 8px; margin-top: 12px; }.mobile-param-card footer .el-button { flex: 1; margin: 0; }.mobile-template-manager :deep(.el-button) { min-height: 44px; }.mobile-param-empty { padding: 24px 0; text-align: center; }
.mobile-param-steps { display: flex; gap: 8px; margin-bottom: 18px; }.mobile-param-steps button { flex: 1; min-height: 44px; border-radius: 9px; background: #f1f5f9; color: #64748b; }.mobile-param-steps button.active { background: #eff6ff; color: #2563eb; }
@media (max-width: 767px) { :deep(.template-param-edit .el-input__wrapper), :deep(.template-param-edit .el-select__wrapper) { min-height: 44px; } }

.params-content {
    overflow-y: auto;
}

.param-item {
    transition: all 0.2s ease;
}

.param-item:hover {
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
</style>
