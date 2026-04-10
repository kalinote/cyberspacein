<template>
  <div class="border border-gray-200 rounded-lg bg-white">
    <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
      <div v-if="depth > 0" class="text-xs text-gray-400 select-none">层级 {{ depth }}</div>
      <el-select v-model="type" size="small" style="width: 120px" @change="handleTypeChange">
        <el-option label="字符串" value="string" />
        <el-option label="数值" value="number" />
        <el-option label="布尔" value="boolean" />
        <el-option label="空值" value="null" />
        <el-option label="数组" value="array" />
        <el-option label="对象" value="object" />
      </el-select>

      <div class="ml-auto flex items-center gap-2">
        <el-button
          v-if="type === 'array'"
          size="small"
          type="primary"
          @click="addArrayItem"
        >
          添加元素
        </el-button>
        <el-button
          v-if="type === 'object'"
          size="small"
          type="primary"
          @click="addObjectField"
        >
          添加字段
        </el-button>
      </div>
    </div>

    <div class="p-3">
      <el-input
        v-if="type === 'string'"
        v-model="localValue"
        size="small"
        placeholder="请输入值"
        clearable
      />

      <el-input-number
        v-else-if="type === 'number'"
        v-model="localValue"
        size="small"
        class="w-full"
        controls-position="right"
      />

      <el-switch v-else-if="type === 'boolean'" v-model="localValue" />

      <div v-else-if="type === 'null'" class="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-md px-2 py-2">
        当前值为 null
      </div>

      <div v-else-if="type === 'array'" class="space-y-2">
        <div v-if="!Array.isArray(localValue) || localValue.length === 0" class="text-xs text-gray-400">
          暂无元素
        </div>

        <div
          v-for="(item, idx) in localValue"
          :key="idx"
          class="border border-gray-100 rounded-lg bg-gray-50"
        >
          <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
            <div class="text-xs text-gray-500 font-mono">[{{ idx }}]</div>
            <el-button
              size="small"
              @click="toggleArrayItem(idx)"
            >
              {{ isArrayItemExpanded(idx) ? '折叠' : '展开' }}
            </el-button>
            <div class="ml-auto flex items-center gap-2">
              <el-button size="small" @click="moveArrayItem(idx, -1)" :disabled="idx === 0">上移</el-button>
              <el-button size="small" @click="moveArrayItem(idx, 1)" :disabled="idx === localValue.length - 1">下移</el-button>
              <el-button size="small" type="danger" @click="removeArrayItem(idx)">删除</el-button>
            </div>
          </div>
          <div class="p-3">
            <div
              v-if="!isArrayItemExpanded(idx)"
              class="text-xs text-gray-500 bg-white border border-gray-200 rounded-md px-2 py-2"
            >
              {{ summarize(item) }}
            </div>
            <AnyValueTreeNode
              v-else
              v-model="localValue[idx]"
              :depth="depth + 1"
            />
          </div>
        </div>
      </div>

      <div v-else-if="type === 'object'" class="space-y-2">
        <div v-if="!isPlainObject(localValue) || Object.keys(localValue).length === 0" class="text-xs text-gray-400">
          暂无字段
        </div>

        <div
          v-for="(entry, idx) in objectEntries"
          :key="entry.__id"
          class="border border-gray-100 rounded-lg bg-gray-50"
        >
          <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
            <el-input
              v-model="entry.key"
              size="small"
              style="width: 220px"
              placeholder="键"
              @input="syncObjectFromEntries"
            />
            <el-button size="small" @click="toggleObjectField(entry.__id)">
              {{ isObjectFieldExpanded(entry.__id) ? '折叠' : '展开' }}
            </el-button>
            <div class="ml-auto flex items-center gap-2">
              <el-button size="small" type="danger" @click="removeObjectField(idx)">删除</el-button>
            </div>
          </div>
          <div class="p-3">
            <div
              v-if="!isObjectFieldExpanded(entry.__id)"
              class="text-xs text-gray-500 bg-white border border-gray-200 rounded-md px-2 py-2"
            >
              {{ summarize(entry.value) }}
            </div>
            <AnyValueTreeNode
              v-else
              v-model="entry.value"
              :depth="depth + 1"
              @update:model-value="syncObjectFromEntries"
            />
          </div>
        </div>

        <div v-if="objectKeyErrors.length" class="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-2">
          {{ objectKeyErrors[0] }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * AnyValueTreeNode
 *
 * 简介：
 * - `AnyValueTreeEditor` 的递归节点组件，负责渲染与编辑单个值节点（并递归编辑子节点）。
 *
 * 详细用法：
 * - 通常不要直接在业务页面引用它；请使用 `AnyValueTreeEditor`。
 *
 * 交互说明：
 * - 数组：支持添加/删除/上移/下移；可对单个元素折叠/展开。
 * - 对象：支持添加/删除字段、编辑键；键为空/重复会提示。
 */
import { computed, ref, watch } from 'vue'

defineOptions({ name: 'AnyValueTreeNode' })

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean, Array, Object, null],
    default: null
  },
  depth: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:modelValue'])

