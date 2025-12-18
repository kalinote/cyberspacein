<template>
    <div class="tag-input-container">
        <div v-if="tags.length > 0" class="tags-display mb-2">
            <el-tag
                v-for="(tag, index) in tags"
                :key="index"
                closable
                :disable-transitions="false"
                @close="handleRemoveTag(index)"
                size="small"
                class="mr-1 mb-1"
            >
                {{ tag }}
            </el-tag>
        </div>
        
        <div class="input-with-button flex gap-2">
            <el-input
                v-model="inputValue"
                :placeholder="placeholder"
                size="small"
                clearable
                @keyup.enter="handleAddTag"
                :disabled="disabled"
                class="flex-1"
            />
            <el-button
                size="small"
                type="primary"
                :icon="Plus"
                @click="handleAddTag"
                :disabled="disabled || !inputValue.trim()"
            >
                添加
            </el-button>
        </div>
        
        <div v-if="showCount" class="text-xs text-gray-400 mt-1">
            已添加 {{ tags.length }} 项
            <span v-if="maxTags"> / 最多 {{ maxTags }} 项</span>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
    modelValue: {
        type: Array,
        default: () => []
    },
    placeholder: {
        type: String,
        default: '输入内容后按回车或点击添加'
    },
    maxTags: {
        type: Number,
        default: null
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

const inputValue = ref('')
const tags = ref([...props.modelValue])

watch(() => props.modelValue, (newVal) => {
    tags.value = [...(newVal || [])]
}, { deep: true })

const handleAddTag = () => {
    const value = inputValue.value.trim()
    if (!value) return
    
    if (tags.value.includes(value)) {
        ElMessage.warning('该标签已存在')
        return
    }
    
    if (props.maxTags && tags.value.length >= props.maxTags) {
        ElMessage.warning(`最多只能添加 ${props.maxTags} 个标签`)
        return
    }
    
    tags.value.push(value)
    emit('update:modelValue', tags.value)
    inputValue.value = ''
}

const handleRemoveTag = (index) => {
    tags.value.splice(index, 1)
    emit('update:modelValue', tags.value)
}
</script>

<style scoped>
.tag-input-container {
    width: 100%;
}

.tags-display {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    min-height: 28px;
    padding: 4px;
    background-color: #f5f7fa;
    border-radius: 4px;
}

.input-with-button {
    width: 100%;
}
</style>
