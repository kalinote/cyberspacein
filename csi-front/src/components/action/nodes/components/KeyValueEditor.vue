<template>
    <div class="key-value-editor">
        <div v-if="keyValuePairs.length > 0" class="pairs-display mb-3 space-y-2">
            <div
                v-for="(pair, index) in keyValuePairs"
                :key="index"
                class="flex items-center gap-2 p-2 bg-gray-50 rounded border border-gray-200"
            >
                <el-input
                    v-model="pair.key"
                    placeholder="键"
                    size="small"
                    class="flex-1"
                    @input="updateModelValue"
                />
                <span class="text-gray-400">:</span>
                <el-input
                    v-model="pair.value"
                    placeholder="值"
                    size="small"
                    class="flex-1"
                    @input="updateModelValue"
                />
                <el-button
                    type="danger"
                    size="small"
                    link
                    @click="removePair(index)"
                >
                    <template #icon>
                        <Icon icon="mdi:delete" />
                    </template>
                </el-button>
            </div>
        </div>
        
        <el-button
            type="primary"
            size="small"
            @click="addPair"
        >
            <template #icon>
                <Icon icon="mdi:plus" />
            </template>
            添加键值对
        </el-button>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
    modelValue: {
        type: Object,
        default: () => ({})
    }
})

const emit = defineEmits(['update:modelValue'])

const keyValuePairs = ref([])

const updatePairsFromModel = () => {
    if (!props.modelValue || typeof props.modelValue !== 'object') {
        keyValuePairs.value = []
        return
    }

    const currentObj = {}
    keyValuePairs.value.forEach(pair => {
        if (pair.key && pair.key.trim()) {
            currentObj[pair.key.trim()] = pair.value || ''
        }
    })

    if (JSON.stringify(currentObj) === JSON.stringify(props.modelValue)) {
        return
    }

    keyValuePairs.value = Object.entries(props.modelValue).map(([key, value]) => ({
        key,
        value: String(value)
    }))
}

watch(() => props.modelValue, updatePairsFromModel, { immediate: true, deep: true })

const updateModelValue = () => {
    const obj = {}
    keyValuePairs.value.forEach(pair => {
        if (pair.key && pair.key.trim()) {
            obj[pair.key.trim()] = pair.value || ''
        }
    })
    emit('update:modelValue', obj)
}

const addPair = () => {
    keyValuePairs.value.push({ key: '', value: '' })
}

const removePair = (index) => {
    keyValuePairs.value.splice(index, 1)
    updateModelValue()
}
</script>

<style scoped>
.key-value-editor {
    width: 100%;
}
</style>
