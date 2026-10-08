<template>
  <div class="alert-page min-h-screen bg-white">
    <Header />

    <FunctionalPageHeader
      v-if="!isMobile"
      title-prefix="告警"
      title-suffix="中心"
      subtitle="模块统一接入、规则检测与异常生命周期管理"
      highlight-color="red-600"
      class="border-red-100! from-red-50!"
    >
      <template #actions>
        <div class="flex flex-wrap items-center justify-end gap-2.5 text-sm text-slate-600">
          <span class="inline-flex items-center gap-2 rounded-full border border-red-100 bg-white px-3 py-1.5 shadow-sm">
            <span :class="streamDotClass" class="h-2 w-2 rounded-full" />
            页面实时流：{{ streamStatusText }}
          </span>
          <span class="inline-flex items-center gap-2 rounded-full border border-red-100 bg-white px-3 py-1.5 shadow-sm">
            <span :class="workerStatus.online ? 'bg-emerald-400' : 'bg-slate-400'" class="h-2 w-2 rounded-full" />
            检测 Worker：{{ workerStatus.online ? '在线' : '离线' }}
          </span>
          <el-button type="danger" plain :loading="loading" @click="refreshAll">
            <Icon icon="mdi:refresh" class="mr-1" />刷新
          </el-button>
        </div>
      </template>
    </FunctionalPageHeader>

    <section v-else class="mobile-alert-heading">
      <div><p>异常跟进</p><h1>告警中心</h1></div>
      <button type="button" :disabled="loading" aria-label="刷新告警" @click="refreshAll"><Icon icon="mdi:refresh" :class="{ 'animate-spin': loading }" /></button>
      <div class="mobile-alert-connection"><span :class="streamDotClass" />{{ streamStatusText }}<span :class="workerStatus.online ? 'bg-emerald-400' : 'bg-slate-400'" />检测服务{{ workerStatus.online ? '在线' : '离线' }}</div>
    </section>

    <main class="alert-main mx-auto max-w-[1920px] px-4 py-7 sm:px-6 lg:px-8">
      <section class="alert-summary mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="card in summaryCards"
          :key="card.label"
          class="flex items-center gap-4 rounded-xl border border-red-100 bg-white px-5 py-4 shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-colors hover:border-red-200"
        >
          <div :class="card.iconClass" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl">
            <Icon :icon="card.icon" class="text-xl" />
          </div>
          <div>
            <p class="text-sm text-slate-500">{{ card.label }}</p>
            <p class="mt-0.5 text-2xl font-semibold text-red-700">{{ card.value }}</p>
          </div>
        </div>
      </section>

      <section class="rounded-2xl border border-red-100 bg-white shadow-[0_10px_32px_rgba(15,23,42,0.05)]">
        <el-tabs v-model="activeTab" class="alert-tabs px-5 pt-2" @tab-change="handleTabChange">
          <el-tab-pane name="instances">
            <template #label>
              <span class="flex items-center gap-2"><Icon icon="mdi:alert-box-outline" />告警事件</span>
            </template>

            <div v-if="isMobile" class="mobile-alert-search">
              <el-input v-model="instanceFilters.keyword" clearable placeholder="搜索告警或关联资源" aria-label="搜索告警" @keyup.enter="searchInstances" @clear="searchInstances"><template #prefix><Icon icon="mdi:magnify" /></template></el-input>
              <button type="button" aria-label="筛选告警" @click="Object.assign(instanceFilterDraft, instanceFilters); filterPanel = 'instances'"><Icon icon="mdi:filter-variant" /><span>筛选{{ instanceFilterCount ? ` · ${instanceFilterCount}` : '' }}</span></button>
            </div>
            <div v-else class="mb-4 flex flex-wrap items-center gap-3">
              <el-input
                v-model="instanceFilters.keyword"
                clearable
                placeholder="搜索告警、资源名称或资源 ID"
                style="width: 280px"
                @keyup.enter="searchInstances"
                @clear="searchInstances"
              >
                <template #prefix><Icon icon="mdi:magnify" /></template>
              </el-input>
              <el-select v-model="instanceFilters.status" clearable placeholder="全部状态" style="width: 140px" @change="searchInstances">
                <el-option label="告警中" value="firing" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
              </el-select>
              <el-select v-model="instanceFilters.severity" clearable placeholder="全部等级" style="width: 130px" @change="searchInstances">
                <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <el-select v-model="instanceFilters.sourceKey" clearable placeholder="全部模块" style="width: 170px" @change="searchInstances">
                <el-option v-for="source in sources" :key="source.source_key" :label="source.module_name" :value="source.source_key" />
              </el-select>
            </div>

            <div v-if="isMobile" v-loading="instanceLoading" class="mobile-alert-list" aria-live="polite">
              <div v-if="instanceError" class="mobile-alert-load-error" role="status"><p>告警加载失败{{ instances.length ? '，下方保留上次成功加载的结果' : '' }}。</p><el-button :loading="instanceLoading" @click="loadInstances().catch(() => {})">重新加载</el-button></div>
              <article v-for="row in instances" :key="row.id" class="mobile-alert-card" :class="`severity-${row.current_severity}`">
                <div class="mobile-alert-card-tags"><el-tag :type="severityTag(row.current_severity)" :effect="row.current_severity === 'critical' ? 'dark' : 'light'">{{ severityText(row.current_severity) }}</el-tag><el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag><span>{{ sourceName(row.source_key) }}</span></div>
                <button type="button" class="mobile-alert-card-title" @click="openAlertDetail(row)">{{ row.title }}</button>
                <p class="mobile-alert-reason">{{ row.detail || '暂无异常说明' }}</p>
                <button type="button" class="mobile-alert-resource" :disabled="!row.resource_url?.startsWith('/') || row.resource_url.startsWith('//')" @click="openResource(row)"><Icon icon="mdi:link-variant" /><span>{{ row.resource_name || row.resource_id || '未关联资源' }}</span><Icon v-if="row.resource_url" icon="mdi:chevron-right" /></button>
                <dl class="mobile-alert-card-meta"><div><dt>当前值</dt><dd>{{ displayValue(row.latest_value) }}</dd></div><div><dt>更新时间</dt><dd>{{ formatTime(row.updated_at) }}</dd></div></dl>
                <div class="mobile-alert-card-actions"><el-button @click="openAlertDetail(row)">事件详情</el-button><el-button v-if="row.status === 'firing' && canAcknowledge" type="warning" plain :disabled="operationLoading" @click="acknowledgeAlert(row)">确认</el-button><el-button v-if="row.status !== 'resolved' && canResolve" type="success" plain :disabled="operationLoading" @click="openResolveDialog(row)">解决</el-button></div>
              </article>
              <el-empty v-if="!instanceLoading && !instanceError && !instances.length" description="暂无符合条件的告警" :image-size="70" />
            </div>
            <el-table v-else v-loading="instanceLoading" :data="instances" stripe row-key="id" empty-text="暂无符合条件的告警">
              <el-table-column label="告警" min-width="280">
                <template #default="{ row }">
                  <button class="block max-w-full text-left" @click="openAlertDetail(row)">
                    <span class="block truncate font-medium text-slate-900 hover:text-blue-600">{{ row.title }}</span>
                    <span class="mt-1 block truncate text-xs text-slate-500">{{ row.detail }}</span>
                  </button>
                </template>
              </el-table-column>
              <el-table-column label="资源" min-width="200">
                <template #default="{ row }">
                  <button
                    :class="row.resource_url ? 'text-blue-600 hover:underline' : 'text-slate-700'"
                    class="block max-w-full truncate text-left"
                    @click="openResource(row)"
                  >
                    {{ row.resource_name }}
                  </button>
                  <span class="text-xs text-slate-400">{{ sourceName(row.source_key) }} · {{ row.resource_id }}</span>
                </template>
              </el-table-column>
              <el-table-column label="等级" width="90">
                <template #default="{ row }">
                  <el-tag :type="severityTag(row.current_severity)" :effect="row.current_severity === 'critical' ? 'dark' : 'light'">
                    {{ severityText(row.current_severity) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="当前值" width="120">
                <template #default="{ row }"><span class="font-mono text-sm">{{ displayValue(row.latest_value) }}</span></template>
              </el-table-column>
              <el-table-column label="触发时间" width="175">
                <template #default="{ row }"><span class="text-sm text-slate-600">{{ formatTime(row.triggered_at) }}</span></template>
              </el-table-column>
              <el-table-column label="更新时间" width="175">
                <template #default="{ row }"><span class="text-sm text-slate-600">{{ formatTime(row.updated_at) }}</span></template>
              </el-table-column>
              <el-table-column label="操作" fixed="right" width="190">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="openAlertDetail(row)">详情</el-button>
                  <el-button
                    v-if="row.status === 'firing' && canAcknowledge"
                    type="warning"
                    link
                    size="small"
                    @click="acknowledgeAlert(row)"
                  >确认</el-button>
                  <el-button
                    v-if="row.status !== 'resolved' && canResolve"
                    type="success"
                    link
                    size="small"
                    @click="openResolveDialog(row)"
                  >解决</el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="alert-pagination flex justify-end py-5">
              <el-pagination
                v-model:current-page="instancePage.page"
                v-model:page-size="instancePage.pageSize"
                background
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
                :pager-count="isMobile ? 5 : 7"
                :page-sizes="[10, 20, 50, 100]"
                :total="instancePage.total"
                @change="loadInstances"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="rules" lazy>
            <template #label>
              <span class="flex items-center gap-2"><Icon icon="mdi:tune-variant" />规则管理</span>
            </template>

            <div v-if="isMobile" class="mobile-alert-search">
              <el-input v-model="ruleFilters.keyword" clearable placeholder="搜索规则名称" aria-label="搜索告警规则" @keyup.enter="searchRules" @clear="searchRules" />
              <button type="button" aria-label="筛选告警规则" @click="Object.assign(ruleFilterDraft, ruleFilters); filterPanel = 'rules'"><Icon icon="mdi:filter-variant" />筛选</button>
              <el-button v-if="canCreateRule" type="primary" @click="openCreateRule">新建规则</el-button>
            </div>
            <div v-else class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap gap-3">
                <el-input
                  v-model="ruleFilters.keyword"
                  clearable
                  placeholder="搜索规则名称"
                  style="width: 240px"
                  @keyup.enter="searchRules"
                  @clear="searchRules"
                />
                <el-select v-model="ruleFilters.sourceKey" clearable placeholder="全部模块" style="width: 170px" @change="searchRules">
                  <el-option v-for="source in sources" :key="source.source_key" :label="source.module_name" :value="source.source_key" />
                </el-select>
                <el-select v-model="ruleFilters.enabled" clearable placeholder="全部状态" style="width: 130px" @change="searchRules">
                  <el-option label="已启用" :value="true" />
                  <el-option label="已停用" :value="false" />
                </el-select>
              </div>
              <el-button v-if="canCreateRule" type="primary" @click="openCreateRule">
                <Icon icon="mdi:plus" class="mr-1" />新建规则
              </el-button>
            </div>

            <div v-if="isMobile" v-loading="ruleLoading" class="mobile-alert-list">
              <div v-if="ruleError" class="mobile-alert-load-error" role="status"><p>规则加载失败{{ rules.length ? '，下方保留上次成功加载的结果' : '' }}。</p><el-button :loading="ruleLoading" @click="loadRules().catch(() => {})">重新加载</el-button></div>
              <article v-for="row in rules" :key="row.id" class="mobile-alert-card">
                <div class="mobile-alert-card-tags"><el-tag :type="severityTag(row.severity)">{{ severityText(row.severity) }}</el-tag><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag><span>{{ sourceName(row.source_key) }}</span></div>
                <h3 class="mobile-alert-rule-title">{{ row.name }}</h3><p v-if="row.description" class="mobile-alert-reason">{{ row.description }}</p>
                <dl class="mobile-alert-rule-conditions"><div><dt>触发条件</dt><dd>{{ expressionText(row.source_key, row.trigger_expression) }}</dd></div><div><dt>恢复条件</dt><dd>{{ row.recovery_expression ? expressionText(row.source_key, row.recovery_expression) : '不自动恢复' }}</dd></div></dl>
                <p class="mobile-alert-rule-health" :class="{ 'text-red-600': row.last_error }">{{ evaluationText(row) }} · {{ row.last_error ? `检测失败：${row.last_error}` : `最近检测 ${formatTime(row.last_success_at)}` }}</p>
                <div class="mobile-alert-rule-switch"><span>规则状态</span><el-switch :model-value="row.enabled" :disabled="!canUpdateRule" inline-prompt active-text="启用" inactive-text="停用" @change="toggleRule(row, $event)" /></div>
                <div class="mobile-alert-card-actions"><el-button v-if="canUpdateRule" @click="openEditRule(row)">编辑</el-button><el-button v-if="canExecuteRule" type="success" plain @click="testExistingRule(row)">试运行</el-button><el-button v-if="canDeleteRule" type="danger" plain @click="deleteExistingRule(row)">删除</el-button></div>
              </article>
              <el-empty v-if="!ruleLoading && !ruleError && !rules.length" description="暂无告警规则" :image-size="70" />
            </div>
            <el-table v-else v-loading="ruleLoading" :data="rules" stripe row-key="id" empty-text="暂无告警规则">
              <el-table-column prop="name" label="规则名称" min-width="190">
                <template #default="{ row }">
                  <div class="font-medium text-slate-900">{{ row.name }}</div>
                  <div v-if="row.description" class="mt-1 truncate text-xs text-slate-500">{{ row.description }}</div>
                </template>
              </el-table-column>
              <el-table-column label="模块 / 检测项" min-width="180">
                <template #default="{ row }">
                  <span>{{ sourceName(row.source_key) }}</span>
                  <span class="text-slate-400"> / {{ fieldName(row.source_key, row.field_key) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="触发条件" min-width="190">
                <template #default="{ row }">{{ expressionText(row.source_key, row.trigger_expression) }}</template>
              </el-table-column>
              <el-table-column label="恢复条件" min-width="190">
                <template #default="{ row }">{{ row.recovery_expression ? expressionText(row.source_key, row.recovery_expression) : '不自动恢复' }}</template>
              </el-table-column>
              <el-table-column label="等级" width="85">
                <template #default="{ row }"><el-tag :type="severityTag(row.severity)">{{ severityText(row.severity) }}</el-tag></template>
              </el-table-column>
              <el-table-column label="检测方式" width="120">
                <template #default="{ row }">{{ evaluationText(row) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-switch
                    :model-value="row.enabled"
                    :disabled="!canUpdateRule"
                    inline-prompt
                    active-text="启用"
                    inactive-text="停用"
                    @change="toggleRule(row, $event)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="最近检测" width="175">
                <template #default="{ row }">
                  <span :class="row.last_error ? 'text-red-600' : 'text-slate-600'" class="text-sm">
                    {{ row.last_error ? '检测失败' : formatTime(row.last_success_at) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" fixed="right" width="180">
                <template #default="{ row }">
                  <el-button v-if="canUpdateRule" type="primary" link size="small" @click="openEditRule(row)">编辑</el-button>
                  <el-button v-if="canExecuteRule" type="success" link size="small" @click="testExistingRule(row)">试运行</el-button>
                  <el-button v-if="canDeleteRule" type="danger" link size="small" @click="deleteExistingRule(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="alert-pagination flex justify-end py-5">
              <el-pagination
                v-model:current-page="rulePage.page"
                v-model:page-size="rulePage.pageSize"
                background
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
                :pager-count="isMobile ? 5 : 7"
                :page-sizes="[10, 20, 50]"
                :total="rulePage.total"
                @change="loadRules"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="sources" lazy>
            <template #label>
              <span class="flex items-center gap-2"><Icon icon="mdi:connection" />模块接入</span>
            </template>

            <el-alert
              class="mb-5"
              type="info"
              :closable="false"
              title="业务模块通过 Provider 声明可检测字段并发布标准观测；新增模块无需修改规则引擎和告警生命周期。"
            />
            <div class="grid gap-4 lg:grid-cols-2">
              <article v-for="source in sources" :key="source.source_key" class="rounded-xl border border-slate-200 p-5">
                <div class="mb-4 flex items-start justify-between">
                  <div>
                    <h3 class="font-semibold text-slate-900">{{ source.module_name }}</h3>
                    <p class="mt-1 text-sm text-slate-500">{{ source.resource_name }} · {{ source.source_key }}</p>
                  </div>
                  <el-tag type="success">已注册 · v{{ source.schema_version }}</el-tag>
                </div>
                <div class="space-y-3">
                  <div v-for="field in source.fields" :key="field.field_key" class="rounded-lg bg-slate-50 px-4 py-3">
                    <div class="flex items-center justify-between">
                      <span class="font-medium text-slate-800">{{ field.field_name }}</span>
                      <span class="font-mono text-xs text-slate-400">{{ field.value_type }}</span>
                    </div>
                    <p class="mt-2 text-xs text-slate-500">
                      运算符：{{ field.supported_operators.map(operatorText).join('、') }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      检测：{{ field.supported_evaluation_modes.map(modeText).join('、') }}
                    </p>
                  </div>
                </div>
              </article>
            </div>
            <el-empty v-if="!sources.length" description="当前没有已注册的告警模块" />
            <div class="h-5" />
          </el-tab-pane>
        </el-tabs>
      </section>
    </main>

    <MobileSheet :model-value="Boolean(filterPanel)" :title="filterPanel === 'rules' ? '筛选告警规则' : '筛选告警'" @update:model-value="value => { if (!value) filterPanel = '' }">
      <el-form label-position="top">
        <template v-if="filterPanel === 'instances'">
          <el-form-item label="处理状态"><el-select v-model="instanceFilterDraft.status" clearable placeholder="全部状态" class="w-full"><el-option label="告警中" value="firing" /><el-option label="已确认" value="acknowledged" /><el-option label="已解决" value="resolved" /></el-select></el-form-item>
          <el-form-item label="异常等级"><el-select v-model="instanceFilterDraft.severity" clearable placeholder="全部等级" class="w-full"><el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="所属模块"><el-select v-model="instanceFilterDraft.sourceKey" clearable placeholder="全部模块" class="w-full"><el-option v-for="source in sources" :key="source.source_key" :label="source.module_name" :value="source.source_key" /></el-select></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="规则状态"><el-select v-model="ruleFilterDraft.enabled" clearable placeholder="全部状态" class="w-full"><el-option label="已启用" :value="true" /><el-option label="已停用" :value="false" /></el-select></el-form-item>
          <el-form-item label="所属模块"><el-select v-model="ruleFilterDraft.sourceKey" clearable placeholder="全部模块" class="w-full"><el-option v-for="source in sources" :key="source.source_key" :label="source.module_name" :value="source.source_key" /></el-select></el-form-item>
        </template>
      </el-form>
      <template #footer><div class="mobile-alert-filter-actions"><el-button @click="filterPanel === 'instances' ? Object.assign(instanceFilterDraft, { status: '', severity: '', sourceKey: '' }) : Object.assign(ruleFilterDraft, { enabled: '', sourceKey: '' })">重置筛选</el-button><el-button type="primary" @click="filterPanel === 'instances' ? (Object.assign(instanceFilters, instanceFilterDraft), searchInstances()) : (Object.assign(ruleFilters, ruleFilterDraft), searchRules()); filterPanel = ''">查看结果</el-button></div></template>
    </MobileSheet>

    <el-drawer v-model="detailVisible" title="告警详情" :direction="isMobile ? 'btt' : 'rtl'" :size="isMobile ? 'auto' : 'min(680px, 94vw)'" :class="isMobile ? 'mobile-sheet alert-mobile-detail' : ''" :modal-class="isMobile ? 'mobile-sheet-overlay' : ''" :append-to-body="isMobile" destroy-on-close>
      <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" class="mb-4" />
      <div v-if="detailLoading && !selectedAlert?.title" class="py-8 text-center text-slate-500">正在加载告警详情…</div>
      <template v-if="selectedAlert?.title">
        <div class="mb-5 flex flex-wrap items-center gap-2">
          <el-tag :type="severityTag(selectedAlert.current_severity)" effect="dark">{{ severityText(selectedAlert.current_severity) }}</el-tag>
          <el-tag :type="statusTag(selectedAlert.status)">{{ statusText(selectedAlert.status) }}</el-tag>
          <span class="text-sm text-slate-400">版本 {{ selectedAlert.version }}</span>
        </div>
        <h2 class="text-xl font-semibold text-slate-900">{{ selectedAlert.title }}</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">{{ selectedAlert.detail }}</p>
        <button v-if="isMobile && selectedAlert.resource_url?.startsWith('/') && !selectedAlert.resource_url.startsWith('//')" type="button" class="mobile-alert-resource mt-4" @click="openResource(selectedAlert)"><Icon icon="mdi:link-variant" /><span>{{ selectedAlert.resource_name || '查看关联任务或资源' }}</span><Icon icon="mdi:chevron-right" /></button>
        <el-descriptions class="mt-5" :column="1" border>
          <el-descriptions-item label="关联资源">{{ selectedAlert.resource_name }}（{{ selectedAlert.resource_id }}）</el-descriptions-item>
          <el-descriptions-item label="当前值">{{ displayValue(selectedAlert.latest_value) }}</el-descriptions-item>
          <el-descriptions-item label="触发值">{{ displayValue(selectedAlert.trigger_value) }}</el-descriptions-item>
          <el-descriptions-item label="触发时间">{{ formatTime(selectedAlert.triggered_at) }}</el-descriptions-item>
          <el-descriptions-item label="解决时间">{{ formatTime(selectedAlert.resolved_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedAlert.resolution_type" label="解决方式">
            {{ selectedAlert.resolution_type === 'auto' ? '自动恢复' : '手动解决' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedAlert.resolution_note" label="处理说明">{{ selectedAlert.resolution_note }}</el-descriptions-item>
        </el-descriptions>

        <div class="mt-7 flex items-center justify-between">
          <h3 class="font-semibold text-slate-900">事件历史</h3>
          <el-button size="small" :loading="eventLoading" @click="loadAlertEvents(selectedAlert.id)">刷新</el-button>
        </div>
        <el-timeline class="mt-5">
          <el-timeline-item
            v-for="event in alertEvents"
            :key="event.id"
            :timestamp="formatTime(event.created_at)"
            placement="top"
            :type="eventTimelineType(event.event_type)"
          >
            <div class="font-medium text-slate-800">{{ eventText(event) }}</div>
            <div v-if="event.note" class="mt-1 text-sm text-slate-500">{{ event.note }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!eventLoading && !alertEvents.length" description="暂无事件历史" />
      </template>
      <template v-if="isMobile && selectedAlert?.version != null" #footer><div class="mobile-alert-detail-actions"><el-button @click="detailVisible = false">关闭</el-button><el-button v-if="selectedAlert.status === 'firing' && canAcknowledge" type="warning" :loading="operationLoading" :disabled="detailLoading" @click="acknowledgeAlert(selectedAlert)">确认告警</el-button><el-button v-if="selectedAlert.status !== 'resolved' && canResolve" type="success" :disabled="operationLoading || detailLoading" @click="openResolveDialog(selectedAlert)">解决告警</el-button></div></template>
    </el-drawer>

    <el-dialog v-model="resolveVisible" title="手动解决告警" width="min(520px, 92vw)" class="alert-operation-dialog" :append-to-body="isMobile" destroy-on-close>
      <p class="mb-4 text-sm text-slate-600">
        手动解决后，当前异常持续期间不会再次生成告警；资源恢复正常后会重新布防。
      </p>
      <el-form label-position="top">
        <el-form-item :required="resolveNoteRequired" label="处理说明">
          <el-input
            v-model="resolveNote"
            type="textarea"
            :rows="5"
            maxlength="2000"
            show-word-limit
            :placeholder="resolveNoteRequired ? '严重和致命告警必须填写处理说明' : '可选：填写处理过程或结论'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveVisible = false">取消</el-button>
        <el-button type="success" :loading="operationLoading" @click="resolveAlert">确认解决</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ruleVisible"
      :title="editingRule ? '编辑告警规则' : '新建告警规则'"
      width="min(760px, 94vw)"
      class="alert-operation-dialog"
      :append-to-body="isMobile"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <div class="grid gap-x-4 md:grid-cols-2">
          <el-form-item label="规则名称" required>
            <el-input v-model="ruleForm.name" maxlength="200" placeholder="例如：行动执行超时" />
          </el-form-item>
          <el-form-item label="告警等级" required>
            <el-select v-model="ruleForm.severity" class="w-full">
              <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="功能模块" required>
            <el-select v-model="ruleForm.sourceKey" class="w-full" :disabled="Boolean(editingRule)" @change="onRuleSourceChange">
              <el-option v-for="source in sources" :key="source.source_key" :label="`${source.module_name} / ${source.resource_name}`" :value="source.source_key" />
            </el-select>
          </el-form-item>
          <el-form-item label="触发项" required>
            <el-select v-model="ruleForm.fieldKey" class="w-full" :disabled="Boolean(editingRule)" @change="onRuleFieldChange">
              <el-option v-for="field in selectedSourceFields" :key="field.field_key" :label="field.field_name" :value="field.field_key" />
            </el-select>
          </el-form-item>
        </div>

        <div class="rounded-xl border border-red-100 bg-red-50/50 p-4">
          <div class="mb-3 flex items-center gap-2 font-medium text-slate-900"><Icon icon="mdi:alert-circle-outline" class="text-red-500" />触发条件</div>
          <div class="grid gap-3 md:grid-cols-[180px_1fr_120px]">
            <el-select v-model="ruleForm.triggerOperator" @change="normalizeRuleValues">
              <el-option v-for="operator in selectedField?.supported_operators || []" :key="operator" :label="operatorText(operator)" :value="operator" />
            </el-select>
            <el-select
              v-if="selectedField?.value_type === 'enum'"
              v-model="ruleForm.triggerValue"
              :multiple="isMultiOperator(ruleForm.triggerOperator)"
              filterable
              placeholder="选择触发值"
            >
              <el-option v-for="option in selectedField.enum_options" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-select v-else-if="selectedField?.value_type === 'boolean'" v-model="ruleForm.triggerValue">
              <el-option label="是" :value="true" /><el-option label="否" :value="false" />
            </el-select>
            <el-date-picker v-else-if="selectedField?.value_type === 'datetime'" v-model="ruleForm.triggerValue" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full!" />
            <el-input v-else-if="selectedField?.value_type === 'string'" v-model="ruleForm.triggerValue" placeholder="输入触发值" />
            <el-input-number v-else v-model="ruleForm.triggerValue" class="w-full!" :controls="false" />
            <el-select v-if="selectedField?.value_type === 'duration'" v-model="ruleForm.triggerUnit">
              <el-option v-for="unit in durationUnits" :key="unit.value" :label="unit.label" :value="unit.value" />
            </el-select>
            <div v-else class="flex items-center text-sm text-slate-400">{{ selectedField?.unit || valueTypeText(selectedField?.value_type) }}</div>
          </div>
        </div>

        <div class="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/40 p-4">
          <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-2 font-medium text-slate-900"><Icon icon="mdi:check-circle-outline" class="text-emerald-600" />自动恢复条件</div>
            <el-switch v-model="ruleForm.recoveryEnabled" inline-prompt active-text="启用" inactive-text="关闭" />
          </div>
          <div v-if="ruleForm.recoveryEnabled" class="grid gap-3 md:grid-cols-[180px_1fr_120px]">
            <el-select v-model="ruleForm.recoveryOperator" @change="normalizeRuleValues">
              <el-option v-for="operator in selectedField?.supported_operators || []" :key="operator" :label="operatorText(operator)" :value="operator" />
            </el-select>
            <el-select
              v-if="selectedField?.value_type === 'enum'"
              v-model="ruleForm.recoveryValue"
              :multiple="isMultiOperator(ruleForm.recoveryOperator)"
              filterable
              placeholder="选择恢复值"
            >
              <el-option v-for="option in selectedField.enum_options" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-select v-else-if="selectedField?.value_type === 'boolean'" v-model="ruleForm.recoveryValue">
              <el-option label="是" :value="true" /><el-option label="否" :value="false" />
            </el-select>
            <el-date-picker v-else-if="selectedField?.value_type === 'datetime'" v-model="ruleForm.recoveryValue" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full!" />
            <el-input v-else-if="selectedField?.value_type === 'string'" v-model="ruleForm.recoveryValue" placeholder="输入恢复值" />
            <el-input-number v-else v-model="ruleForm.recoveryValue" class="w-full!" :controls="false" />
            <el-select v-if="selectedField?.value_type === 'duration'" v-model="ruleForm.recoveryUnit">
              <el-option v-for="unit in durationUnits" :key="unit.value" :label="unit.label" :value="unit.value" />
            </el-select>
            <div v-else class="flex items-center text-sm text-slate-400">{{ selectedField?.unit || valueTypeText(selectedField?.value_type) }}</div>
          </div>
          <p v-else class="text-sm text-slate-500">该规则不会自动恢复，只能由用户手动解决。</p>
        </div>

        <div class="mt-4 grid gap-x-4 md:grid-cols-2">
          <el-form-item label="检测方式" required>
            <el-select v-model="ruleForm.evaluationMode" class="w-full" @change="onEvaluationModeChange">
              <el-option v-for="mode in selectedField?.supported_evaluation_modes || []" :key="mode" :label="modeText(mode)" :value="mode" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="ruleForm.evaluationMode !== 'realtime'" label="检测周期" required>
            <el-select v-model="ruleForm.intervalSeconds" class="w-full">
              <el-option label="1 分钟" :value="60" />
              <el-option label="5 分钟" :value="300" />
              <el-option label="15 分钟" :value="900" />
              <el-option label="1 小时" :value="3600" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="说明">
          <el-input v-model="ruleForm.description" type="textarea" :rows="2" maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleVisible = false">取消</el-button>
        <el-button v-if="canExecuteRule" :loading="ruleValidating" @click="validateCurrentRule">校验</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { alertApi } from '@/api/alert'
import { openAuthenticatedSse } from '@/utils/agentSseClient'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

defineOptions({ name: 'Alert' })

const router = useRouter()
const route = useRoute()
const { isMobile } = useMobileViewport()
const severityOptions = [
  { label: '一般', value: 'info' },
  { label: '重要', value: 'warning' },
  { label: '严重', value: 'error' },
  { label: '致命', value: 'critical' }
]
const durationUnits = [
  { label: '秒', value: 'seconds' },
  { label: '分钟', value: 'minutes' },
  { label: '小时', value: 'hours' },
  { label: '天', value: 'days' }
]
const operatorLabels = { eq: '当前为', ne: '不等于', lt: '小于', lte: '小于等于', gt: '大于', gte: '大于等于', in: '属于', not_in: '不属于' }
const modeLabels = { realtime: '实时', interval: '周期', hybrid: '实时 + 周期补偿' }
const eventLabels = {
  triggered: '告警已触发',
  acknowledged: '告警已确认',
  severity_changed: '告警等级已变化',
  auto_resolved: '资源恢复正常，告警已自动恢复',
  manual_resolved: '告警已手动解决',
  rule_attached: '新增规则参与当前告警',
  rule_detached: '规则已退出当前告警'
}

const activeTab = ref('instances')
const loading = ref(false)
const instanceLoading = ref(false)
const ruleLoading = ref(false)
const instanceError = ref(false)
const ruleError = ref(false)
const operationLoading = ref(false)
const eventLoading = ref(false)
const ruleSaving = ref(false)
const ruleValidating = ref(false)
const sources = ref([])
const sourceStatus = ref([])
const workerStatus = ref({ online: false })
const stats = ref({
  firing: 0,
  acknowledged: 0,
  resolved_today_auto: 0,
  resolved_today_manual: 0,
  by_severity: {}
})
const instances = ref([])
const rules = ref([])
const instancePage = reactive({ page: 1, pageSize: 20, total: 0 })
const rulePage = reactive({ page: 1, pageSize: 20, total: 0 })
const instanceFilters = reactive({ keyword: '', status: '', severity: '', sourceKey: '' })
const ruleFilters = reactive({ keyword: '', sourceKey: '', enabled: '' })
const filterPanel = ref('')
const instanceFilterDraft = reactive({ ...instanceFilters })
const ruleFilterDraft = reactive({ ...ruleFilters })
const instanceFilterCount = computed(() => [instanceFilters.status, instanceFilters.severity, instanceFilters.sourceKey].filter(Boolean).length)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selectedAlert = ref(null)
const alertEvents = ref([])
const resolveVisible = ref(false)
const resolvingAlert = ref(null)
const resolveNote = ref('')
const ruleVisible = ref(false)
const editingRule = ref(null)
const streamState = ref('offline')
const streamCursor = ref('')
let streamController = null
let streamTask = null
let reconnectAttempt = 0
let initialized = false
let refreshTimer = null
let detailSequence = 0
let eventSequence = 0
let instancesInitialized = false
let rulesInitialized = false

const canAcknowledge = computed(() => hasPerm(PERM.operations.alert.instance.acknowledge))
const canResolve = computed(() => hasPerm(PERM.operations.alert.instance.resolve))
const canCreateRule = computed(() => hasPerm(PERM.operations.alert.rule.create))
const canUpdateRule = computed(() => hasPerm(PERM.operations.alert.rule.update))
const canDeleteRule = computed(() => hasPerm(PERM.operations.alert.rule.delete))
const canExecuteRule = computed(() => hasPerm(PERM.operations.alert.rule.execute))

const summaryCards = computed(() => [
  { label: '正在告警', value: stats.value.firing || 0, icon: 'mdi:alert', iconClass: 'bg-red-50 text-red-600' },
  { label: '已确认', value: stats.value.acknowledged || 0, icon: 'mdi:check-decagram-outline', iconClass: 'bg-amber-50 text-amber-600' },
  {
    label: '今日已解决',
    value: (stats.value.resolved_today_auto || 0) + (stats.value.resolved_today_manual || 0),
    icon: 'mdi:check-circle-outline',
    iconClass: 'bg-emerald-50 text-emerald-600'
  },
  { label: '致命告警', value: stats.value.by_severity?.critical || 0, icon: 'mdi:alert-octagon-outline', iconClass: 'bg-fuchsia-50 text-fuchsia-700' }
])
const streamStatusText = computed(() => ({ online: '已连接', reconnecting: '重连中', offline: '未连接' }[streamState.value]))
const streamDotClass = computed(() => ({ online: 'bg-emerald-400', reconnecting: 'bg-amber-400 animate-pulse', offline: 'bg-slate-400' }[streamState.value]))
const resolveNoteRequired = computed(() => ['error', 'critical'].includes(resolvingAlert.value?.current_severity))
const selectedSource = computed(() => sources.value.find(item => item.source_key === ruleForm.sourceKey))
const selectedSourceFields = computed(() => selectedSource.value?.fields || [])
const selectedField = computed(() => selectedSourceFields.value.find(item => item.field_key === ruleForm.fieldKey))

const ruleForm = reactive(defaultRuleForm())

function defaultRuleForm() {
  return {
    name: '',
    description: '',
    sourceKey: '',
    fieldKey: '',
    severity: 'warning',
    triggerOperator: 'eq',
    triggerValue: '',
    triggerUnit: 'days',
    recoveryEnabled: false,
    recoveryOperator: 'eq',
    recoveryValue: '',
    recoveryUnit: 'days',
    evaluationMode: 'realtime',
    intervalSeconds: 300
  }
}

function pagePayload(response) {
  return response?.data || response || { items: [], total: 0 }
}

function severityText(value) {
  return severityOptions.find(item => item.value === value)?.label || value || '-'
}

function severityTag(value) {
  return { critical: 'danger', error: 'danger', warning: 'warning', info: 'primary' }[value] || 'info'
}

function statusText(value) {
  return { firing: '告警中', acknowledged: '已确认', resolved: '已解决' }[value] || value || '-'
}

function statusTag(value) {
  return { firing: 'danger', acknowledged: 'warning', resolved: 'success' }[value] || 'info'
}

function operatorText(value) {
  return operatorLabels[value] || value
}

function modeText(value) {
  return modeLabels[value] || value
}

function valueTypeText(value) {
  return { enum: '枚举', string: '文本', number: '数值', percentage: '百分比', duration: '时长', datetime: '时间', boolean: '布尔值' }[value] || ''
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Array.isArray(value) ? value.join('、') : String(value)
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date).replaceAll('/', '-')
}

function sourceName(sourceKey) {
  return sources.value.find(item => item.source_key === sourceKey)?.module_name || sourceKey
}

function fieldDescriptor(sourceKey, fieldKey) {
  return sources.value.find(item => item.source_key === sourceKey)?.fields?.find(item => item.field_key === fieldKey)
}

function fieldName(sourceKey, fieldKey) {
  return fieldDescriptor(sourceKey, fieldKey)?.field_name || fieldKey
}

function thresholdText(sourceKey, condition) {
  const field = fieldDescriptor(sourceKey, condition?.field_key)
  const raw = condition?.value?.value
  let text = displayValue(raw)
  if (field?.value_type === 'enum') {
    const values = Array.isArray(raw) ? raw : [raw]
    text = values.map(value => field.enum_options.find(item => item.value === value)?.label || value).join('、')
  }
  const unit = condition?.value?.unit
  const unitText = durationUnits.find(item => item.value === unit)?.label || unit || ''
  return `${text}${unitText ? ` ${unitText}` : ''}`
}

function expressionText(sourceKey, expression) {
  const condition = expression?.conditions?.[0]
  if (!condition) return '-'
  return `${fieldName(sourceKey, condition.field_key)} ${operatorText(condition.operator)} ${thresholdText(sourceKey, condition)}`
}

function evaluationText(rule) {
  if (rule.evaluation_mode === 'realtime') return '实时'
  const seconds = rule.interval_seconds || 0
  const interval = seconds >= 3600 ? `${seconds / 3600} 小时` : `${seconds / 60} 分钟`
  return rule.evaluation_mode === 'hybrid' ? `实时 + ${interval}` : interval
}

function isMultiOperator(operator) {
  return ['in', 'not_in'].includes(operator)
}

async function loadStats() {
  const response = await alertApi.getStats()
  stats.value = response.data
  if (!streamCursor.value && response.data?.stream_cursor) streamCursor.value = response.data.stream_cursor
}

async function loadSources() {
  const [sourceResponse, statusResponse] = await Promise.all([
    alertApi.getSources(),
    alertApi.getSourcesStatus()
  ])
  sources.value = sourceResponse.data || []
  sourceStatus.value = statusResponse.data?.sources || []
  workerStatus.value = statusResponse.data?.worker || { online: false }
}

async function loadInstances() {
  instanceLoading.value = true
  instanceError.value = false
  try {
    const response = await alertApi.getInstances({
      page: instancePage.page,
      page_size: instancePage.pageSize,
      keyword: instanceFilters.keyword || undefined,
      status: instanceFilters.status || undefined,
      severity: instanceFilters.severity || undefined,
      source_key: instanceFilters.sourceKey || undefined
    })
    const data = pagePayload(response)
    instances.value = data.items || []
    instancePage.total = data.total || 0
    instancesInitialized = true
    instanceError.value = false
  } catch (error) {
    instanceError.value = true
    throw error
  } finally {
    instanceLoading.value = false
  }
}

async function loadRules() {
  ruleLoading.value = true
  ruleError.value = false
  try {
    const response = await alertApi.getRules({
      page: rulePage.page,
      page_size: rulePage.pageSize,
      keyword: ruleFilters.keyword || undefined,
      source_key: ruleFilters.sourceKey || undefined,
      enabled: ruleFilters.enabled === '' ? undefined : ruleFilters.enabled
    })
    const data = pagePayload(response)
    rules.value = data.items || []
    rulePage.total = data.total || 0
    rulesInitialized = true
    ruleError.value = false
  } catch (error) {
    ruleError.value = true
    throw error
  } finally {
    ruleLoading.value = false
  }
}

async function refreshAll() {
  loading.value = true
  try {
    // 先记录事件流游标，再读取快照，连接后允许重复刷新但不能漏过并发事件。
    await loadStats()
    await Promise.all([loadSources(), loadInstances(), loadRules()])
  } catch (error) {
    if (!instancesInitialized) instanceError.value = true
    if (!rulesInitialized) ruleError.value = true
    ElMessage.error(error?.message || '告警中心加载失败')
  } finally {
    loading.value = false
  }
}

function searchInstances() {
  instancePage.page = 1
  loadInstances()
}

function searchRules() {
  rulePage.page = 1
  loadRules()
}

function handleTabChange(name) {
  if (name === 'rules') loadRules()
  if (name === 'sources') loadSources()
}

function openResource(row) {
  if (row.resource_url?.startsWith('/') && !row.resource_url.startsWith('//')) router.push(row.resource_url)
}

async function openAlertDetail(row) {
  if (!hasPerm(PERM.operations.alert.instance.read)) {
    ElMessage.warning('无权限查看告警详情')
    return
  }
  const sequence = ++detailSequence
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  selectedAlert.value = row
  alertEvents.value = []
  try {
    const [detailResponse] = await Promise.all([
      alertApi.getInstance(row.id),
      loadAlertEvents(row.id)
    ])
    if (sequence === detailSequence && detailVisible.value) selectedAlert.value = detailResponse.data
  } catch (error) {
    if (sequence !== detailSequence || !detailVisible.value) return
    detailError.value = error?.message || '告警详情加载失败'
    ElMessage.error(error?.message || '告警详情加载失败')
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}

async function loadAlertEvents(alertId) {
  const sequence = ++eventSequence
  eventLoading.value = true
  try {
    const response = await alertApi.getEvents(alertId, { page: 1, page_size: 100 })
    if (sequence === eventSequence && selectedAlert.value?.id === alertId) alertEvents.value = pagePayload(response).items || []
  } finally {
    if (sequence === eventSequence) eventLoading.value = false
  }
}

async function acknowledgeAlert(row) {
  if (operationLoading.value || !canAcknowledge.value || row.status !== 'firing') return
  operationLoading.value = true
  try {
    const response = await alertApi.acknowledge(row.id, row.version)
    replaceInstance(response.data)
    if (selectedAlert.value?.id === row.id) selectedAlert.value = response.data
    ElMessage.success('告警已确认')
    await loadStats()
    if (detailVisible.value && selectedAlert.value?.id === row.id) await loadAlertEvents(row.id)
  } catch (error) {
    if (error?.code === 240903) {
      await loadInstances()
      if (detailVisible.value && selectedAlert.value?.id === row.id) await openAlertDetail(row)
    }
  } finally {
    operationLoading.value = false
  }
}

function openResolveDialog(row) {
  if (operationLoading.value || !canResolve.value || row.status === 'resolved') return
  resolvingAlert.value = row
  resolveNote.value = ''
  resolveVisible.value = true
}

async function resolveAlert() {
  if (operationLoading.value || !canResolve.value || !resolvingAlert.value) return
  if (resolveNoteRequired.value && !resolveNote.value.trim()) {
    ElMessage.warning('严重和致命告警必须填写处理说明')
    return
  }
  operationLoading.value = true
  try {
    const response = await alertApi.resolve(
      resolvingAlert.value.id,
      resolvingAlert.value.version,
      resolveNote.value.trim() || null
    )
    replaceInstance(response.data)
    if (selectedAlert.value?.id === response.data.id) selectedAlert.value = response.data
    resolveVisible.value = false
    ElMessage.success('告警已手动解决')
    await loadStats()
    if (detailVisible.value && selectedAlert.value?.id === response.data.id) await loadAlertEvents(response.data.id)
  } catch (error) {
    if (error?.code === 240903) {
      const response = await alertApi.getInstance(resolvingAlert.value.id)
      resolvingAlert.value = response.data
      replaceInstance(response.data)
      if (selectedAlert.value?.id === response.data.id) selectedAlert.value = response.data
      if (response.data.status === 'resolved') resolveVisible.value = false
    }
  } finally {
    operationLoading.value = false
  }
}

function replaceInstance(alert) {
  const index = instances.value.findIndex(item => item.id === alert.id)
  if (index >= 0) instances.value.splice(index, 1, alert)
}

function eventTimelineType(type) {
  return { triggered: 'danger', acknowledged: 'warning', severity_changed: 'primary', auto_resolved: 'success', manual_resolved: 'success' }[type] || 'info'
}

function eventText(event) {
  if (event.event_type === 'severity_changed') return `告警等级由 ${severityText(event.from_severity)} 调整为 ${severityText(event.to_severity)}`
  return eventLabels[event.event_type] || event.event_type
}

function resetRuleForm() {
  Object.assign(ruleForm, defaultRuleForm())
  const source = sources.value[0]
  if (source) {
    ruleForm.sourceKey = source.source_key
    ruleForm.fieldKey = source.fields?.[0]?.field_key || ''
    onRuleFieldChange()
  }
}

function openCreateRule() {
  editingRule.value = null
  resetRuleForm()
  ruleVisible.value = true
}

function openEditRule(rule) {
  editingRule.value = rule
  const trigger = rule.trigger_expression.conditions[0]
  const recovery = rule.recovery_expression?.conditions?.[0]
  Object.assign(ruleForm, {
    name: rule.name,
    description: rule.description || '',
    sourceKey: rule.source_key,
    fieldKey: rule.field_key,
    severity: rule.severity,
    triggerOperator: trigger.operator,
    triggerValue: trigger.value.value,
    triggerUnit: trigger.value.unit || 'days',
    recoveryEnabled: Boolean(recovery),
    recoveryOperator: recovery?.operator || trigger.operator,
    recoveryValue: recovery?.value?.value ?? '',
    recoveryUnit: recovery?.value?.unit || trigger.value.unit || 'days',
    evaluationMode: rule.evaluation_mode,
    intervalSeconds: rule.interval_seconds || 300
  })
  ruleVisible.value = true
}

function onRuleSourceChange() {
  ruleForm.fieldKey = selectedSourceFields.value[0]?.field_key || ''
  onRuleFieldChange()
}

function onRuleFieldChange() {
  const field = selectedField.value
  if (!field) return
  ruleForm.triggerOperator = field.supported_operators[0]
  ruleForm.recoveryOperator = field.supported_operators[0]
  ruleForm.evaluationMode = field.supported_evaluation_modes[0]
  ruleForm.intervalSeconds = Math.max(field.default_interval_seconds || 300, 60)
  ruleForm.triggerValue = field.value_type === 'enum' ? field.enum_options[0]?.value || '' : field.value_type === 'boolean' ? true : null
  ruleForm.recoveryValue = field.value_type === 'enum' ? field.enum_options[0]?.value || '' : field.value_type === 'boolean' ? false : null
}

function onEvaluationModeChange(mode) {
  if (mode !== 'realtime' && !ruleForm.intervalSeconds) ruleForm.intervalSeconds = 300
}

function normalizeRuleValues() {
  if (selectedField.value?.value_type !== 'enum') return
  for (const prefix of ['trigger', 'recovery']) {
    const operatorKey = `${prefix}Operator`
    const valueKey = `${prefix}Value`
    if (isMultiOperator(ruleForm[operatorKey]) && !Array.isArray(ruleForm[valueKey])) {
      ruleForm[valueKey] = ruleForm[valueKey] === '' ? [] : [ruleForm[valueKey]]
    } else if (!isMultiOperator(ruleForm[operatorKey]) && Array.isArray(ruleForm[valueKey])) {
      ruleForm[valueKey] = ruleForm[valueKey][0] || ''
    }
  }
}

function threshold(value, unit) {
  return {
    value,
    unit: selectedField.value?.value_type === 'duration' ? unit : null
  }
}

function expression(operator, value, unit) {
  return {
    logic: 'all',
    conditions: [{
      field_key: ruleForm.fieldKey,
      operator,
      value: threshold(value, unit)
    }]
  }
}

function createRulePayload() {
  return {
    name: ruleForm.name.trim(),
    description: ruleForm.description.trim(),
    source_key: ruleForm.sourceKey,
    field_key: ruleForm.fieldKey,
    resource_scope: { type: 'all' },
    trigger_expression: expression(ruleForm.triggerOperator, ruleForm.triggerValue, ruleForm.triggerUnit),
    recovery_expression: ruleForm.recoveryEnabled
      ? expression(ruleForm.recoveryOperator, ruleForm.recoveryValue, ruleForm.recoveryUnit)
      : null,
    severity: ruleForm.severity,
    evaluation_mode: ruleForm.evaluationMode,
    interval_seconds: ruleForm.evaluationMode === 'realtime' ? null : ruleForm.intervalSeconds,
    initial_evaluation_policy: selectedField.value?.initial_evaluation_policy,
    trigger_consecutive_count: 1,
    recovery_consecutive_count: 1,
    enabled: true
  }
}

function validateRuleForm() {
  if (!ruleForm.name.trim()) return '请填写规则名称'
  if (!selectedField.value) return '请选择功能模块和触发项'
  const values = [ruleForm.triggerValue]
  if (ruleForm.recoveryEnabled) values.push(ruleForm.recoveryValue)
  if (values.some(value => value === '' || value === null || value === undefined || (Array.isArray(value) && !value.length))) return '请填写完整的条件值'
  if (ruleForm.evaluationMode !== 'realtime' && !ruleForm.intervalSeconds) return '请选择检测周期'
  return ''
}

async function validateCurrentRule() {
  const message = validateRuleForm()
  if (message) {
    ElMessage.warning(message)
    return false
  }
  ruleValidating.value = true
  try {
    await alertApi.validateRule(createRulePayload())
    ElMessage.success('规则校验通过')
    return true
  } finally {
    ruleValidating.value = false
  }
}

async function saveRule() {
  const message = validateRuleForm()
  if (message) {
    ElMessage.warning(message)
    return
  }
  ruleSaving.value = true
  try {
    const createPayload = createRulePayload()
    await alertApi.validateRule(createPayload)
    if (editingRule.value) {
      await alertApi.updateRule(editingRule.value.id, {
        name: createPayload.name,
        description: createPayload.description,
        trigger_expression: createPayload.trigger_expression,
        recovery_expression: createPayload.recovery_expression,
        clear_recovery_expression: !createPayload.recovery_expression,
        severity: createPayload.severity,
        evaluation_mode: createPayload.evaluation_mode,
        interval_seconds: createPayload.interval_seconds,
        initial_evaluation_policy: createPayload.initial_evaluation_policy,
        trigger_consecutive_count: 1,
        recovery_consecutive_count: 1,
        expected_version: editingRule.value.version
      })
      ElMessage.success('告警规则已更新')
    } else {
      await alertApi.createRule(createPayload)
      ElMessage.success('告警规则已创建')
    }
    ruleVisible.value = false
    await loadRules()
  } finally {
    ruleSaving.value = false
  }
}

async function toggleRule(rule, enabled) {
  try {
    const response = await alertApi.setRuleEnabled(rule.id, {
      enabled,
      expected_version: rule.version
    })
    const index = rules.value.findIndex(item => item.id === rule.id)
    if (index >= 0) rules.value.splice(index, 1, response.data)
    ElMessage.success(enabled ? '规则已启用' : '规则已停用')
  } catch {
    await loadRules()
  }
}

async function testExistingRule(rule) {
  const response = await alertApi.testRule(rule.id)
  await ElMessageBox.alert(
    `已扫描 ${response.data.scanned} 个资源，当前命中 ${response.data.matched} 个${response.data.truncated ? '（结果已截断）' : ''}。`,
    '试运行结果',
    { confirmButtonText: '知道了' }
  )
}

async function deleteExistingRule(rule) {
  await ElMessageBox.confirm(
    `确认删除规则“${rule.name}”？历史告警和事件不会删除。`,
    '删除告警规则',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await alertApi.deleteRule(rule.id, rule.version)
  ElMessage.success('规则已删除')
  await loadRules()
}

function scheduleRealtimeRefresh(type) {
  if (refreshTimer) clearTimeout(refreshTimer)
  refreshTimer = setTimeout(async () => {
    refreshTimer = null
    try {
      if (type.startsWith('rule.')) await loadRules()
      if (type.startsWith('alert.') && activeTab.value === 'instances') await loadInstances()
      await loadStats()
    } catch {
      // SSE 会继续重试，REST 刷新失败由下一条事件或手动刷新补偿。
    }
  }, 120)
}

function stopStream() {
  streamController?.abort()
  streamController = null
  streamTask = null
  streamState.value = 'offline'
}

function startStream() {
  if (streamTask || !hasPerm(PERM.operations.alert.instance.read)) return
  streamController = new AbortController()
  const signal = streamController.signal
  streamTask = (async () => {
    while (!signal.aborted) {
      streamState.value = reconnectAttempt ? 'reconnecting' : 'offline'
      try {
        await openAuthenticatedSse(alertApi.streamUrl(streamCursor.value), {
          signal,
          onOpen: () => {
            streamState.value = 'online'
            reconnectAttempt = 0
          },
          onEvent: event => {
            if (event.lastEventId) streamCursor.value = event.lastEventId
            if (event.type === 'stream.error') {
              streamState.value = 'reconnecting'
              return
            }
            try { JSON.parse(event.data) } catch { return }
            if (event.type === 'stream.reset') {
              void refreshAll()
              return
            }
            scheduleRealtimeRefresh(event.type)
          }
        })
      } catch (error) {
        if (signal.aborted || error?.name === 'AbortError') break
      }
      if (signal.aborted) break
      streamState.value = 'reconnecting'
      reconnectAttempt += 1
      await new Promise(resolve => setTimeout(resolve, Math.min(1000 * 2 ** Math.min(reconnectAttempt, 5), 30000)))
    }
  })().finally(() => {
    streamTask = null
  })
}

watch([() => route.name, () => route.query.alert_id], ([name, alertId], previous = []) => {
  if (name !== 'alert') return
  if (typeof alertId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(alertId)) {
    if (previous[1]) detailVisible.value = false
    return
  }
  activeTab.value = 'instances'
  openAlertDetail({ id: alertId })
}, { immediate: true })

watch(detailVisible, visible => {
  if (visible) return
  ++detailSequence
  ++eventSequence
  detailLoading.value = false
  eventLoading.value = false
  if (route.name === 'alert' && route.query.alert_id) {
    const query = { ...route.query }
    delete query.alert_id
    router.replace({ query })
  }
})

watch(isMobile, () => { filterPanel.value = '' })

onMounted(async () => {
  await refreshAll()
  initialized = true
  startStream()
})
onActivated(() => {
  if (initialized) startStream()
})
onDeactivated(() => {
  stopStream()
  filterPanel.value = ''
  detailVisible.value = false
  resolveVisible.value = false
  ruleVisible.value = false
})
onUnmounted(() => {
  stopStream()
  if (refreshTimer) clearTimeout(refreshTimer)
})
</script>

<style scoped>
.mobile-alert-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 20px 16px 8px; }
.mobile-alert-heading p { margin: 0 0 4px; font-size: 12px; color: #64748b; }
.mobile-alert-heading h1 { margin: 0; color: #0f172a; font-size: 26px; font-weight: 700; }
.mobile-alert-heading > button { display: grid; place-items: center; width: 44px; height: 44px; border: 1px solid #fecaca; border-radius: 12px; color: #dc2626; font-size: 22px; }
.mobile-alert-connection { display: flex; align-items: center; gap: 6px; width: 100%; font-size: 12px; color: #64748b; }
.mobile-alert-connection > span { width: 6px; height: 6px; border-radius: 50%; }
.mobile-alert-connection > span:nth-child(2) { margin-left: 10px; }
.mobile-alert-search { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.mobile-alert-search > .el-input { min-width: 0; flex: 1; }
.mobile-alert-search > button { display: inline-flex; flex-shrink: 0; align-items: center; justify-content: center; gap: 4px; min-height: 44px; padding: 0 10px; border: 1px solid #e2e8f0; border-radius: 8px; color: #475569; font-size: 13px; }
.mobile-alert-list { min-height: 120px; }
.mobile-alert-load-error { margin-bottom: 12px; padding: 14px; border: 1px solid #fed7aa; border-radius: 10px; background: #fff7ed; color: #9a3412; font-size: 13px; }
.mobile-alert-load-error p { margin: 0 0 10px; line-height: 1.7; }
.mobile-alert-load-error .el-button { min-height: 44px; }
.mobile-alert-card { margin-bottom: 12px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; overflow-wrap: anywhere; }
.mobile-alert-card.severity-critical, .mobile-alert-card.severity-error { border-left: 3px solid #dc2626; }
.mobile-alert-card.severity-warning { border-left: 3px solid #d97706; }
.mobile-alert-card-tags { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.mobile-alert-card-tags > span:last-child:not(.el-tag) { margin-left: auto; color: #64748b; font-size: 12px; }
.mobile-alert-card-title { display: block; width: 100%; min-height: 44px; padding: 10px 0 6px; text-align: left; font-size: 16px; font-weight: 600; color: #0f172a; }
.mobile-alert-rule-title { margin: 12px 0 6px; color: #0f172a; font-size: 16px; font-weight: 600; }
.mobile-alert-reason { margin: 2px 0 10px; font-size: 13px; line-height: 1.7; color: #475569; }
.mobile-alert-resource { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 44px; padding: 8px 10px; border-radius: 8px; background: #f8fafc; color: #2563eb; text-align: left; font-size: 13px; }
.mobile-alert-resource > span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.mobile-alert-resource > svg { flex-shrink: 0; }
.mobile-alert-resource:disabled { color: #64748b; }
.mobile-alert-card-meta { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.8fr); gap: 12px; margin: 12px 0; font-size: 12px; }
.mobile-alert-card-meta dt, .mobile-alert-rule-conditions dt { color: #64748b; }
.mobile-alert-card-meta dd { margin: 4px 0 0; color: #334155; }
.mobile-alert-card-actions, .mobile-alert-filter-actions, .mobile-alert-detail-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.mobile-alert-card-actions .el-button, .mobile-alert-filter-actions .el-button, .mobile-alert-detail-actions .el-button { min-width: 0; min-height: 44px; flex: 1; margin-left: 0; padding: 10px 8px; }
.mobile-alert-rule-conditions { display: grid; gap: 8px; margin: 12px 0; font-size: 13px; }
.mobile-alert-rule-conditions > div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; }
.mobile-alert-rule-conditions dd { margin: 0; color: #334155; }
.mobile-alert-rule-health { font-size: 12px; color: #64748b; line-height: 1.6; }
.mobile-alert-rule-switch { display: flex; align-items: center; justify-content: space-between; min-height: 44px; margin: 8px 0; font-size: 13px; color: #475569; }
@media (max-width: 767px) {
  .alert-main { padding-top: 12px; }
  .alert-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
  .alert-summary > div { padding: 12px; gap: 8px; }
  .alert-summary > div > div:first-child { width: 32px; height: 32px; border-radius: 8px; }
  .alert-summary p:first-child { font-size: 12px; }
  .alert-summary p:last-child { font-size: 22px; }
  .alert-tabs { padding-left: 12px; padding-right: 12px; }
  .alert-pagination { justify-content: center; }
  .alert-tabs :deep(.el-tabs__item) { padding: 0 10px; font-size: 13px; }
  .alert-tabs :deep(.el-pagination) { max-width: 100%; }
  .alert-tabs :deep(.el-tabs__content) { overflow-wrap: anywhere; }
  .alert-tabs :deep(.el-input__wrapper), .alert-tabs :deep(.el-select__wrapper) { min-height: 44px; }
  .alert-tabs :deep(.el-switch) { min-height: 44px; }
}

.alert-page {
  --el-color-primary: #dc2626;
  --el-color-primary-light-3: #ef4444;
  --el-color-primary-light-5: #f87171;
  --el-color-primary-light-7: #fecaca;
  --el-color-primary-light-8: #fee2e2;
  --el-color-primary-light-9: #fef2f2;
  --el-color-primary-dark-2: #b91c1c;
}

:deep(.alert-tabs > .el-tabs__header) {
  margin-bottom: 20px;
}

:deep(.alert-tabs > .el-tabs__content) {
  overflow: visible;
}

:deep(.alert-tabs > .el-tabs__header .el-tabs__item) {
  color: #64748b;
  font-weight: 500;
}

:deep(.alert-tabs > .el-tabs__header .el-tabs__item.is-active),
:deep(.alert-tabs > .el-tabs__header .el-tabs__item:hover) {
  color: #dc2626;
}

:deep(.alert-tabs > .el-tabs__header .el-tabs__active-bar) {
  background-color: #dc2626;
}

:deep(.alert-tabs .el-table__header-wrapper th.el-table__cell) {
  background-color: #fff7f7;
  color: #475569;
  font-weight: 600;
}

:deep(.alert-tabs .el-table__row:hover > td.el-table__cell) {
  background-color: #fff8f8;
}

:deep(.alert-tabs .el-pagination.is-background .el-pager li.is-active) {
  background-color: #dc2626;
}
</style>

<style>
@media (max-width: 767px) {
  .alert-mobile-detail .el-drawer__body { overflow-wrap: anywhere; }
  .alert-mobile-detail .el-descriptions__table { table-layout: fixed; }
  .alert-mobile-detail .el-descriptions__label { width: 85px; }
  .alert-mobile-detail .el-descriptions__content { overflow-wrap: anywhere; }
  .alert-mobile-detail .el-timeline { padding-left: 4px; }
  .alert-operation-dialog .el-dialog__footer { display: flex; flex-wrap: wrap; gap: 8px; }
  .alert-operation-dialog .el-dialog__footer .el-button { flex: 1; min-height: 44px; margin-left: 0; }
}
</style>
