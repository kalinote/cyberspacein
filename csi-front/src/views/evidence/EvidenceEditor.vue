<template>
  <div class="evidence-editor bg-gray-50" :class="{ 'evidence-editor-mobile': isMobile }"><Header />
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-500">正在加载证据链…</div>
    <div v-else-if="loadError" class="p-12"><el-result icon="error" title="证据链加载失败" :sub-title="loadError"><template #extra><el-button @click="load">重试</el-button><el-button @click="router.push('/evidence/chains')">返回列表</el-button></template></el-result></div>
    <template v-else-if="graph">
      <MobileEvidenceEditor v-if="isMobile" ref="mobileEditor" :graph="graph" :rendered="rendered" :display-edges="displayEdges" :selection="selection" :editable="editable" :dirty="dirty" :saving="saving" :save-error="saveError" :refreshing="refreshing" :can-undo="history.length > 1 || history.at(-1) !== serialized" :can-redo="Boolean(future.length)" :resolving="resolving" :expanded="expanded" :resolve-errors="resolveErrors" :flow-id="flowId" :node-types="nodeTypes"
        @save="save" @undo="undo" @redo="redo" @refresh="refreshReferences" @export="exportGraph" @reload="reloadFromServer" @select-node="selectNodeById" @select-edge="onEdgeClick({ edge: $event })" @resolve="resolveSelection" @expand="toggleExpand" @remove-node="removeNode" @remove-edge="removeEdge" @add-nodes="addNodes" @edit-node="commitMobileNode" @edit-edge="commitMobileEdge" @edit-meta="commitMobileMeta" @fit="fitView({ padding: 0.15, duration: 250 })" />
      <template v-else>
      <div class="editor-heading">
        <el-button link @click="router.push('/evidence/chains')"><Icon icon="mdi:arrow-left" class="mr-1" />证据链</el-button><div class="h-8 border-l border-gray-200 mx-2"></div>
        <div class="min-w-0 flex-1"><h1 class="font-bold text-lg truncate">{{ graph.title }}</h1><p class="text-xs text-gray-400">修订 {{ graph.revision }} · {{ dirty ? '有未保存的更改' : '所有更改已保存' }}<span v-if="!editable"> · 只读</span></p></div>
        <el-tag size="small" :type="graph.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[graph.status] }}</el-tag>
        <EvidenceUsageTour :steps="tourSteps" />
        <el-button data-evidence-tour="settings" @click="selection = null; panelTab = 'meta'">证据链设置</el-button>
        <el-button data-evidence-tour="refresh" :loading="refreshing" @click="refreshReferences">刷新引用</el-button>
        <el-button data-evidence-tour="save" type="primary" :loading="saving" :disabled="!editable || !dirty" @click="save"><Icon icon="mdi:content-save-outline" class="mr-1" />保存</el-button>
      </div>
      <el-alert v-if="saveError" :title="saveError" type="error" show-icon :closable="false" class="shrink-0"><el-button link type="primary" @click="exportGraph">导出当前编辑</el-button><el-button link type="primary" @click="reloadFromServer">重新加载服务器内容</el-button></el-alert>
      <div class="editor-body">
        <aside class="editor-palette">
          <div class="p-4 border-b border-gray-100"><h2 class="font-semibold text-sm mb-3">构建图谱</h2>
            <button data-evidence-tour="entity" class="palette-button" :disabled="!editable" @click="openPicker('nodes')"><Icon icon="mdi:database-search-outline" class="text-blue-500" /><span>添加实体<small>检索、重点实体、专题事件</small></span></button>
            <button data-evidence-tour="virtual" class="palette-button" :disabled="!editable" @click="addNote"><Icon icon="mdi:lightbulb-outline" class="text-amber-500" /><span>虚拟节点<small>事件、问题、判断</small></span></button>
            <button data-evidence-tour="chain" class="palette-button" :disabled="!editable" @click="chainPicker = true"><Icon icon="mdi:graph-outline" class="text-indigo-500" /><span>引用子链<small>组合已有证据链</small></span></button>
            <button data-evidence-tour="relation" class="palette-button" :disabled="!editable || rendered.nodes.length < 2" @click="openRelation"><Icon icon="mdi:vector-line" class="text-teal-600" /><span>建立关系<small>连接节点并记录依据</small></span></button>
          </div>
          <div class="p-4 flex-1 overflow-auto"><div class="text-xs text-gray-400 mb-3">本链节点 · {{ graph.nodes.length }}</div><el-input v-model="nodeQuery" size="small" placeholder="查找节点" aria-label="查找图中节点" clearable class="mb-3" />
            <button v-for="node in filteredNodes" :key="node.id" class="w-full text-left flex items-center gap-2 py-2 px-2 text-xs rounded hover:bg-blue-50" :class="selection?.id === node.id ? 'bg-blue-50 text-blue-600' : 'text-gray-600'" @click="selectNodeById(node.id)"><Icon :icon="NODE_KINDS[node.kind].icon" :style="{ color: NODE_KINDS[node.kind].color }" class="shrink-0" /><span class="truncate">{{ node.label }}</span></button>
          </div>
          <p class="p-4 text-xs leading-5 text-gray-400 border-t border-gray-100">拖动节点两侧的圆点可建立关系。选择节点后，在右侧查看实体或展开集合。</p>
        </aside>
        <section class="graph-region">
          <div class="graph-toolbar"><el-button-group><el-button size="small" :disabled="!editable || history.length < 2" @click="undo">撤销</el-button><el-button size="small" :disabled="!editable || !future.length" @click="redo">重做</el-button></el-button-group><el-button size="small" :disabled="!editable" @click="arrange('grid')">网格排列</el-button><el-button size="small" :disabled="!editable" @click="arrange('tree')">层级排列</el-button><el-button size="small" @click="fitView({ padding: 0.15, duration: 250 })">适应画布</el-button><span class="ml-auto text-xs text-gray-400">{{ graph.nodes.length }} 节点 · {{ graph.edges.length }} 关系</span></div>
          <VueFlow :id="flowId" :nodes="rendered.nodes" :edges="displayEdges" :node-types="nodeTypes" :nodes-connectable="editable" :nodes-draggable="editable" :delete-key-code="null" :min-zoom="0.15" :max-zoom="2.5" fit-view-on-init class="evidence-flow" @node-click="onNodeClick" @edge-click="onEdgeClick" @pane-click="selection = null; panelTab = 'meta'" @node-drag-stop="onDragStop" @connect="connect">
            <Background :gap="22" pattern-color="#d7e0ee" /><Controls :show-interactive="false" /><MiniMap :node-color="node => NODE_KINDS[node.data?.node?.kind]?.color || '#94a3b8'" pannable zoomable />
          </VueFlow>
          <div v-if="!graph.nodes.length" class="graph-empty"><Icon icon="mdi:graph-outline" class="text-5xl text-blue-200 mb-4" /><h2 class="font-semibold text-gray-700">从一个实体或问题开始</h2><p class="text-sm text-gray-400 mt-2 mb-4">添加节点，再建立有依据的联系。</p><el-button type="primary" :disabled="!editable" @click="openPicker('nodes')">添加第一个实体</el-button></div>
        </section>
        <aside class="editor-inspector">
          <template v-if="selectedNode">
            <div class="inspector-title"><Icon :icon="NODE_KINDS[selectedNode.kind].icon" class="text-blue-500" />{{ NODE_KINDS[selectedNode.kind].label }}<el-tag v-if="selectedEntry?.data.inherited" size="small" type="info">引用内容</el-tag></div>
            <div class="inspector-content">
              <el-alert v-if="selectedEntry?.data.inherited" title="此节点属于引用内容，可作为关系端点；编辑子链内容请进入子链。" :closable="false" type="info" class="mb-4" />
              <el-form label-position="top" :disabled="!editable || selectedEntry?.data.inherited">
                <el-form-item label="名称"><el-input v-model="selectedNode.label" maxlength="300" /></el-form-item>
                <el-form-item label="说明"><el-input v-model="selectedNode.description" type="textarea" :rows="3" maxlength="20000" placeholder="记录该节点在本链中的含义" /></el-form-item>
                <el-form-item label="自定义属性"><div class="w-full space-y-2"><div v-for="(_, key) in selectedNode.attributes" :key="key" class="flex items-center gap-2"><span class="text-xs text-gray-500 w-20 truncate" :title="key">{{ key }}</span><el-input v-model="selectedNode.attributes[key]" size="small" maxlength="4000" /><el-button link type="danger" @click="delete selectedNode.attributes[key]">移除</el-button></div><el-button size="small" @click="addAttribute">添加属性</el-button></div></el-form-item>
              </el-form>
              <template v-if="selectedNode.kind !== 'note'">
                <div class="flex gap-2 flex-wrap my-4"><el-button size="small" :loading="resolving.has(selection.id)" @click="resolveSelection">重新读取</el-button><el-button v-if="['versions', 'collection', 'chain'].includes(selectedNode.kind)" size="small" type="primary" plain @click="toggleExpand">{{ expanded.has(selection.id) ? '收起图中内容' : '在图中展开' }}</el-button><el-button v-if="selectedNode.kind === 'chain'" size="small" @click="router.push(`/evidence/chains/${selectedNode.chain_id}`)">进入子链</el-button></div>
                <p v-if="selectedNode.kind === 'versions'" class="text-xs text-gray-500 leading-5 mb-3">{{ selectedNode.version_source.platform }} · {{ selectedNode.version_source.source_id }}<br>每次读取时检索全部版本，包含未来采集的数据。</p>
                <el-alert v-if="resolveErrors[selection.id]" :title="resolveErrors[selection.id]" type="error" :closable="false" class="mb-3" />
                <p v-if="selectedResolved?.resolved_at" class="text-xs text-gray-400 mb-3">读取于 {{ new Date(selectedResolved.resolved_at).toLocaleString('zh-CN') }}</p>
                <div v-if="selectedResolved?.chain" class="p-3 rounded-lg bg-indigo-50 text-sm"><strong>{{ selectedResolved.chain.title }}</strong><p class="text-xs mt-2 text-gray-500">当前修订 {{ selectedResolved.chain.revision }} · {{ selectedResolved.chain.nodes.length }} 个节点 · {{ selectedResolved.chain.edges.length }} 条关系</p><p class="text-xs mt-2">{{ selectedResolved.chain.purpose }}</p></div>
                <div v-for="item in selectedResolved?.items || []" :key="`${item.entity_type}:${item.uuid}`" class="entity-preview"><el-tag v-if="item.missing" type="danger" size="small">实体缺失</el-tag><router-link :to="entityDetailPath(item)" target="_blank" class="text-sm font-medium text-blue-600">{{ item.title || '查看实体' }} ↗</router-link><p class="text-xs text-gray-400 mt-1">{{ item.platform }} · {{ item.crawled_at || item.last_edit_at || '时间未提供' }}</p><p class="text-xs text-gray-500 mt-2 line-clamp-4 whitespace-pre-wrap">{{ item.clean_content }}</p><el-button v-if="selectedNode.kind === 'collection' && editable && !selectedEntry?.data.inherited" link type="danger" size="small" :disabled="selectedNode.members.length === 1" @click="removeMember(item)">移出集合</el-button></div>
                <el-empty v-if="selectedResolved?.total === 0" description="当前没有匹配的实体" :image-size="50" />
                <div v-if="selectedResolved?.total > 30" class="my-3"><p class="text-xs text-gray-400 mb-2">共 {{ selectedResolved.total }} 个成员，图中展开当前页。</p><el-pagination small :current-page="selectedResolved.page" :page-size="30" :total="selectedResolved.total" layout="prev, pager, next" :pager-count="5" @current-change="resolveSelection" /></div>
                <el-button v-if="selectedNode.kind === 'collection' && editable && !selectedEntry?.data.inherited" size="small" @click="openPicker('members')">补充集合成员</el-button>
              </template>
              <el-button v-if="!selectedEntry?.data.inherited" class="mt-6" type="danger" plain size="small" :disabled="!editable" @click="removeNode">移出当前证据链</el-button>
            </div>
          </template>
          <template v-else-if="selectedEdge">
            <div class="inspector-title"><Icon icon="mdi:vector-line" class="text-blue-500" />关系与依据</div><div class="inspector-content">
              <el-alert v-if="selectedEdgeEntry.data.inherited" title="这是子链内的关系，请进入子链编辑。" type="info" :closable="false" class="mb-4" />
              <p class="text-xs text-gray-500 mb-4 break-words">{{ endpointLabel(selectedEdge.source, selectedEdgeEntry.data.ownerPath) }} → {{ endpointLabel(selectedEdge.target, selectedEdgeEntry.data.ownerPath) }}</p>
              <el-alert v-if="selectedEdgeEntry.data.missing" title="引用的内部节点已不可用，关系依据仍保留。请重新选择端点。" type="warning" :closable="false" class="mb-4" />
              <el-form label-position="top" :disabled="!editable || selectedEdgeEntry.data.inherited">
                <template v-if="!selectedEdgeEntry.data.inherited">
                  <el-form-item label="起点"><el-select v-model="selectedEdge.source" filterable class="w-full"><el-option v-for="node in rendered.nodes" :key="node.id" :value="node.id" :label="node.data.node.label" /></el-select></el-form-item>
                  <el-form-item label="终点"><el-select v-model="selectedEdge.target" filterable class="w-full"><el-option v-for="node in rendered.nodes" :key="node.id" :value="node.id" :label="node.data.node.label" /></el-select></el-form-item>
                </template>
                <el-form-item label="关系类型"><el-select v-model="selectedEdge.label" filterable allow-create default-first-option class="w-full"><el-option v-for="label in graph.relation_types" :key="label" :label="label" :value="label" /></el-select></el-form-item>
                <el-form-item label="方向"><el-switch v-model="selectedEdge.directed" active-text="有向关系" inactive-text="无向关系" /></el-form-item>
                <el-form-item label="核实状态"><el-select v-model="selectedEdge.status" class="w-full"><el-option v-for="(label, value) in RELATION_STATUS" :key="value" :value="value" :label="label" /></el-select></el-form-item>
                <el-form-item label="关系说明"><el-input v-model="selectedEdge.description" type="textarea" :rows="4" maxlength="20000" placeholder="为什么建立这条关系？有哪些依据或疑点？" /></el-form-item>
                <p v-if="['先于', '导致'].includes(selectedEdge.label)" class="text-xs text-amber-600 mb-4">时间先后与因果关系需要分别判断，请在说明中记录理由。</p>
                <div class="flex justify-between items-center mb-3"><h3 class="text-sm font-semibold">原文依据</h3><el-button size="small" @click="openPicker('anchors')">添加依据</el-button></div>
                <div v-for="(anchor, index) in selectedEdge.anchors" :key="index" class="bg-gray-50 rounded-lg border border-gray-200 p-3 mb-3"><router-link :to="entityDetailPath(anchor.entity)" target="_blank" class="text-xs text-blue-600 break-all">{{ anchor.entity.entity_type }} · {{ anchor.entity.uuid }} ↗</router-link><el-input v-model="anchor.quote" type="textarea" :rows="3" maxlength="10000" placeholder="摘录原文，保留支持该关系的具体内容" class="mt-3" /><el-input v-model="anchor.locator" maxlength="1000" placeholder="定位说明：段落、楼层或时间点" class="mt-2" /><el-button link type="danger" size="small" @click="selectedEdge.anchors.splice(index, 1)">移除依据</el-button></div>
                <el-button type="danger" plain size="small" class="mt-4" @click="removeEdge">删除关系</el-button>
              </el-form>
            </div>
          </template>
          <template v-else>
            <div class="inspector-title"><Icon icon="mdi:tune" class="text-blue-500" />证据链设置</div><div class="inspector-content"><el-form label-position="top" :disabled="!editable">
              <el-form-item label="名称"><el-input v-model="graph.title" maxlength="200" /></el-form-item>
              <el-form-item label="分析目的"><el-input v-model="graph.purpose" type="textarea" :rows="2" maxlength="500" placeholder="本链希望回答什么问题？" /></el-form-item>
              <el-form-item label="说明"><el-input v-model="graph.description" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
              <el-form-item label="状态"><el-select v-model="graph.status" class="w-full"><el-option v-for="(label, value) in CHAIN_STATUS" :key="value" :value="value" :label="label" /></el-select></el-form-item>
              <el-form-item label="标签"><el-select v-model="graph.tags" multiple filterable allow-create default-first-option class="w-full" placeholder="输入标签后回车" /></el-form-item>
              <el-form-item label="常用关系类型"><el-select v-model="graph.relation_types" multiple filterable allow-create default-first-option class="w-full" placeholder="输入自定义关系后回车" /></el-form-item>
            </el-form><div class="mt-6 p-4 bg-blue-50 rounded-lg text-xs text-blue-700 leading-6">实体节点指向确定版本；动态版本节点按需检索；子链节点读取被引用图的当前内容。图中的连线由你建立和核实。</div><el-button class="mt-4" size="small" @click="exportGraph">导出图定义</el-button></div>
          </template>
        </aside>
      </div>
      </template>
    </template>
    <EvidenceEntityPicker v-model="entityPicker" :allow-dynamic="pickerMode === 'nodes'" @add="acceptEntities" />
    <EvidenceChainPicker v-model="chainPicker" :exclude-id="String(route.params.id)" @select="addChain" />
    <el-dialog v-model="relationVisible" title="建立关系" width="500px"><el-form label-position="top"><el-form-item label="起点"><el-select v-model="relationSource" filterable class="w-full"><el-option v-for="node in rendered.nodes" :key="node.id" :value="node.id" :label="node.data.node.label + (node.data.inherited ? '（引用内）' : '')" /></el-select></el-form-item><el-form-item label="终点"><el-select v-model="relationTarget" filterable class="w-full"><el-option v-for="node in rendered.nodes" :key="node.id" :value="node.id" :label="node.data.node.label + (node.data.inherited ? '（引用内）' : '')" /></el-select></el-form-item></el-form><template #footer><el-button @click="relationVisible = false">取消</el-button><el-button type="primary" :disabled="!relationSource || !relationTarget" @click="connect({ source: relationSource, target: relationTarget }); relationVisible = false">建立并填写依据</el-button></template></el-dialog>
  </div>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { VueFlow, useVueFlow } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { MiniMap } from '@vue-flow/minimap';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';
