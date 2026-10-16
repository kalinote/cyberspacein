<template>
  <div class="min-h-screen bg-gray-50"><Header />
    <main v-if="isMobile" class="mobile-evidence-list">
      <header><div><h1>证据链</h1><p>从关系查找依据，继续整理材料</p></div><el-button circle aria-label="刷新证据链" :loading="loading" :disabled="!canRead" @click="load"><Icon icon="mdi:refresh" /></el-button></header>
      <MobileKnowledgeNav />
      <form class="mobile-evidence-search" role="search" @submit.prevent="applyFilters()">
        <el-input v-model="query" clearable aria-label="搜索证据链" placeholder="搜索名称、目的或标签" /><el-button type="primary" native-type="submit" :disabled="!canRead">搜索</el-button>
      </form>
      <div class="mobile-evidence-tools"><span>{{ total }} 条证据链</span><el-button :type="appliedStatus ? 'primary' : 'default'" plain @click="statusDraft = appliedStatus; filterVisible = true">{{ CHAIN_STATUS[appliedStatus] || '全部状态' }}<Icon icon="mdi:filter-variant" /></el-button></div>
      <p v-if="!canRead" class="mobile-evidence-empty">当前账号没有读取证据链的权限。</p>
      <el-alert v-else-if="error" :title="error" type="error" :closable="false" show-icon><el-button link @click="load">重试</el-button><span v-if="items.length">下方保留上次加载的结果。</span></el-alert>
      <el-skeleton v-if="canRead && loading && !items.length" :rows="6" animated />
      <div v-if="canRead" class="mobile-evidence-cards" :aria-busy="loading">
        <article v-for="chain in items" :key="chain.id">
          <router-link :to="`/evidence/chains/${chain.id}`"><div class="card-heading"><h2>{{ chain.title }}</h2><el-tag size="small" :type="chain.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[chain.status] || chain.status }}</el-tag></div><p>{{ chain.purpose || chain.description || '尚未填写分析目的' }}</p></router-link>
          <div class="card-tags"><el-tag v-for="tag in (chain.tags || []).slice(0, 3)" :key="tag" size="small" type="info">{{ tag }}</el-tag></div>
          <div class="card-meta"><span>{{ chain.node_count || 0 }} 个节点 · {{ chain.edge_count || 0 }} 条关系</span><el-button text aria-label="证据链更多操作" @click="selectedChain = chain; actionsVisible = true"><Icon icon="mdi:dots-horizontal" /></el-button></div>
          <small>更新于 {{ new Date(chain.updated_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}</small>
        </article>
        <div v-if="!loading && !error && !items.length" class="mobile-evidence-empty"><Icon icon="mdi:graph-outline" /><h2>{{ appliedQuery || appliedStatus ? '没有匹配的证据链' : '还没有证据链' }}</h2><p>{{ appliedQuery || appliedStatus ? '调整关键词或筛选条件后再试。' : '可以从一个问题开始，逐步补充材料和依据。' }}</p></div>
      </div>
      <el-pagination v-if="canRead && total > 20" v-model:current-page="page" :page-size="20" :total="total" :pager-count="5" layout="prev, pager, next" class="mobile-evidence-pagination" />
      <MobileActionBar aria-label="证据链操作"><el-button type="primary" :disabled="!hasPerm(PERM.operations.evidence.chain.create)" @click="createVisible = true"><Icon icon="mdi:plus" />新建证据链</el-button></MobileActionBar>
      <MobileSheet v-model="filterVisible" title="筛选证据链"><el-radio-group v-model="statusDraft" class="mobile-evidence-status"><el-radio value="">全部状态</el-radio><el-radio v-for="(name, key) in CHAIN_STATUS" :key="key" :value="key">{{ name }}</el-radio></el-radio-group><template #footer><el-button @click="statusDraft = ''">重置</el-button><el-button type="primary" @click="applyFilters(statusDraft); filterVisible = false">应用筛选</el-button></template></MobileSheet>
      <MobileSheet v-model="actionsVisible" :title="selectedChain?.title || '证据链操作'"><p class="text-sm text-gray-500 mb-4">{{ selectedChain?.purpose || selectedChain?.description || '尚未填写分析目的' }}</p><div class="mobile-evidence-menu"><el-button @click="router.push(`/evidence/chains/${selectedChain.id}`); actionsVisible = false">打开关系与依据</el-button><el-button type="danger" plain :disabled="!hasPerm(PERM.operations.evidence.chain.delete) || Boolean(removingId)" @click="remove(selectedChain)">删除证据链</el-button></div></MobileSheet>
    </main>
    <template v-else>
    <FunctionalPageHeader title-prefix="证据链" title-suffix="管理" subtitle="管理分析图谱、组合子链，持续整理关联信息。" :back-handler="() => router.push('/evidence')"><template #actions><el-button type="primary" :disabled="!hasPerm(PERM.operations.evidence.chain.create)" @click="createVisible = true">新建证据链</el-button></template></FunctionalPageHeader>
    <main class="max-w-7xl mx-auto px-6 py-8">
      <form class="bg-white rounded-xl border border-gray-200 p-5 flex flex-wrap gap-4 mb-6" @submit.prevent="applyFilters()">
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
        <div class="p-5 flex justify-center"><el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" /></div>
      </div>
    </main>
    </template><EvidenceCreateDialog v-model="createVisible" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { ElMessageBox, ElMessage } from 'element-plus';
import Header from '@/components/Header.vue';
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue';
import EvidenceCreateDialog from '@/components/evidence/EvidenceCreateDialog.vue';
import { evidenceApi } from '@/api/evidence';
import { CHAIN_STATUS } from '@/utils/evidence';
import { PERM } from '@/utils/permissions';
import { hasPerm, guardPermission } from '@/utils/permissionKit';
import { useMobileViewport } from '@/composables/useMobileViewport';
import MobileKnowledgeNav from '@/components/mobile/MobileKnowledgeNav.vue';
import MobileSheet from '@/components/mobile/MobileSheet.vue';
import MobileActionBar from '@/components/mobile/MobileActionBar.vue';
defineOptions({ name: 'EvidenceList' });
const router = useRouter();
const { isMobile } = useMobileViewport();
const canRead = computed(() => hasPerm(PERM.operations.evidence.chain.read));
const appliedQuery = ref(''), appliedStatus = ref(''), statusDraft = ref('');
const filterVisible = ref(false), actionsVisible = ref(false), selectedChain = ref(null), removingId = ref('');
const items = ref([]),
  total = ref(0),
  page = ref(1),
  query = ref(''),
  status = ref(''),
  loading = ref(false),
  error = ref(''),
  createVisible = ref(false);
let requestId = 0;
let visitId = 0;
let active = false;
let removalId = 0;
let confirmingDelete = false;
/** """两端共享已提交的筛选，输入草稿和视口切换不改变分页条件。""" */
function applyFilters(nextStatus = isMobile.value ? appliedStatus.value : status.value) {
  appliedQuery.value = query.value.trim();
  appliedStatus.value = nextStatus;
  status.value = nextStatus;
  if (page.value === 1) return load();
  page.value = 1;
}
/** """读取当前证据链分页，迟到响应不能覆盖筛选或离页状态。""" */
async function load() {
  if (!active || !canRead.value) return;
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const response = await evidenceApi.list({
      q: appliedQuery.value,
      status: appliedStatus.value || undefined,
      page: page.value,
      page_size: 20
    });
    if (!Array.isArray(response?.data?.items) || !Number.isFinite(response.data.total)) throw new Error('证据链数据格式异常，请重试');
    if (id === requestId && active) {
      items.value = response.data.items;
      total.value = response.data.total;
    }
  } catch (e) {
    if (id === requestId) error.value = e.message;
  } finally {
    if (id === requestId) loading.value = false;
  }
}
/** """按既有修订号删除证据链，取消确认不会更改列表。""" */
async function remove(chain) {
  if (!chain?.id || removingId.value || !guardPermission(PERM.operations.evidence.chain.delete)) return;
  const visit = visitId;
  const operation = ++removalId;
  removingId.value = chain.id;
  confirmingDelete = true;
  try {
    await ElMessageBox.confirm(`删除「${chain.title}」？原始实体和引用的子链会保留。`, '删除证据链', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    });
    if (operation === removalId) confirmingDelete = false;
    if (!active || visit !== visitId || !guardPermission(PERM.operations.evidence.chain.delete)) return;
    await evidenceApi.remove(chain.id, chain.revision);
    if (!active || visit !== visitId) return;
    ElMessage.success('证据链已删除');
    actionsVisible.value = false;
    await load();
  } catch {/* 取消或失败时保留列表。 */} finally {
    if (operation === removalId) { removingId.value = ''; confirmingDelete = false; }
  }
}
/** """进入列表时刷新结果，保留已应用条件和页码。""" */
function activate() {
  if (active) return;
  active = true;
  void load();
}
/** """离开缓存列表时清理弹层并作废未完成的读取。""" */
function deactivate() {
  active = false;
  visitId += 1;
  requestId += 1;
  loading.value = false;
  filterVisible.value = false;
  actionsVisible.value = false;
  createVisible.value = false;
  if (confirmingDelete) {
    ElMessageBox.close();
    confirmingDelete = false;
    removalId += 1;
    removingId.value = '';
  }
}
watch(canRead, value => { requestId += 1; items.value = []; total.value = 0; loading.value = false; actionsVisible.value = false; selectedChain.value = null; if (value) void load(); });
watch(page, load, { flush: 'sync' });
watch(isMobile, () => { filterVisible.value = false; actionsVisible.value = false; });
onMounted(activate);
onActivated(activate);
onDeactivated(deactivate);
onBeforeUnmount(deactivate);
</script>

