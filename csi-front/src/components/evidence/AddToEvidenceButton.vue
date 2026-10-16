<template>
  <el-button v-if="visible" type="primary" link :disabled="!canAdd" @click="pickerVisible = true"><Icon icon="mdi:graph-outline" class="mr-1" />加入证据链</el-button>
  <EvidenceEntityPicker v-model="pickerVisible" :initial-entity="entity" @add="chooseChain" />
  <EvidenceChainPicker v-model="chainVisible" title="添加到证据链" :busy="busy" @select="append">
    <template #footer><el-button v-if="hasPerm(PERM.operations.evidence.chain.create)" type="primary" :loading="busy" @click="create">新建证据链并添加</el-button></template>
  </EvidenceChainPicker>
</template>
<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import EvidenceEntityPicker from './EvidenceEntityPicker.vue';
import EvidenceChainPicker from './EvidenceChainPicker.vue';
import { evidenceApi } from '@/api/evidence';
import { graphPayload, makeEvidenceGraph } from '@/utils/evidence';
import { hasPerm } from '@/utils/permissionKit';
import { PERM } from '@/utils/permissions';
defineProps({
  entity: {
    type: Object,
    required: true
  }
});
const router = useRouter();
const pickerVisible = ref(false),
  chainVisible = ref(false),
  pending = ref([]),
  busy = ref(false);
const visible = computed(() => hasPerm(PERM.pages.evidence.visible));
const canAdd = computed(() => hasPerm(PERM.pages.evidence.access) && hasPerm(PERM.operations.evidence.chain.read) && (hasPerm(PERM.operations.evidence.chain.update) || hasPerm(PERM.operations.evidence.chain.create)));
function chooseChain(nodes) {
  pending.value = nodes;
  chainVisible.value = true;
}
async function append(chain) {
  if (busy.value) return;
  if (!hasPerm(PERM.operations.evidence.chain.update)) {
    ElMessage.warning('没有编辑已有证据链的权限，可新建证据链');
    return;
  }
  busy.value = true;
  try {
    const graph = (await evidenceApi.get(chain.id)).data;
    const bottom = Math.max(0, ...graph.nodes.map(node => node.position.y)) + 200;
    graph.nodes.push(...pending.value.map((node, i) => ({
      ...node,
      position: {
        x: 80 + i % 3 * 320,
        y: bottom + Math.floor(i / 3) * 170
      }
    })));
    await evidenceApi.save(chain.id, {
      ...graphPayload(graph),
      expected_revision: graph.revision
    });
    chainVisible.value = false;
    ElMessage.success(`已添加到「${chain.title}」`);
  } catch {/* 保存冲突时保留待添加内容，允许重试。 */} finally {
    busy.value = false;
  }
}
async function create() {
  if (busy.value) return;
  try {
    const {
      value
    } = await ElMessageBox.prompt('请输入证据链名称', '新建证据链', {
      inputPattern: /\S/,
      inputErrorMessage: '名称不能为空',
      confirmButtonText: '创建',
      cancelButtonText: '取消'
    });
    busy.value = true;
    const graph = makeEvidenceGraph('blank', value.trim());
    graph.nodes = pending.value.map((node, i) => ({
      ...node,
      position: {
        x: 80 + i * 320,
        y: 100
      }
    }));
    const response = await evidenceApi.create(graph);
    chainVisible.value = false;
    router.push(`/evidence/chains/${response.data.id}`);
  } catch {/* 取消或失败时保留原页面。 */} finally {
    busy.value = false;
  }
}
</script>
