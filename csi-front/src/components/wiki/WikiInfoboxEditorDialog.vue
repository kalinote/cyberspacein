<template>
  <el-dialog
    v-model="visible"
    title="编辑信息框"
    width="560px"
    destroy-on-close
    @closed="onClosed"
  >
    <el-form v-if="form" label-position="top" class="space-y-1">
      <el-form-item label="标题" required>
        <el-input v-model="form.caption" placeholder="信息框标题" />
      </el-form-item>
      <el-form-item label="副标题">
        <el-input v-model="form.series" placeholder="可选" />
      </el-form-item>
      <el-form-item label="图片 URL">
        <el-input v-model="form.image" placeholder="留空则不显示图片" clearable />
      </el-form-item>
      <el-form-item label="字段">
        <div class="w-full space-y-2">
          <div
            v-for="(row, index) in form.rows"
            :key="index"
            class="flex gap-2 items-start"
          >
            <el-input v-model="row.label" placeholder="标签" class="flex-1" />
            <el-input
              v-model="row.value"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="内容"
              class="flex-[1.5]"
            />
            <el-button
              type="danger"
              link
              :disabled="form.rows.length <= 1"
              @click="removeRow(index)"
            >
              <Icon icon="mdi:delete-outline" class="text-lg" />
            </el-button>
          </div>
          <el-button type="primary" link @click="addRow">
            <Icon icon="mdi:plus" class="mr-1" />
            添加行
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { cloneWikiInfobox } from '@/utils/wikiTree.js'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  infobox: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue', 'save'])

const visible = ref(props.modelValue)
/** @type {import('vue').Ref<import('@/types/wiki.js').WikiInfobox|null>} */
const form = ref(null)

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
    if (val) {
      form.value = cloneWikiInfobox(props.infobox) || {
        caption: '',
        series: '',
        image: null,
        rows: [{ label: '', value: '' }],
      }
      if (!form.value.rows?.length) {
        form.value.rows = [{ label: '', value: '' }]
      }
      form.value.image = form.value.image || ''
    }
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function addRow() {
  form.value?.rows.push({ label: '', value: '' })
}

function removeRow(index) {
  if (!form.value || form.value.rows.length <= 1) return
  form.value.rows.splice(index, 1)
}

function onClosed() {
  form.value = null
}

function handleSave() {
  if (!form.value?.caption?.trim()) {
    ElMessage.warning('请填写信息框标题')
    return
  }
  const payload = {
    caption: form.value.caption.trim(),
    series: form.value.series?.trim() || '',
    image: form.value.image?.trim() ? form.value.image.trim() : null,
    rows: (form.value.rows || [])
      .map((row) => ({
        label: String(row.label || '').trim(),
        value: String(row.value || '').trim(),
      }))
      .filter((row) => row.label || row.value),
  }
  emit('save', payload)
  visible.value = false
}
</script>
