<template>
  <main class="mobile-evidence-editor">
    <header class="evidence-mobile-heading">
      <div><h1>{{ graph.title }}</h1><p>修订 {{ graph.revision }} · {{ dirty ? '有未保存的更改' : '已保存' }}<span v-if="!editable"> · 只读</span></p></div>
      <el-tag :type="graph.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[graph.status] }}</el-tag>
    </header>
    <p v-if="graph.purpose" class="evidence-purpose">{{ graph.purpose }}</p>
    <div class="evidence-tools">
      <el-button @click="graphVisible = true">查看图谱</el-button><el-button @click="openMeta">设置</el-button>
      <el-button :loading="refreshing" @click="$emit('refresh')">刷新引用</el-button>
      <el-button :disabled="!editable || !canUndo" @click="$emit('undo')">撤销</el-button><el-button :disabled="!editable || !canRedo" @click="$emit('redo')">重做</el-button>
    </div>
    <el-alert v-if="saveError" title="保存未完成，当前编辑已保留" type="error" :closable="false" show-icon>
      <p>{{ saveError }}</p><el-button link type="primary" @click="$emit('export')">导出当前编辑</el-button><el-button link type="primary" @click="$emit('reload')">重新加载服务器内容</el-button>
    </el-alert>
    <el-input v-model="query" aria-label="查找证据节点与关系" placeholder="查找判断、材料或关系" clearable class="evidence-query" />
    <section class="evidence-reading-section">
      <h2>判断与问题 <span>{{ sections.judgments.length }}</span></h2>
      <p v-if="!sections.judgments.length" class="evidence-empty-hint">可添加一个判断或问题，组织支持材料与反证。</p>
      <article v-for="entry in sections.judgments.filter(matchesNode)" :key="entry.id" class="evidence-reading-card" :class="{ selected: selection?.id === entry.id }">
        <button type="button" class="evidence-card-title" @click="showNode(entry.id)"><Icon icon="mdi:lightbulb-outline" /><strong>{{ entry.data.node.label }}</strong><Icon icon="mdi:chevron-right" /></button>
        <p v-if="entry.data.node.description" class="evidence-copy">{{ entry.data.node.description }}</p>
        <p v-if="entry.data.inherited" class="evidence-caption">来自引用子链</p>
        <button v-for="relation in relationsFor(entry.id)" :key="relation.id" type="button" class="evidence-relation-preview" @click="showEdge(relation)">
          <span :class="relation.data.edge.label === '反驳' ? 'text-red-700' : 'text-blue-700'">{{ relation.data.edge.label }}</span>
          <span>{{ endpointLabel(`${relation.data.ownerPath || ''}${relation.data.edge.source}`) }} {{ relation.data.edge.directed ? '→' : '↔' }} {{ endpointLabel(`${relation.data.ownerPath || ''}${relation.data.edge.target}`) }}</span>
          <small>{{ RELATION_STATUS[relation.data.edge.status] }} · {{ relation.data.edge.anchors.length }} 项原始依据</small>
          <q v-if="relation.data.edge.anchors[0]?.quote">{{ relation.data.edge.anchors[0].quote }}</q>
        </button>
        <p v-if="!relationsFor(entry.id).length" class="evidence-caption">尚未建立关系</p>
      </article>
    </section>
    <section class="evidence-reading-section">
      <h2>关系与原始依据 <span>{{ sections.relations.length }}</span></h2>
      <button v-for="entry in sections.relations.filter(matchesRelation)" :key="entry.id" type="button" class="evidence-reading-card evidence-relation-preview" :class="{ selected: selection?.id === entry.id }" @click="showEdge(entry)">
        <strong>{{ entry.data.edge.label }} <small>{{ RELATION_STATUS[entry.data.edge.status] }}</small></strong>
        <span>{{ endpointLabel(`${entry.data.ownerPath || ''}${entry.data.edge.source}`) }} {{ entry.data.edge.directed ? '→' : '↔' }} {{ endpointLabel(`${entry.data.ownerPath || ''}${entry.data.edge.target}`) }}</span>
        <span v-if="entry.data.missing" class="text-red-700">内部节点已不可用，原始依据仍保留</span>
        <q v-if="entry.data.edge.anchors[0]?.quote">{{ entry.data.edge.anchors[0].quote }}</q>
        <small>{{ entry.data.edge.anchors.length }} 项原始依据 · 查看关系与出处</small>
      </button>
      <p v-if="!sections.relations.length" class="evidence-empty-hint">选择两个节点，记录它们的关系与原文依据。</p>
    </section>
    <section class="evidence-reading-section">
      <h2>材料与引用 <span>{{ sections.materials.length }}</span></h2>
      <button v-for="entry in sections.materials.filter(matchesNode)" :key="entry.id" type="button" class="evidence-reading-card evidence-material-card" :class="{ selected: selection?.id === entry.id }" @click="showNode(entry.id)">
        <Icon :icon="NODE_KINDS[entry.data.node.kind].icon" /><div><strong>{{ entry.data.node.label }}</strong><p>{{ NODE_KINDS[entry.data.node.kind].label }}{{ entry.data.inherited ? ' · 引用内容' : '' }}</p></div><Icon icon="mdi:chevron-right" />
      </button>
      <p v-if="!sections.materials.length" class="evidence-empty-hint">可选择具体实体版本、固定集合、动态版本或已有子链。</p>
    </section>
    <MobileActionBar aria-label="证据链操作">
      <el-button :disabled="!editable" @click="startNode">添加节点</el-button>
      <el-button :disabled="!editable || rendered.nodes.length < 2" @click="startRelation()">建立关系</el-button>
      <el-button type="primary" :loading="saving" :disabled="!editable || !dirty" @click="$emit('save')">保存</el-button>
    </MobileActionBar>

    <MobileSheet v-model="sheetVisible" :title="sheetTitle">
      <div v-if="sheet === 'node' && selectedNode" class="evidence-mobile-panel">
        <div class="evidence-panel-heading"><el-tag>{{ NODE_KINDS[selectedNode.kind].label }}</el-tag><el-tag v-if="selectedEntry.data.inherited" type="info">引用内容 · 只读</el-tag></div>
        <h2>{{ selectedNode.label }}</h2><p class="evidence-copy">{{ selectedNode.description || '尚未填写说明' }}</p>
        <dl v-if="Object.keys(selectedNode.attributes).length"><template v-for="(value, key) in selectedNode.attributes" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></template></dl>
        <template v-if="selectedNode.kind !== 'note'">
          <p v-if="selectedNode.kind === 'entity'" class="evidence-caption">具体版本：{{ selectedNode.entity.uuid }}</p>
          <p v-if="selectedNode.kind === 'collection'" class="evidence-caption">固定集合 · {{ selectedNode.members.length }} 个指定版本</p>
          <p v-if="selectedNode.kind === 'versions'" class="evidence-caption">动态读取全部版本，包含未来采集的数据。{{ selectedNode.version_source.platform }} · {{ selectedNode.version_source.source_id }}</p>
          <div class="evidence-tools"><el-button :loading="resolving.has(selection.id)" @click="$emit('resolve')">重新读取材料</el-button><el-button v-if="['collection', 'versions', 'chain'].includes(selectedNode.kind)" :loading="resolving.has(selection.id)" @click="$emit('expand')">{{ expanded.has(selection.id) ? '收起内部节点' : '展开内部节点' }}</el-button></div>
          <el-alert v-if="resolveErrors[selection.id]" :title="resolveErrors[selection.id]" type="error" :closable="false" />
          <p v-if="resolving.has(selection.id)" role="status" class="evidence-caption">正在读取原始材料…</p>
          <p v-if="selectedResolved?.resolved_at" class="evidence-caption">读取于 {{ new Date(selectedResolved.resolved_at).toLocaleString('zh-CN') }}</p>
          <article v-if="selectedNode.kind === 'chain'" class="evidence-anchor">
            <strong>{{ selectedResolved?.chain?.title || selectedNode.label }}</strong><p>{{ selectedResolved?.chain?.purpose }}</p><p v-if="selectedResolved?.chain">修订 {{ selectedResolved.chain.revision }} · {{ selectedResolved.chain.nodes.length }} 节点 · {{ selectedResolved.chain.edges.length }} 关系</p>
            <router-link :to="`/evidence/chains/${encodeURIComponent(selectedNode.chain_id)}`">进入子链查看与编辑 →</router-link>
          </article>
          <article v-for="item in selectedResolved?.items || []" :key="`${item.entity_type}:${item.uuid}`" class="evidence-anchor">
            <el-tag v-if="item.missing" type="danger">原始材料缺失</el-tag><strong>{{ plainEntityTitle(item.title) }}</strong><p class="evidence-caption">{{ item.platform || item.entity_type }} · {{ item.crawled_at || item.last_edit_at || '时间未提供' }}</p><p class="evidence-copy">{{ item.clean_content }}</p>
            <router-link v-if="!item.missing" :to="entityDetailPath(item)">查看原始材料与版本 →</router-link>
          </article>
          <el-empty v-if="selectedResolved?.total === 0" description="当前没有匹配材料" :image-size="50" />
          <el-pagination v-if="selectedResolved?.total > 30" :current-page="selectedResolved.page" :page-size="30" :total="selectedResolved.total" :pager-count="5" layout="prev, pager, next" @current-change="$emit('resolve', $event)" />
          <div v-if="expanded.has(selection.id)" class="evidence-related"><h3>已展开的内部节点</h3><button v-for="entry in rendered.nodes.filter(item => item.id.startsWith(`${selection.id}/`))" :key="entry.id" type="button" @click="showNode(entry.id)">{{ entry.data.node.label }} →</button></div>
        </template>
        <div class="evidence-related"><h3>相关关系</h3><button v-for="entry in relationsFor(selection.id)" :key="entry.id" type="button" @click="showEdge(entry)">{{ entry.data.edge.label }} · {{ entry.data.edge.anchors.length }} 项依据 →</button><p v-if="!relationsFor(selection.id).length" class="evidence-caption">暂无相关关系</p></div>
        <div v-if="editable && !selectedEntry.data.inherited" class="evidence-tools"><el-button type="primary" @click="editNode">编辑节点</el-button><el-button @click="startRelation()">建立关系</el-button><el-button type="danger" plain @click="$emit('remove-node')">移出本链</el-button></div>
      </div>

      <div v-else-if="sheet === 'edge' && selectedEdge" class="evidence-mobile-panel">
        <el-tag>{{ RELATION_STATUS[selectedEdge.status] }}</el-tag><el-tag v-if="selectedEdgeEntry.data.inherited" type="info">子链关系 · 只读</el-tag>
        <h2>{{ selectedEdge.label }}</h2>
        <div class="evidence-endpoints"><button type="button" @click="showEndpoint(`${selectedEdgeEntry.data.ownerPath || ''}${selectedEdge.source}`)">{{ endpointLabel(`${selectedEdgeEntry.data.ownerPath || ''}${selectedEdge.source}`) }}</button><span>{{ selectedEdge.directed ? '→' : '↔' }}</span><button type="button" @click="showEndpoint(`${selectedEdgeEntry.data.ownerPath || ''}${selectedEdge.target}`)">{{ endpointLabel(`${selectedEdgeEntry.data.ownerPath || ''}${selectedEdge.target}`) }}</button></div>
        <el-alert v-if="selectedEdgeEntry.data.missing" title="内部端点已不可用，依据仍保留，可编辑关系重新选择端点。" type="warning" :closable="false" />
        <p class="evidence-copy">{{ selectedEdge.description || '尚未填写关系说明' }}</p><h3>原始依据 · {{ selectedEdge.anchors.length }} 项</h3>
        <article v-for="(anchor, index) in selectedEdge.anchors" :key="index" class="evidence-anchor"><strong>依据 {{ index + 1 }}</strong><blockquote>{{ anchor.quote || '未填写原文摘录' }}</blockquote><p v-if="anchor.locator">定位：{{ anchor.locator }}</p><p class="evidence-caption">{{ anchor.entity.entity_type }} · {{ anchor.entity.uuid }}</p><router-link :to="entityDetailPath(anchor.entity)">追溯原始材料 →</router-link></article>
        <p v-if="!selectedEdge.anchors.length" class="evidence-empty-hint">尚未添加原始依据。</p>
        <div v-if="editable && !selectedEdgeEntry.data.inherited" class="evidence-tools"><el-button type="primary" @click="startRelation(selectedEdgeEntry)">编辑关系与依据</el-button><el-button type="danger" plain @click="deleteRelation">删除关系</el-button></div>
        <router-link v-if="selectedEdgeEntry.data.inherited && ownerChainId" :to="`/evidence/chains/${encodeURIComponent(ownerChainId)}`">进入所属子链编辑 →</router-link>
      </div>

      <div v-else-if="sheet === 'add'" class="evidence-mobile-panel">
        <p class="evidence-step">第 {{ nodeStep + 1 }} 步 / 3 · {{ ['选择类型', '选择材料与填写信息', '确认添加'][nodeStep] }}</p>
        <div v-if="nodeStep === 0" class="evidence-type-options">
          <button v-for="kind in [{ value: 'note', title: '判断或问题', text: '记录待验证判断、事件或问题' }, { value: 'material', title: '材料与版本', text: '独立实体、固定集合或动态全部版本' }, { value: 'chain', title: '引用已有子链', text: '读取子链当前内容，不复制原图' }]" :key="kind.value" type="button" :aria-pressed="nodeKind === kind.value" :class="{ active: nodeKind === kind.value }" @click="chooseNodeKind(kind.value)"><strong>{{ kind.title }}</strong><small>{{ kind.text }}</small></button>
        </div>
        <template v-else-if="nodeStep === 1">
          <el-button v-if="nodeKind === 'material'" type="primary" plain @click="pickerPurpose = 'new'; entityPicker = true">{{ pendingNodes.length ? '重新选择材料' : '选择材料与版本' }}</el-button>
          <el-button v-if="nodeKind === 'chain'" type="primary" plain @click="chainPicker = true">{{ pendingNodes.length ? '重新选择子链' : '选择已有子链' }}</el-button>
          <el-form label-position="top"><template v-for="(node, index) in pendingNodes" :key="node.id"><h3>{{ pendingNodes.length > 1 ? `节点 ${index + 1} · ` : '' }}{{ NODE_KINDS[node.kind].label }}</h3><el-form-item label="名称"><el-input v-model="node.label" maxlength="300" /></el-form-item><el-form-item label="说明"><el-input v-model="node.description" type="textarea" :rows="3" maxlength="20000" /></el-form-item></template></el-form>
        </template>
        <template v-else><p class="evidence-caption">确认后加入当前编辑，点击页面“保存”后写入证据链。</p><article v-for="node in pendingNodes" :key="node.id" class="evidence-anchor"><el-tag>{{ NODE_KINDS[node.kind].label }}</el-tag><h3>{{ node.label }}</h3><p>{{ node.description }}</p><p v-if="node.kind === 'versions'">全部版本动态引用，包含未来采集版本</p><p v-if="node.kind === 'collection'">固定 {{ node.members.length }} 个实体版本</p><p v-if="node.kind === 'entity'">指定版本：{{ node.entity.uuid }}</p><p v-if="node.kind === 'chain'">实时读取所引用子链的当前内容</p></article></template>
      </div>

      <el-form v-else-if="sheet === 'node-edit' && nodeDraft" label-position="top" class="evidence-mobile-panel">
        <el-form-item label="名称"><el-input v-model="nodeDraft.label" maxlength="300" /></el-form-item><el-form-item label="说明"><el-input v-model="nodeDraft.description" type="textarea" :rows="4" maxlength="20000" /></el-form-item>
        <h3>自定义属性</h3><div v-for="(_, key) in nodeDraft.attributes" :key="key" class="evidence-attribute"><label>{{ key }}</label><el-input v-model="nodeDraft.attributes[key]" maxlength="4000" /><el-button link type="danger" @click="delete nodeDraft.attributes[key]">移除</el-button></div>
        <div class="evidence-tools"><el-input v-model="attributeName" maxlength="100" placeholder="新属性名称" aria-label="新属性名称" /><el-button :disabled="!attributeName.trim() || Object.keys(nodeDraft.attributes).length >= 50" @click="addDraftAttribute">添加属性</el-button></div>
        <template v-if="nodeDraft.kind === 'collection'"><h3>固定集合成员 · {{ nodeDraft.members.length }}</h3><div v-for="member in nodeDraft.members" :key="`${member.entity_type}:${member.uuid}`" class="evidence-anchor"><router-link :to="entityDetailPath(member)">{{ member.entity_type }} · {{ member.uuid }}</router-link><el-button type="danger" link :disabled="nodeDraft.members.length < 2" @click="nodeDraft.members = nodeDraft.members.filter(item => item !== member)">移出集合</el-button></div><el-button @click="pickerPurpose = 'members'; entityPicker = true">补充集合成员</el-button></template>
      </el-form>

      <div v-else-if="sheet === 'relation' && relationDraft" class="evidence-mobile-panel">
        <p class="evidence-step">第 {{ relationStep + 1 }} 步 / 3 · {{ ['选择关系端点', '关系类型与原始依据', '确认关系'][relationStep] }}</p>
        <el-form v-if="relationStep === 0" label-position="top"><el-form-item label="起点"><el-select v-model="relationDraft.source" filterable><el-option v-for="node in endpointOptions" :key="node.id" :value="node.id" :label="node.label" /></el-select></el-form-item><el-form-item label="终点"><el-select v-model="relationDraft.target" filterable><el-option v-for="node in endpointOptions" :key="node.id" :value="node.id" :label="node.label" /></el-select></el-form-item><p class="evidence-caption">如需连接集合或子链中的节点，请先在节点详情展开内部内容。已存在的内部端点会完整保留。</p></el-form>
        <el-form v-else-if="relationStep === 1" label-position="top">
          <el-form-item label="关系类型"><el-select v-model="relationDraft.label" filterable allow-create default-first-option><el-option v-for="label in graph.relation_types" :key="label" :value="label" :label="label" /></el-select></el-form-item><el-form-item label="方向"><el-switch v-model="relationDraft.directed" active-text="有向关系" inactive-text="无向关系" /></el-form-item><el-form-item label="核实状态"><el-select v-model="relationDraft.status"><el-option v-for="(label, value) in RELATION_STATUS" :key="value" :value="value" :label="label" /></el-select></el-form-item><el-form-item label="关系说明"><el-input v-model="relationDraft.description" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
          <el-alert v-if="['先于', '导致'].includes(relationDraft.label)" title="时间先后与因果需要分别判断，请记录建立关系的理由。" type="warning" :closable="false" />
          <h3>原始依据 · {{ relationDraft.anchors.length }} 项</h3><p class="evidence-caption">请选择具体版本，并填写支持或反驳该关系的摘录与定位。</p>
          <article v-for="(anchor, index) in relationDraft.anchors" :key="index" class="evidence-anchor"><router-link :to="entityDetailPath(anchor.entity)">{{ anchor.entity.entity_type }} · {{ anchor.entity.uuid }} ↗</router-link><el-form-item :label="`依据 ${index + 1} 原文摘录`"><el-input v-model="anchor.quote" type="textarea" :rows="3" maxlength="10000" /></el-form-item><el-form-item label="定位：段落、楼层或时间点"><el-input v-model="anchor.locator" maxlength="1000" /></el-form-item><el-button link type="danger" @click="relationDraft.anchors.splice(index, 1)">移除依据</el-button></article>
          <el-button :disabled="relationDraft.anchors.length >= 100" @click="pickerPurpose = 'anchors'; entityPicker = true">添加原始依据</el-button>
        </el-form>
        <template v-else><div class="evidence-anchor"><strong>{{ endpointLabel(relationDraft.source) }} {{ relationDraft.directed ? '→' : '↔' }} {{ endpointLabel(relationDraft.target) }}</strong><h3>{{ relationDraft.label }} · {{ RELATION_STATUS[relationDraft.status] }}</h3><p>{{ relationDraft.description }}</p><p>{{ relationDraft.anchors.length }} 项原始依据</p><blockquote v-for="(anchor, index) in relationDraft.anchors" :key="index">{{ anchor.quote || '未填写摘录' }}<small v-if="anchor.locator">{{ anchor.locator }}</small></blockquote></div><p class="evidence-caption">确认后更新当前编辑，点击页面“保存”后写入证据链。</p></template>
      </div>

      <el-form v-else-if="sheet === 'meta' && metaDraft" label-position="top" :disabled="!editable" class="evidence-mobile-panel"><el-form-item label="名称"><el-input v-model="metaDraft.title" maxlength="200" /></el-form-item><el-form-item label="分析目的"><el-input v-model="metaDraft.purpose" type="textarea" :rows="3" maxlength="500" /></el-form-item><el-form-item label="说明"><el-input v-model="metaDraft.description" type="textarea" :rows="4" maxlength="20000" /></el-form-item><el-form-item label="状态"><el-select v-model="metaDraft.status"><el-option v-for="(label, value) in CHAIN_STATUS" :key="value" :value="value" :label="label" /></el-select></el-form-item><el-form-item label="标签"><el-select v-model="metaDraft.tags" multiple filterable allow-create default-first-option /></el-form-item><el-form-item label="常用关系类型"><el-select v-model="metaDraft.relation_types" multiple filterable allow-create default-first-option /></el-form-item></el-form>
      <el-alert v-if="formError" :title="formError" type="error" :closable="false" />
      <template #footer>
        <div class="evidence-sheet-actions">
          <template v-if="sheet === 'add'"><el-button @click="nodeStep ? nodeStep-- : sheet = ''">{{ nodeStep ? '上一步' : '取消' }}</el-button><el-button v-if="nodeStep < 2" type="primary" :disabled="!editable || (nodeStep === 1 && (!pendingNodes.length || pendingNodes.some(node => !node.label.trim())))" @click="nodeStep++">下一步</el-button><el-button v-else type="primary" :disabled="!editable" @click="confirmNodes">确认添加</el-button></template>
          <template v-else-if="sheet === 'relation'"><el-button @click="relationStep ? relationStep-- : sheet = ''">{{ relationStep ? '上一步' : '取消' }}</el-button><el-button v-if="relationStep < 2" type="primary" :disabled="!editable || !relationDraft.source || !relationDraft.target || !relationDraft.label?.trim()" @click="relationStep++">下一步</el-button><el-button v-else type="primary" :disabled="!editable" @click="confirmRelation">确认关系</el-button></template>
          <template v-else-if="sheet === 'node-edit'"><el-button @click="sheet = 'node'">取消</el-button><el-button type="primary" :disabled="!editable || !nodeDraft.label.trim()" @click="confirmNodeEdit">应用修改</el-button></template>
          <template v-else-if="sheet === 'meta'"><el-button @click="$emit('export')">导出图定义</el-button><el-button v-if="editable" type="primary" :disabled="!metaDraft.title.trim()" @click="confirmMeta">应用设置</el-button><el-button v-else @click="sheet = ''">关闭</el-button></template>
          <el-button v-else class="w-full" @click="sheet = ''">返回阅读列表</el-button>
        </div>
      </template>
    </MobileSheet>

    <EvidenceEntityPicker v-model="entityPicker" :allow-dynamic="pickerPurpose === 'new'" @add="acceptMaterials" />
    <EvidenceChainPicker v-model="chainPicker" :exclude-id="graph.id" @select="acceptChain" />
    <el-drawer v-model="graphVisible" title="证据图谱" size="100%" direction="btt" append-to-body class="mobile-evidence-graph" modal-class="mobile-evidence-graph-overlay" destroy-on-close @opened="$emit('fit')">
      <div class="evidence-graph-tools"><el-button @click="$emit('fit')">适应画布</el-button><el-button :disabled="!selection" @click="openGraphSelection">查看已选{{ selection?.type === 'edge' ? '关系' : '节点' }}</el-button></div>
      <p class="evidence-caption">双指缩放、拖动画布，点选节点或关系查看详情。</p>
      <VueFlow :id="flowId" :nodes="rendered.nodes.map(node => ({ ...node, selected: selection?.type === 'node' && selection.id === node.id }))" :edges="displayEdges" :node-types="nodeTypes" :nodes-connectable="false" :nodes-draggable="false" :delete-key-code="null" :min-zoom="0.15" :max-zoom="2.5" fit-view-on-init class="evidence-mobile-flow" @node-click="$emit('select-node', $event.node.id)" @edge-click="!$event.edge.data?.containment && $emit('select-edge', $event.edge)"><Background :gap="22" /><Controls :show-interactive="false" /></VueFlow>
      <template #footer><el-button type="primary" class="w-full" @click="graphVisible = false">返回阅读列表</el-button></template>
    </el-drawer>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessageBox } from 'element-plus'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import MobileActionBar from '@/components/mobile/MobileActionBar.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import EvidenceEntityPicker from '@/components/evidence/EvidenceEntityPicker.vue'
