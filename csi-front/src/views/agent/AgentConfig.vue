<template>
  <ConfigCenterLayout
    title-prefix="分析引擎"
    title-suffix="配置"
    subtitle="管理分析选项、模型资源、提示词模板与工具等配置"
    sidebar-title="配置类型"
    :nav-items="engineTabs"
    v-model="activeTab"
    :get-badge="getResourceCount"
  >
    <template #actions>
      <div class="flex items-center gap-3">
        <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
          <Icon icon="mdi:format-list-checks" class="text-blue-600 text-xl" />
          <div>
            <p class="text-xs text-gray-500">分析引擎</p>
            <p class="text-lg font-bold text-gray-900">{{ statistics.analysisOptions }}</p>
          </div>
        </div>
        <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
          <Icon icon="mdi:server" class="text-green-600 text-xl" />
          <div>
            <p class="text-xs text-gray-500">模型资源</p>
            <p class="text-lg font-bold text-gray-900">{{ statistics.modelResources }}</p>
          </div>
        </div>
      </div>
    </template>
    <template #toolbar>
      <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
          <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <el-input
            v-if="activeTab !== 'tools'"
            v-model="searchKeyword"
            :placeholder="'搜索' + currentTabLabel + '...'"
            clearable
            class="w-64"
            @keyup.enter="handleCurrentTabSearch"
          >
            <template #prefix>
              <Icon icon="mdi:magnify" class="text-gray-400" />
            </template>
          </el-input>
          <el-button
            v-if="activeTab !== 'tools'"
            type="default"
            @click="handleCurrentTabSearch"
          >
            <template #icon><Icon icon="mdi:magnify" /></template>
            搜索
          </el-button>
          <el-button v-if="activeTab === 'skills'" type="primary" @click="openSkillUploadDialog">
            <template #icon>
              <Icon icon="mdi:upload" />
            </template>
            上传技能
          </el-button>
          <el-button v-else-if="activeTab !== 'tools'" type="primary" @click="handleAdd">
            <template #icon>
              <Icon icon="mdi:plus" />
            </template>
            新增{{ currentTabLabel }}
          </el-button>
        </div>
      </div>
    </template>
          <div v-if="activeTab === 'analysisEngines'" class="space-y-4">
            <div v-loading="agentListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in agentList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-blue-100">
                      <Icon icon="mdi:brain" class="text-2xl text-blue-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div v-if="item.llm_provider" class="flex items-center gap-2">
                          <Icon icon="mdi:api" class="text-cyan-500" />
                          <span class="text-gray-600">LLM 提供商:</span>
                          <span class="text-gray-700">{{ formatLlmProviderLabel(item.llm_provider) }}</span>
                        </div>
                        <div v-if="item.llm_config && Object.keys(item.llm_config).length" class="flex items-center gap-2">
                          <Icon icon="mdi:cog" class="text-orange-500" />
                          <span class="text-gray-600">LLM 配置:</span>
                          <span class="text-gray-700">{{ Object.keys(item.llm_config).length }} 项</span>
                        </div>
                        <div v-if="item.tools?.length" class="flex items-center gap-2">
                          <Icon icon="mdi:tools" class="text-purple-500" />
                          <span class="text-gray-600">工具:</span>
                          <span class="text-gray-700">{{ item.tools.join(', ') }}</span>
                        </div>
                        <div v-if="item.skills?.length" class="flex items-center gap-2">
                          <Icon icon="mdi:puzzle-outline" class="text-violet-500" />
                          <span class="text-gray-600">技能:</span>
                          <span class="text-gray-700">{{ item.skills.length }} 项</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openAgentDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openAgentEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteAgent(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!agentListLoading && agentList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!agentListLoading && agentList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="agentPagination.page"
                v-model:page-size="agentPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="agentPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleAgentPageChange"
                @size-change="handleAgentPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'modelResources'" class="space-y-4">
            <div v-loading="modelListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in modelList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-green-100">
                      <Icon icon="mdi:server" class="text-2xl text-green-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                        <el-tag size="small" class="border-0" type="success">已配置</el-tag>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:link-variant" class="text-blue-500" />
                          <span class="text-gray-600">API 地址:</span>
                          <span class="font-mono text-xs text-gray-900">{{ item.base_url }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:key" class="text-purple-500" />
                          <span class="text-gray-600">API Key:</span>
                          <span class="font-mono text-xs text-gray-900">{{ maskApiKey(item.api_key) }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:brain" class="text-orange-500" />
                          <span class="text-gray-600">模型:</span>
                          <span class="font-medium text-gray-900">{{ item.model }}</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openModelDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openModelEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteModel(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!modelListLoading && modelList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!modelListLoading && modelList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="modelPagination.page"
                v-model:page-size="modelPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="modelPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleModelPageChange"
                @size-change="handleModelPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'promptTemplates'" class="space-y-4">
            <div v-loading="promptTemplateListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in promptTemplateList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-amber-100">
                      <Icon icon="mdi:file-document-edit" class="text-2xl text-amber-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p class="text-sm text-gray-600 mb-3 line-clamp-2">{{ getPromptTemplatePreview(item) }}</p>
                      <div class="flex items-center gap-2 text-sm text-gray-500">
                        <Icon icon="mdi:clock-outline" />
                        <span>更新于 {{ formatModelDate(item.updated_at) }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openPromptTemplateDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openPromptTemplateEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeletePromptTemplate(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!promptTemplateListLoading && promptTemplateList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!promptTemplateListLoading && promptTemplateList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="promptTemplatePagination.page"
                v-model:page-size="promptTemplatePagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="promptTemplatePagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePromptTemplatePageChange"
                @size-change="handlePromptTemplatePageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'systemPrompts'" class="space-y-4">
            <div v-loading="systemPromptListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="item in systemPromptList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-cyan-100">
                      <Icon icon="mdi:file-cog-outline" class="text-2xl text-cyan-600" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name || '-' }}</h3>
                        <el-tag size="small" class="border-0" type="info">{{ getSystemPromptTypeLabel(item.type) }}</el-tag>
                        <el-tag size="small" class="border-0">{{ item.type }}</el-tag>
                      </div>
                      <p class="text-sm text-gray-600 mb-3 line-clamp-2">{{ getSystemPromptPreview(item) }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:view-dashboard-variant" class="text-indigo-500" />
                          <span class="text-gray-600">工作区:</span>
                          <span class="font-mono text-xs text-gray-900">{{ item.workspace_id || '-' }}</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openSystemPromptDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openSystemPromptEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteSystemPrompt(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!systemPromptListLoading && systemPromptList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!systemPromptListLoading && systemPromptList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="systemPromptPagination.page"
                v-model:page-size="systemPromptPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="systemPromptPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleSystemPromptPageChange"
                @size-change="handleSystemPromptPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'workspaces'" class="space-y-4">
            <div v-loading="workspaceListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in workspaceList"
                :key="item.id || index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-indigo-100">
                      <Icon icon="mdi:view-dashboard-variant" class="text-2xl text-indigo-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2 whitespace-pre-line">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:server" class="text-green-600" />
                          <span class="text-gray-600">模型白名单:</span>
                          <span class="text-gray-900">{{ Array.isArray(item.model_config_ids) ? item.model_config_ids.length : 0 }} 项</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:file-document-edit" class="text-amber-600" />
                          <span class="text-gray-600">模板白名单:</span>
                          <span class="text-gray-900">{{ Array.isArray(item.prompt_template_ids) ? item.prompt_template_ids.length : 0 }} 项</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openWorkspaceDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openWorkspaceEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteWorkspace(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!workspaceListLoading && workspaceList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!workspaceListLoading && workspaceList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="workspacePagination.page"
                v-model:page-size="workspacePagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="workspacePagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleWorkspacePageChange"
                @size-change="handleWorkspacePageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'skills'" class="space-y-4">
            <div v-loading="skillListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="item in skillList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-violet-100">
                      <Icon icon="mdi:puzzle-outline" class="text-2xl text-violet-600" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                        <el-tag v-if="item.always" size="small" class="border-0" type="warning">始终注入</el-tag>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:file-multiple" class="text-blue-500" />
                          <span class="text-gray-600">文件数:</span>
                          <span class="text-gray-700">{{ item.file_count ?? 0 }}</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="openSkillDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      详情
                    </el-button>
                    <el-button type="primary" link @click="openSkillEditor(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteSkill(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!skillListLoading && skillList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!skillListLoading && skillList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="skillPagination.page"
                v-model:page-size="skillPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="skillPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleSkillPageChange"
                @size-change="handleSkillPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'sandboxes'" class="space-y-4">
            <div v-loading="sandboxListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="sandbox in filteredSandboxList"
                :key="sandbox.sandbox_id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-indigo-100">
                      <Icon icon="mdi:cube-outline" class="text-2xl text-indigo-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">
                          {{ sandbox.display_name || sandbox.name || sandbox.sandbox_id }}
                        </h3>
                        <el-tag
                          size="small"
                          :type="sandbox.status === ACTION_STATUS.RUNNING ? 'success' : sandbox.status === ACTION_STATUS.STOPPED ? 'info' : 'warning'"
                          class="border-0"
                        >
                          {{ sandbox.status || '未知' }}
                        </el-tag>
                        <el-tag
                          size="small"
                          :type="getSandboxStatusTagType(sandbox.sandbox_status)"
                          effect="plain"
                          class="border-0"
                        >
                          {{ sandboxStatusLabel(sandbox.sandbox_status) }}
                        </el-tag>
                      </div>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:identifier" class="text-gray-500" />
                          <span class="text-gray-600">沙盒ID:</span>
                          <span class="font-mono text-xs text-gray-900">{{ sandbox.sandbox_id }}</span>
                        </div>
                        <div v-if="sandbox.image" class="flex items-center gap-2">
                          <Icon icon="mdi:docker" class="text-blue-500" />
                          <span class="text-gray-600">镜像:</span>
                          <span class="font-mono text-xs text-gray-900">{{ sandbox.image }}</span>
                        </div>
                        <div v-if="sandbox.host_port" class="flex items-center gap-2">
                          <Icon icon="mdi:lan" class="text-green-500" />
                          <span class="text-gray-600">访问端口:</span>
                          <a
                            class="font-mono text-xs text-blue-600 hover:text-blue-800 underline"
                            :href="getSandboxUrl(sandbox.host_port)"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {{ sandbox.host_port }}
                          </a>
                        </div>
                        <div v-if="sandbox.created_at" class="flex items-center gap-2">
                          <Icon icon="mdi:calendar-clock" class="text-purple-500" />
                          <span class="text-gray-600">创建时间:</span>
                          <span class="font-medium text-gray-900">
                            {{ formatDateTime(sandbox.created_at, { defaultValue: '-' }) }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button
                      v-if="sandbox.host_port"
                      type="primary"
                      link
                      @click="handleConnectSandbox(sandbox)"
                    >
                      <template #icon>
                        <Icon icon="mdi:web" />
                      </template>
                      浏览器
                    </el-button>
                    <el-button
                      v-if="sandbox.host_port"
                      type="primary"
                      link
                      @click="handleOpenCodeServer(sandbox)"
                    >
                      <template #icon>
                        <Icon icon="mdi:code-braces" />
                      </template>
                      Code Server
                    </el-button>
                    <el-button type="primary" link @click="handleViewSandbox(sandbox)">
                      <template #icon>
                        <Icon icon="mdi:eye" />
                      </template>
                      查看
                    </el-button>
                    <el-button type="danger" link @click="handleDestroySandbox(sandbox)">
                      <template #icon>
                        <Icon icon="mdi:delete" />
                      </template>
                      销毁
                    </el-button>
                  </div>
                </div>
              </div>
              <div
                v-if="!sandboxListLoading && filteredSandboxList.length === 0"
                class="flex flex-col items-center justify-center py-16"
              >
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无沙盒容器</p>
              </div>
            </div>
            <div v-if="!searchKeyword && sandboxList.length > 0" class="flex justify-center mt-6">
              <el-pagination
                v-model:current-page="sandboxPagination.page"
                v-model:page-size="sandboxPagination.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="sandboxPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleSandboxPageChange"
                @size-change="handleSandboxPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'tools'" class="space-y-4">
            <div v-loading="toolsListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in toolsList"
                :key="item.name + '-' + index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start gap-4">
                  <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-purple-100">
                    <Icon icon="mdi:tools" class="text-2xl text-purple-600" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <h3 class="text-lg font-bold text-gray-900 mb-2">{{ item.name }}</h3>
                    <p v-if="item.description" class="text-sm text-gray-600 mb-3 whitespace-pre-line">{{ item.description }}</p>
                    <div v-if="item.parameters?.length" class="mt-3">
                      <p class="text-sm font-medium text-gray-700 mb-2">参数</p>
                      <el-table :data="item.parameters" size="small" border>
                        <el-table-column prop="name" label="参数名称" min-width="120" />
                        <el-table-column prop="description" label="参数描述" min-width="160">
                          <template #default="{ row }">
                            <span class="whitespace-pre-line">{{ row.description ?? '-' }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column prop="type" label="类型" width="100" />
                        <el-table-column label="必填" width="70" align="center">
                          <template #default="{ row }">
                            <el-tag v-if="row.required" size="small" type="danger">是</el-tag>
                            <el-tag v-else size="small" type="info">否</el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column label="默认值" min-width="100">
                          <template #default="{ row }">
                            {{ row.default !== undefined && row.default !== null ? String(row.default) : '-' }}
                          </template>
                        </el-table-column>
                      </el-table>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="!toolsListLoading && toolsList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
          </div>
  </ConfigCenterLayout>

    <el-dialog
      v-model="modelDialogVisible"
      :title="editingModelId ? '编辑模型资源' : '新增模型资源'"
      width="560px"
      :close-on-click-modal="false"
      @close="handleModelDialogClose"
    >
      <el-form
        ref="modelFormRef"
        :model="modelFormData"
        :rules="modelFormRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="modelFormData.name" placeholder="请输入名称" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="modelFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="API 地址" prop="base_url">
          <el-input v-model="modelFormData.base_url" placeholder="请输入 base_url" clearable />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="modelFormData.api_key" type="password" placeholder="请输入 api_key" clearable show-password />
        </el-form-item>
        <el-form-item label="模型" prop="model">
          <el-input v-model="modelFormData.model" placeholder="请输入模型名称" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleModelDialogClose">取消</el-button>
        <el-button type="primary" :loading="modelSubmitLoading" @click="handleModelSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="modelDetailVisible"
      title="模型资源详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="modelDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="modelDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="配置ID">{{ modelDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ modelDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ modelDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="API 地址">
              <span class="font-mono text-xs">{{ modelDetail.base_url || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="API Key">
              <span class="font-mono text-xs">{{ maskApiKey(modelDetail.api_key) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型">{{ modelDetail.model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ modelDetail.created_at ? formatModelDate(modelDetail.created_at) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ modelDetail.updated_at ? formatModelDate(modelDetail.updated_at) : '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="modelDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="promptTemplateDialogVisible"
      :title="editingPromptTemplateId ? '编辑提示词模板' : '新增提示词模板'"
      width="96%"
      top="2vh"
      class="prompt-template-dialog"
      destroy-on-close
      :close-on-click-modal="false"
      @close="handlePromptTemplateDialogClose"
    >
      <el-form
        ref="promptTemplateFormRef"
        :model="promptTemplateFormData"
        :rules="promptTemplateFormRules"
        label-width="100px"
      >
        <el-form-item label="标题" prop="name">
          <el-input v-model="promptTemplateFormData.name" placeholder="请输入提示词标题" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="promptTemplateFormData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-tabs v-model="promptTemplateActiveTab" class="prompt-template-tabs">
          <el-tab-pane label="系统提示词" name="system_prompt">
            <el-form-item label="系统提示词" prop="system_prompt" class="prompt-template-editor-item">
              <MarkdownPromptField
                v-model="promptTemplateFormData.system_prompt"
                layout="toggle"
                :min-height="640"
              />
            </el-form-item>
          </el-tab-pane>
          <el-tab-pane label="用户提示词" name="user_prompt">
            <el-form-item label="用户提示词" prop="user_prompt" class="prompt-template-editor-item">
              <MarkdownPromptField
                v-model="promptTemplateFormData.user_prompt"
                layout="toggle"
                :min-height="640"
              />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="handlePromptTemplateDialogClose">取消</el-button>
        <el-button type="primary" :loading="promptTemplateSubmitLoading" @click="handlePromptTemplateSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="promptTemplateDetailVisible"
      title="提示词模板详情"
      width="960px"
      :close-on-click-modal="true"
    >
      <div v-loading="promptTemplateDetailLoading" element-loading-text="加载中..." class="min-h-50">
        <template v-if="promptTemplateDetail">
          <div class="space-y-4">
            <div>
              <div class="text-sm text-gray-500 mb-1">名称</div>
              <div class="text-base font-medium text-gray-900">{{ promptTemplateDetail.name }}</div>
            </div>
            <div v-if="promptTemplateDetail.description">
              <div class="text-sm text-gray-500 mb-1">描述</div>
              <div class="text-sm text-gray-700 whitespace-pre-line">{{ promptTemplateDetail.description }}</div>
            </div>
            <div class="flex items-center gap-4 text-sm text-gray-500">
              <span>创建时间：{{ formatModelDate(promptTemplateDetail.created_at) }}</span>
              <span>更新时间：{{ formatModelDate(promptTemplateDetail.updated_at) }}</span>
            </div>
            <el-tabs v-model="promptTemplateDetailActiveTab">
              <el-tab-pane label="系统提示词" name="system_prompt">
                <div class="text-sm text-gray-500 mb-1">系统提示词</div>
                <MonacoEditor
                  :model-value="promptTemplateDetail.system_prompt || ''"
                  language="markdown"
                  :read-only="true"
                  :min-height="360"
                />
              </el-tab-pane>
              <el-tab-pane label="用户提示词" name="user_prompt">
                <div class="text-sm text-gray-500 mb-1">用户提示词</div>
                <MonacoEditor
                  :model-value="promptTemplateDetail.user_prompt || ''"
                  language="markdown"
                  :read-only="true"
                  :min-height="360"
                />
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="promptTemplateDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="systemPromptDialogVisible"
      :title="editingSystemPromptId ? '编辑系统指令' : '新增系统指令'"
      width="960px"
      :close-on-click-modal="false"
      @close="handleSystemPromptDialogClose"
      @opened="loadSystemPromptDialogOptions"
    >
      <el-form
        ref="systemPromptFormRef"
        :model="systemPromptFormData"
        :rules="systemPromptFormRules"
        label-width="100px"
      >
        <el-form-item label="工作区" prop="workspace_id">
          <el-select
            v-model="systemPromptFormData.workspace_id"
            placeholder="请选择工作区"
            class="w-full"
            filterable
            clearable
            :loading="systemPromptWorkspaceOptionsLoading"
          >
            <el-option
              v-for="item in systemPromptWorkspaceOptions"
              :key="item.id"
              :label="item.name || item.id"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="systemPromptFormData.type" placeholder="请选择系统指令类型" class="w-full">
            <el-option
              v-for="item in systemPromptTypeOptions"
              :key="item.value"
              :label="`${item.label} (${item.value})`"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="systemPromptFormData.name" placeholder="请输入模板名称" clearable />
        </el-form-item>
        <el-form-item label="模板描述" prop="description">
          <el-input
            v-model="systemPromptFormData.description"
            type="textarea"
            :rows="3"
            placeholder="选填，简要说明用途"
            clearable
          />
        </el-form-item>
        <el-form-item label="模板内容" prop="content">
          <MonacoEditor
            v-model="systemPromptFormData.content"
            language="markdown"
            :read-only="false"
            :min-height="560"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleSystemPromptDialogClose">取消</el-button>
        <el-button type="primary" :loading="systemPromptSubmitLoading" @click="handleSystemPromptSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="systemPromptDetailVisible"
      title="系统指令详情"
      width="960px"
      :close-on-click-modal="true"
    >
      <div v-loading="systemPromptDetailLoading" element-loading-text="加载中..." class="min-h-50">
        <template v-if="systemPromptDetail">
          <div class="space-y-4">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="系统指令ID">{{ systemPromptDetail.id }}</el-descriptions-item>
              <el-descriptions-item label="工作区ID">{{ systemPromptDetail.workspace_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="模板名称">{{ systemPromptDetail.name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="模板描述">{{ systemPromptDetail.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="类型">
                {{ getSystemPromptTypeLabel(systemPromptDetail.type) }}
                <span class="text-gray-500">({{ systemPromptDetail.type || '-' }})</span>
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ systemPromptDetail.created_at ? formatModelDate(systemPromptDetail.created_at) : '-' }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ systemPromptDetail.updated_at ? formatModelDate(systemPromptDetail.updated_at) : '-' }}</el-descriptions-item>
            </el-descriptions>
            <div>
              <div class="text-sm text-gray-500 mb-1">模板内容</div>
              <MonacoEditor
                :model-value="systemPromptDetail.content || ''"
                language="markdown"
                :read-only="true"
                :min-height="420"
              />
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="systemPromptDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="agentDialogVisible"
      :title="editingAgentId ? '编辑分析引擎' : '新增分析引擎'"
      width="640px"
      :close-on-click-modal="false"
      @closed="afterAgentDialogClosed"
      @opened="loadAgentDialogOptions"
    >
      <el-form
        ref="agentFormRef"
        :model="agentFormData"
        :rules="agentFormRules"
        label-width="120px"
      >
        <el-form-item label="工作区" prop="workspace_id">
          <el-select
            v-model="agentFormData.workspace_id"
            placeholder="请选择工作区"
            class="w-full"
            filterable
            clearable
            :loading="agentWorkspaceOptionsLoading"
            @change="handleAgentWorkspaceChange"
            :disabled="Boolean(editingAgentId)"
          >
            <el-option
              v-for="item in workspaceOptionsForAgent"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="agentFormData.name" placeholder="请输入名称" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="agentFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="内置提示词" prop="agent_builtin_prompt_ids">
          <div class="w-full space-y-2">
            <el-select
              v-model="agentBuiltinPromptPicker"
              placeholder="添加内置提示词（按顺序拼入 system prompt 前部）"
              class="w-full"
              filterable
              clearable
              :loading="agentBuiltinPromptOptionsLoading"
              @change="handleAddAgentBuiltinPrompt"
            >
              <el-option
                v-for="item in agentBuiltinPromptAvailableOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
            <div
              v-if="agentFormData.agent_builtin_prompt_ids.length"
              class="space-y-2"
            >
              <div
                v-for="(id, index) in agentFormData.agent_builtin_prompt_ids"
                :key="id"
                class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
              >
                <span class="shrink-0 text-xs text-gray-500 w-5 text-center">{{ index + 1 }}</span>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium text-gray-900 truncate">{{ getAgentBuiltinPromptLabel(id) }}</div>
                  <div
                    v-if="getAgentBuiltinPromptDescription(id)"
                    class="text-xs text-gray-500 truncate"
                  >
                    {{ getAgentBuiltinPromptDescription(id) }}
                  </div>
                </div>
                <el-button
                  type="primary"
                  link
                  :disabled="index === 0"
                  @click="moveAgentBuiltinPrompt(index, -1)"
                >
                  <Icon icon="mdi:arrow-up" />
                </el-button>
                <el-button
                  type="primary"
                  link
                  :disabled="index === agentFormData.agent_builtin_prompt_ids.length - 1"
                  @click="moveAgentBuiltinPrompt(index, 1)"
                >
                  <Icon icon="mdi:arrow-down" />
                </el-button>
                <el-button type="danger" link @click="removeAgentBuiltinPrompt(index)">
                  <Icon icon="mdi:close" />
                </el-button>
              </div>
            </div>
            <p v-else class="text-xs text-gray-500 m-0">未选择时运行时不注入 nanobot 内置骨架段</p>
          </div>
        </el-form-item>
        <el-form-item label="提示词模板" prop="prompt_template_id">
          <el-select
            v-model="agentFormData.prompt_template_id"
            placeholder="请选择提示词模板"
            class="w-full"
            filterable
            :loading="agentWorkspaceDetailLoading || agentPromptOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="item in promptTemplateOptionsForAgentFiltered"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型" prop="model_config_id">
          <el-select
            v-model="agentFormData.model_config_id"
            placeholder="请选择模型"
            class="w-full"
            filterable
            :loading="agentWorkspaceDetailLoading || agentModelOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="item in modelOptionsForAgentFiltered"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="LLM 提供商" prop="llm_provider">
          <el-select
            v-model="agentFormData.llm_provider"
            placeholder="请选择 LLM 兼容提供商"
            class="w-full"
          >
            <el-option
              v-for="opt in LLM_PROVIDER_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="思考强度" prop="reasoning_effort">
          <div class="w-full space-y-2 pr-2">
            <el-slider
              v-model="agentReasoningEffortIndex"
              :min="0"
              :max="reasoningEffortSliderMax"
              :step="1"
              :show-stops="true"
              :format-tooltip="formatReasoningEffortTooltip"
            />
            <p class="text-xs text-gray-500 m-0">
              当前：{{ formatReasoningEffortLabel(agentFormData.reasoning_effort) }}（关闭时不启用思考流）
            </p>
          </div>
        </el-form-item>
        <el-form-item prop="llm_config">
          <template #label>
            <span class="inline-flex items-center gap-1">
              <span>LLM 配置</span>
              <el-tooltip
                content="该值将被直接用于OpenAI兼容的extra_body传参，Anthropic无效"
                placement="top"
              >
                <span class="inline-flex items-center cursor-help text-gray-400 hover:text-gray-600">
                  <Icon icon="mdi:help-circle-outline" class="text-sm" />
                </span>
              </el-tooltip>
            </span>
          </template>
          <KeyValueEditor v-model="agentFormData.llm_config" typed-values />
        </el-form-item>
        <el-form-item label="工具" prop="tools">
          <el-select
            v-model="agentFormData.tools"
            placeholder="请选择工具（仅白名单，可多选）"
            class="w-full"
            multiple
            filterable
            :loading="agentWorkspaceDetailLoading || agentToolsOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="name in agentToolsListOptionsFiltered"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="技能" prop="skills">
          <el-select
            v-model="agentFormData.skills"
            placeholder="请选择技能（仅工作区白名单，可多选）"
            class="w-full"
            multiple
            filterable
            clearable
            :loading="agentWorkspaceDetailLoading || agentSkillsOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="s in agentSkillsListOptions"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-gray-900">{{ s.name }}</span>
                <span class="text-xs text-gray-500 truncate max-w-80">{{ s.description || '' }}</span>
                <el-tag v-if="s.always" size="small" type="info" class="shrink-0">always</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleAgentDialogClose">取消</el-button>
        <el-button type="primary" :loading="agentSubmitLoading" @click="handleAgentSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="agentDetailVisible"
      title="分析引擎详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="agentDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="agentDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="分析引擎ID">{{ agentDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="工作区ID">{{ agentDetail.workspace_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ agentDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ agentDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型配置ID">{{ agentDetail.model_config_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="内置提示词">
              <span class="whitespace-pre-line">{{ formatAgentBuiltinPromptDetail(agentDetail.agent_builtin_prompt_ids) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="提示词模板ID">{{ agentDetail.prompt_template_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="工具">
              {{ Array.isArray(agentDetail.tools) && agentDetail.tools.length ? agentDetail.tools.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="技能">
              {{ formatSkillIdsDetail(agentDetail.skills) }}
            </el-descriptions-item>
            <el-descriptions-item label="LLM 提供商">
              {{ formatLlmProviderLabel(agentDetail.llm_provider) }}
            </el-descriptions-item>
            <el-descriptions-item label="思考强度">
              {{ formatReasoningEffortLabel(agentDetail.reasoning_effort) }}
            </el-descriptions-item>
            <el-descriptions-item label="LLM 配置">
              <pre class="m-0 p-2 bg-gray-50 rounded text-xs max-h-60 overflow-auto">{{ JSON.stringify(agentDetail.llm_config || {}, null, 2) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ agentDetail.created_at ? formatModelDate(agentDetail.created_at) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ agentDetail.updated_at ? formatModelDate(agentDetail.updated_at) : '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="agentDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="workspaceDialogVisible"
      :title="editingWorkspaceId ? '编辑工作区' : '新增工作区'"
      width="640px"
      :close-on-click-modal="false"
      @close="handleWorkspaceDialogClose"
      @opened="loadWorkspaceDialogOptions"
    >
      <el-form
        ref="workspaceFormRef"
        :model="workspaceFormData"
        :rules="workspaceFormRules"
        label-width="120px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="workspaceFormData.name" placeholder="请输入工作区名称" clearable maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="workspaceFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="模型白名单" prop="model_config_ids">
          <el-select
            v-model="workspaceFormData.model_config_ids"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用模型配置（可多选）"
            :loading="workspaceModelOptionsLoading"
          >
            <el-option
              v-for="opt in workspaceModelOptions"
              :key="opt.id"
              :label="opt.name"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模板白名单" prop="prompt_template_ids">
          <el-select
            v-model="workspaceFormData.prompt_template_ids"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用提示词模板（可多选）"
            :loading="workspacePromptTemplateOptionsLoading"
          >
            <el-option
              v-for="opt in workspacePromptTemplateOptions"
              :key="opt.id"
              :label="opt.name"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工具白名单" prop="enabled_tools">
          <el-select
            v-model="workspaceFormData.enabled_tools"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用工具（可多选）"
            :loading="workspaceToolsOptionsLoading"
          >
            <el-option
              v-for="t in workspaceToolsOptions"
              :key="t.name"
              :label="t.name"
              :value="t.name"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="font-mono text-xs text-gray-900">{{ t.name }}</span>
                <span class="text-xs text-gray-500 truncate max-w-80">{{ t.description || '' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="技能白名单" prop="enabled_skills">
          <el-select
            v-model="workspaceFormData.enabled_skills"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用技能（可多选）"
            :loading="workspaceSkillsOptionsLoading"
          >
            <el-option
              v-for="s in workspaceSkillsOptions"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-gray-900">{{ s.name }}</span>
                <span class="text-xs text-gray-500 truncate max-w-80">{{ s.description || '' }}</span>
                <el-tag v-if="s.always" size="small" type="info" class="shrink-0">always</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleWorkspaceDialogClose">取消</el-button>
        <el-button type="primary" :loading="workspaceSubmitLoading" @click="handleWorkspaceSubmit">确定</el-button>
      </template>
    </el-dialog>

    <SkillEditorDialog
      v-model="skillEditorVisible"
      :skill-id="skillEditorId"
      :skill-name="skillEditorName"
      @saved="onSkillEditorSaved"
    />

    <el-dialog
      v-model="skillDetailVisible"
      title="技能详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="skillDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="skillDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="技能 ID">
              <span class="font-mono text-xs">{{ skillDetail.id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="名称">{{ skillDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ skillDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="始终注入">
              {{ skillDetail.always ? '是' : '否' }}
            </el-descriptions-item>
            <el-descriptions-item label="扩展元数据">
              <pre class="m-0 p-2 bg-gray-50 rounded text-xs max-h-40 overflow-auto">{{ formatSkillMeta(skillDetail.meta) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ skillDetail.created_at ? formatModelDate(skillDetail.created_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ skillDetail.updated_at ? formatModelDate(skillDetail.updated_at) : '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <div class="mt-4">
            <div class="text-sm font-medium text-gray-700 mb-2">文件清单（{{ skillDetailFiles.length }}）</div>
            <el-table v-if="skillDetailFiles.length" :data="skillDetailFiles" size="small" border max-height="280">
              <el-table-column prop="path" label="路径" min-width="200">
                <template #default="{ row }">
                  <span class="font-mono text-xs">{{ row.path }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="file_type" label="类型" width="120">
                <template #default="{ row }">
                  {{ getSkillFileTypeLabel(row.file_type) }}
                </template>
              </el-table-column>
            </el-table>
            <p v-else class="text-sm text-gray-400">暂无文件</p>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="skillDetailVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!skillDetail?.id" @click="openSkillEditorFromDetail">
          编辑
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="skillUploadDialogVisible"
      title="上传技能"
      width="520px"
      :close-on-click-modal="false"
      @close="handleSkillUploadDialogClose"
    >
      <p class="text-sm text-gray-500 mb-4">仅支持 zip 压缩包，须包含 SKILL.md 及有效 YAML frontmatter，单文件不超过 5MB。</p>
      <el-upload
        ref="skillUploadRef"
        drag
        accept=".zip"
        :limit="1"
        :auto-upload="false"
        :on-exceed="handleSkillUploadExceed"
        :before-upload="beforeSkillUpload"
        :on-change="handleSkillUploadChange"
      >
        <Icon icon="mdi:cloud-upload" class="text-5xl text-gray-400 mb-2" />
        <div class="el-upload__text">将 zip 文件拖到此处，或<em>点击选择</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="handleSkillUploadDialogClose">取消</el-button>
        <el-button type="primary" :loading="skillUploadLoading" :disabled="!skillUploadFile" @click="handleSkillUploadSubmit">
          确认上传
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="workspaceDetailVisible"
      title="工作区详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="workspaceDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="workspaceDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="工作区ID">{{ workspaceDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ workspaceDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ workspaceDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型白名单">
              {{ Array.isArray(workspaceDetail.model_config_ids) && workspaceDetail.model_config_ids.length ? workspaceDetail.model_config_ids.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="模板白名单">
              {{ Array.isArray(workspaceDetail.prompt_template_ids) && workspaceDetail.prompt_template_ids.length ? workspaceDetail.prompt_template_ids.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="工具白名单">
              {{ Array.isArray(workspaceDetail.enabled_tools) && workspaceDetail.enabled_tools.length ? workspaceDetail.enabled_tools.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="技能白名单">
              {{ formatSkillIdsDetail(workspaceDetail.enabled_skills) }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ workspaceDetail.created_at ? formatModelDate(workspaceDetail.created_at) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ workspaceDetail.updated_at ? formatModelDate(workspaceDetail.updated_at) : '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="workspaceDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="createSandboxDialogVisible"
      title="创建沙盒"
      width="420px"
      @open="onCreateSandboxDialogOpen"
      @closed="onCreateSandboxDialogClosed"
    >
      <el-form label-width="80px">
        <el-form-item label="显示名称">
          <el-input
            v-model="createSandboxName"
            placeholder="用于展示的名称，选填"
            clearable
            maxlength="64"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="沙盒类型">
          <el-select v-model="createSandboxImageType" placeholder="选择类型" class="w-full">
            <el-option label="All-in-One" value="all-in-one" />
            <el-option label="Windows" value="windows" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createSandboxDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingSandbox" @click="handleCreateSandboxSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="sandboxDetailDialogVisible"
      title="沙盒容器详情"
      width="640px"
      @close="sandboxDetailData = null"
    >
      <div v-loading="sandboxDetailLoading" class="min-h-50">
        <template v-if="sandboxDetailData">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="沙盒ID">{{ sandboxDetailData.sandbox_id }}</el-descriptions-item>
            <el-descriptions-item label="显示名称">{{ sandboxDetailData.display_name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="容器名称">{{ sandboxDetailData.name }}</el-descriptions-item>
            <el-descriptions-item label="容器状态">{{ sandboxDetailData.status ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="沙盒业务状态">{{ sandboxStatusLabel(sandboxDetailData.sandbox_status) }}</el-descriptions-item>
            <el-descriptions-item label="镜像">{{ sandboxDetailData.image ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="宿主机端口">
              {{ sandboxDetailData.host_port ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatDateTime(sandboxDetailData.created_at, { defaultValue: '-' }) }}
            </el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">端口映射</el-divider>
          <pre class="m-0 p-2 bg-gray-50 rounded text-xs max-h-60 overflow-auto">
{{ formatJson(sandboxDetailData.ports || {}) }}
          </pre>

          <el-divider content-position="left">标签</el-divider>
          <pre class="m-0 p-2 bg-gray-50 rounded text-xs max-h-60 overflow-auto">
{{ formatJson(sandboxDetailData.labels || {}) }}
          </pre>
        </template>
      </div>
    </el-dialog>

    <el-dialog
      v-model="sandboxBrowserDialogVisible"
      :title="sandboxBrowserTitle || '沙盒浏览器'"
      class="sandbox-browser-dialog"
      width="96vw"
      destroy-on-close
      :style="{ maxWidth: '1600px' }"
    >
      <template #header="{ titleId, titleClass }">
        <div class="flex items-center justify-between w-full pr-8">
          <span :id="titleId" :class="titleClass">{{ sandboxBrowserTitle || '沙盒浏览器' }}</span>
          <a
            v-if="sandboxBrowserUrl"
            :href="sandboxBrowserUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="text-sm text-primary hover:underline flex items-center gap-1"
          >
            <Icon icon="mdi:open-in-new" class="w-4 h-4" />
            新窗口打开
          </a>
        </div>
      </template>
      <div class="flex flex-1 min-h-0 flex-col">
        <div v-if="sandboxBrowserUrl" class="flex-1 min-h-0 rounded-lg overflow-hidden bg-black">
          <iframe
            :src="sandboxBrowserUrl"
            class="w-full h-full border-0 block"
            allowfullscreen
            title="沙盒浏览器"
          ></iframe>
        </div>
        <div v-else class="w-full h-full flex items-center justify-center text-gray-500 min-h-100">
          当前没有可用的连接地址。
        </div>
      </div>
    </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import SkillEditorDialog from '@/components/agent/SkillEditorDialog.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkdownPromptField from '@/components/agent/MarkdownPromptField.vue'
import KeyValueEditor from '@/components/action/nodes/components/KeyValueEditor.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi } from '@/api/agent'
import { getPaginatedData } from '@/utils/request'
import { formatDateTime, formatJson, filterByKeyword, ACTION_STATUS } from '@/utils/action'
import {
  REASONING_EFFORT_STEPS,
  formatReasoningEffortLabel,
  formatReasoningEffortTooltip,
  indexToReasoningEffort,
  reasoningEffortToIndex
} from '@/utils/agent/reasoningEffort'

const SANDBOX_HOST = import.meta.env.VITE_SANDBOX_HOST || '127.0.0.1'

const activeTab = ref('analysisEngines')
const searchKeyword = ref('')

const LLM_PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'anthropic', label: 'Anthropic Claude 兼容' }
]

const formatLlmProviderLabel = (value) => {
  const opt = LLM_PROVIDER_OPTIONS.find((item) => item.value === value)
  return opt?.label ?? value ?? '-'
}

const engineTabs = [
  { key: 'workspaces', label: '工作区', icon: 'mdi:view-dashboard-variant' },
  { key: 'analysisEngines', label: '分析引擎', icon: 'mdi:brain' },
  { key: 'modelResources', label: '模型资源', icon: 'mdi:server' },
  { key: 'promptTemplates', label: '提示词模板', icon: 'mdi:file-document-edit' },
  { key: 'systemPrompts', label: '系统指令', icon: 'mdi:file-cog-outline' },
  { key: 'skills', label: '技能', icon: 'mdi:puzzle-outline' },
  { key: 'tools', label: '工具', icon: 'mdi:tools' },
  { key: 'sandboxes', label: '沙盒环境', icon: 'mdi:cube-outline' }
]

const currentTabMeta = computed(() => findNavItemByKey(engineTabs, activeTab.value))
const currentTabIcon = computed(() => currentTabMeta.value?.icon ?? 'mdi:help')
const currentTabLabel = computed(() => currentTabMeta.value?.label ?? '')

const statisticsData = ref({
  agent_count: 0,
  model_count: 0,
  prompt_template_count: 0,
  tools_count: 0
})

const fetchStatistics = async () => {
  try {
    const res = await agentApi.getConfigStatistics()
    const data = res?.data
    if (data) {
      statisticsData.value = {
        agent_count: data.agent_count ?? 0,
        model_count: data.model_count ?? 0,
        prompt_template_count: data.prompt_template_count ?? 0,
        tools_count: data.tools_count ?? 0
      }
    }
  } catch {
    statisticsData.value = { agent_count: 0, model_count: 0, prompt_template_count: 0, tools_count: 0 }
  }
}

const modelList = ref([])
const modelListLoading = ref(false)
const modelPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const modelLoadedOnce = ref(false)

const fetchModelList = async () => {
  modelListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getModelList, {
      search: searchKeyword.value.trim() || undefined,
      page: modelPagination.value.page,
      page_size: modelPagination.value.pageSize
    })
    modelList.value = result.items
    modelPagination.value = { ...modelPagination.value, ...result.pagination }
    modelLoadedOnce.value = true
  } catch (e) {
    modelList.value = []
  } finally {
    modelListLoading.value = false
  }
}

const promptTemplateList = ref([])
const promptTemplateListLoading = ref(false)
const promptTemplatePagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const promptTemplateLoadedOnce = ref(false)

const fetchPromptTemplateList = async () => {
  promptTemplateListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getPromptTemplateList, {
      search: searchKeyword.value.trim() || undefined,
      page: promptTemplatePagination.value.page,
      page_size: promptTemplatePagination.value.pageSize
    })
    promptTemplateList.value = result.items
    promptTemplatePagination.value = { ...promptTemplatePagination.value, ...result.pagination }
    promptTemplateLoadedOnce.value = true
  } catch (e) {
    promptTemplateList.value = []
  } finally {
    promptTemplateListLoading.value = false
  }
}

const systemPromptList = ref([])
const systemPromptListLoading = ref(false)
const systemPromptPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const systemPromptLoadedOnce = ref(false)

const fetchSystemPromptList = async () => {
  systemPromptListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getSystemPromptList, {
      search: searchKeyword.value.trim() || undefined,
      page: systemPromptPagination.value.page,
      page_size: systemPromptPagination.value.pageSize
    })
    systemPromptList.value = result.items
    systemPromptPagination.value = { ...systemPromptPagination.value, ...result.pagination }
    systemPromptLoadedOnce.value = true
  } catch (e) {
    systemPromptList.value = []
  } finally {
    systemPromptListLoading.value = false
  }
}

const skillList = ref([])
const skillListLoading = ref(false)
const skillPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const skillLoadedOnce = ref(false)

const SKILL_ZIP_MAX_BYTES = 5 * 1024 * 1024

const fetchSkillList = async () => {
  skillListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getSkillList, {
      search: searchKeyword.value.trim() || undefined,
      page: skillPagination.value.page,
      page_size: skillPagination.value.pageSize
    })
    skillList.value = result.items
    skillPagination.value = { ...skillPagination.value, ...result.pagination }
    skillLoadedOnce.value = true
  } catch (e) {
    skillList.value = []
  } finally {
    skillListLoading.value = false
  }
}

const toolsList = ref([])
const toolsListLoading = ref(false)
const toolsLoadedOnce = ref(false)

const fetchToolsList = async () => {
  toolsListLoading.value = true
  try {
    const res = await agentApi.getToolsList()
    toolsList.value = Array.isArray(res?.data) ? res.data : []
    toolsLoadedOnce.value = true
  } catch (e) {
    toolsList.value = []
  } finally {
    toolsListLoading.value = false
  }
}

const agentList = ref([])
const agentListLoading = ref(false)
const agentPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const agentLoadedOnce = ref(false)

const fetchAgentList = async () => {
  agentListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getAgentList, {
      search: searchKeyword.value.trim() || undefined,
      page: agentPagination.value.page,
      page_size: agentPagination.value.pageSize
    })
    agentList.value = result.items
    agentPagination.value = { ...agentPagination.value, ...result.pagination }
    agentLoadedOnce.value = true
  } catch (e) {
    agentList.value = []
  } finally {
    agentListLoading.value = false
  }
}

const workspaceList = ref([])
const workspaceListLoading = ref(false)
const workspacePagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const workspaceLoadedOnce = ref(false)

const fetchWorkspaceList = async () => {
  workspaceListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getWorkspaceList, {
      search: searchKeyword.value.trim() || undefined,
      page: workspacePagination.value.page,
      page_size: workspacePagination.value.pageSize
    })
    workspaceList.value = result.items
    workspacePagination.value = { ...workspacePagination.value, ...result.pagination }
    workspaceLoadedOnce.value = true
  } catch (e) {
    workspaceList.value = []
  } finally {
    workspaceListLoading.value = false
  }
}

const sandboxList = ref([])
const sandboxListLoading = ref(false)
const sandboxPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const sandboxLoadedOnce = ref(false)

const filteredSandboxList = computed(() =>
  filterByKeyword(sandboxList.value, ['sandbox_id', 'name', 'display_name', 'status', 'sandbox_status', 'image'], searchKeyword.value)
)

const getSandboxUrl = (port) => {
  if (!port) return ''
  return `http://${SANDBOX_HOST}:${port}`
}

const getSandboxBrowserUrl = (port) => {
  if (!port) return ''
  return `http://${SANDBOX_HOST}:${port}/browser-ui`
}

const getSandboxCodeServerUrl = (port) => {
  if (!port) return ''
  return `http://${SANDBOX_HOST}:${port}/code-server/`
}

const SANDBOX_STATUS_LABELS = {
  created: '已创建',
  deployed: '已部署',
  stopped: '已停止',
  destroyed: '已销毁'
}
const sandboxStatusLabel = (status) => SANDBOX_STATUS_LABELS[status] || status || '-'

const getSandboxStatusTagType = (sandboxStatus) => {
  const map = { created: 'info', deployed: 'success', stopped: 'warning', destroyed: 'danger' }
  return map[sandboxStatus] || 'info'
}

const fetchSandboxList = async () => {
  sandboxListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getSandboxList, {
      page: sandboxPagination.value.page,
      page_size: sandboxPagination.value.pageSize
    })
    sandboxList.value = result.items || []
    sandboxPagination.value = {
      ...sandboxPagination.value,
      total: result.pagination.total ?? 0,
      page: result.pagination.page ?? 1,
      pageSize: result.pagination.pageSize ?? sandboxPagination.value.pageSize,
      totalPages: result.pagination.totalPages ?? 0
    }
    sandboxLoadedOnce.value = true
  } catch {
    sandboxList.value = []
  } finally {
    sandboxListLoading.value = false
  }
}

const handleSandboxPageChange = (page) => {
  sandboxPagination.value.page = page
  fetchSandboxList()
}

const handleSandboxPageSizeChange = (pageSize) => {
  sandboxPagination.value.pageSize = pageSize
  sandboxPagination.value.page = 1
  fetchSandboxList()
}

const creatingSandbox = ref(false)
const createSandboxDialogVisible = ref(false)
const createSandboxName = ref('')
const createSandboxImageType = ref('all-in-one')

const onCreateSandboxDialogOpen = () => {
  createSandboxName.value = ''
  createSandboxImageType.value = 'all-in-one'
}

const onCreateSandboxDialogClosed = () => {
  createSandboxName.value = ''
  createSandboxImageType.value = 'all-in-one'
}

const handleCreateSandbox = () => {
  createSandboxDialogVisible.value = true
}

const handleCreateSandboxSubmit = async () => {
  creatingSandbox.value = true
  try {
    const payload = {
      image_type: createSandboxImageType.value || 'all-in-one'
    }
    if (createSandboxName.value.trim()) {
      payload.name = createSandboxName.value.trim()
    }
    const res = await agentApi.createSandbox(payload)
    if (res.code === 0) {
      ElMessage.success('创建沙盒容器成功')
      createSandboxDialogVisible.value = false
      await fetchSandboxList()
    } else {
      ElMessage.error(res.message || '创建沙盒容器失败')
    }
  } catch (error) {
    ElMessage.error(error?.message || '创建沙盒容器失败')
  } finally {
    creatingSandbox.value = false
  }
}

const sandboxDetailDialogVisible = ref(false)
const sandboxBrowserDialogVisible = ref(false)
const sandboxDetailLoading = ref(false)
const sandboxDetailData = ref(null)
const sandboxBrowserUrl = ref('')
const sandboxBrowserTitle = ref('')

const handleViewSandbox = async (sandbox) => {
  if (!sandbox?.sandbox_id) return
  sandboxDetailDialogVisible.value = true
  sandboxDetailData.value = null
  sandboxDetailLoading.value = true
  try {
    const res = await agentApi.getSandboxDetail(sandbox.sandbox_id)
    if (res.code === 0 && res.data) {
      sandboxDetailData.value = res.data
    } else {
      ElMessage.error(res.message || '获取沙盒详情失败')
      sandboxDetailDialogVisible.value = false
    }
  } catch (error) {
    ElMessage.error(error?.message || '获取沙盒详情失败')
    sandboxDetailDialogVisible.value = false
  } finally {
    sandboxDetailLoading.value = false
  }
}

const handleConnectSandbox = (sandbox) => {
  if (!sandbox || !sandbox.host_port) {
    ElMessage.error('该沙盒未配置宿主机端口，无法连接')
    return
  }
  const url = getSandboxBrowserUrl(sandbox.host_port)
  if (!url) {
    ElMessage.error('无法生成沙盒连接地址')
    return
  }
  sandboxBrowserUrl.value = url
  sandboxBrowserTitle.value = sandbox.display_name || sandbox.name || sandbox.sandbox_id || '沙盒浏览器'
  sandboxBrowserDialogVisible.value = true
}

const handleOpenCodeServer = (sandbox) => {
  if (!sandbox?.host_port) {
    ElMessage.error('该沙盒未配置宿主机端口，无法打开 Code Server')
    return
  }
  const url = getSandboxCodeServerUrl(sandbox.host_port)
  window.open(url, '_blank', 'noopener,noreferrer')
}

const handleDestroySandbox = (sandbox) => {
  if (!sandbox?.sandbox_id) return
  const name = sandbox.display_name || sandbox.name || sandbox.sandbox_id
  ElMessageBox.confirm(
    `确定要销毁沙盒「${name}」吗？`,
    '确认销毁',
    {
      confirmButtonText: '确定销毁',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      try {
        const res = await agentApi.destroySandbox(sandbox.sandbox_id)
        if (res.code === 0) {
          ElMessage.success('沙盒已销毁')
          await fetchSandboxList()
        } else {
          ElMessage.error(res.message || '销毁沙盒失败')
        }
      } catch (error) {
        ElMessage.error(error?.message || '销毁沙盒失败')
      }
    })
    .catch(() => {})
}

watch(activeTab, (tab) => {
  if (tab === 'analysisEngines' && !agentLoadedOnce.value) fetchAgentList()
  if (tab === 'modelResources' && !modelLoadedOnce.value) fetchModelList()
  if (tab === 'promptTemplates' && !promptTemplateLoadedOnce.value) fetchPromptTemplateList()
  if (tab === 'systemPrompts' && !systemPromptLoadedOnce.value) fetchSystemPromptList()
  if (tab === 'workspaces' && !workspaceLoadedOnce.value) fetchWorkspaceList()
  if (tab === 'skills' && !skillLoadedOnce.value) fetchSkillList()
  if (tab === 'tools' && !toolsLoadedOnce.value) fetchToolsList()
  if (tab === 'sandboxes' && !sandboxLoadedOnce.value) fetchSandboxList()
}, { immediate: true })

onMounted(() => {
  fetchStatistics()
})

const maskApiKey = (key) => {
  if (!key) return '***'
  if (key.length <= 4) return '***'
  return '***' + key.slice(-4)
}

const formatModelDate = (dateStr) => formatDateTime(dateStr, { includeSecond: true })

const statistics = computed(() => ({
  analysisEngines: statisticsData.value.agent_count,
  analysisOptions: statisticsData.value.agent_count,
  modelResources: statisticsData.value.model_count,
  promptTemplates: statisticsData.value.prompt_template_count,
  systemPrompts: systemPromptPagination.value.total ?? 0,
  workspaces: workspacePagination.value.total ?? 0,
  skills: skillPagination.value.total ?? 0,
  tools: statisticsData.value.tools_count,
  sandboxes: sandboxPagination.value.total ?? 0
}))

const getResourceCount = (tabKey) => statistics.value[tabKey] ?? 0

const getPromptTemplatePreview = (item) => {
  if (item.description) return item.description
  const text = (item.system_prompt || item.user_prompt || '').trim()
  return text.length > 80 ? text.slice(0, 80) + '...' : text || '-'
}

const systemPromptTypeOptions = [
  { value: 'memory', label: '长期记忆文档' },
  { value: 'soul', label: 'Agent 风格/报告类系统指令' },
  { value: 'user', label: '用户相关长期文档' },
  { value: 'agent', label: 'Agent 类系统指令模板' }
]

const getSystemPromptTypeLabel = (type) => {
  return systemPromptTypeOptions.find((item) => item.value === type)?.label || type || '-'
}

const getSystemPromptPreview = (item) => {
  if (item?.description && String(item.description).trim()) {
    const d = String(item.description).trim()
    return d.length > 120 ? d.slice(0, 120) + '...' : d
  }
  const text = (item?.content || '').trim()
  return text.length > 120 ? text.slice(0, 120) + '...' : text || '-'
}

const handleModelPageChange = (page) => {
  modelPagination.value.page = page
  fetchModelList()
}
const handleModelPageSizeChange = (pageSize) => {
  modelPagination.value.pageSize = pageSize
  modelPagination.value.page = 1
  fetchModelList()
}
const handleModelSearch = () => {
  modelPagination.value.page = 1
  fetchModelList()
}

const handlePromptTemplatePageChange = (page) => {
  promptTemplatePagination.value.page = page
  fetchPromptTemplateList()
}
const handlePromptTemplatePageSizeChange = (pageSize) => {
  promptTemplatePagination.value.pageSize = pageSize
  promptTemplatePagination.value.page = 1
  fetchPromptTemplateList()
}
const handlePromptTemplateSearch = () => {
  promptTemplatePagination.value.page = 1
  fetchPromptTemplateList()
}

const handleSystemPromptPageChange = (page) => {
  systemPromptPagination.value.page = page
  fetchSystemPromptList()
}
const handleSystemPromptPageSizeChange = (pageSize) => {
  systemPromptPagination.value.pageSize = pageSize
  systemPromptPagination.value.page = 1
  fetchSystemPromptList()
}
const handleSystemPromptSearch = () => {
  systemPromptPagination.value.page = 1
  fetchSystemPromptList()
}

const handleAgentPageChange = (page) => {
  agentPagination.value.page = page
  fetchAgentList()
}
const handleAgentPageSizeChange = (pageSize) => {
  agentPagination.value.pageSize = pageSize
  agentPagination.value.page = 1
  fetchAgentList()
}
const handleAgentSearch = () => {
  agentPagination.value.page = 1
  fetchAgentList()
}

const handleWorkspacePageChange = (page) => {
  workspacePagination.value.page = page
  fetchWorkspaceList()
}
const handleWorkspacePageSizeChange = (pageSize) => {
  workspacePagination.value.pageSize = pageSize
  workspacePagination.value.page = 1
  fetchWorkspaceList()
}
const handleWorkspaceSearch = () => {
  workspacePagination.value.page = 1
  fetchWorkspaceList()
}

const handleSkillPageChange = (page) => {
  skillPagination.value.page = page
  fetchSkillList()
}
const handleSkillPageSizeChange = (pageSize) => {
  skillPagination.value.pageSize = pageSize
  skillPagination.value.page = 1
  fetchSkillList()
}
const handleSkillSearch = () => {
  skillPagination.value.page = 1
  fetchSkillList()
}

const handleCurrentTabSearch = () => {
  if (activeTab.value === 'analysisEngines') {
    handleAgentSearch()
  } else if (activeTab.value === 'modelResources') {
    handleModelSearch()
  } else if (activeTab.value === 'promptTemplates') {
    handlePromptTemplateSearch()
  } else if (activeTab.value === 'systemPrompts') {
    handleSystemPromptSearch()
  } else if (activeTab.value === 'workspaces') {
    handleWorkspaceSearch()
  } else if (activeTab.value === 'skills') {
    handleSkillSearch()
  } else if (activeTab.value === 'sandboxes') {
    searchKeyword.value = searchKeyword.value.trim()
  }
}

const modelDialogVisible = ref(false)
const modelFormRef = ref(null)
const modelSubmitLoading = ref(false)
const editingModelId = ref(null)
const modelFormData = ref({
  name: '',
  description: '',
  base_url: '',
  api_key: '',
  model: ''
})
const modelFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
  model: [{ required: true, message: '请输入模型', trigger: 'blur' }]
}

const modelDetailVisible = ref(false)
const modelDetail = ref(null)
const modelDetailLoading = ref(false)

const workspaceDialogVisible = ref(false)
const workspaceFormRef = ref(null)
const workspaceSubmitLoading = ref(false)
const editingWorkspaceId = ref(null)
const workspaceFormData = ref({
  name: '',
  description: '',
  model_config_ids: [],
  prompt_template_ids: [],
  enabled_tools: [],
  enabled_skills: []
})
const workspaceFormRules = {
  name: [
    { required: true, message: '请输入工作区名称', trigger: 'blur' },
    { min: 1, max: 64, message: '名称长度需为 1~64', trigger: 'blur' }
  ]
}

const workspaceModelOptions = ref([])
const workspacePromptTemplateOptions = ref([])
const workspaceModelOptionsLoading = ref(false)
const workspacePromptTemplateOptionsLoading = ref(false)
const workspaceToolsOptions = ref([])
const workspaceToolsOptionsLoading = ref(false)
const workspaceSkillsOptions = ref([])
const workspaceSkillsOptionsLoading = ref(false)
const globalSkillsById = ref(new Map())

const workspaceDetailVisible = ref(false)
const workspaceDetail = ref(null)
const workspaceDetailLoading = ref(false)

const loadWorkspaceDialogOptions = async () => {
  if (workspaceModelOptions.value.length === 0) {
    workspaceModelOptionsLoading.value = true
    try {
      const res = await agentApi.getModelsList()
      workspaceModelOptions.value = Array.isArray(res?.data) ? res.data : []
    } catch {
      workspaceModelOptions.value = []
    } finally {
      workspaceModelOptionsLoading.value = false
    }
  }

  if (workspacePromptTemplateOptions.value.length === 0) {
    workspacePromptTemplateOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getPromptTemplateList, { page: 1, page_size: 100 })
      workspacePromptTemplateOptions.value = Array.isArray(result?.items) ? result.items : []
    } catch {
      workspacePromptTemplateOptions.value = []
    } finally {
      workspacePromptTemplateOptionsLoading.value = false
    }
  }

  if (workspaceToolsOptions.value.length === 0) {
    workspaceToolsOptionsLoading.value = true
    try {
      const res = await agentApi.getToolsList()
      workspaceToolsOptions.value = Array.isArray(res?.data) ? res.data : []
    } catch {
      workspaceToolsOptions.value = []
    } finally {
      workspaceToolsOptionsLoading.value = false
    }
  }

  if (workspaceSkillsOptions.value.length === 0) {
    workspaceSkillsOptionsLoading.value = true
    try {
      const res = await agentApi.getSkillsList()
      const list = Array.isArray(res?.data) ? res.data : []
      workspaceSkillsOptions.value = list
      globalSkillsById.value = new Map(list.filter((s) => s?.id).map((s) => [s.id, s]))
    } catch {
      workspaceSkillsOptions.value = []
      globalSkillsById.value = new Map()
    } finally {
      workspaceSkillsOptionsLoading.value = false
    }
  }
}

const resetWorkspaceForm = () => {
  workspaceFormData.value = {
    name: '',
    description: '',
    model_config_ids: [],
    prompt_template_ids: [],
    enabled_tools: [],
    enabled_skills: []
  }
  workspaceFormRef.value?.resetFields()
}

const handleWorkspaceDialogClose = () => {
  workspaceDialogVisible.value = false
  editingWorkspaceId.value = null
  resetWorkspaceForm()
}

const agentDialogVisible = ref(false)
const agentFormRef = ref(null)
const agentSubmitLoading = ref(false)
const reasoningEffortSliderMax = REASONING_EFFORT_STEPS.length - 1

const agentFormData = ref({
  workspace_id: '',
  name: '',
  description: '',
  agent_builtin_prompt_ids: [],
  prompt_template_id: '',
  model_config_id: '',
  llm_provider: 'openai',
  reasoning_effort: null,
  llm_config: {},
  tools: [],
  skills: []
})

const agentReasoningEffortIndex = computed({
  get() {
    return reasoningEffortToIndex(agentFormData.value.reasoning_effort)
  },
  set(index) {
    agentFormData.value.reasoning_effort = indexToReasoningEffort(index)
  }
})
const agentFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  workspace_id: [{ required: true, message: '请选择工作区', trigger: 'change' }],
  prompt_template_id: [{ required: true, message: '请选择提示词模板', trigger: 'change' }],
  model_config_id: [{ required: true, message: '请选择模型', trigger: 'change' }]
}
const agentBuiltinPromptOptions = ref([])
const agentBuiltinPromptOptionsLoading = ref(false)
const agentBuiltinPromptPicker = ref('')
const agentBuiltinPromptById = computed(() => {
  const map = new Map()
  for (const item of agentBuiltinPromptOptions.value || []) {
    if (item?.id) map.set(item.id, item)
  }
  return map
})
const agentBuiltinPromptAvailableOptions = computed(() => {
  const selected = new Set(agentFormData.value.agent_builtin_prompt_ids || [])
  return (agentBuiltinPromptOptions.value || []).filter((item) => item?.id && !selected.has(item.id))
})

const getAgentBuiltinPromptLabel = (id) => agentBuiltinPromptById.value.get(id)?.name || id
const getAgentBuiltinPromptDescription = (id) => agentBuiltinPromptById.value.get(id)?.description || ''

const formatAgentBuiltinPromptDetail = (ids) => {
  if (!Array.isArray(ids) || !ids.length) return '-'
  return ids
    .map((id, index) => {
      const item = agentBuiltinPromptById.value.get(id)
      const name = item?.name || id
      const desc = item?.description ? ` — ${item.description}` : ''
      return `${index + 1}. ${name}${desc}`
    })
    .join('\n')
}

const loadAgentBuiltinPromptOptions = async () => {
  if (agentBuiltinPromptOptions.value.length > 0) return
  agentBuiltinPromptOptionsLoading.value = true
  try {
    const res = await agentApi.getAgentBuiltinPromptOptions()
    agentBuiltinPromptOptions.value = Array.isArray(res?.data) ? res.data : []
  } catch {
    agentBuiltinPromptOptions.value = []
  } finally {
    agentBuiltinPromptOptionsLoading.value = false
  }
}

const handleAddAgentBuiltinPrompt = (id) => {
  if (!id) return
  const ids = agentFormData.value.agent_builtin_prompt_ids || []
  if (ids.includes(id)) {
    agentBuiltinPromptPicker.value = ''
    return
  }
  agentFormData.value.agent_builtin_prompt_ids = [...ids, id]
  agentBuiltinPromptPicker.value = ''
}

const removeAgentBuiltinPrompt = (index) => {
  const ids = [...(agentFormData.value.agent_builtin_prompt_ids || [])]
  ids.splice(index, 1)
  agentFormData.value.agent_builtin_prompt_ids = ids
}

const moveAgentBuiltinPrompt = (index, delta) => {
  const ids = [...(agentFormData.value.agent_builtin_prompt_ids || [])]
  const next = index + delta
  if (next < 0 || next >= ids.length) return
  const tmp = ids[index]
  ids[index] = ids[next]
  ids[next] = tmp
  agentFormData.value.agent_builtin_prompt_ids = ids
}

const agentToolsListOptions = ref([])
const agentToolsOptionsLoading = ref(false)
const agentSkillsListOptions = ref([])
const agentSkillsOptionsLoading = ref(false)
const promptTemplateOptionsForAgent = ref([])
const agentPromptOptionsLoading = ref(false)
const modelOptionsForAgent = ref([])
const agentModelOptionsLoading = ref(false)

const workspaceOptionsForAgent = ref([])
const agentWorkspaceOptionsLoading = ref(false)
const agentWorkspaceDetailLoading = ref(false)
const agentWorkspaceDetail = ref(null)

const allowedPromptTemplateIdSet = computed(() => {
  const ids = agentWorkspaceDetail.value?.prompt_template_ids
  if (!Array.isArray(ids)) return new Set()
  return new Set(ids)
})

const allowedModelConfigIdSet = computed(() => {
  const ids = agentWorkspaceDetail.value?.model_config_ids
  if (!Array.isArray(ids)) return new Set()
  return new Set(ids)
})

const allowedToolNameSet = computed(() => {
  const names = agentWorkspaceDetail.value?.enabled_tools
  if (!Array.isArray(names)) return new Set()
  return new Set(names)
})

const promptTemplateOptionsForAgentFiltered = computed(() => {
  const set = allowedPromptTemplateIdSet.value
  if (!agentFormData.value.workspace_id) return []
  return (promptTemplateOptionsForAgent.value || []).filter((t) => t?.id && set.has(t.id))
})

const modelOptionsForAgentFiltered = computed(() => {
  const set = allowedModelConfigIdSet.value
  if (!agentFormData.value.workspace_id) return []
  return (modelOptionsForAgent.value || []).filter((m) => m?.id && set.has(m.id))
})

const agentToolsListOptionsFiltered = computed(() => {
  const set = allowedToolNameSet.value
  if (!agentFormData.value.workspace_id) return []
  return (agentToolsListOptions.value || []).filter((name) => set.has(name))
})

const formatSkillIdsDetail = (ids) => {
  if (!Array.isArray(ids) || !ids.length) return '-'
  return ids
    .map((id) => {
      const skill = globalSkillsById.value.get(id)
      return skill?.name ? `${skill.name} (${id})` : id
    })
    .join(', ')
}

const loadAgentSkillsOptions = async (workspaceId) => {
  agentSkillsListOptions.value = []
  if (!workspaceId) return
  agentSkillsOptionsLoading.value = true
  try {
    const res = await agentApi.getSkillsListForAgent(workspaceId)
    const list = Array.isArray(res?.data) ? res.data : []
    agentSkillsListOptions.value = list
    for (const s of list) {
      if (s?.id) globalSkillsById.value.set(s.id, s)
    }
  } catch {
    agentSkillsListOptions.value = []
  } finally {
    agentSkillsOptionsLoading.value = false
  }
}

const loadAgentDialogOptions = async () => {
  if (agentBuiltinPromptOptions.value.length === 0) {
    await loadAgentBuiltinPromptOptions()
  }

  agentToolsOptionsLoading.value = true
  try {
    const res = await agentApi.getToolsListForAgent()
    agentToolsListOptions.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    agentToolsListOptions.value = []
  } finally {
    agentToolsOptionsLoading.value = false
  }

  if (workspaceOptionsForAgent.value.length === 0) {
    agentWorkspaceOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getWorkspaceList, { page: 1, page_size: 100 })
      workspaceOptionsForAgent.value = Array.isArray(result?.items) ? result.items : []
    } catch {
      workspaceOptionsForAgent.value = []
    } finally {
      agentWorkspaceOptionsLoading.value = false
    }
  }

  if (promptTemplateOptionsForAgent.value.length === 0) {
    agentPromptOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getPromptTemplateList, { page: 1, page_size: 100 })
      promptTemplateOptionsForAgent.value = result.items || []
    } catch (e) {
      promptTemplateOptionsForAgent.value = []
    } finally {
      agentPromptOptionsLoading.value = false
    }
  }
  if (modelOptionsForAgent.value.length === 0) {
    agentModelOptionsLoading.value = true
    try {
      const res = await agentApi.getModelsList()
      modelOptionsForAgent.value = Array.isArray(res?.data) ? res.data : []
    } catch (e) {
      modelOptionsForAgent.value = []
    } finally {
      agentModelOptionsLoading.value = false
    }
  }
}

async function loadAgentWorkspaceDetail(workspaceId) {
  agentWorkspaceDetail.value = null
  if (!workspaceId) return null

  agentWorkspaceDetailLoading.value = true
  try {
    const res = await agentApi.getWorkspaceDetail(workspaceId)
    agentWorkspaceDetail.value = res?.data ?? null
    return agentWorkspaceDetail.value
  } catch {
    agentWorkspaceDetail.value = null
    ElMessage.error('获取工作区详情失败')
    return null
  } finally {
    agentWorkspaceDetailLoading.value = false
  }
}

const handleAgentWorkspaceChange = async () => {
  const workspaceId = agentFormData.value.workspace_id
  agentFormData.value.prompt_template_id = ''
  agentFormData.value.model_config_id = ''
  agentFormData.value.tools = []
  agentFormData.value.skills = []
  await loadAgentWorkspaceDetail(workspaceId)
  await loadAgentSkillsOptions(workspaceId)
}

const resetAgentForm = () => {
  agentFormData.value = {
    workspace_id: '',
    name: '',
    description: '',
    agent_builtin_prompt_ids: [],
    prompt_template_id: '',
    model_config_id: '',
    llm_provider: 'openai',
    reasoning_effort: null,
    llm_config: {},
    tools: [],
    skills: []
  }
  agentBuiltinPromptPicker.value = ''
  agentFormRef.value?.resetFields()
  agentWorkspaceDetail.value = null
  agentSkillsListOptions.value = []
}

const editingAgentId = ref(null)

const agentDetailVisible = ref(false)
const agentDetail = ref(null)
const agentDetailLoading = ref(false)

const handleAgentDialogClose = () => {
  agentDialogVisible.value = false
}

const afterAgentDialogClosed = () => {
  editingAgentId.value = null
  resetAgentForm()
}

const handleAgentSubmit = async () => {
  if (!agentFormRef.value) return
  try {
    await agentFormRef.value.validate()
    agentSubmitLoading.value = true
    const payload = {
      name: agentFormData.value.name,
      description: agentFormData.value.description || undefined,
      prompt_template_id: agentFormData.value.prompt_template_id,
      model_config_id: agentFormData.value.model_config_id,
      agent_builtin_prompt_ids: agentFormData.value.agent_builtin_prompt_ids || [],
      llm_provider: agentFormData.value.llm_provider || 'openai',
      reasoning_effort: agentFormData.value.reasoning_effort ?? null,
      llm_config: agentFormData.value.llm_config || {},
      tools: agentFormData.value.tools || [],
      skills: agentFormData.value.skills || []
    }

    if (editingAgentId.value) {
      await agentApi.updateAgent(editingAgentId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createAgent({
        ...payload,
        workspace_id: agentFormData.value.workspace_id
      })
      ElMessage.success('新增成功')
    }
    handleAgentDialogClose()
    agentPagination.value.page = 1
    fetchAgentList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) console.error(editingAgentId.value ? '修改分析引擎失败:' : '新增分析引擎失败:', e)
  } finally {
    agentSubmitLoading.value = false
  }
}

const openAgentDialog = () => {
  editingAgentId.value = null
  agentDialogVisible.value = true
}

const openAgentDetail = async (item) => {
  const id = item?.id
  if (!id) return
  agentDetailVisible.value = true
  agentDetail.value = null
  agentDetailLoading.value = true
  try {
    await loadAgentBuiltinPromptOptions()
    if (globalSkillsById.value.size === 0) {
      try {
        const res = await agentApi.getSkillsList()
        const list = Array.isArray(res?.data) ? res.data : []
        globalSkillsById.value = new Map(list.filter((s) => s?.id).map((s) => [s.id, s]))
      } catch {
        /* 详情展示回退为 ID */
      }
    }
    const res = await agentApi.getAgentDetail(id)
    agentDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取分析引擎详情失败')
    agentDetailVisible.value = false
  } finally {
    agentDetailLoading.value = false
  }
}

const openAgentEdit = async (item) => {
  const id = item?.id
  if (!id) return
  editingAgentId.value = id
  agentDialogVisible.value = true
  resetAgentForm()
  agentSubmitLoading.value = true
  try {
    await loadAgentDialogOptions()
    const res = await agentApi.getAgentDetail(id)
    const d = res?.data
    if (!d) throw new Error('empty agent detail')

    agentFormData.value = {
      workspace_id: d.workspace_id ?? '',
      name: d.name ?? '',
      description: d.description ?? '',
      agent_builtin_prompt_ids: Array.isArray(d.agent_builtin_prompt_ids) ? [...d.agent_builtin_prompt_ids] : [],
      prompt_template_id: d.prompt_template_id ?? '',
      model_config_id: d.model_config_id ?? '',
      llm_provider: d.llm_provider || 'openai',
      reasoning_effort: d.reasoning_effort ?? null,
      llm_config: d.llm_config && typeof d.llm_config === 'object' ? d.llm_config : {},
      tools: Array.isArray(d.tools) ? d.tools : [],
      skills: Array.isArray(d.skills) ? d.skills : []
    }
    agentBuiltinPromptPicker.value = ''

    if (agentFormData.value.workspace_id) {
      await loadAgentWorkspaceDetail(agentFormData.value.workspace_id)
      await loadAgentSkillsOptions(agentFormData.value.workspace_id)
      const allowedTools = allowedToolNameSet.value
      agentFormData.value.tools = (agentFormData.value.tools || []).filter((t) => allowedTools.has(t))
      const allowedSkills = new Set(agentSkillsListOptions.value.map((s) => s.id))
      agentFormData.value.skills = (agentFormData.value.skills || []).filter((id) => allowedSkills.has(id))
      if (agentFormData.value.prompt_template_id && !allowedPromptTemplateIdSet.value.has(agentFormData.value.prompt_template_id)) {
        agentFormData.value.prompt_template_id = ''
      }
      if (agentFormData.value.model_config_id && !allowedModelConfigIdSet.value.has(agentFormData.value.model_config_id)) {
        agentFormData.value.model_config_id = ''
      }
    }
  } catch (e) {
    ElMessage.error('获取分析引擎详情失败')
    agentDialogVisible.value = false
    editingAgentId.value = null
  } finally {
    agentSubmitLoading.value = false
  }
}

const handleDeleteAgent = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return
  ElMessageBox.confirm(
    `确定要删除分析引擎“${name}”吗？运行中可能无法删除。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteAgent(id)
      ElMessage.success('删除成功')
      if (agentList.value.length === 1 && agentPagination.value.page > 1) {
        agentPagination.value.page -= 1
      }
      fetchAgentList()
      fetchStatistics()
    })
    .catch(() => {})
}

const openWorkspaceCreate = () => {
  editingWorkspaceId.value = null
  workspaceDialogVisible.value = true
  resetWorkspaceForm()
}

const openWorkspaceDetail = async (item) => {
  const id = item?.id
  if (!id) return
  workspaceDetailVisible.value = true
  workspaceDetail.value = null
  workspaceDetailLoading.value = true
  try {
    if (globalSkillsById.value.size === 0) {
      try {
        const skillsRes = await agentApi.getSkillsList()
        const list = Array.isArray(skillsRes?.data) ? skillsRes.data : []
        globalSkillsById.value = new Map(list.filter((s) => s?.id).map((s) => [s.id, s]))
      } catch {
        /* 详情展示回退为 ID */
      }
    }
    const res = await agentApi.getWorkspaceDetail(id)
    workspaceDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取工作区详情失败')
    workspaceDetailVisible.value = false
  } finally {
    workspaceDetailLoading.value = false
  }
}

const openWorkspaceEdit = async (item) => {
  const id = item?.id
  if (!id) return
  editingWorkspaceId.value = id
  workspaceDialogVisible.value = true
  resetWorkspaceForm()
  workspaceSubmitLoading.value = true
  try {
    await loadWorkspaceDialogOptions()
    const res = await agentApi.getWorkspaceDetail(id)
    const d = res?.data
    if (d) {
      workspaceFormData.value = {
        name: d.name ?? '',
        description: d.description ?? '',
        model_config_ids: Array.isArray(d.model_config_ids) ? d.model_config_ids : [],
        prompt_template_ids: Array.isArray(d.prompt_template_ids) ? d.prompt_template_ids : [],
        enabled_tools: Array.isArray(d.enabled_tools) ? d.enabled_tools : [],
        enabled_skills: Array.isArray(d.enabled_skills) ? d.enabled_skills : []
      }
    }
  } catch (e) {
    ElMessage.error('获取工作区详情失败')
    workspaceDialogVisible.value = false
    editingWorkspaceId.value = null
  } finally {
    workspaceSubmitLoading.value = false
  }
}

const handleWorkspaceSubmit = async () => {
  if (!workspaceFormRef.value) return
  try {
    await workspaceFormRef.value.validate()
    workspaceSubmitLoading.value = true
    const payload = {
      name: (workspaceFormData.value.name || '').trim(),
      description: workspaceFormData.value.description || undefined,
      model_config_ids: workspaceFormData.value.model_config_ids || [],
      prompt_template_ids: workspaceFormData.value.prompt_template_ids || [],
      enabled_tools: workspaceFormData.value.enabled_tools || [],
      enabled_skills: workspaceFormData.value.enabled_skills || []
    }
    if (editingWorkspaceId.value) {
      await agentApi.updateWorkspace(editingWorkspaceId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createWorkspace(payload)
      ElMessage.success('新增成功')
    }
    handleWorkspaceDialogClose()
    workspacePagination.value.page = 1
    fetchWorkspaceList()
  } catch (e) {
    if (e !== false) console.error(editingWorkspaceId.value ? '修改工作区失败:' : '新增工作区失败:', e)
  } finally {
    workspaceSubmitLoading.value = false
  }
}

const handleDeleteWorkspace = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除工作区“${name}”吗？删除前请确保该工作区下已无分析引擎。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteWorkspace(id)
      ElMessage.success('删除成功')
      if (workspaceList.value.length === 1 && workspacePagination.value.page > 1) {
        workspacePagination.value.page -= 1
      }
      fetchWorkspaceList()
    })
    .catch(() => {})
}

const handleAdd = () => {
  if (activeTab.value === 'analysisEngines') {
    openAgentDialog()
  } else if (activeTab.value === 'modelResources') {
    editingModelId.value = null
    modelDialogVisible.value = true
  } else if (activeTab.value === 'promptTemplates') {
    editingPromptTemplateId.value = null
    promptTemplateFormData.value = { name: '', description: '', system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE, user_prompt: DEFAULT_USER_PROMPT_TEMPLATE }
    promptTemplateActiveTab.value = 'system_prompt'
    promptTemplateDialogVisible.value = true
  } else if (activeTab.value === 'systemPrompts') {
    openSystemPromptCreate()
  } else if (activeTab.value === 'workspaces') {
    openWorkspaceCreate()
  } else if (activeTab.value === 'skills') {
    openSkillUploadDialog()
  } else if (activeTab.value === 'sandboxes') {
    handleCreateSandbox()
  } else {
    ElMessage.info('功能开发中')
  }
}

const SKILL_FILE_TYPE_LABELS = {
  skill: '技能主文件',
  reference: '参考文档',
  script: '脚本',
  asset: '资源',
  other: '其他'
}

const getSkillFileTypeLabel = (fileType) => SKILL_FILE_TYPE_LABELS[fileType] || fileType || '-'

const formatSkillMeta = (meta) => {
  if (!meta || typeof meta !== 'object' || !Object.keys(meta).length) return '-'
  try {
    return JSON.stringify(meta, null, 2)
  } catch {
    return String(meta)
  }
}

const skillDetailVisible = ref(false)
const skillDetail = ref(null)
const skillDetailLoading = ref(false)

const skillDetailFiles = computed(() => {
  const files = skillDetail.value?.files
  return Array.isArray(files) ? files : []
})

const openSkillDetail = async (item) => {
  const id = item?.id
  if (!id) return
  skillDetailVisible.value = true
  skillDetail.value = null
  skillDetailLoading.value = true
  try {
    const res = await agentApi.getSkillDetail(id)
    skillDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取技能详情失败')
    skillDetailVisible.value = false
  } finally {
    skillDetailLoading.value = false
  }
}

const skillEditorVisible = ref(false)
const skillEditorId = ref('')
const skillEditorName = ref('')

const openSkillEditor = (item) => {
  const id = item?.id
  if (!id) return
  skillEditorId.value = id
  skillEditorName.value = item?.name || ''
  skillEditorVisible.value = true
}

const openSkillEditorFromDetail = () => {
  const d = skillDetail.value
  if (!d?.id) return
  skillDetailVisible.value = false
  openSkillEditor({ id: d.id, name: d.name })
}

const onSkillEditorSaved = () => {
  fetchSkillList()
}

const skillUploadDialogVisible = ref(false)
const skillUploadLoading = ref(false)
const skillUploadRef = ref(null)
const skillUploadFile = ref(null)

const validateSkillZipFile = (file) => {
  const name = (file?.name || '').toLowerCase()
  if (!name.endsWith('.zip')) {
    ElMessage.warning('仅支持 zip 压缩包')
    return false
  }
  if (file.size > SKILL_ZIP_MAX_BYTES) {
    ElMessage.warning('zip 文件不能超过 5MB')
    return false
  }
  return true
}

const beforeSkillUpload = () => false

const handleSkillUploadChange = (uploadFile) => {
  const raw = uploadFile?.raw
  if (!raw) {
    skillUploadFile.value = null
    return
  }
  if (!validateSkillZipFile(raw)) {
    skillUploadRef.value?.clearFiles()
    skillUploadFile.value = null
    return
  }
  skillUploadFile.value = raw
}

const handleSkillUploadExceed = () => {
  ElMessage.warning('仅可选择一个 zip 文件，请先移除已选文件')
}

const openSkillUploadDialog = () => {
  skillUploadFile.value = null
  skillUploadDialogVisible.value = true
}

const handleSkillUploadDialogClose = () => {
  skillUploadDialogVisible.value = false
  skillUploadFile.value = null
  skillUploadRef.value?.clearFiles()
}

const handleSkillUploadSubmit = async () => {
  const file = skillUploadFile.value
  if (!file) {
    ElMessage.warning('请选择 zip 文件')
    return
  }
  if (!validateSkillZipFile(file)) return

  skillUploadLoading.value = true
  try {
    const res = await agentApi.uploadSkill(file)
    const data = res?.data
    const total = data?.total ?? 0
    const names = Array.isArray(data?.skills)
      ? data.skills.map((s) => s.name).filter(Boolean).join('、')
      : ''
    const detail = names ? `：${names}` : ''
    ElMessage.success(total > 0 ? `成功导入 ${total} 个技能${detail}` : '上传成功')
    handleSkillUploadDialogClose()
    skillPagination.value.page = 1
    await fetchSkillList()
  } catch (e) {
    if (e !== false) console.error('上传技能失败:', e)
  } finally {
    skillUploadLoading.value = false
  }
}

const handleDeleteSkill = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除技能「${name}」吗？若仍被工作区或分析引擎引用将无法删除。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteSkill(id)
      ElMessage.success('删除成功')
      if (skillList.value.length === 1 && skillPagination.value.page > 1) {
        skillPagination.value.page -= 1
      }
      fetchSkillList()
    })
    .catch(() => {})
}

const handleModelDialogClose = () => {
  modelDialogVisible.value = false
  editingModelId.value = null
  modelFormRef.value?.resetFields()
  modelFormData.value = { name: '', description: '', base_url: '', api_key: '', model: '' }
}

const handleModelSubmit = async () => {
  if (!modelFormRef.value) return
  try {
    await modelFormRef.value.validate()
    modelSubmitLoading.value = true
    const payload = {
      name: modelFormData.value.name,
      description: modelFormData.value.description || undefined,
      base_url: modelFormData.value.base_url,
      api_key: modelFormData.value.api_key,
      model: modelFormData.value.model
    }
    if (editingModelId.value) {
      await agentApi.updateModel(editingModelId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createModel(payload)
      ElMessage.success('新增成功')
    }
    handleModelDialogClose()
    modelPagination.value.page = 1
    fetchModelList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) console.error(editingModelId.value ? '修改模型失败:' : '新增模型失败:', e)
  } finally {
    modelSubmitLoading.value = false
  }
}

const openModelDetail = async (item) => {
  const id = item?.id
  if (!id) return
  modelDetailVisible.value = true
  modelDetailLoading.value = true
  modelDetail.value = null
  try {
    const res = await agentApi.getModelDetail(id)
    modelDetail.value = res?.data ?? null
  } catch {
    ElMessage.error('获取模型资源详情失败')
    modelDetailVisible.value = false
  } finally {
    modelDetailLoading.value = false
  }
}

const openModelEdit = async (item) => {
  const id = item?.id
  if (!id) return
  editingModelId.value = id
  modelDialogVisible.value = true
  modelSubmitLoading.value = true
  modelFormRef.value?.resetFields()
  try {
    const res = await agentApi.getModelDetail(id)
    const d = res?.data
    if (!d) throw new Error('empty model detail')
    modelFormData.value = {
      name: d.name ?? '',
      description: d.description ?? '',
      base_url: d.base_url ?? '',
      api_key: d.api_key ?? '',
      model: d.model ?? ''
    }
  } catch (e) {
    ElMessage.error('获取模型资源详情失败')
    modelDialogVisible.value = false
    editingModelId.value = null
  } finally {
    modelSubmitLoading.value = false
  }
}

const handleDeleteModel = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除模型资源“${name}”吗？若仍被分析引擎或工作区引用将无法删除。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteModel(id)
      ElMessage.success('删除成功')
      if (modelList.value.length === 1 && modelPagination.value.page > 1) {
        modelPagination.value.page -= 1
      }
      fetchModelList()
      fetchStatistics()
    })
    .catch(() => {})
}

const createSystemPromptFormData = () => ({
  workspace_id: '',
  type: 'memory',
  name: '',
  description: '',
  content: ''
})

const systemPromptDialogVisible = ref(false)
const editingSystemPromptId = ref(null)
const systemPromptFormRef = ref(null)
const systemPromptSubmitLoading = ref(false)
const systemPromptFormData = ref(createSystemPromptFormData())
const systemPromptFormRules = {
  workspace_id: [{ required: true, message: '请选择工作区', trigger: 'change' }],
  type: [{ required: true, message: '请选择系统指令类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  content: [{ required: true, message: '请输入模板内容', trigger: 'blur' }]
}
const systemPromptWorkspaceOptions = ref([])
const systemPromptWorkspaceOptionsLoading = ref(false)

const systemPromptDetailVisible = ref(false)
const systemPromptDetail = ref(null)
const systemPromptDetailLoading = ref(false)

const loadSystemPromptDialogOptions = async () => {
  if (systemPromptWorkspaceOptions.value.length > 0) return

  systemPromptWorkspaceOptionsLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getWorkspaceList, { page: 1, page_size: 100 })
    systemPromptWorkspaceOptions.value = Array.isArray(result?.items) ? result.items : []
  } catch {
    systemPromptWorkspaceOptions.value = []
  } finally {
    systemPromptWorkspaceOptionsLoading.value = false
  }
}

const resetSystemPromptForm = () => {
  systemPromptFormData.value = createSystemPromptFormData()
  systemPromptFormRef.value?.resetFields()
}

const openSystemPromptCreate = () => {
  editingSystemPromptId.value = null
  resetSystemPromptForm()
  systemPromptDialogVisible.value = true
}

const openSystemPromptDetail = async (item) => {
  if (!item?.id) return
  systemPromptDetailVisible.value = true
  systemPromptDetail.value = null
  systemPromptDetailLoading.value = true
  try {
    const res = await agentApi.getSystemPromptDetail(item.id)
    systemPromptDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取系统指令详情失败')
    systemPromptDetailVisible.value = false
  } finally {
    systemPromptDetailLoading.value = false
  }
}

const openSystemPromptEdit = async (item) => {
  if (!item?.id) return
  editingSystemPromptId.value = item.id
  systemPromptDialogVisible.value = true
  resetSystemPromptForm()
  systemPromptSubmitLoading.value = true
  try {
    await loadSystemPromptDialogOptions()
    const res = await agentApi.getSystemPromptDetail(item.id)
    const d = res?.data
    if (!d) throw new Error('empty system prompt detail')
    systemPromptFormData.value = {
      workspace_id: d.workspace_id ?? '',
      type: d.type ?? 'memory',
      name: d.name ?? '',
      description: d.description ?? '',
      content: d.content ?? ''
    }
  } catch (e) {
    ElMessage.error('获取系统指令详情失败')
    systemPromptDialogVisible.value = false
    editingSystemPromptId.value = null
  } finally {
    systemPromptSubmitLoading.value = false
  }
}

const handleSystemPromptDialogClose = () => {
  systemPromptDialogVisible.value = false
  editingSystemPromptId.value = null
  resetSystemPromptForm()
}

const handleSystemPromptSubmit = async () => {
  if (!systemPromptFormRef.value) return
  try {
    await systemPromptFormRef.value.validate()
    systemPromptSubmitLoading.value = true
    const descTrim = (systemPromptFormData.value.description || '').trim()
    const payload = {
      workspace_id: systemPromptFormData.value.workspace_id,
      type: systemPromptFormData.value.type,
      name: systemPromptFormData.value.name.trim(),
      description: descTrim || null,
      content: systemPromptFormData.value.content
    }

    if (editingSystemPromptId.value) {
      await agentApi.updateSystemPrompt(editingSystemPromptId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createSystemPrompt(payload)
      ElMessage.success('新增成功')
    }
    handleSystemPromptDialogClose()
    systemPromptPagination.value.page = 1
    fetchSystemPromptList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) console.error(editingSystemPromptId.value ? '修改系统指令失败:' : '新增系统指令失败:', e)
  } finally {
    systemPromptSubmitLoading.value = false
  }
}

const handleDeletePromptTemplate = (item) => {
  const id = item?.id
  const displayName = item?.name?.trim() || id
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除提示词模板「${displayName}」吗？`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deletePromptTemplate(id)
      ElMessage.success('删除成功')
      if (promptTemplateList.value.length === 1 && promptTemplatePagination.value.page > 1) {
        promptTemplatePagination.value.page -= 1
      }
      fetchPromptTemplateList()
      fetchStatistics()
    })
    .catch(() => {})
}

const handleDeleteSystemPrompt = (item) => {
  const id = item?.id
  const displayName = item?.name?.trim() || `${getSystemPromptTypeLabel(item?.type)} / ${item?.workspace_id || id}`
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除系统指令模板「${displayName}」吗？`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteSystemPrompt(id)
      ElMessage.success('删除成功')
      if (systemPromptList.value.length === 1 && systemPromptPagination.value.page > 1) {
        systemPromptPagination.value.page -= 1
      }
      fetchSystemPromptList()
      fetchStatistics()
    })
    .catch(() => {})
}

const DEFAULT_SYSTEM_PROMPT_TEMPLATE = `---
创建者查看，记得删除
# 文本翻译任务样本提示词
---
## Role: 文本翻译 Agent

## Capability: 
1. 可以通过多种工具来实现目标
2. 具备有限的数据访问能力，你只能访问提供的 \`uuid\` 的数据
3. 具备有限的数据字段修改的能力，你只能修改 \`translate_content\` 字段。

## Workflow:
1. 分析任务目标，通过工具创建 Todos，在每一步完成后设置完成 Todo，随时回顾 Todos 以确认步骤进度。
1. 通过工具读取对应 \`uuid\` 和 \`entity_type\` 的 \`clean_content\` 字段
2. 如果 \`clean_content\` 字段内容为空或None，则立即结束并上报失败
3. 对 \`clean_content\` 字段内容进行翻译，将内容原文翻译成指定的语言。
4. 将翻译内容写入到对应 \`uuid\` 和 \`entity_type\` 的 \`translate_content\` 字段。
5. 按照规定格式输出最终结果。

## Constraints:
- 进度透明: Todos 必须具备可读性，作为用户监控进度的唯一凭证。
- 数据安全: 严禁尝试读取或修改本指令授权之外的任何字段。
- 翻译准则:
    - 语境重建: 针对 HTML 提取导致的破碎文本，必须先根据上下文拼接成完整意群再翻译，严禁碎片化直译。
    - 专业标注: 专业词汇保留原文（如：\`深度学习 (Deep Learning)\`）。
    - 译者辅助: 仅在俚语或文化差异极大时使用 \`(译者注: ...)\`。
- 格式保持: 在处理混乱格式时，应通过换行符重新构建合理的段落结构。
- 终态定义: 任何路径的终点必须包含原因说明。成功统一标识为“任务完成”。`

const DEFAULT_USER_PROMPT_TEMPLATE = `---
创建者查看，记得删除
# 文本翻译任务样本提示词
**注意：** 使用 {{ template_params }} 可以在实体分析时自动填充实体参数，如 {{ uuid }} 将在运行时自动替换为实体uuid
---
# 🚀 启动翻译任务

### 1. 翻译目标 (Target)
- UUID: {{ uuid }}
- Entity Type: {{ entity_type }}

### 2. 翻译参数 (Context)
- 目标语言: **中文 (zh-CN)**
---
**请按照系统设定的 Workflow 开始执行：创建 Todos -> 读取数据 -> 执行翻译 -> 回写字段。**`

const promptTemplateDialogVisible = ref(false)
const editingPromptTemplateId = ref(null)
const promptTemplateActiveTab = ref('system_prompt')
const promptTemplateFormRef = ref(null)
const promptTemplateSubmitLoading = ref(false)
const promptTemplateFormData = ref({
  name: '',
  description: '',
  system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE,
  user_prompt: DEFAULT_USER_PROMPT_TEMPLATE
})
const promptTemplateFormRules = {
  name: [{ required: true, message: '请输入提示词标题', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
  user_prompt: [{ required: true, message: '请输入用户提示词', trigger: 'blur' }]
}

const promptTemplateDetailVisible = ref(false)
const promptTemplateDetail = ref(null)
const promptTemplateDetailLoading = ref(false)
const promptTemplateDetailActiveTab = ref('system_prompt')

const openPromptTemplateDetail = async (item) => {
  if (!item?.id) return
  promptTemplateDetailVisible.value = true
  promptTemplateDetail.value = null
  promptTemplateDetailActiveTab.value = 'system_prompt'
  promptTemplateDetailLoading.value = true
  try {
    const res = await agentApi.getPromptTemplateDetail(item.id)
    promptTemplateDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取详情失败')
  } finally {
    promptTemplateDetailLoading.value = false
  }
}

const openPromptTemplateEdit = async (item) => {
  if (!item?.id) return
  editingPromptTemplateId.value = item.id
  promptTemplateDialogVisible.value = true
  promptTemplateActiveTab.value = 'system_prompt'
  promptTemplateFormData.value = { name: '', description: '', system_prompt: '', user_prompt: '' }
  promptTemplateSubmitLoading.value = true
  try {
    const res = await agentApi.getPromptTemplateDetail(item.id)
    const d = res?.data
    if (d) {
      promptTemplateFormData.value = {
        name: d.name ?? '',
        description: d.description ?? '',
        system_prompt: d.system_prompt ?? '',
        user_prompt: d.user_prompt ?? ''
      }
    }
  } catch (e) {
    ElMessage.error('获取模板详情失败')
    promptTemplateDialogVisible.value = false
    editingPromptTemplateId.value = null
  } finally {
    promptTemplateSubmitLoading.value = false
  }
}

const handlePromptTemplateDialogClose = () => {
  promptTemplateDialogVisible.value = false
  editingPromptTemplateId.value = null
  promptTemplateActiveTab.value = 'system_prompt'
  promptTemplateFormRef.value?.resetFields()
  promptTemplateFormData.value = { name: '', description: '', system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE, user_prompt: DEFAULT_USER_PROMPT_TEMPLATE }
}

const handlePromptTemplateSubmit = async () => {
  if (!promptTemplateFormRef.value) return
  try {
    await promptTemplateFormRef.value.validate()
    promptTemplateSubmitLoading.value = true
    const payload = {
      name: promptTemplateFormData.value.name,
      description: promptTemplateFormData.value.description || undefined,
      system_prompt: promptTemplateFormData.value.system_prompt,
      user_prompt: promptTemplateFormData.value.user_prompt
    }
    if (editingPromptTemplateId.value) {
      await agentApi.updatePromptTemplate(editingPromptTemplateId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createPromptTemplate(payload)
      ElMessage.success('新增成功')
    }
    handlePromptTemplateDialogClose()
    promptTemplatePagination.value.page = 1
    fetchPromptTemplateList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) {
      const data = promptTemplateFormData.value
      if (!data.system_prompt?.trim()) promptTemplateActiveTab.value = 'system_prompt'
      else if (!data.user_prompt?.trim()) promptTemplateActiveTab.value = 'user_prompt'
      console.error(editingPromptTemplateId.value ? '修改提示词模板失败:' : '新增提示词模板失败:', e)
    }
  } finally {
    promptTemplateSubmitLoading.value = false
  }
}

</script>

<style>
.sandbox-browser-dialog.el-dialog {
  --el-dialog-width: 96vw;
  max-width: 1600px;
  margin-top: 1vh;
}
.sandbox-browser-dialog .el-dialog__body {
  padding: 0.75rem;
  height: 0;
  min-height: 88vh;
  max-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
}

.prompt-template-dialog.el-dialog {
  --el-dialog-width: 96%;
  max-width: 1800px;
  margin-bottom: 1vh;
}

.prompt-template-dialog .el-dialog__body {
  max-height: calc(98vh - 100px);
  overflow-y: auto;
}

.prompt-template-tabs .el-tabs__content {
  overflow: visible;
}

.prompt-template-editor-item .el-form-item__content {
  width: 100%;
}
</style>