import '@vue-flow/minimap/dist/style.css';
import Header from '@/components/Header.vue';
import EvidenceEntityPicker from '@/components/evidence/EvidenceEntityPicker.vue';
import EvidenceChainPicker from '@/components/evidence/EvidenceChainPicker.vue';
import EvidenceGraphNode from '@/components/evidence/EvidenceGraphNode.vue';
import EvidenceUsageTour from '@/components/evidence/EvidenceUsageTour.vue';
import MobileEvidenceEditor from '@/components/evidence/mobile/MobileEvidenceEditor.vue';
import { commitEvidenceRelation } from '@/components/evidence/mobile/mobileEvidence';
import { useMobileViewport } from '@/composables/useMobileViewport';
import { rememberRecentVisit } from '@/stores/recentVisits';
import { evidenceApi } from '@/api/evidence';
import { CHAIN_STATUS, RELATION_STATUS, NODE_KINDS, evidenceId, makeEvidenceNode, graphPayload, projectEvidenceGraph, entityDetailPath } from '@/utils/evidence';
import { hasPerm } from '@/utils/permissionKit';
import { PERM } from '@/utils/permissions';
const router = useRouter(),
  route = useRoute();
const { isMobile } = useMobileViewport();
const mobileEditor = ref(null);
const flowId = 'evidence-editor';
const {
  fitView,
  setCenter
} = useVueFlow(flowId);
const nodeTypes = {
  evidence: markRaw(EvidenceGraphNode)
};
const tourSteps = [{
  title: '1. 明确分析目的',
  target: '[data-evidence-tour="settings"]',
  content: ['在“证据链设置”中修改名称、分析目的、状态和标签，也可自定义常用关系类型。先明确这张图希望回答什么问题。']
}, {
  title: '2. 添加实体与版本',
  target: '[data-evidence-tour="entity"]',
  placement: 'right',
  content: ['从检索结果、重点实体库或专题事件中选择材料，作为独立节点或固定集合。', '点击“选择版本”可选取具体版本，也可添加“全部版本”动态节点：每次读取时重新检索，包含未来采集的版本。']
}, {
  title: '3. 用虚拟节点组织思路',
  target: '[data-evidence-tour="virtual"]',
  placement: 'right',
  content: ['创建事件、问题、待验证判断等自定义节点，在右侧补充名称、说明和属性。虚拟节点用于组织分析，不会新增原始实体。']
}, {
  title: '4. 组合已有子链',
  target: '[data-evidence-tour="chain"]',
  placement: 'right',
  content: ['选择已有证据链作为一个节点加入。选中后可在图中展开，或进入子链编辑。', '子链是实时引用：读取时展示它的当前内容，修改子链会影响其他引用它的图。']
}, {
  title: '5. 为节点建立关系',
  target: '[data-evidence-tour="relation"]',
  placement: 'right',
  content: ['至少有两个节点时，点击“建立关系”选择起点和终点；也可拖动节点两侧的圆点连线。', '可以连接整个集合或子链，也可以展开后连接其中的具体节点。关系类型由你定义，时间先后和因果关系需要分别判断。']
}, {
  title: '6. 记录关系与原文依据',
  target: '.evidence-editor .editor-inspector',
  placement: 'left',
  content: ['单击节点，右侧显示节点详情；单击连线，则显示关系类型、方向、核实状态和说明。', '使用“添加依据”选择具体实体版本，再填写原文摘录及段落、楼层等定位信息，让这条关系有据可查。']
}, {
  title: '7. 整理与浏览图谱',
  target: '.evidence-editor .graph-toolbar',
  content: ['拖动节点调整位置，用滚轮缩放画布。“适应画布”可查看整体，网格与层级排列可帮助整理布局。', '编辑过程中可以撤销或重做。选中集合或子链后，可在右侧展开、收起其内容。']
}, {
  title: '8. 读取最新引用内容',
  target: '[data-evidence-tour="refresh"]',
  content: ['“刷新引用”会重新读取已查看或展开的内容。动态版本节点会重新查询，固定集合始终保留你选择的版本，子链读取当前图。', '新增版本不会自动成为已建立关系的依据，具体版本的依据仍需人工选择。']
}, {
  title: '9. 保存后再离开',
  target: '[data-evidence-tour="save"]',
  content: ['编辑后点击“保存”，标题下方会显示修订号和保存状态。多人同时修改时，系统会提示冲突并保留当前编辑。', '引导结束后即可操作。需要回顾时，随时点击“使用引导”；只读账号可浏览图谱，编辑需要相应权限。']
}];
const graph = ref(null),
  loading = ref(true),
  loadError = ref(''),
  saving = ref(false),
  saveError = ref(''),
  savedState = ref('');