<style scoped>
.mobile-evidence-list { padding: 18px 16px 24px; color: #1e293b; }
.mobile-evidence-list > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.mobile-evidence-list h1 { font-size: 23px; font-weight: 700; margin: 0 0 6px; }
.mobile-evidence-list header p { font-size: 13px; color: #64748b; }
.mobile-evidence-list header .el-button { width: 44px; height: 44px; flex-shrink: 0; }
.mobile-evidence-search, .mobile-evidence-tools, .card-heading, .card-meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.mobile-evidence-tools { margin: 12px 0; font-size: 12px; color: #64748b; }
.mobile-evidence-list :deep(.el-button) { min-height: 44px; }
.mobile-evidence-cards { display: grid; gap: 12px; }
.mobile-evidence-cards article { padding: 16px; border: 1px solid #e2e8f0; border-radius: 15px; background: #fff; }
.card-heading { align-items: flex-start; }
.card-heading h2 { margin: 0; font-size: 16px; line-height: 1.6; font-weight: 650; overflow-wrap: anywhere; }
.card-heading :deep(.el-tag) { flex-shrink: 0; margin-top: 3px; }
.mobile-evidence-cards article p { margin: 8px 0; font-size: 13px; line-height: 1.8; color: #64748b; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.card-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.card-meta { font-size: 12px; color: #64748b; }
.mobile-evidence-cards small { font-size: 11px; color: #94a3b8; }
.mobile-evidence-empty { padding: 36px 12px; text-align: center; color: #64748b; line-height: 1.8; font-size: 13px; }
.mobile-evidence-empty > svg { font-size: 40px; margin: 0 auto 12px; color: #93c5fd; }
.mobile-evidence-empty h2 { font-size: 16px; color: #334155; }
.mobile-evidence-pagination { justify-content: center; margin: 20px 0; }
.mobile-evidence-status, .mobile-evidence-menu { display: flex; flex-direction: column; align-items: stretch; gap: 8px; }
.mobile-evidence-status :deep(.el-radio) { min-height: 44px; margin: 0; }
.mobile-evidence-menu .el-button { min-height: 48px; margin: 0; }
</style>
