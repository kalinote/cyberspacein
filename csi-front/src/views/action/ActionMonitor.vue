<template>
  <div>
    <Header />
    
    <!-- 英雄区域 -->
    <section class="bg-linear-to-br from-blue-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">行动</span>部署中心</h1>
            <p class="text-gray-600 text-lg mb-6">统一管理信息收集、处理、存储、分析行动，从资源调配、目标设定到行动执行的全流程控制平台。</p>
            <div class="flex flex-wrap gap-4">
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:file-document-multiple" class="text-blue-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">蓝图数量</p>
                  <!-- 占位数据，等待后端API完成 -->
                  <p class="text-xl font-bold text-gray-900">328</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:target" class="text-green-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">执行中行动</p>
                  <!-- 占位数据，等待后端API完成 -->
                  <p class="text-xl font-bold text-gray-900">12</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:timeline-clock" class="text-amber-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">已完成行动</p>
                  <!-- 占位数据，等待后端API完成 -->
                  <p class="text-xl font-bold text-gray-900">47</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">快速部署行动</h3>
            <div class="space-y-4">
              <button class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2" @click="router.push('/action/new')">
                <Icon icon="mdi:rocket-launch-outline" />
                <span>新建标准行动蓝图</span>
              </button>
              <button class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2" @click="router.push('/action/resource-config')">
                <Icon icon="mdi:server-network" />
                <span>行动资源配置</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2" @click="router.push('/action/history')">
                <Icon icon="mdi:history" />
                <span>查看历史行动</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 置顶行动蓝图 -->
    <section class="py-12 bg-linear-to-b from-white to-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:file-document-multiple" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">置顶</span>行动蓝图</span>
          </h2>
          <el-button type="primary" link @click="router.push('/action/blueprints')">
            <template #icon><Icon icon="mdi:arrow-right" /></template>
            查看全部蓝图
          </el-button>
        </div>

        <p class="text-sm text-gray-500 mb-6">展示全部已置顶蓝图，置顶设置对所有用户生效。</p>
        <div v-loading="loadingBlueprints" :element-loading-text="'加载中...'" class="min-h-[200px]">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
            <ActionBlueprintCard
              v-for="blueprint in commonBlueprints"
              :key="blueprint.id"
              :blueprint="blueprint"
              :disabled="actionStarting"
              @pin-change="commonBlueprints = commonBlueprints.filter(item => item.id !== blueprint.id)"
              @view="viewBlueprint(blueprint)"
              @edit="editBlueprint(blueprint)"
              @publish="openPublishDialog(blueprint)"
              @encapsulate="openEncapsulateDialog(blueprint)"
              @history="openRevisionHistory(blueprint)"
              @branch="createBranchVersion(blueprint)"
              @run="createActionFromBlueprint(blueprint, false, $event)"
              @debug="createActionFromBlueprint(blueprint, true, $event)"
              @delete="handleDeleteBlueprint(blueprint)"
            />
          </div>

          <div v-if="!loadingBlueprints && commonBlueprints.length === 0" class="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-300">
            <Icon icon="mdi:file-document-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">暂无置顶蓝图</p>
            <p class="text-gray-400 text-sm">在全部蓝图中点击置顶，即可在此处展示。</p>
            <el-button type="primary" link class="mt-4" @click="router.push('/action/blueprints')">
              去置顶蓝图
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- 资源管理 -->
    <section class="py-12 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:server-network" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">资源</span>管理</span>
          </h2>
          <el-button type="primary" link>
            <template #icon><Icon icon="mdi:settings" /></template>
            资源配置
          </el-button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 border border-blue-100 shadow-sm cursor-pointer">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:server" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">代理网络</h3>
                  <p class="text-sm text-gray-500">全球接入节点</p>
                </div>
              </div>
              <span class="text-green-600 font-bold">87%</span>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">可用节点</span>
                  <span class="font-medium">152/175</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-green-500 rounded-full" style="width: 87%"></div>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 pt-3">
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">响应延迟</p>
                  <p class="text-lg font-bold text-gray-900">≤2.1s</p>
                </div>
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">可用地区</p>
                  <p class="text-lg font-bold text-gray-900">24</p>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-linear-to-br from-amber-50 to-white rounded-2xl p-6 border border-amber-100 shadow-sm cursor-pointer">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-amber-500 to-orange-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:account-key" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">采集账号</h3>
                  <p class="text-sm text-gray-500">平台身份资源</p>
                </div>
              </div>
              <span class="text-amber-600 font-bold">64%</span>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">可用账号</span>
                  <span class="font-medium">89/139</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-amber-500 rounded-full" style="width: 64%"></div>
                </div>
              </div>
              <div class="grid grid-cols-3 gap-2 pt-3">
                <div class="text-center p-2 bg-white rounded-lg">
                  <p class="text-xs text-gray-500">社交</p>
                  <p class="text-sm font-bold text-gray-900">42</p>
                </div>
                <div class="text-center p-2 bg-white rounded-lg">
                  <p class="text-xs text-gray-500">论坛</p>
                  <p class="text-sm font-bold text-gray-900">31</p>
                </div>
                <div class="text-center p-2 bg-white rounded-lg">
                  <p class="text-xs text-gray-500">新闻</p>
                  <p class="text-sm font-bold text-gray-900">16</p>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-linear-to-br from-purple-50 to-white rounded-2xl p-6 border border-purple-100 shadow-sm cursor-pointer">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center space-x-3">
                <div class="w-12 h-12 bg-linear-to-br from-purple-500 to-pink-400 rounded-xl flex items-center justify-center">
                  <Icon icon="mdi:cube-outline" class="text-white text-2xl" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">沙盒容器</h3>
                  <p class="text-sm text-gray-500">隔离执行环境</p>
                </div>
              </div>
              <span class="text-purple-600 font-bold">92%</span>
            </div>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">可用容器</span>
                  <span class="font-medium">46/50</span>
                </div>
                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full bg-purple-500 rounded-full" style="width: 92%"></div>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 pt-3">
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">CPU负载</p>
                  <p class="text-lg font-bold text-gray-900">34%</p>
                </div>
                <div class="text-center p-3 bg-white rounded-lg">
                  <p class="text-sm text-gray-500">内存使用</p>
                  <p class="text-lg font-bold text-gray-900">61%</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 行动执行监控 -->
    <section class="py-12 bg-linear-to-b from-gray-50 to-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:monitor-dashboard" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">行动</span>执行监控</span>
          </h2>
          <el-button type="primary" link @click="router.push('/action/history')">
            <template #icon><Icon icon="mdi:arrow-right" /></template>
            查看历史行动
          </el-button>
        </div>

        <!-- 正在执行的行动 -->
        <div class="mb-12">
          <div v-loading="loadingRunningActions" :element-loading-text="'加载中...'" class="min-h-[200px]">
            <div v-if="runningActions.length === 0" class="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-300">
              <Icon icon="mdi:play-circle-outline" class="text-6xl text-gray-300 mb-4" />
              <p class="text-gray-500 text-lg mb-2">暂无正在执行的行动</p>
              <p class="text-gray-400 text-sm">创建新行动后，执行中的行动将显示在这里</p>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div
                v-for="action in runningActions"
                :key="action.id"
                class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-all hover:border-blue-300"
              >
                <div class="flex items-start justify-between mb-4">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-2">
                      <h3 class="text-lg font-bold text-gray-900 line-clamp-1">{{ action.name }}</h3>
                      <el-tag
                        v-if="action.debug"
                        size="small"
                        effect="plain"
                        class="shrink-0 border-slate-300! text-slate-600! bg-slate-50!"
                      >
                        调试
                      </el-tag>
                      <el-tag size="small" effect="plain" type="info" class="shrink-0">
                        {{ action.schedulingMode === 'streaming' ? '异步执行' : '同步执行' }}
                      </el-tag>
                    </div>
                    <p class="text-sm text-gray-600 line-clamp-2 mb-3">{{ action.description }}</p>
                  </div>
                  <div class="ml-3 shrink-0">
                    <div
                      :class="['w-12 h-12 rounded-xl flex items-center justify-center', getActionStatusIcon(action.status).bgClass]"
                    >
                      <Icon
                        :icon="getActionStatusIcon(action.status).icon"
                        :class="['text-2xl', getActionStatusIcon(action.status).iconClass]"
                      />
                    </div>
                  </div>
                </div>

                <div class="space-y-3 mb-4">
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:clock-outline" class="text-blue-500" />
                      开始时间
                    </span>
                    <span class="font-medium text-gray-900">{{ formatTime(action.startTime) }}</span>
                  </div>
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:progress-clock" class="text-green-500" />
                      运行时长
                    </span>
                    <span class="font-medium text-gray-900">{{ formatDuration(action.duration) }}</span>
                  </div>
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-500 flex items-center gap-2">
                      <Icon icon="mdi:chart-line" class="text-purple-500" />
                      完成进度
                    </span>
                    <span class="font-medium text-gray-900">{{ action.progress }}%</span>
                  </div>
                </div>

                <div class="mb-4">
                  <div class="flex justify-between text-xs text-gray-600 mb-1">
                    <span>执行进度</span>
                    <span>{{ action.completedSteps }}/{{ action.totalSteps }} 步骤</span>
                  </div>
                  <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      class="h-full bg-linear-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
                      :style="{ width: action.progress + '%' }"
                    ></div>
                  </div>
                </div>

                <div class="flex items-center gap-2 pt-4 border-t border-gray-200">
                  <el-button type="primary" link size="small" class="flex-1" @click="viewActionDetail(action.id)">
                    <template #icon><Icon icon="mdi:eye" /></template>
                    查看详情
                  </el-button>
                  <el-button
                    v-if="action.status === ACTION_STATUS.RUNNING"
                    type="warning"
                    link
                    size="small"
                    @click="pauseAction(action.id)"
                  >
                    <template #icon><Icon icon="mdi:pause" /></template>
                    暂停
                  </el-button>
                  <el-button
                    v-else-if="action.status === ACTION_STATUS.PAUSED"
                    type="success"
                    link
                    size="small"
                    @click="resumeAction(action.id)"
                  >
                    <template #icon><Icon icon="mdi:play" /></template>
                    恢复
                  </el-button>
                  <el-button type="danger" link size="small" @click="stopAction(action.id)">
                    <template #icon><Icon icon="mdi:stop" /></template>
                    停止
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 监控数据 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-red-100">
            <h3 class="text-lg font-bold text-gray-900 mb-6">当前行动状态</h3>
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 bg-linear-to-r from-red-50 to-white rounded-xl border border-red-200">
                <div class="flex items-center space-x-3">
                  <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                    <Icon icon="mdi:alert-circle" class="text-red-600 text-xl" />
                  </div>
                  <div>
                    <p class="font-medium text-gray-900">异常行为检测</p>
                    <p class="text-sm text-gray-500">3个代理节点响应异常</p>
                  </div>
                </div>
                <el-button type="danger" link size="small">查看详情</el-button>
              </div>

              <div class="flex items-center justify-between p-4 bg-linear-to-r from-green-50 to-white rounded-xl border border-green-200">
                <div class="flex items-center space-x-3">
                  <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                    <Icon icon="mdi:check-circle" class="text-green-600 text-xl" />
                  </div>
                  <div>
                    <p class="font-medium text-gray-900">数据采集流量</p>
                    <p class="text-sm text-gray-500">平均 2.4GB/小时，正常</p>
                  </div>
                </div>
                <div class="text-green-600 text-sm font-medium">+12%</div>
              </div>

              <div class="flex items-center justify-between p-4 bg-linear-to-r from-blue-50 to-white rounded-xl border border-blue-200">
                <div class="flex items-center space-x-3">
                  <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Icon icon="mdi:chart-line" class="text-blue-600 text-xl" />
                  </div>
                  <div>
                    <p class="font-medium text-gray-900">任务成功率</p>
                    <p class="text-sm text-gray-500">今日成功 147/150 任务</p>
                  </div>
                </div>
                <div class="text-blue-600 text-sm font-medium">98%</div>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-lg border border-red-100">
            <h3 class="text-lg font-bold text-gray-900 mb-6">资源使用热图</h3>
            <div class="grid grid-cols-4 gap-3">
              <div class="col-span-4 h-6 bg-linear-to-r from-green-400 via-yellow-400 to-red-500 rounded-full mb-2"></div>
              <div class="text-center">
                <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mx-auto mb-2">
                  <Icon icon="mdi:server" class="text-green-600 text-2xl" />
                </div>
                <p class="text-xs text-gray-600">美洲节点</p>
                <p class="text-sm font-bold text-gray-900">42%</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 bg-yellow-100 rounded-xl flex items-center justify-center mx-auto mb-2">
                  <Icon icon="mdi:server" class="text-yellow-600 text-2xl" />
                </div>
                <p class="text-xs text-gray-600">欧洲节点</p>
                <p class="text-sm font-bold text-gray-900">68%</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center mx-auto mb-2">
                  <Icon icon="mdi:server" class="text-orange-600 text-2xl" />
                </div>
                <p class="text-xs text-gray-600">亚洲节点</p>
                <p class="text-sm font-bold text-gray-900">79%</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center mx-auto mb-2">
                  <Icon icon="mdi:server" class="text-red-600 text-2xl" />
                </div>
                <p class="text-xs text-gray-600">大洋洲节点</p>
                <p class="text-sm font-bold text-gray-900">91%</p>
              </div>
            </div>
            <div class="mt-6 pt-6 border-t border-gray-200">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">建议操作</span>
                <el-button type="primary" link size="small">优化资源分配</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 蓝图流程图弹窗 -->
    <BlueprintFlowDialog
      v-model="blueprintDialogVisible"
      :blueprint-id="selectedBlueprintId"
    />

    <!-- 模板参数输入弹窗 -->
    <TemplateParamsDialog
      v-model="templateParamsDialogVisible"
      :blueprint-id="selectedBlueprintForRun?.id"
      :debug="selectedRunDebug"
      :scheduling-mode="selectedRunSchedulingMode"
      :submitting="actionStarting"
      @submit="handleParamsSubmit"
    />
    <BlueprintPublishDialog
      v-model="publishDialogVisible"
      :submitting="publishing"
      @submit="handlePublish"
    />
    <BlueprintEncapsulateDialog
      v-model="encapsulateDialogVisible"
      :interfaces="encapsulateInterfaces"
      :target-nodes="encapsulatedTargetNodes"
      :submitting="encapsulating"
      @submit="handleEncapsulate"
    />
    <el-dialog v-model="revisionDialogVisible" title="蓝图发布历史" width="720px">
      <el-table v-loading="revisionsLoading" :data="revisions" size="small">
        <el-table-column prop="revision_number" label="Revision" width="100" />
        <el-table-column prop="version" label="蓝图版本" width="120" />
        <el-table-column label="内容哈希" min-width="220">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.content_hash?.slice(0, 16) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" min-width="180">
          <template #default="{ row }">{{ formatPublishedAt(row.published_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!revisionsLoading && revisions.length === 0"
        description="尚未发布 Revision"
        :image-size="56"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Header from '@/components/Header.vue'