const selection = ref(null),
  nodeQuery = ref(''),
  panelTab = ref('meta'),
  resolved = ref({}),
  resolveErrors = ref({}),
  expanded = ref(new Set()),
  resolving = ref(new Set()),
  refreshing = ref(false);
const entityPicker = ref(false),
  chainPicker = ref(false),
  pickerMode = ref('nodes'),
  pickerTarget = ref(null);
const relationVisible = ref(false),
  relationSource = ref(''),
  relationTarget = ref('');
const history = ref([]),
  future = ref([]);
let historyTimer,
  tracking = true,
  loadSequence = 0;
const resolveSequence = new Map();
const editable = computed(() => hasPerm(PERM.operations.evidence.chain.update));
const serialized = computed(() => graph.value ? JSON.stringify(graphPayload(graph.value)) : '');
const dirty = computed(() => serialized.value !== savedState.value);
const rendered = computed(() => graph.value ? projectEvidenceGraph(graph.value, resolved.value, expanded.value) : {
  nodes: [],
  edges: []
});
const displayEdges = computed(() => {
  const nodeId = selection.value?.type === 'node' ? selection.value.id : null;
  return rendered.value.edges.map(edge => {
    const active = nodeId !== null && (edge.source === nodeId || edge.target === nodeId);
    return {
      ...edge,
      animated: active,
      style: active ? { ...edge.style, strokeWidth: 2.8, strokeDasharray: '6 4' } : edge.style
    };
  });
});
const filteredNodes = computed(() => graph.value?.nodes.filter(node => node.label.toLowerCase().includes(nodeQuery.value.toLowerCase())) || []);
const selectedEntry = computed(() => selection.value?.type === 'node' ? rendered.value.nodes.find(node => node.id === selection.value.id) : null);
const selectedNode = computed(() => selectedEntry.value?.data.node);
const selectedResolved = computed(() => selectedEntry.value?.data.resolved);
const selectedEdgeEntry = computed(() => selection.value?.type === 'edge' ? rendered.value.edges.find(edge => edge.id === selection.value.id) : null);
const selectedEdge = computed(() => selectedEdgeEntry.value?.data.edge);
async function load() {
  const sequence = ++loadSequence;
  loading.value = true;
  loadError.value = '';
  saveError.value = '';
  clearTimeout(historyTimer);
  tracking = false;
  try {
    const response = await evidenceApi.get(String(route.params.id));
    if (sequence !== loadSequence) return;
    graph.value = response.data;
    rememberRecentVisit(route, graph.value.title);
    savedState.value = serialized.value;
    resolved.value = {};
    resolveErrors.value = {};
    expanded.value = new Set();
    resolving.value = new Set();
    resolveSequence.clear();
    selection.value = null;
    history.value = [serialized.value];
    future.value = [];
    await nextTick();
  } catch (e) {
    if (sequence === loadSequence) loadError.value = e.message;
  } finally {
    if (sequence === loadSequence) {
      tracking = true;
      loading.value = false;
    }
  }
}
async function save() {
  if (!editable.value || saving.value) return false;
  if (!graph.value.title.trim() || graph.value.nodes.some(node => !node.label.trim())) {
    ElMessage.warning('证据链和节点名称不能为空');
    return false;
  }
  const submitted = serialized.value;
  const submittedGraph = graph.value;
  const generation = loadSequence;
  saving.value = true;
  saveError.value = '';
  try {
    const response = await evidenceApi.save(graph.value.id, {
      ...JSON.parse(submitted),
      expected_revision: graph.value.revision
    });
    // 离开或重载后的迟到响应不能写入另一条证据链。
    if (graph.value !== submittedGraph || generation !== loadSequence) return false;
    graph.value.revision = response.data.revision;
    savedState.value = submitted;
    rememberRecentVisit(route, graph.value.title);
    ElMessage.success('证据链已保存');
    return true;
  } catch (e) {
    if (graph.value === submittedGraph && generation === loadSequence) saveError.value = e.message || '保存失败，当前编辑已保留';
    return false;
  } finally {
    saving.value = false;
  }
}
async function canLeave() {
  if (mobileEditor.value?.hasDraft) {
    try {
      await ElMessageBox.confirm('分步编辑尚未确认。离开会放弃表单草稿，已应用到证据链的更改仍可保存。', '尚有表单草稿', { confirmButtonText: '放弃草稿并继续', cancelButtonText: '继续编辑', type: 'warning' });
    } catch { return false; }
  }
  if (!dirty.value || !graph.value) return true;
  try {
    await ElMessageBox.confirm('当前证据链有未保存的更改。保存后继续？', '离开编辑页', {
      distinguishCancelAndClose: true,
      confirmButtonText: '保存并继续',
      cancelButtonText: '放弃更改',
      type: 'warning'
    });
    return await save();
  } catch (action) {
    return action === 'cancel';
  }
}
async function reloadFromServer() {
  try {
    await ElMessageBox.confirm('重新加载会丢弃当前未保存编辑。建议先导出图定义。', '重新加载', {
      confirmButtonText: '重新加载',
      cancelButtonText: '取消',
      type: 'warning'
    });
    await load();
  } catch {/* 取消时保留当前编辑。 */}
}
function flushHistory() {
  clearTimeout(historyTimer);
  if (serialized.value && history.value.at(-1) !== serialized.value) {
    history.value.push(serialized.value);
    if (history.value.length > 80) history.value.shift();
    future.value = [];
  }
}
async function restoreSnapshot(snapshot) {
  tracking = false;
  clearTimeout(historyTimer);
  ++loadSequence;
  resolved.value = {};
  resolveErrors.value = {};
  resolving.value = new Set();
  expanded.value = new Set();
  resolveSequence.clear();
  graph.value = {
    ...graph.value,
    ...JSON.parse(snapshot)
  };
  selection.value = null;
  await nextTick();
  tracking = true;
}
async function undo() {
  flushHistory();
  if (history.value.length > 1) {
    future.value.push(history.value.pop());
    await restoreSnapshot(history.value.at(-1));
  }
}
async function redo() {
  if (future.value.length) {
    const snapshot = future.value.pop();
    history.value.push(snapshot);
    await restoreSnapshot(snapshot);
  }
}
watch(serialized, () => {
  if (!tracking) return;
  future.value = [];
  clearTimeout(historyTimer);
  historyTimer = setTimeout(flushHistory, 500);
});
function addNodes(nodes) {
  if (!editable.value || !nodes.length) return;
  if (isMobile.value) flushHistory();
  const bottom = graph.value.nodes.length ? Math.max(...graph.value.nodes.map(node => node.position.y)) + 190 : 100;
  graph.value.nodes.push(...nodes.map((node, index) => ({
    ...node,
    position: {
      x: 80 + index % 3 * 320,
      y: bottom + Math.floor(index / 3) * 170
    }
  })));
  if (isMobile.value) flushHistory();
  nextTick(() => {
    selection.value = {
      type: 'node',
      id: nodes[0].id
    };
    if (!isMobile.value) fitView({
      padding: 0.2,
      duration: 250
    });
  });
}
/**
 * 提交本链节点的移动表单，保留引用身份并复用撤销历史。
 * @param {object} draft 已确认的节点草稿。
 */