import EvidenceChainPicker from '@/components/evidence/EvidenceChainPicker.vue'
import { CHAIN_STATUS, RELATION_STATUS, NODE_KINDS, makeEvidenceNode, plainEntityTitle, entityDetailPath } from '@/utils/evidence'
import { evidenceReadingSections, evidenceEndpointLabel, createEvidenceRelationDraft, evidenceMaterialRefs, commitEvidenceRelation } from './mobileEvidence'

const props = defineProps({ graph: { type: Object, required: true }, rendered: { type: Object, required: true }, displayEdges: Array, selection: Object, editable: Boolean, dirty: Boolean, saving: Boolean, saveError: String, refreshing: Boolean, canUndo: Boolean, canRedo: Boolean, resolving: { type: Set, required: true }, expanded: { type: Set, required: true }, resolveErrors: Object, flowId: String, nodeTypes: Object })
const emit = defineEmits(['save', 'undo', 'redo', 'refresh', 'export', 'reload', 'select-node', 'select-edge', 'resolve', 'expand', 'remove-node', 'remove-edge', 'add-nodes', 'edit-node', 'edit-edge', 'edit-meta', 'fit'])
const query = ref(''), sheet = ref(''), graphVisible = ref(false), formError = ref('')
const entityPicker = ref(false), chainPicker = ref(false), pickerPurpose = ref('new')
const nodeStep = ref(0), nodeKind = ref('note'), pendingNodes = ref([]), nodeDraft = ref(null), attributeName = ref('')
const relationStep = ref(0), relationDraft = ref(null), relationBaseline = ref(''), metaDraft = ref(null)
const sheetVisible = computed({ get: () => Boolean(sheet.value), set: value => { if (!value) sheet.value = '' } })
const sheetTitle = computed(() => ({ node: '节点与原始材料', edge: '关系与原始依据', add: '添加证据节点', 'node-edit': '编辑节点', relation: '关系与依据编辑', meta: '证据链设置' }[sheet.value] || '证据详情'))
const sections = computed(() => evidenceReadingSections(props.rendered))
const selectedEntry = computed(() => props.selection?.type === 'node' ? props.rendered.nodes.find(node => node.id === props.selection.id) : null)
const selectedNode = computed(() => selectedEntry.value?.data.node)
const selectedResolved = computed(() => selectedEntry.value?.data.resolved)
const selectedEdgeEntry = computed(() => props.selection?.type === 'edge' ? props.rendered.edges.find(edge => edge.id === props.selection.id) : null)
const selectedEdge = computed(() => selectedEdgeEntry.value?.data.edge)
const ownerChainId = computed(() => props.rendered.nodes.find(node => node.id === selectedEdgeEntry.value?.data.ownerPath?.replace(/\/$/, ''))?.data.node.chain_id)
const hasDraft = computed(() => {
  if (sheet.value === 'add') return pendingNodes.value.some(node => node.label.trim() || node.description.trim())
  if (sheet.value === 'relation') return JSON.stringify(relationDraft.value) !== relationBaseline.value
  if (sheet.value === 'node-edit') return JSON.stringify(nodeDraft.value) !== JSON.stringify(selectedNode.value)
  if (sheet.value === 'meta') return Object.keys(metaDraft.value || {}).some(key => JSON.stringify(metaDraft.value[key]) !== JSON.stringify(props.graph[key]))
  return false
})
defineExpose({ hasDraft })
const endpointOptions = computed(() => {
  const options = props.rendered.nodes.map(node => ({ id: node.id, label: node.data.node.label + (node.data.inherited ? '（引用内）' : '') }))
  for (const endpoint of [relationDraft.value?.source, relationDraft.value?.target]) if (endpoint && !options.some(node => node.id === endpoint)) options.push({ id: endpoint, label: evidenceEndpointLabel(endpoint, props.rendered.nodes) })
  return options
})