import ActionBlueprintCard from '@/components/action/ActionBlueprintCard.vue'
import BlueprintFlowDialog from '@/components/action/BlueprintFlowDialog.vue'
import TemplateParamsDialog from '@/components/action/template/TemplateParamsDialog.vue'
import BlueprintPublishDialog from '@/components/action/BlueprintPublishDialog.vue'
import BlueprintEncapsulateDialog from '@/components/action/BlueprintEncapsulateDialog.vue'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { ACTION_STATUS, getActionStatusIcon } from '@/utils/action'
import { buildActionRunRequest } from '@/utils/action/run'

defineOptions({ name: 'Action' })

const router = useRouter()
const blueprintDialogVisible = ref(false)
const selectedBlueprintId = ref(null)
const templateParamsDialogVisible = ref(false)
const selectedBlueprintForRun = ref(null)
const selectedRunDebug = ref(false)
const selectedRunSchedulingMode = ref('barrier')
const actionStarting = ref(false)
const selectedBlueprintForRelease = ref(null)
const publishDialogVisible = ref(false)
const encapsulateDialogVisible = ref(false)
const publishing = ref(false)
const encapsulating = ref(false)
const encapsulateInterfaces = ref([])
const encapsulatedTargetNodes = ref([])
const revisionDialogVisible = ref(false)
const revisionsLoading = ref(false)
const revisions = ref([])
const loadingRunningActions = ref(false)
const loadingBlueprints = ref(false)
const runningActions = ref([])
const commonBlueprints = ref([])
const formatPublishedAt = value => (
  value ? new Date(value).toLocaleString('zh-CN') : '-'
)