function detect(val) {
  if (val === null) return 'null'
  if (Array.isArray(val)) return 'array'
  if (typeof val === 'object') return 'object'
  if (typeof val === 'boolean') return 'boolean'
  if (typeof val === 'number') return 'number'
  return 'string'
}

const type = ref(detect(props.modelValue))

const localValue = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

watch(
  () => props.modelValue,
  (val) => {
    const nextType = detect(val)
    if (nextType !== type.value) type.value = nextType
    if (nextType === 'object') ensureObjectEntries()
  },
  { deep: true }
)

function isPlainObject(val) {
  return val !== null && typeof val === 'object' && !Array.isArray(val)
}

function handleTypeChange(next) {
  if (next === 'string') localValue.value = ''
  else if (next === 'number') localValue.value = 0
  else if (next === 'boolean') localValue.value = false
  else if (next === 'null') localValue.value = null
  else if (next === 'array') localValue.value = []
  else if (next === 'object') localValue.value = {}
}

function createDefaultItemValue() {
  return ''
}

function summarize(val) {
  if (val === null) return 'null'
  const t = typeof val
  if (t === 'string') return val.length > 80 ? JSON.stringify(val.slice(0, 80) + '...') : JSON.stringify(val)
  if (t === 'number' || t === 'boolean') return String(val)
  if (Array.isArray(val)) return `数组(${val.length})`
  if (t === 'object') return `对象(${Object.keys(val || {}).length})`
  return String(val)
}

const arrayExpanded = ref({})
function isArrayItemExpanded(idx) {
  if (arrayExpanded.value[idx] === undefined) return props.depth < 2
  return !!arrayExpanded.value[idx]
}
function toggleArrayItem(idx) {
  arrayExpanded.value[idx] = !isArrayItemExpanded(idx)
}

function addArrayItem() {
  if (!Array.isArray(localValue.value)) localValue.value = []
  localValue.value = [...localValue.value, createDefaultItemValue()]
}

function removeArrayItem(idx) {
  if (!Array.isArray(localValue.value)) return
  const next = [...localValue.value]
  next.splice(idx, 1)
  localValue.value = next
}

function moveArrayItem(idx, delta) {
  if (!Array.isArray(localValue.value)) return
  const nextIdx = idx + delta
  if (nextIdx < 0 || nextIdx >= localValue.value.length) return
  const next = [...localValue.value]
  const tmp = next[idx]
  next[idx] = next[nextIdx]
  next[nextIdx] = tmp
  localValue.value = next
}

const objectEntries = ref([])
const objectExpanded = ref({})

function ensureObjectEntries() {
  if (!isPlainObject(localValue.value)) {
    objectEntries.value = []
    return
  }
  // 注意：Object.keys 对“整数样式字符串键”(如 "1","2") 会有特殊排序规则，
  // 若按 keys 重建 entries 会导致编辑时跳行/失焦。这里以现有 entries 顺序为准更新。
  const obj = localValue.value
  const currentKeys = Object.keys(obj)
  const existingByKey = new Map(objectEntries.value.map((e) => [e.key, e]))
  const used = new Set()
  const nextEntries = []

  // 先按当前 entries 的顺序更新，保持 __id 与对象引用稳定
  objectEntries.value.forEach((e) => {
    const k = e.key
    if (!k || !Object.prototype.hasOwnProperty.call(obj, k)) return
    e.value = obj[k]
    used.add(k)
    nextEntries.push(e)
  })

  // 再追加新增的键
  currentKeys.forEach((k) => {
    if (used.has(k)) return
    const existed = existingByKey.get(k)
    if (existed) {
      existed.value = obj[k]
      nextEntries.push(existed)
    } else {
      nextEntries.push({ __id: `${Date.now()}_${Math.random()}`, key: k, value: obj[k] })
    }
  })

  objectEntries.value = nextEntries
}

watch(
  () => type.value,
  (t) => {
    if (t === 'object') ensureObjectEntries()
  },
  { immediate: true }
)

function addObjectField() {
  if (!isPlainObject(localValue.value)) localValue.value = {}
  const id = `${Date.now()}_${Math.random()}`
  objectEntries.value.push({ __id: id, key: '', value: '' })
  objectExpanded.value[id] = true
}

function removeObjectField(idx) {
  objectEntries.value.splice(idx, 1)
  syncObjectFromEntries()
}

function isObjectFieldExpanded(id) {
  if (objectExpanded.value[id] === undefined) return props.depth < 2
  return !!objectExpanded.value[id]
}
function toggleObjectField(id) {
  objectExpanded.value[id] = !isObjectFieldExpanded(id)
}

const objectKeyErrors = computed(() => {
  if (type.value !== 'object') return []
  const keys = objectEntries.value.map((e) => (e.key ?? '').trim())
  const errors = []
  if (keys.some((k) => !k)) errors.push('对象键不能为空')
  const seen = new Set()
  for (const k of keys) {
    if (!k) continue
    if (seen.has(k)) errors.push(`对象键重复：${k}`)
    else seen.add(k)
  }
  return errors
})

function syncObjectFromEntries() {
  if (type.value !== 'object') return
  const next = {}
  objectEntries.value.forEach((e) => {
    const k = (e.key ?? '').trim()
    if (!k) return
    next[k] = e.value
  })
  localValue.value = next
}
</script>

