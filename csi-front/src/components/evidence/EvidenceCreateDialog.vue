<template>
  <el-dialog :model-value="modelValue" title="新建证据链" width="620px" class="evidence-create-dialog" :append-to-body="isMobile" @update:model-value="$emit('update:modelValue', $event)">
    <p v-if="isMobile" class="evidence-create-progress" aria-live="polite">第 {{ step }} 步，共 2 步 · {{ step === 1 ? '填写基础资料' : '选择起始结构' }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" class="mb-4" />
    <el-form label-position="top" @submit.prevent="isMobile && step === 1 ? (title.trim() && (step = 2)) : create()">
      <template v-if="!isMobile || step === 1">
      <el-form-item label="证据链名称" required><el-input v-model="title" maxlength="200" placeholder="例如：某事件的发展与影响" /></el-form-item>
      <el-form-item label="分析目的"><el-input v-model="purpose" maxlength="500" placeholder="描述希望梳理的问题或线索，可随时调整" /></el-form-item>
      </template>
      <template v-if="!isMobile || step === 2">
      <div v-if="isMobile" class="evidence-create-summary"><strong>{{ title }}</strong><p>{{ purpose || '未填写分析目的，可稍后补充。' }}</p></div>
      <div class="evidence-template-grid grid grid-cols-2 gap-3">
        <button v-for="item in EVIDENCE_TEMPLATES" :key="item.id" type="button" :aria-pressed="template === item.id" class="text-left rounded-xl border p-4 transition-colors" :class="template === item.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'" @click="template = item.id">
          <span class="font-semibold flex items-center gap-2"><Icon :icon="item.icon" class="text-blue-500 text-xl" />{{ item.name }}</span>
          <span class="block mt-2 text-xs text-gray-500 leading-5">{{ item.description }}</span>
        </button>
      </div>
      <p class="text-xs text-gray-400 mt-3">模板仅提供起始结构，节点和关系均可自由修改。</p>
      </template>
    </el-form>
    <template #footer><el-button v-if="isMobile && step === 2" :disabled="busy" @click="step = 1">上一步</el-button><el-button v-else @click="$emit('update:modelValue', false)">取消</el-button><el-button v-if="isMobile && step === 1" type="primary" :disabled="!title.trim() || !canCreate" @click="step = 2">下一步</el-button><el-button v-else type="primary" :loading="busy" :disabled="!title.trim() || !canCreate" @click="create">{{ isMobile ? '创建并打开' : '创建并打开图谱' }}</el-button></template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed, onBeforeUnmount, onDeactivated } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { evidenceApi } from '@/api/evidence';
import { EVIDENCE_TEMPLATES, makeEvidenceGraph } from '@/utils/evidence';
import { useMobileViewport } from '@/composables/useMobileViewport';
import { PERM } from '@/utils/permissions';
import { hasPerm, guardPermission } from '@/utils/permissionKit';
const props = defineProps({
  modelValue: Boolean,
  initialTemplate: {
    type: String,
    default: 'blank'
  }
});
const emit = defineEmits(['update:modelValue', 'created']);
const router = useRouter();
const { isMobile } = useMobileViewport();
const title = ref('');
const purpose = ref('');
const template = ref('blank');
const busy = ref(false);
const error = ref('');
const step = ref(1);
const canCreate = computed(() => hasPerm(PERM.operations.evidence.chain.create));
let requestId = 0;
watch(() => props.modelValue, value => {
  requestId += 1;
  busy.value = false;
  error.value = '';
  if (value) {
    step.value = 1;
    title.value = '';
    purpose.value = '';
    template.value = EVIDENCE_TEMPLATES.some(item => item.id === props.initialTemplate) ? props.initialTemplate : 'blank';
  }
});
/** """使用现有模板创建证据链，关闭后的迟到结果不再跳转。""" */
async function create() {
  if (!props.modelValue || busy.value || !title.value.trim() || (isMobile.value && step.value !== 2) || !guardPermission(PERM.operations.evidence.chain.create)) return;
  const id = ++requestId;
  busy.value = true;
  error.value = '';
  try {
    const response = await evidenceApi.create({
      ...makeEvidenceGraph(template.value, title.value.trim()),
      purpose: purpose.value.trim()
    });
    if (id !== requestId || !props.modelValue) return;
    if (!response?.data?.id) throw new Error('创建结果缺少证据链标识，请刷新列表查看');
    emit('created', response.data);
    emit('update:modelValue', false);
    router.push(`/evidence/chains/${response.data.id}`);
  } catch (e) { if (id === requestId) error.value = e.message || '创建失败，请重试'; } finally {
    if (id === requestId) busy.value = false;
  }
}
/** """离开页面时关闭创建表单并作废旧请求的界面回写。""" */
function deactivate() { requestId += 1; busy.value = false; emit('update:modelValue', false); }
onDeactivated(deactivate);
onBeforeUnmount(deactivate);
</script>

<style>
.evidence-create-progress { margin: 0 0 20px; font-size: 13px; color: #2563eb; }
.evidence-create-summary { margin-bottom: 16px; padding: 12px; border-radius: 10px; background: #f8fafc; overflow-wrap: anywhere; }
.evidence-create-summary p { margin-top: 6px; font-size: 13px; line-height: 1.7; color: #64748b; }
@media (max-width: 767px) {
  .evidence-create-dialog .evidence-template-grid { grid-template-columns: 1fr; }
  .evidence-create-dialog .el-dialog__footer { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: max(16px, env(safe-area-inset-bottom)); }
  .evidence-create-dialog .el-dialog__footer .el-button { flex: 1 1 120px; min-height: 44px; margin-left: 0; }
}
</style>