async function createActionFromBlueprint(
  blueprint,
  debug = false,
  schedulingMode = blueprint?.defaultSchedulingMode || 'barrier'
) {
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }

  if (debug && !blueprint.isTemplate) {
    try {
      await ElMessageBox.confirm(
        '调试运行会启用蓝图中的调试输出节点，并将接收到的数据写入行动日志。',
        '调试运行',
        {
          confirmButtonText: '开始调试',
          cancelButtonText: '取消',
          type: 'info'
        }
      )
    } catch {
      return
    }
  }

  selectedRunDebug.value = debug
  selectedRunSchedulingMode.value = schedulingMode === 'streaming' ? 'streaming' : 'barrier'
  if (blueprint.isTemplate) {
    templateParamsDialogVisible.value = true
    selectedBlueprintForRun.value = blueprint
  } else {
    await runBlueprint(blueprint.id, null, debug, selectedRunSchedulingMode.value)
  }
}

async function runBlueprint(blueprintId, params, debug = false, schedulingMode = 'barrier') {
  if (actionStarting.value) return false
  actionStarting.value = true
  try {
    const data = buildActionRunRequest(blueprintId, params, debug, schedulingMode)

    const response = await actionApi.runAction(data)

    if (response.code === 0 && response.data && response.data.action_id) {
      ElMessage.success('行动已创建并开始执行')
      router.push(`/action/${response.data.action_id}`)
      return true
    } else {
      ElMessage.error(response.message || '创建行动失败')
      return false
    }
  } catch (error) {
    console.error('创建行动失败:', error)
    ElMessage.error(error.message || '创建行动失败，请稍后重试')
    return false
  } finally {
    actionStarting.value = false
  }
}