/** """匹配节点名称与说明。""" */
function matchesNode(entry) { return `${entry.data.node.label} ${entry.data.node.description}`.toLowerCase().includes(query.value.trim().toLowerCase()) }
/** """匹配关系类型、说明以及原文摘录。""" */
function matchesRelation(entry) { return `${entry.data.edge.label} ${entry.data.edge.description} ${entry.data.edge.anchors.map(anchor => anchor.quote).join(' ')}`.toLowerCase().includes(query.value.trim().toLowerCase()) }
/** """返回节点相关的真实关系，折叠端点仍可从所属节点追溯。""" */
function relationsFor(id) { return sections.value.relations.filter(entry => [entry.source, entry.target, `${entry.data.ownerPath || ''}${entry.data.edge.source}`, `${entry.data.ownerPath || ''}${entry.data.edge.target}`].includes(id)) }
/** """用原始端点身份显示名称。""" */
function endpointLabel(path) { return evidenceEndpointLabel(path, props.rendered.nodes) }
/** """选择节点并打开其材料详情。""" */
function showNode(id) { emit('select-node', id); sheet.value = 'node' }
/** """选择真实关系并打开依据详情。""" */
function showEdge(entry) { emit('select-edge', entry); sheet.value = 'edge' }
/**
 * 跳到端点；内部节点折叠时先进入所属节点，允许继续展开追溯。
 * @param {string} path 关系保存的完整端点。
 */
