<template>
  <el-dialog
    v-model="visible"
    title="编辑注释"
    width="560px"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <p class="text-xs text-gray-500 mb-3">
      正文使用 <code class="text-blue-600">[^a]</code> 引用注释，字母与列表 ID 一致；删除条目不会自动改正文。
    </p>
    <div v-if="draft.length" class="flex flex-col gap-3 max-h-96 overflow-y-auto pr-1">
      <div
        v-for="(item, index) in draft"
        :key="item.id"
        class="flex gap-2 items-start rounded-lg border border-gray-200 p-3 bg-gray-50/50"
      >
        <span
          class="shrink-0 text-sm font-mono font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded min-w-8 text-center"
        >
          {{ item.id }}
        </span>
        <el-input
          v-model="item.text"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          placeholder="注释正文"
          class="flex-1 min-w-0"
        />
        <div class="flex flex-col gap-1 shrink-0">
          <el-button
            size="small"
            :disabled="index === 0"
            title="上移"
            @click="moveItem(index, -1)"
          >
            <Icon icon="mdi:chevron-up" />
          </el-button>
          <el-button
            size="small"
            :disabled="index === draft.length - 1"
            title="下移"
            @click="moveItem(index, 1)"
          >
            <Icon icon="mdi:chevron-down" />
          </el-button>
          <el-button size="small" type="danger" plain title="删除" @click="removeItem(index)">
            <Icon icon="mdi:delete-outline" />
          </el-button>
        </div>
      </div>
    </div>
    <p v-else class="text-sm text-gray-400 text-center py-6">暂无注释，点击下方添加</p>
    <el-button type="primary" plain class="w-full mt-3" @click="addItem">
      <Icon icon="mdi:plus" class="mr-1" />
      添加注释
    </el-button>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleApply">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { nextFootnoteId } from '@/utils/wikiCitationIds.js'

/** @typedef {import('@/types/wiki.js').WikiFootnote} WikiFootnote */

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  /** @type {import('vue').PropType<WikiFootnote[]>} */
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue', 'apply'])

const visible = ref(props.modelValue)
/** @type {import('vue').Ref<WikiFootnote[]>} */
const draft = ref([])

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function cloneItems(items) {
  return (items || []).map((item) => ({
    id: String(item.id),
    text: String(item.text ?? ''),
  }))
}

function onOpen() {
  draft.value = cloneItems(props.items)
}

function onClosed() {
  draft.value = []
}

function addItem() {
  const id = nextFootnoteId(draft.value.map((item) => item.id))
  draft.value.push({ id, text: '' })
}

/**
 * @param {number} index
 */
function removeItem(index) {
  draft.value.splice(index, 1)
}

/**
 * @param {number} index
 * @param {number} delta
 */
function moveItem(index, delta) {
  const next = index + delta
  if (next < 0 || next >= draft.value.length) return
  const list = [...draft.value]
  const [item] = list.splice(index, 1)
  list.splice(next, 0, item)
  draft.value = list
}

function handleApply() {
  emit('apply', cloneItems(draft.value))
  visible.value = false
}
</script>
