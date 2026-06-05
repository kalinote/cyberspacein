<template>
    <div class="key-value-editor w-full min-w-0">
        <div v-if="keyValuePairs.length > 0" class="mb-3 space-y-2">
            <div
                v-for="(pair, index) in keyValuePairs"
                :key="index"
                class="rounded-lg border border-gray-200 bg-gray-50 p-2 min-w-0"
            >
                <div
                    class="flex items-center gap-2 min-w-0"
                    :class="isJsonValueType(pair) ? 'mb-2' : ''"
                >
                    <el-input
                        v-model="pair.key"
                        placeholder="键"
                        size="small"
                        class="kv-field-key min-w-0"
                        @input="onPairChange"
                    />
                    <template v-if="typedValues">
                        <el-select
                            v-model="pair.valueType"
                            size="small"
                            class="kv-field-type shrink-0"
                            @change="onValueTypeChange(index)"
                        >
                            <el-option
                                v-for="opt in TYPED_VALUE_OPTIONS"
                                :key="opt.value"
                                :label="opt.label"
                                :value="opt.value"
                            />
                        </el-select>
                    </template>
                    <template v-else>
                        <span class="shrink-0 text-gray-400 text-sm leading-none select-none">:</span>
                    </template>
                    <el-input
                        v-if="!typedValues || !isJsonValueType(pair)"
                        v-model="pair.value"
                        :placeholder="valuePlaceholder(pair)"
                        size="small"
                        class="kv-field-value min-w-0"
                        @input="onPairChange"
                    />
                    <el-button
                        type="danger"
                        size="small"
                        link
                        class="shrink-0 ml-0!"
                        @click="removePair(index)"
                    >
                        <template #icon>
                            <Icon icon="mdi:delete" />
                        </template>
                    </el-button>
                </div>
                <el-input
                    v-if="typedValues && isJsonValueType(pair)"
                    v-model="pair.value"
                    type="textarea"
                    :rows="3"
                    :placeholder="valuePlaceholder(pair)"
                    size="small"
                    class="w-full font-mono text-xs"
                    @input="onPairChange"
                />
                <p v-if="pair.parseError" class="text-xs text-red-600 mt-1.5 mb-0">{{ pair.parseError }}</p>
            </div>
        </div>

        <el-button type="primary" size="small" @click="addPair">
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
import {
    TYPED_VALUE_OPTIONS,
    inferValueType,
    parseTypedValue,
    stableStringifyObject,
    valueToEditString,
} from '@/utils/typedKeyValue'

const props = defineProps({
    modelValue: {
        type: Object,
        default: () => ({}),
    },
    typedValues: {
        type: Boolean,
        default: false,
    },
})

const emit = defineEmits(['update:modelValue'])

/** @type {import('vue').Ref<Array<{ key: string, value: string, valueType?: string, parseError?: string }>>} */
const keyValuePairs = ref([])

let syncingFromParent = false

function isJsonValueType(pair) {
    return pair.valueType === 'array' || pair.valueType === 'object'
}

function valuePlaceholder(pair) {
    if (!props.typedValues) return '值'
    if (pair.valueType === 'number') return '数字，如 0.7'
    if (pair.valueType === 'array') return 'JSON 数组，如 ["a","b"]'
    if (pair.valueType === 'object') return 'JSON 对象，如 {"k":"v"}'
    return '字符串值'
}

function buildObjectFromPairs() {
    /** @type {Record<string, unknown>} */
    const obj = {}
    let hasError = false

    for (const pair of keyValuePairs.value) {
        const key = pair.key?.trim()
        if (!key) continue

        if (!props.typedValues) {
            obj[key] = pair.value ?? ''
            continue
        }

        const parsed = parseTypedValue(pair.value, pair.valueType || 'string')
        if (!parsed.ok) {
            pair.parseError = parsed.error
            hasError = true
            continue
        }
        pair.parseError = ''
        obj[key] = parsed.value
    }

    return { obj, hasError }
}

function updatePairsFromModel() {
    if (!props.modelValue || typeof props.modelValue !== 'object') {
        keyValuePairs.value = []
        return
    }

    const { obj: currentObj } = buildObjectFromPairs()
    const incoming = props.modelValue

    if (props.typedValues) {
        if (stableStringifyObject(currentObj) === stableStringifyObject(incoming)) {
            return
        }
    } else if (JSON.stringify(currentObj) === JSON.stringify(incoming)) {
        return
    }

    syncingFromParent = true
    keyValuePairs.value = Object.entries(incoming).map(([key, value]) => {
        if (props.typedValues) {
            const valueType = inferValueType(value)
            return {
                key,
                valueType,
                value: valueToEditString(value, valueType),
                parseError: '',
            }
        }
        return {
            key,
            value: value == null ? '' : String(value),
            parseError: '',
        }
    })
    syncingFromParent = false
}

watch(() => props.modelValue, updatePairsFromModel, { immediate: true, deep: true })

function emitModelValue() {
    if (syncingFromParent) return

    const { obj, hasError } = buildObjectFromPairs()
    if (props.typedValues && hasError) {
        return
    }
    emit('update:modelValue', obj)
}

function onPairChange() {
    emitModelValue()
}

function onValueTypeChange(index) {
    const pair = keyValuePairs.value[index]
    if (!pair) return
    pair.parseError = ''
    if (pair.valueType === 'array') {
        pair.value = '[]'
    } else if (pair.valueType === 'object') {
        pair.value = '{}'
    } else if (pair.valueType === 'number') {
        pair.value = ''
    } else {
        pair.value = ''
    }
    emitModelValue()
}

function addPair() {
    if (props.typedValues) {
        keyValuePairs.value.push({
            key: '',
            valueType: 'string',
            value: '',
            parseError: '',
        })
    } else {
        keyValuePairs.value.push({ key: '', value: '', parseError: '' })
    }
}

function removePair(index) {
    keyValuePairs.value.splice(index, 1)
    emitModelValue()
}
</script>

<style scoped>
.key-value-editor :deep(.kv-field-key) {
    flex: 1 1 28%;
    min-width: 5rem;
}

.key-value-editor :deep(.kv-field-type) {
    width: 5.5rem;
}

.key-value-editor :deep(.kv-field-type .el-select__wrapper) {
    min-height: 24px;
}

.key-value-editor :deep(.kv-field-value) {
    flex: 1 1 36%;
    min-width: 6rem;
}

.key-value-editor :deep(.el-input__wrapper),
.key-value-editor :deep(.el-select__wrapper) {
    box-shadow: 0 0 0 1px var(--el-border-color) inset;
}
</style>
