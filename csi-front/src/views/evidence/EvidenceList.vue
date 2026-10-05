<template>
  <div class="min-h-screen bg-gray-50"><Header />
    <FunctionalPageHeader title-prefix="证据链" title-suffix="管理" subtitle="管理分析图谱、组合子链，持续整理关联信息。" :back-handler="() => router.push('/evidence')"><template #actions><el-button type="primary" :disabled="!hasPerm(PERM.operations.evidence.chain.create)" @click="createVisible = true">新建证据链</el-button></template></FunctionalPageHeader>
    <main class="max-w-7xl mx-auto px-6 py-8">
      <form class="bg-white rounded-xl border border-gray-200 p-5 flex flex-wrap gap-4 mb-6" @submit.prevent="page = 1; load()">
        <el-input v-model="query" clearable placeholder="搜索名称、目的、标签" class="flex-1 min-w-60" aria-label="搜索证据链" />
        <el-select v-model="status" placeholder="全部状态" clearable style="width: 150px" aria-label="证据链状态"><el-option v-for="(name, key) in CHAIN_STATUS" :key="key" :label="name" :value="key" /></el-select>
        <el-button type="primary" native-type="submit">搜索</el-button>
      </form>
      <el-alert v-if="error" :title="error" type="error" :closable="false" class="mb-4"><el-button link @click="load">重新加载</el-button></el-alert>
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden" v-loading="loading">
        <el-table :data="items" empty-text="暂无证据链，可点击右上角新建" style="min-height: 260px">
          <el-table-column label="证据链" min-width="270"><template #default="{ row }"><router-link :to="`/evidence/chains/${row.id}`" class="font-semibold text-blue-600">{{ row.title }}</router-link><p class="text-xs text-gray-500 mt-1 line-clamp-1">{{ row.purpose || row.description || '未填写分析目的' }}</p><div class="flex gap-1 mt-2"><el-tag v-for="tag in row.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag></div></template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[row.status] }}</el-tag></template></el-table-column>
          <el-table-column prop="node_count" label="节点" width="80" /><el-table-column prop="edge_count" label="关系" width="80" /><el-table-column prop="subchain_count" label="子链" width="80" />
          <el-table-column label="更新时间" width="170"><template #default="{ row }">{{ new Date(row.updated_at).toLocaleString('zh-CN', { hour12: false }) }}</template></el-table-column>
          <el-table-column label="操作" width="130"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/evidence/chains/${row.id}`)">打开</el-button><el-button link type="danger" :disabled="!hasPerm(PERM.operations.evidence.chain.delete)" @click="remove(row)">删除</el-button></template></el-table-column>
        </el-table>
        <div class="p-5 flex justify-center"><el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" /></div>
      </div>
    </main><EvidenceCreateDialog v-model="createVisible" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessageBox, ElMessage } from 'element-plus';
import Header from '@/components/Header.vue';
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue';
import EvidenceCreateDialog from '@/components/evidence/EvidenceCreateDialog.vue';
import { evidenceApi } from '@/api/evidence';
import { CHAIN_STATUS } from '@/utils/evidence';
import { PERM } from '@/utils/permissions';
import { hasPerm } from '@/utils/permissionKit';
const router = useRouter();
const items = ref([]),
  total = ref(0),
  page = ref(1),
  query = ref(''),
  status = ref(''),
  loading = ref(false),
  error = ref(''),
  createVisible = ref(false);
let requestId = 0;
async function load() {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const response = await evidenceApi.list({
      q: query.value,
      status: status.value || undefined,
      page: page.value,
      page_size: 20
    });
    if (id === requestId) {
      items.value = response.data.items;
      total.value = response.data.total;
    }
  } catch (e) {
    if (id === requestId) error.value = e.message;
  } finally {
    if (id === requestId) loading.value = false;
  }
}
async function remove(chain) {
  try {
    await ElMessageBox.confirm(`删除「${chain.title}」？原始实体和引用的子链会保留。`, '删除证据链', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    });
    await evidenceApi.remove(chain.id, chain.revision);
    ElMessage.success('证据链已删除');
    await load();
  } catch {/* 取消或失败时保留列表。 */}
}
onMounted(load);
</script>