function showEndpoint(path) {
  const entry = props.rendered.nodes.find(node => node.id === path) || props.rendered.nodes.filter(node => path.startsWith(`${node.id}/`)).sort((a, b) => b.id.length - a.id.length)[0]
  if (entry) showNode(entry.id)
}
/** """开始新增节点，不修改现有图定义。""" */
function startNode() { if (!props.editable) return; nodeStep.value = 0; chooseNodeKind('note'); sheet.value = 'add' }
/** """切换类型时重置尚未确认的节点草稿。""" */
function chooseNodeKind(kind) { nodeKind.value = kind; pendingNodes.value = kind === 'note' ? [makeEvidenceNode('note', { label: '' })] : [] }
/** """保存选中的子链引用到待确认草稿。""" */
function acceptChain(chain) { if (!props.editable) return; pendingNodes.value = [makeEvidenceNode('chain', { label: chain.title, chain_id: chain.id })]; chainPicker.value = false }
/**
 * 将选择器结果送入节点、集合或多项依据草稿，绝不直接修改图。
 * @param {Array} nodes 选择器生成的实体或版本节点。
 */
function acceptMaterials(nodes) {
  if (!props.editable) return
  if (pickerPurpose.value === 'new') { pendingNodes.value = JSON.parse(JSON.stringify(nodes)); return }
  const refs = evidenceMaterialRefs(nodes)
  if (pickerPurpose.value === 'anchors' && relationDraft.value) {
    if (relationDraft.value.anchors.length + refs.length > 100) { formError.value = '每条关系最多保留 100 项原始依据，请减少选择'; return }
    relationDraft.value.anchors.push(...refs.map(entity => ({ entity, quote: '', locator: '' })))
  } else if (pickerPurpose.value === 'members' && nodeDraft.value?.kind === 'collection') {
    const merged = evidenceMaterialRefs([{ kind: 'collection', members: [...nodeDraft.value.members, ...refs] }])
    if (merged.length > 2000) { formError.value = '固定集合最多保留 2000 个成员'; return }
    nodeDraft.value.members = merged
  }
}
/** """确认有效节点并交给现有编辑历史。""" */
function confirmNodes() { if (!props.editable || !pendingNodes.value.length || pendingNodes.value.some(node => !node.label.trim())) return; emit('add-nodes', JSON.parse(JSON.stringify(pendingNodes.value))); sheet.value = '' }
/** """只允许编辑本链节点，取消时保留原节点。""" */
function editNode() { if (!props.editable || !selectedNode.value || selectedEntry.value.data.inherited) return; nodeDraft.value = JSON.parse(JSON.stringify(selectedNode.value)); attributeName.value = ''; sheet.value = 'node-edit' }
/** """添加不覆盖既有键的自定义属性。""" */
function addDraftAttribute() { const key = attributeName.value.trim(); if (!key || Object.hasOwn(nodeDraft.value.attributes, key)) return; Object.defineProperty(nodeDraft.value.attributes, key, { value: '', enumerable: true, configurable: true, writable: true }); attributeName.value = '' }
/** """确认节点草稿后返回阅读详情。""" */
function confirmNodeEdit() { if (!props.editable || !nodeDraft.value.label.trim()) return; emit('edit-node', JSON.parse(JSON.stringify(nodeDraft.value))); sheet.value = 'node' }
/** """新增或编辑关系时复制真实端点，避免把折叠后的端点写回。""" */
function startRelation(entry = null) { if (!props.editable) return; relationDraft.value = createEvidenceRelationDraft(entry, props.graph, selectedEntry.value?.id || props.rendered.nodes[0]?.id || ''); if (!relationDraft.value) return; relationBaseline.value = JSON.stringify(relationDraft.value); relationStep.value = 0; sheet.value = 'relation' }
/**
 * 在独立图副本上校验草稿，成功后交给父编辑器提交。
 */
