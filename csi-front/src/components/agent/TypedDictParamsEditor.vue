<!--
  类型化字典参数编辑器 (TypedDictParamsEditor)

  支持多行键值参数编辑，值类型涵盖 string / number / boolean / null / array / object。
  array、object 类型可通过侧栏 JSON 编辑器与 AnyValueTreeEditor 可视化编辑。

  使用场景：
  - 分析引擎启动弹窗中的执行参数 (injection_param)
  - 其他需要用户自定义多类型字典参数的表单

  使用方法：
  <template>
    <TypedDictParamsEditor
      v-model="paramRows"
      title="执行参数 (injection_param)"
    />
  </template>

  <script setup>
  import TypedDictParamsEditor from '@/components/agent/TypedDictParamsEditor.vue'
  import { objectToParamRows, buildObjectFromParamRows } from '@/utils/typedDictParams'

  const paramRows = ref(objectToParamRows({ entity_uuid: '...', entity_type: 'article' }))

  function getInjectionParam() {
    return buildObjectFromParamRows(paramRows.value)
  }
  </script>

  Props:
  - modelValue (Array, 默认: []): 参数行数组 ParamRow[]，支持 v-model
      每行格式: { key: string, valueType: string, value: any }
  - title (String, 默认: '执行参数'): 编辑器标题

  Events:
  - update:modelValue: 参数行变化

  Expose:
  - resetValuePanelState(): 关闭 array/object 侧栏编辑面板

  配套工具：
  - @/utils/typedDictParams.js 提供 objectToParamRows / buildObjectFromParamRows / validateParamRows
-->
<template>
  <div class="flex gap-4 min-w-0">
    <div class="flex-1 min-w-0 border border-gray-200 rounded-xl overflow-hidden">
      <div class="bg-blue-50 px-4 py-2.5 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Icon icon="mdi:cog-outline" class="text-blue-600" />
          <span class="font-medium text-blue-800 text-sm">{{ title }}</span>
        </div>
        <el-button size="small" type="primary" link @click="addRow">
          <template #icon><Icon icon="mdi:plus" /></template>
          添加参数
        </el-button>
      </div>
      <div class="p-4">
        <div v-if="rows.length === 0" class="text-center text-gray-400 text-sm py-3">
          暂无参数
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="(row, index) in rows"
            :key="index"
            class="border border-gray-100 rounded-lg p-2.5 bg-white"
          >
            <div class="flex items-center gap-2 mb-1.5">
              <el-input v-model="row.key" placeholder="参数名" size="small" style="width:140px;flex-shrink:0" />
              <el-select
                v-model="row.valueType"
                size="small"
                style="width:100px;flex-shrink:0"
                @change="onValueTypeChange(row)"
              >
                <el-option label="字符串" value="string" />
                <el-option label="数值" value="number" />
                <el-option label="布尔" value="boolean" />
                <el-option label="空值" value="null" />
                <el-option label="数组" value="array" />
                <el-option label="对象" value="object" />
              </el-select>
              <el-switch v-if="row.valueType === 'boolean'" v-model="row.value" class="ml-1" />
              <div class="ml-auto">
                <el-button size="small" type="danger" link @click="removeRow(index)">
                  <Icon icon="mdi:delete" />
                </el-button>
              </div>
            </div>
            <div v-if="row.valueType !== 'boolean'">
              <el-input
                v-if="row.valueType === 'string'"
                v-model="row.value"
                placeholder="参数值"
                size="small"
              />
              <el-input-number
                v-else-if="row.valueType === 'number'"
                v-model="row.value"
                size="small"
                class="w-full"
                controls-position="right"
              />
              <div
                v-else-if="row.valueType === 'null'"
                class="text-xs text-gray-500 px-2 py-2 bg-gray-50 border border-gray-200 rounded-md"
              >
                当前值为 null
              </div>
              <div v-else-if="row.valueType === 'array' || row.valueType === 'object'" class="flex items-center gap-2">
                <div class="flex-1 min-w-0">
                  <div class="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-md px-2 py-2 wrap-break-word">
                    {{ summarizeValue(row.value) }}
                  </div>
                </div>
                <el-button
                  size="small"
                  :type="isValueSlotActive(index) ? 'primary' : 'default'"
                  @click="toggleValueSlot(index)"
                >
                  编辑
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="isValuePanelOpen"
      class="flex w-full min-w-0 max-w-[min(400px,42vw)] shrink-0 flex-col border border-gray-200 rounded-xl overflow-hidden"
    >
      <div class="bg-gray-50 px-4 py-2.5 text-sm font-medium text-gray-800 border-b border-gray-200">
        {{ valuePanelTitle }}
      </div>
      <div class="p-3 flex flex-col min-h-0 flex-1">
        <div
          v-if="valuePanelJsonError"
          class="mb-2 flex shrink-0 items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600"
        >
          <Icon icon="mdi:alert-circle" />
          {{ valuePanelJsonError }}
        </div>
        <div
          class="flex min-h-0 flex-[1_1_42%] flex-col mb-2 [&_.monaco-editor-container]:min-h-40 [&_.monaco-editor-container]:h-full [&_.monaco-editor-container]:flex-1"
        >
          <MonacoEditor
            v-model="valuePanelJsonString"
            language="json"
            :min-height="160"
          />
        </div>
        <div class="mb-2 shrink-0 text-xs text-gray-500">
          支持任意类型与多重嵌套。上方为 JSON 预览，可与下方可视化编辑双向同步。
        </div>
        <div class="min-h-0 flex-[1_1_50%] overflow-y-auto">
          <AnyValueTreeEditor ref="valueEditorRef" v-model="valuePanelTempValue" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import AnyValueTreeEditor from '@/components/common/AnyValueTreeEditor/AnyValueTreeEditor.vue'
