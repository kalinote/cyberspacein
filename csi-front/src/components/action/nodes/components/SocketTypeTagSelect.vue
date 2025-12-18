<template>
    <div class="socket-type-tag-select">
        <div v-if="selectedTypes.length > 0" class="tags-display mb-2">
            <el-tag
                v-for="(type, index) in selectedTypes"
                :key="index"
                closable
                :disable-transitions="false"
                @close="handleRemoveTag(index)"
                size="small"
                class="mr-1 mb-1"
            >
                {{ type }}
            </el-tag>
        </div>
        
        <div class="select-with-button flex gap-2">
            <el-select
                v-model="selectedValue"
                placeholder="请选择接口类型"
                size="small"
                class="flex-1"
                :disabled="disabled"
                clearable
            >
                <el-option
                    v-for="socketType in availableSocketTypes"
                    :key="socketType.socket_type"
                    :label="socketType.socket_type"
                    :value="socketType.socket_type"
                />
            </el-select>
            <el-button
                size="small"
                type="primary"
                :icon="Plus"
                @click="handleAddTag"
                :disabled="disabled || !selectedValue"
            >
                添加
            </el-button>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
    modelValue: {
        type: Array,
        default: () => []
    },
    socketTypes: {
        type: Array,
        default: () => []
    },
    placeholder: {
        type: String,
        default: '请选择接口类型'
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['update:modelValue'])

const selectedTypes = ref([...props.modelValue])
const selectedValue = ref('')

watch(() => props.modelValue, (newVal) => {
    selectedTypes.value = [...(newVal || [])]
}, { deep: true })

const availableSocketTypes = computed(() => {
    return props.socketTypes.filter(st => !selectedTypes.value.includes(st.socket_type))
})

const handleAddTag = () => {
    if (!selectedValue.value) return
    
    if (selectedTypes.value.includes(selectedValue.value)) {
        ElMessage.warning('该类型已存在')
        return
    }
    
    selectedTypes.value.push(selectedValue.value)
    emit('update:modelValue', selectedTypes.value)
    selectedValue.value = ''
}

const handleRemoveTag = (index) => {
    selectedTypes.value.splice(index, 1)
    emit('update:modelValue', selectedTypes.value)
}
</script>

<style scoped>
.socket-type-tag-select {
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

.select-with-button {
    width: 100%;
}
</style>