function confirmRelation() {
  const graph = JSON.parse(JSON.stringify(props.graph))
  formError.value = commitEvidenceRelation(graph, relationDraft.value, props.rendered.nodes, props.editable)
  if (formError.value) return
  emit('edit-edge', JSON.parse(JSON.stringify(relationDraft.value)))
  sheet.value = 'edge'
}
/** """删除关系前确认，保留取消与撤销能力。""" */
async function deleteRelation() { if (!props.editable || selectedEdgeEntry.value?.data.inherited) return; const id = props.selection?.id; try { await ElMessageBox.confirm('删除此关系及其依据记录？原始材料会保留，可通过撤销恢复关系。', '删除关系', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }); if (props.editable && props.selection?.id === id) emit('remove-edge') } catch { /* 取消时保留关系。 */ } }
/** """复制基础设置，阅读时不修改原始图。""" */
function openMeta() { metaDraft.value = JSON.parse(JSON.stringify(Object.fromEntries(['title', 'purpose', 'description', 'status', 'tags', 'relation_types'].map(key => [key, props.graph[key]])))); sheet.value = 'meta' }
/** """确认基础设置后回到阅读列表。""" */
function confirmMeta() { if (!props.editable || !metaDraft.value.title.trim()) return; emit('edit-meta', JSON.parse(JSON.stringify(metaDraft.value))); sheet.value = '' }
/** """退出全屏图时保留选择并打开相应详情。""" */
function openGraphSelection() { graphVisible.value = false; sheet.value = props.selection?.type === 'edge' ? 'edge' : 'node' }
watch(sheet, () => { formError.value = '' })
watch(() => props.selection, value => { if (!value && ['node', 'edge', 'node-edit'].includes(sheet.value)) sheet.value = '' })
watch(() => props.graph.id, () => { sheet.value = ''; graphVisible.value = false; entityPicker.value = false; chainPicker.value = false })
</script>