async function handleParamsSubmit(params) {
  const started = await runBlueprint(
    selectedBlueprintForRun.value.id,
    params,
    selectedRunDebug.value,
    selectedRunSchedulingMode.value
  )
  if (started) templateParamsDialogVisible.value = false
}

function createBranchVersion(blueprint) {
  ElMessage.info('创建分支版本功能开发中...')
}

function editBlueprint(blueprint) {
  if (!blueprint?.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }
  router.push({
    name: 'edit-action-blueprint',
    params: { blueprintId: blueprint.id }
  })
}

function openPublishDialog(blueprint) {
  selectedBlueprintForRelease.value = blueprint
  publishDialogVisible.value = true
}

async function openRevisionHistory(blueprint) {
  if (!blueprint?.id || revisionsLoading.value) return
  revisionDialogVisible.value = true
  revisionsLoading.value = true
  revisions.value = []
  try {
    const response = await actionApi.getBlueprintRevisions(blueprint.id)
    revisions.value = response.data || []
  } catch {
    revisions.value = []
  } finally {
    revisionsLoading.value = false
  }
}

async function openEncapsulateDialog(blueprint) {
  selectedBlueprintForRelease.value = blueprint
  try {
    const [detailResponse, nodesResponse, validationResponse] = await Promise.all([
      actionApi.getBlueprint(blueprint.id),
      actionApi.getNodes(),
      actionApi.validateBlueprint(blueprint.id)
    ])
    const validation = validationResponse.data || {}
    if (!validation.valid) {
      ElMessage.error(validation.errors?.[0]?.message || '蓝图校验未通过')
      return
    }
    const detail = detailResponse.data || {}
    const interfaceSpec = detail.interface || validation.interface || {}
    encapsulateInterfaces.value = [
      ...(interfaceSpec.inputs || []),
      ...(interfaceSpec.outputs || [])
    ].map(item => ({
      ...item,
      interfaceTypeId: item.interface_type_id
    }))
    encapsulatedTargetNodes.value = (nodesResponse.data || []).filter(node => (
      node.node_kind === 'encapsulated'
      && node.source_blueprint_id === blueprint.id
      && node.is_latest
    ))
    encapsulateDialogVisible.value = true
  } catch (error) {
    console.error('准备封装蓝图失败:', error)
    ElMessage.error('准备封装蓝图失败')
  }
}

