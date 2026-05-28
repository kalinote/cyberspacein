<template>
  <el-dialog
    v-model="visible"
    title="新建专题事件"
    width="520px"
    destroy-on-close
    @closed="onClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" @submit.prevent>
      <el-form-item label="Slug" prop="slug">
        <el-input
          v-model="form.slug"
          placeholder="如 traveler-genshin（小写字母、数字、连字符）"
          maxlength="128"
        />
      </el-form-item>
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="页面标题" maxlength="200" />
      </el-form-item>
      <el-form-item label="来源说明" prop="sourceNote">
        <el-input v-model="form.sourceNote" placeholder="可选" maxlength="500" />
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
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { wikiApi } from '@/api/wiki.js'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'created'])

const router = useRouter()
const visible = ref(props.modelValue)
const submitting = ref(false)
const formRef = ref(null)

const form = ref({
  slug: '',
  title: '',
  sourceNote: '',
  categories: [],
})

const SLUG_PATTERN = /^[a-z0-9-]{2,128}$/

const rules = {
  slug: [
    { required: true, message: '请输入 Slug', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (!value || SLUG_PATTERN.test(String(value).trim())) {
          callback()
        } else {
          callback(new Error('Slug 仅支持 2–128 位小写字母、数字与连字符'))
        }
      },
      trigger: 'blur',
    },
  ],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function onClosed() {
  form.value = { slug: '', title: '', sourceNote: '', categories: [] }
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const detail = await wikiApi.createPage({
      slug: form.value.slug.trim(),
      title: form.value.title.trim(),
      sourceNote: form.value.sourceNote.trim() || undefined,
      categories: form.value.categories?.length ? form.value.categories : undefined,
    })
    visible.value = false
    emit('created', detail)
    ElMessage.success('创建成功')
    await router.push({ name: 'wiki-detail', params: { slug: detail.slug } })
  } catch {
    /* 错误由 request 拦截器提示 */
  } finally {
    submitting.value = false
  }
}
</script>