<style scoped>
.mobile-evidence-editor { padding: 16px; background: #f5f7fb; min-width: 0; }
.evidence-mobile-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.evidence-mobile-heading h1 { margin: 0; font-size: 22px; font-weight: 700; color: #0f172a; overflow-wrap: anywhere; }
.evidence-mobile-heading p, .evidence-caption, .evidence-empty-hint { font-size: 12px; color: #64748b; line-height: 1.7; margin: 8px 0; overflow-wrap: anywhere; }
.evidence-purpose { padding: 12px; margin: 12px 0; color: #334155; background: #eff6ff; border-radius: 12px; font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.evidence-tools { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.evidence-tools :deep(.el-button) { margin: 0; }
.evidence-tools :deep(.el-input) { flex: 1; min-width: 120px; }
.evidence-query { margin: 8px 0; }
.evidence-reading-section { margin: 16px 0 24px; }
.evidence-reading-section h2 { font-size: 17px; color: #0f172a; font-weight: 700; margin-bottom: 12px; }
.evidence-reading-section h2 span { color: #64748b; font-size: 13px; font-weight: 400; }
.evidence-reading-card { display: block; width: 100%; text-align: left; margin-bottom: 12px; padding: 14px; border-radius: 14px; border: 1px solid #e2e8f0; background: #fff; overflow-wrap: anywhere; }
.evidence-reading-card.selected { border-color: #93c5fd; }
.evidence-card-title { display: flex; width: 100%; align-items: center; gap: 8px; min-height: 44px; font-size: 16px; color: #0f172a; text-align: left; }
.evidence-card-title strong { flex: 1; }
.evidence-card-title svg { flex-shrink: 0; color: #2563eb; }
.evidence-copy { font-size: 14px; white-space: pre-wrap; line-height: 1.8; margin: 10px 0; overflow-wrap: anywhere; }
.evidence-reading-card > .evidence-copy { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.evidence-relation-preview { display: flex; flex-direction: column; gap: 8px; width: 100%; min-height: 44px; text-align: left; font-size: 13px; }
.evidence-reading-card > .evidence-relation-preview { margin-top: 10px; padding: 12px; border-radius: 10px; background: #f8fafc; }
.evidence-relation-preview small { color: #64748b; font-size: 12px; }
.evidence-relation-preview q { color: #475569; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.evidence-material-card { display: flex; align-items: center; gap: 10px; }
.evidence-material-card > div { flex: 1; min-width: 0; }
.evidence-material-card p { color: #64748b; font-size: 12px; margin-top: 6px; }
.evidence-material-card svg { color: #2563eb; flex-shrink: 0; }
.evidence-mobile-panel { color: #334155; overflow-wrap: anywhere; }
.evidence-mobile-panel h2 { font-size: 20px; font-weight: 700; margin: 14px 0; }
.evidence-mobile-panel h3 { font-size: 15px; font-weight: 600; margin: 16px 0 10px; }
.evidence-mobile-panel .el-select { width: 100%; }
.evidence-mobile-panel dt { font-size: 12px; color: #64748b; margin-top: 10px; }.evidence-mobile-panel dd { font-size: 14px; margin-top: 4px; }
.evidence-panel-heading { display: flex; flex-wrap: wrap; gap: 8px; }
.evidence-anchor { padding: 12px; border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 12px; margin: 12px 0; font-size: 13px; overflow-wrap: anywhere; }
.evidence-anchor strong { display: block; margin: 6px 0; }.evidence-anchor p { margin: 8px 0; }.evidence-anchor blockquote { margin: 12px 0; padding-left: 10px; border-left: 3px solid #bfdbfe; line-height: 1.8; white-space: pre-wrap; }.evidence-anchor blockquote small { display: block; color: #64748b; }
.evidence-mobile-panel a { display: inline-flex; align-items: center; min-height: 44px; color: #2563eb; }
.evidence-related button { display: block; width: 100%; min-height: 44px; padding: 10px; text-align: left; color: #2563eb; background: #eff6ff; border-radius: 8px; margin: 8px 0; }
.evidence-endpoints { display: flex; flex-direction: column; align-items: center; gap: 4px; margin: 12px 0; }.evidence-endpoints button { width: 100%; min-height: 44px; border: 1px solid #dbeafe; padding: 10px; color: #2563eb; border-radius: 8px; }
.evidence-step { font-size: 13px; color: #2563eb; margin: 6px 0 18px; }.evidence-type-options { display: flex; flex-direction: column; gap: 12px; }.evidence-type-options button { min-height: 80px; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; text-align: left; }.evidence-type-options button.active { border-color: #3b82f6; background: #eff6ff; }.evidence-type-options small { display: block; color: #64748b; margin-top: 6px; }
.evidence-attribute { margin: 10px 0; }.evidence-attribute label { display: block; font-size: 13px; margin-bottom: 6px; }
.evidence-sheet-actions { display: flex; flex-wrap: wrap; gap: 8px; }.evidence-sheet-actions .el-button { flex: 1; margin: 0; }
.mobile-evidence-editor :deep(.el-button), .evidence-mobile-panel :deep(.el-button) { min-height: 44px; }.mobile-evidence-editor :deep(.el-input__wrapper), .evidence-mobile-panel :deep(.el-input__wrapper), .evidence-mobile-panel :deep(.el-select__wrapper) { min-height: 44px; }.evidence-mobile-panel :deep(input), .evidence-mobile-panel :deep(textarea) { font-size: 16px; }
.evidence-mobile-flow { flex: 1; min-height: 0; background: #f8fafc; }.evidence-graph-tools { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
<style>
.mobile-evidence-graph-overlay { top: var(--mobile-viewport-top, 0px); bottom: auto; height: var(--mobile-viewport-height, 100dvh); }
.mobile-evidence-graph .el-drawer__body { display: flex; flex-direction: column; min-height: 0; padding: 12px; overflow: hidden; }
.mobile-evidence-graph .el-drawer__header, .mobile-evidence-graph .el-drawer__footer { flex-shrink: 0; }.mobile-evidence-graph .el-drawer__header { margin-bottom: 0; padding-top: max(16px, env(safe-area-inset-top)); }.mobile-evidence-graph .el-drawer__footer { padding-bottom: max(16px, env(safe-area-inset-bottom)); }.mobile-evidence-graph .el-button, .mobile-evidence-graph .el-drawer__close-btn { min-height: 44px; }.mobile-evidence-graph .vue-flow__controls-button { width: 44px; height: 44px; }
</style>