async function handlePublish() {
  const blueprint = selectedBlueprintForRelease.value
  if (!blueprint?.id) return
  publishing.value = true
  try {
    const response = await actionApi.publishBlueprint(blueprint.id)
    ElMessage.success(`已发布 Revision ${response.data?.revision?.revision_number || ''}`)
    publishDialogVisible.value = false
    await fetchCommonBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  } finally {
    publishing.value = false
  }
}

async function handleEncapsulate(form) {
  const blueprint = selectedBlueprintForRelease.value
  if (!blueprint?.id) return
  encapsulating.value = true
  try {
    const response = await actionApi.encapsulateBlueprint(blueprint.id, form)
    ElMessage.success(`已生成封装节点 ${response.data?.encapsulated_node?.name || ''}`)
    encapsulateDialogVisible.value = false
    await fetchCommonBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  } finally {
    encapsulating.value = false
  }
}

async function handleDeleteBlueprint(blueprint) {
  try {
    await ElMessageBox.confirm(
      `确定要删除蓝图“${blueprint.title}”吗？其所有历史行动和运行日志也将被永久删除，此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    ElMessage.info('已取消删除')
    return
  }

  try {
    await actionApi.deleteBlueprint(blueprint.id)
    ElMessage.success('蓝图及历史行动已删除')
    await fetchCommonBlueprints()
  } catch {
    // 请求层统一展示后端错误信息
  }
}

function viewSteps(blueprintId) {
  ElMessage.error(`[尚未实现] 查看步骤: ${blueprintId}`)
}

function formatImplementationPeriod(seconds) {
  if (!seconds || seconds <= 0) {
    return '未设置'
  }

  const oneDay = 24 * 3600
  const oneHour = 3600
  const oneMinute = 60

  if (seconds >= oneDay) {
    const days = Math.floor(seconds / oneDay)
    return `${days}天`
  } else if (seconds >= oneHour) {
    const hours = Math.floor(seconds / oneHour)
    return `${hours}小时`
  } else if (seconds >= oneMinute) {
    const minutes = Math.floor(seconds / oneMinute)
    return `${minutes}分钟`
  } else {
    return `${seconds}秒`
  }
}

async function fetchRunningActions() {
  loadingRunningActions.value = true
  try {
    const result = await getPaginatedData(actionApi.getActionHistory, {
      page: 1,
      page_size: 100
    })
    runningActions.value = (result.items || [])
      .filter(item => [ACTION_STATUS.RUNNING, ACTION_STATUS.PAUSED].includes(item.status))
      .slice(0, 3)
      .map(item => ({
        ...item,
        startTime: item.start_at || null,
        endTime: item.finished_at || null,
        completedSteps: item.completed_steps || 0,
        totalSteps: item.total_steps || 0,
        duration: item.duration ? item.duration * 1000 : 0,
        progress: item.progress ?? 0,
        schedulingMode: item.scheduling_mode === 'streaming' ? 'streaming' : 'barrier'
      }))
  } catch (error) {
    console.error('获取行动列表失败:', error)
    runningActions.value = []
  } finally {
    loadingRunningActions.value = false
  }
}

async function fetchCommonBlueprints() {
  loadingBlueprints.value = true
  try {
    const items = []
    let page = 1
    let totalPages = 1
    // 逐页取完置顶蓝图，展示数量不受接口单页上限影响。
    do {
      const response = await actionApi.getBlueprintsBaseInfo({
        page,
        page_size: 100,
        is_pinned: true
      })
      // 兼容统一响应封装和直接返回的分页数据。
      const result = response.code === 0 ? response.data : response
      items.push(...result.items)
      totalPages = result.total_pages
      page += 1
    } while (page <= totalPages)

    commonBlueprints.value = items.map(item => {
      return {
        id: item.id,
        title: item.name || '',
        taskType: item.default_scheduling_mode === 'streaming' ? '异步执行' : '',
        taskTypeTagColor: item.type_tag_color || '#dbeafe',
        taskTypeTagTextColor: item.type_text_color || '#1e40af',
        taskGoal: item.target || '',
        resourceAllocation: '未配置',
        executionDeadline: formatImplementationPeriod(item.implementation_period),
        branchCount: item.branches || 0,
        stepCount: item.steps || 0,
        isTemplate: item.is_template || false,
        isPinned: item.is_pinned || false,
        defaultSchedulingMode: item.default_scheduling_mode === 'streaming' ? 'streaming' : 'barrier',
        latestRevisionNumber: item.latest_revision_number,
        encapsulatedNodeCount: item.encapsulated_node_count || 0
      }
    })
  } catch (error) {
    ElMessage.error('获取行动蓝图失败')
    commonBlueprints.value = []
  } finally {
    loadingBlueprints.value = false
  }
}

function formatTime(date) {
  if (!date) return '未知'
  const d = new Date(date)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDuration(ms) {
  if (!ms) return '0分钟'
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    return `${hours}小时${minutes % 60}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟`
  } else {
    return `${seconds}秒`
  }
}

function viewActionDetail(actionId) {
  router.push(`/action/${actionId}`)
}

async function pauseAction(actionId) {
  try {
    await ElMessageBox.confirm('确定要暂停此行动吗？', '确认暂停', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await actionApi.pauseAction(actionId)
    if (response.code !== 0) {
      ElMessage.error(response.message || '暂停行动失败')
      return
    }
    ElMessage.success(response.message || '行动已暂停')
    await fetchRunningActions()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.message || '暂停行动失败')
    }
  }
}

async function resumeAction(actionId) {
  try {
    const response = await actionApi.resumeAction(actionId)
    if (response.code !== 0) {
      ElMessage.error(response.message || '恢复行动失败')
      return
    }
    ElMessage.success(response.message || '行动已恢复')
    await fetchRunningActions()
  } catch (error) {
    ElMessage.error(error?.message || '恢复行动失败')
  }
}

async function stopAction(actionId) {
  try {
    await ElMessageBox.confirm('确定要停止此行动吗？此操作不可恢复。', '确认停止', {
      confirmButtonText: '确定停止',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await actionApi.stopAction(actionId)
    if (response.code !== 0) {
      ElMessage.error(response.message || '停止行动失败')
      return
    }
    ElMessage.success(response.message || '行动已停止')
    await fetchRunningActions()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.message || '停止行动失败')
    }
  }
}

function handleBlueprintDialogOpen() {
  blueprintDialogVisible.value = true
}

function handleBlueprintDialogClose() {
  blueprintDialogVisible.value = false
}

async function viewBlueprint(blueprint) {
  if (!blueprint || !blueprint.id) {
    ElMessage.error('蓝图ID不存在')
    return
  }
  selectedBlueprintId.value = blueprint.id
  blueprintDialogVisible.value = true
}

onMounted(() => {
  fetchRunningActions()
})

onActivated(fetchCommonBlueprints)
</script>


