<template>
  <el-dialog
    v-model="visible"
    title="编辑专题事件"
    width="520px"
    destroy-on-close
    @closed="onClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" @submit.prevent>
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="页面标题" maxlength="200" />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="form.status" placeholder="选择状态" class="w-full">
          <el-option label="草稿" value="draft" />
          <el-option label="构建中" value="building" />
          <el-option label="已发布" value="published" />
        </el-select>
      </el-form-item>
      <el-form-item label="分类" prop="categories">
        <el-select
          v-model="form.categories"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="输入后回车添加分类"
          class="w-full"
        />
      </el-form-item>
      <el-form-item label="来源说明" prop="sourceNote">
        <el-input v-model="form.sourceNote" placeholder="可选" maxlength="500" />
      </el-form-item>
      <el-form-item label="变更说明" prop="changeSummary">
        <el-input
          v-model="form.changeSummary"
          type="textarea"
          :rows="2"
          placeholder="可选，将写入版本历史"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { wikiApi } from '@/api/wiki.js'
import { isWikiRevisionConflict } from '@/utils/wikiPersist.js'

/**
 * @typedef {import('@/types/wiki.js').WikiPageListItem} WikiPageListItem
 */

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  row: {
    /** @type {import('vue').PropType<WikiPageListItem|null>} */
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue', 'updated'])

const visible = ref(props.modelValue)
const submitting = ref(false)
const formRef = ref(null)
/** @type {import('vue').Ref<number>} */
const expectedRevision = ref(0)

const form = ref({
  title: '',
  status: 'draft',
  categories: [],
  sourceNote: '',
  changeSummary: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
    if (val && props.row) {
      fillFormFromRow(props.row)
    }
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

/**
 * @param {WikiPageListItem} row
 */
function fillFormFromRow(row) {
  expectedRevision.value = row.revision ?? 0
  form.value = {
    title: row.title || '',
    status: row.status || 'draft',
    categories: Array.isArray(row.categories) ? [...row.categories] : [],
    sourceNote: row.sourceNote || '',
    changeSummary: '',
  }
}

function onClosed() {
  expectedRevision.value = 0
  form.value = {
    title: '',
    status: 'draft',
    categories: [],
    sourceNote: '',
    changeSummary: '',
  }
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value || !props.row?.id) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await wikiApi.updateMeta(props.row.id, {
      expectedRevision: expectedRevision.value,
      title: form.value.title.trim(),
      status: form.value.status,
      categories: form.value.categories,
      sourceNote: form.value.sourceNote.trim() || undefined,
      changeSummary: form.value.changeSummary.trim() || undefined,
    })
    visible.value = false
    emit('updated')
    ElMessage.success('已保存')
  } catch (e) {
    if (isWikiRevisionConflict(e)) {
      ElMessage.warning('页面已被他人修改，请关闭后刷新列表再试')
    }
  } finally {
    submitting.value = false
  }
}
</script>