import {
  summarizeValue,
  deepCloneJsonLike,
  resetParamRowValueByType,
  createEmptyParamRow,
} from '@/utils/typedDictParams'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: '执行参数',
  },
})

const emit = defineEmits(['update:modelValue'])

const rows = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const activeValueIndex = ref(null)
const valuePanelTempValue = ref(null)
const valueEditorRef = ref(null)
const valuePanelJsonString = ref('')
const valuePanelJsonError = ref('')

const VALUE_JSON_DEBOUNCE_MS = 300
let isValueUpdatingFromMonaco = false
let isValueUpdatingFromTree = false
let valueJsonDebounceTimer = null

const isValuePanelOpen = computed(() => activeValueIndex.value !== null)

const valuePanelTitle = computed(() => {
  const index = activeValueIndex.value
  if (index === null) return ''
  const row = rows.value[index]
  if (!row) return '编辑值'
  return `编辑值：${row.key || '(未命名参数)'}`
})

function getRow(index) {
  return rows.value[index]
}

function loadValuePanelFromRow(index) {
  const row = getRow(index)
  if (!row) return
  activeValueIndex.value = index
  valuePanelTempValue.value = deepCloneJsonLike(
    row.value,
    row.valueType === 'array' ? [] : row.valueType === 'object' ? {} : null
  )
  isValueUpdatingFromTree = true
  valuePanelJsonError.value = ''
  try {
    valuePanelJsonString.value = JSON.stringify(valuePanelTempValue.value, null, 2)
  } catch {
    valuePanelJsonString.value = ''
    valuePanelJsonError.value = '当前值无法序列化为 JSON'
  }
  nextTick(() => {
    isValueUpdatingFromTree = false
  })
}

function resetValuePanelState() {
  clearTimeout(valueJsonDebounceTimer)
  valueJsonDebounceTimer = null
  isValueUpdatingFromTree = true
  valuePanelJsonString.value = ''
  valuePanelJsonError.value = ''
  activeValueIndex.value = null
  valuePanelTempValue.value = null
  nextTick(() => {
    isValueUpdatingFromTree = false
  })
}

function commitValuePanelToRow() {
  const index = activeValueIndex.value
  if (index === null) return
  const row = getRow(index)
  if (!row) return
  const next = [...rows.value]
  next[index] = {
    ...row,
    value: deepCloneJsonLike(valuePanelTempValue.value, row.valueType === 'array' ? [] : {}),
  }
  rows.value = next
}

function isValueSlotActive(index) {
  return activeValueIndex.value === index
}

function toggleValueSlot(index) {
  if (activeValueIndex.value === index) {
    resetValuePanelState()
    return
  }
  loadValuePanelFromRow(index)
}

function addRow() {
  rows.value = [...rows.value, createEmptyParamRow()]
}

function removeRow(index) {
  if (activeValueIndex.value === index) {
    resetValuePanelState()
  } else if (activeValueIndex.value !== null && activeValueIndex.value > index) {
    activeValueIndex.value -= 1
  }
  const next = [...rows.value]
  next.splice(index, 1)
  rows.value = next
}

function onValueTypeChange(row) {
  resetParamRowValueByType(row)
  if (activeValueIndex.value !== null) {
    const activeRow = getRow(activeValueIndex.value)
    if (activeRow === row) {
      loadValuePanelFromRow(activeValueIndex.value)
    }
  }
}

watch(
  () => valuePanelTempValue.value,
  () => {
    if (!isValuePanelOpen.value) return
    if (isValueUpdatingFromMonaco) return
    isValueUpdatingFromTree = true
    try {
      valuePanelJsonString.value = JSON.stringify(valuePanelTempValue.value, null, 2)
      valuePanelJsonError.value = ''
      commitValuePanelToRow()
    } catch (e) {
      valuePanelJsonError.value = 'JSON 格式错误：' + e.message
    }
    nextTick(() => {
      isValueUpdatingFromTree = false
    })
  },
  { deep: true }
)

watch(valuePanelJsonString, (val) => {
  if (isValueUpdatingFromTree) return
  clearTimeout(valueJsonDebounceTimer)
  valueJsonDebounceTimer = setTimeout(() => {
    try {
      const parsed = JSON.parse(val)
      isValueUpdatingFromMonaco = true
      valuePanelTempValue.value = parsed
      valuePanelJsonError.value = ''
      commitValuePanelToRow()
      nextTick(() => {
        isValueUpdatingFromMonaco = false
      })
    } catch (e) {
      valuePanelJsonError.value = 'JSON 格式错误：' + e.message
    }
  }, VALUE_JSON_DEBOUNCE_MS)
})

defineExpose({ resetValuePanelState })
</script>
