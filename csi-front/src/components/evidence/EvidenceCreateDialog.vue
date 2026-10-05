<template>
  <el-dialog :model-value="modelValue" title="新建证据链" width="620px" @update:model-value="$emit('update:modelValue', $event)">
    <el-form label-position="top" @submit.prevent="create">
      <el-form-item label="证据链名称" required><el-input v-model="title" maxlength="200" placeholder="例如：某事件的发展与影响" @keyup.enter="create" /></el-form-item>
      <el-form-item label="分析目的"><el-input v-model="purpose" maxlength="500" placeholder="描述希望梳理的问题或线索，可随时调整" /></el-form-item>
      <div class="grid grid-cols-2 gap-3">
        <button v-for="item in EVIDENCE_TEMPLATES" :key="item.id" type="button" class="text-left rounded-xl border p-4 transition-colors" :class="template === item.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'" @click="template = item.id">
          <span class="font-semibold flex items-center gap-2"><Icon :icon="item.icon" class="text-blue-500 text-xl" />{{ item.name }}</span>
          <span class="block mt-2 text-xs text-gray-500 leading-5">{{ item.description }}</span>
        </button>
      </div>
      <p class="text-xs text-gray-400 mt-3">模板仅提供起始结构，节点和关系均可自由修改。</p>
    </el-form>
    <template #footer><el-button @click="$emit('update:modelValue', false)">取消</el-button><el-button type="primary" :loading="busy" :disabled="!title.trim()" @click="create">创建并打开图谱</el-button></template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { evidenceApi } from '@/api/evidence';
import { EVIDENCE_TEMPLATES, makeEvidenceGraph } from '@/utils/evidence';
const props = defineProps({
  modelValue: Boolean,
  initialTemplate: {
    type: String,
    default: 'blank'
  }
});
const emit = defineEmits(['update:modelValue', 'created']);
const router = useRouter();
const title = ref('');
const purpose = ref('');
const template = ref('blank');
const busy = ref(false);
watch(() => props.modelValue, value => {
  if (value) {
    title.value = '';
    purpose.value = '';
    template.value = props.initialTemplate;
  }
});
async function create() {
  if (busy.value || !title.value.trim()) return;
  busy.value = true;
  try {
    const response = await evidenceApi.create({
      ...makeEvidenceGraph(template.value, title.value.trim()),
      purpose: purpose.value.trim()
    });
    emit('created', response.data);
    emit('update:modelValue', false);
    router.push(`/evidence/chains/${response.data.id}`);
  } catch {/* 请求层展示错误，保留表单内容。 */} finally {
    busy.value = false;
  }
}
</script>