function commitMobileNode(draft) {
  if (!editable.value || !draft.label?.trim()) return;
  const node = graph.value.nodes.find(item => item.id === draft.id);
  if (!node) return;
  flushHistory();
  Object.assign(node, { label: draft.label.trim(), description: draft.description, attributes: draft.attributes });
  if (node.kind === 'collection' && draft.members?.length) {
    node.members = draft.members;
    delete resolved.value[node.id];
    resolveSelection();
  }
  flushHistory();
}
/**
 * 提交真实关系端点及依据，不把投影的折叠端点写入图定义。
 * @param {object} draft 已确认的关系草稿。
 */
function commitMobileEdge(draft) {
  if (!editable.value) return;
  flushHistory();
  const error = commitEvidenceRelation(graph.value, draft, rendered.value.nodes, editable.value);
  if (error) { ElMessage.warning(error); return; }
  selection.value = { type: 'edge', id: draft.id };
  flushHistory();
}
/**
 * 将移动设置表单应用到现有图定义，并保留一次完整的撤销记录。
 * @param {object} draft 基础设置表单。
 */
function commitMobileMeta(draft) {
  if (!editable.value || !draft.title?.trim()) return;
  flushHistory();
  for (const key of ['title', 'purpose', 'description', 'status', 'tags', 'relation_types']) graph.value[key] = draft[key];
  flushHistory();
}
function addNote() {
  addNodes([makeEvidenceNode('note', {
    label: '新建虚拟节点'
  })]);
}
function addChain(chain) {
  addNodes([makeEvidenceNode('chain', {
    label: chain.title,
    chain_id: chain.id
  })]);
  chainPicker.value = false;
}
function openPicker(mode) {
  pickerMode.value = mode;
  pickerTarget.value = selection.value ? {
    ...selection.value
  } : null;
  entityPicker.value = true;
}
function acceptEntities(nodes) {
  if (pickerMode.value === 'nodes') {
    addNodes(nodes);
    return;
  }
  const refs = nodes.flatMap(node => node.kind === 'entity' ? [node.entity] : node.kind === 'collection' ? node.members : []);
  if (!refs.length) {
    ElMessage.warning('关系依据与固定集合成员需要选择具体实体版本');
    return;
  }
  if (pickerMode.value === 'anchors') {
    const edge = graph.value.edges.find(item => item.id === pickerTarget.value?.id);
    if (edge) edge.anchors.push(...refs.map(entity => ({
      entity,
      quote: '',
      locator: ''
    })));
  } else {
    const node = graph.value.nodes.find(item => item.id === pickerTarget.value?.id);
    if (node) {
      for (const ref of refs) if (!node.members.some(member => member.uuid === ref.uuid && member.entity_type === ref.entity_type)) node.members.push(ref);
      delete resolved.value[node.id];
    }
  }
}
function connect({
  source,
  target
}) {
  if (!editable.value || !source || !target) return;
  const edge = {
    id: evidenceId(),
    source,
    target,
    label: graph.value.relation_types[0] || '关联',
    directed: true,
    description: '',
    status: 'pending',
    anchors: []
  };
  graph.value.edges.push(edge);
  selection.value = {
    type: 'edge',
    id: edge.id
  };
}
function openRelation() {
  relationSource.value = selectedEntry.value?.id || rendered.value.nodes[0]?.id || '';
  relationTarget.value = '';
  relationVisible.value = true;
}
function onDragStop({
  node
}) {
  const original = graph.value.nodes.find(item => item.id === node.id);
  if (original && editable.value) original.position = {
    ...node.position
  };
}
function onEdgeClick({
  edge
}) {
  if (!edge.data?.containment) selection.value = {
    type: 'edge',
    id: edge.id
  };
}
function onNodeClick({
  node
}) {
  selection.value = {
    type: 'node',
    id: node.id
  };
  if (node.data.node.kind !== 'note') resolveEntry(node);
}
function selectNodeById(id) {
  const node = rendered.value.nodes.find(item => item.id === id);
  if (!node) return;
  onNodeClick({
    node
  });
  if (!isMobile.value) setCenter(node.position.x + 124, node.position.y + 60, {
    zoom: 1,
    duration: 250
  });
}
async function resolveEntry(entry, page = 1) {
  const path = entry.id,
    sequence = (resolveSequence.get(path) || 0) + 1,
    generation = loadSequence;
  resolveSequence.set(path, sequence);
  resolving.value.add(path);
  delete resolveErrors.value[path];
  try {
    // 展开的集合成员是确定实体引用，原始节点定义只保留在父图中。
    const node = {
      ...entry.data.node,
      id: entry.data.node.id.includes('/') ? 'member-preview' : entry.data.node.id
    };
    const response = await evidenceApi.resolve(node, typeof page === 'number' ? page : 1);
    if (generation === loadSequence && resolveSequence.get(path) === sequence) resolved.value[path] = response.data;
  } catch (e) {
    if (generation === loadSequence && resolveSequence.get(path) === sequence) {
      resolveErrors.value[path] = e.message;
      delete resolved.value[path];
    }
  } finally {
    if (generation === loadSequence && resolveSequence.get(path) === sequence) resolving.value.delete(path);
  }
}
async function resolveSelection(page = 1) {
  if (selectedEntry.value) await resolveEntry(selectedEntry.value, page);
}
async function toggleExpand() {
  const entry = selectedEntry.value;
  if (expanded.value.has(entry.id)) {
    expanded.value.delete(entry.id);
    return;
  }
  await resolveEntry(entry);
  if (resolved.value[entry.id]) {
    expanded.value.add(entry.id);
    await nextTick();
    fitView({
      padding: 0.15,
      duration: 250
    });
  }
}
async function refreshReferences() {
  refreshing.value = true;
  try {
    const entries = rendered.value.nodes.filter(node => node.data.node.kind !== 'note' && (expanded.value.has(node.id) || resolved.value[node.id] || node.id === selection.value?.id));
    for (let i = 0; i < entries.length; i += 6) await Promise.all(entries.slice(i, i + 6).map(entry => resolveEntry(entry)));
    if (!entries.length) ElMessage.info('选择或展开节点后可读取引用内容');
  } finally {
    refreshing.value = false;
  }
}
async function addAttribute() {
  try {
    const {
      value
    } = await ElMessageBox.prompt('输入属性名称', '添加属性', {
      inputPattern: /\S/,
      inputErrorMessage: '名称不能为空',
      confirmButtonText: '添加',
      cancelButtonText: '取消'
    });
    const key = value.trim();
    if (key.length > 100 || Object.keys(selectedNode.value.attributes).length >= 50) {
      ElMessage.warning('属性名最多 100 字，每个节点最多 50 项');
      return;
    }
    ;
    if (!(key in selectedNode.value.attributes)) selectedNode.value.attributes[key] = '';
  } catch {/* 取消时保留节点。 */}
}
async function removeNode() {
  if (!editable.value || !selectedNode.value || selectedEntry.value?.data.inherited) return;
  const node = selectedNode.value;
  const currentGraph = graph.value;
  const connected = graph.value.edges.filter(edge => [edge.source, edge.target].some(endpoint => endpoint === node.id || endpoint.startsWith(`${node.id}/`)));
  try {
    await ElMessageBox.confirm(`移出「${node.label}」并删除本链中与它相连的 ${connected.length} 条关系？原始实体和子链会保留。`, '移出节点', {
      type: 'warning',
      confirmButtonText: '移出',
      cancelButtonText: '取消'
    });
    if (!editable.value || graph.value !== currentGraph) return;
    flushHistory();
    graph.value.nodes = graph.value.nodes.filter(item => item.id !== node.id);
    graph.value.edges = graph.value.edges.filter(edge => !connected.includes(edge));
    selection.value = null;
    delete resolved.value[node.id];
    expanded.value.delete(node.id);
    flushHistory();
  } catch {/* 取消时保留节点。 */}
}
function removeEdge() {
  if (!editable.value || !selectedEdge.value || selectedEdgeEntry.value?.data.inherited) return;
  flushHistory();
  graph.value.edges = graph.value.edges.filter(edge => edge.id !== selection.value.id);
  selection.value = null;
  flushHistory();
}
function removeMember(item) {
  selectedNode.value.members = selectedNode.value.members.filter(ref => ref.uuid !== item.uuid || ref.entity_type !== item.entity_type);
  resolveSelection();
}
function endpointLabel(endpoint, prefix = '') {
  return rendered.value.nodes.find(node => node.id === prefix + endpoint)?.data.node.label || `${endpoint.split('/')[0]} 内的节点`;
}
function arrange(mode) {
  const positions = new Map(),
    nodes = graph.value.nodes;
  if (mode === 'tree') {
    const children = new Map(nodes.map(node => [node.id, []])),
      incoming = new Set();
    for (const edge of graph.value.edges) {
      const source = edge.source.split('/')[0],
        target = edge.target.split('/')[0];
      if (source !== target) {
        children.get(source)?.push(target);
        incoming.add(target);
      }
    }
    const queue = nodes.filter(node => !incoming.has(node.id)).map(node => [node.id, 0]);
    if (!queue.length && nodes.length) queue.push([nodes[0].id, 0]);
    const levels = new Map();
    for (let cursor = 0; cursor < queue.length; cursor++) {
      const [id, level] = queue[cursor];
      if (positions.has(id)) continue;
      const row = levels.get(level) || 0;
      positions.set(id, {
        x: 80 + level * 340,
        y: 80 + row * 190
      });
      levels.set(level, row + 1);
      for (const child of children.get(id) || []) if (!positions.has(child)) queue.push([child, level + 1]);
    }
  }
  const bottom = positions.size ? Math.max(...[...positions.values()].map(pos => pos.y)) + 200 : 80;
  let leftover = 0;
  for (const node of nodes) {
    if (positions.has(node.id)) node.position = positions.get(node.id);else {
      node.position = {
        x: 80 + leftover % 3 * 340,
        y: bottom + Math.floor(leftover / 3) * 190
      };
      leftover++;
    }
  }
  expanded.value = new Set();
  nextTick(() => fitView({
    padding: 0.2,
    duration: 250
  }));
}
function exportGraph() {
  const blob = new Blob([JSON.stringify({
    id: graph.value.id,
    revision: graph.value.revision,
    ...graphPayload(graph.value)
  }, null, 2)], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob),
    link = document.createElement('a');
  link.href = url;
  link.download = `证据链-${graph.value.id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function beforeUnload(event) {
  if (dirty.value && graph.value) {
    event.preventDefault();
    event.returnValue = '';
  }
}
/**
 * 处理图谱快捷键，保留输入控件的原生编辑，并避免穿透弹窗。
 * @param {KeyboardEvent} event 当前键盘事件。
 */
function handleEditorKeydown(event) {
  if (event.defaultPrevented || event.isComposing || event.altKey) return;
  const key = event.key.toLowerCase();
  const modifier = event.ctrlKey || event.metaKey;
  const saveShortcut = modifier && key === 's' && !event.shiftKey;
  const undoShortcut = modifier && key === 'z' && !event.shiftKey;
  const redoShortcut = modifier && ((key === 'y' && !event.shiftKey) || (key === 'z' && event.shiftKey));
  const deleteShortcut = key === 'delete' && !modifier && !event.shiftKey;
  if (!saveShortcut && !undoShortcut && !redoShortcut && !deleteShortcut) return;
  if (!saveShortcut && (event.target?.isContentEditable || event.target?.closest?.('input, textarea, select, [role="textbox"]'))) return;
  event.preventDefault();
  if (event.repeat || loading.value || loadError.value || !graph.value || !editable.value || !tracking) return;
  if (entityPicker.value || chainPicker.value || relationVisible.value ||
    [...document.querySelectorAll('[aria-modal="true"], .el-tour__content')].some(element => element.getClientRects().length)) return;
  if (saveShortcut) {
    if (dirty.value) save();
  } else if (undoShortcut) {
    undo();
  } else if (redoShortcut) {
    redo();
  } else if (selectedNode.value && !selectedEntry.value.data.inherited) {
    removeNode();
  } else if (selectedEdge.value && !selectedEdgeEntry.value.data.inherited) {
    removeEdge();
  }
}
onBeforeRouteLeave(canLeave);
onBeforeRouteUpdate(async to => {
  if (to.params.id !== route.params.id) return await canLeave();
});
watch(() => route.params.id, load);
onMounted(() => {
  load();
  window.addEventListener('beforeunload', beforeUnload);
  window.addEventListener('keydown', handleEditorKeydown);
});
onBeforeUnmount(() => {
  ++loadSequence;
  clearTimeout(historyTimer);
  window.removeEventListener('beforeunload', beforeUnload);
  window.removeEventListener('keydown', handleEditorKeydown);
});
</script>

<style scoped>
.evidence-editor.evidence-editor-mobile { height: auto; min-height: calc(100dvh - var(--mobile-header-height) - var(--mobile-nav-height)); overflow: visible; }
:deep(.vue-flow__edge.animated .vue-flow__edge-path){animation-duration:.8s}
@media(prefers-reduced-motion:reduce){:deep(.vue-flow__edge.animated .vue-flow__edge-path){animation:none}}
.evidence-editor{height:100vh;display:flex;flex-direction:column;overflow:hidden}.editor-heading{display:flex;align-items:center;gap:12px;min-height:78px;padding:12px 24px;background:#fff;border-bottom:1px solid #e2e8f0;flex-shrink:0}.editor-body{display:flex;flex:1;min-height:0}.editor-palette{width:216px;flex-shrink:0;background:#fff;border-right:1px solid #e2e8f0;display:flex;flex-direction:column}.palette-button{display:flex;gap:12px;align-items:center;width:100%;text-align:left;padding:12px 8px;border-radius:8px;font-size:13px}.palette-button:hover{background:#eff6ff}.palette-button:disabled{opacity:.45;cursor:not-allowed}.palette-button>svg{font-size:22px}.palette-button small{display:block;font-size:10px;color:#94a3b8;margin-top:4px}.graph-region{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;background:#f8fafc}.graph-toolbar{display:flex;align-items:center;gap:8px;padding:10px 12px;background:#ffffffed;border-bottom:1px solid #e2e8f0;z-index:5;flex-wrap:wrap}.evidence-flow{flex:1;height:0;min-height:200px}.graph-empty{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;text-align:center;width:300px}.editor-inspector{width:330px;flex-shrink:0;border-left:1px solid #e2e8f0;background:white;overflow-y:auto}.inspector-title{display:flex;align-items:center;gap:8px;padding:18px 20px;font-size:14px;font-weight:600;border-bottom:1px solid #f1f5f9;position:sticky;top:0;background:#fff;z-index:4}.inspector-content{padding:20px}.entity-preview{padding:12px;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:10px;overflow-wrap:anywhere}:deep(.vue-flow__edge-text){font-size:11px}:deep(.vue-flow__minimap){width:140px;height:95px}:deep(.vue-flow__edge.selected path){stroke:#2563eb;stroke-width:3}@media(max-width:1200px){.editor-palette{width:180px}.editor-inspector{width:290px}.editor-heading{padding:10px 16px}}@media(max-width:900px){.editor-palette{display:none}.editor-inspector{width:260px}.editor-heading{flex-wrap:wrap}.editor-heading h1{max-width:220px}}@media(max-width:640px){.editor-body{overflow:auto;flex-direction:column}.graph-region{flex:none;height:55vh}.editor-inspector{width:100%;overflow:visible}.editor-heading{gap:6px}.editor-heading>.el-tag{display:none}}
</style>
