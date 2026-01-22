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
              <button class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2" @click="$router.push('/action/new')">
                <Icon icon="mdi:rocket-launch-outline" />
                <span>新建标准行动蓝图</span>
              </button>
              <button class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2" @click="$router.push('/action/resource-config')">
                <Icon icon="mdi:server-network" />
                <span>行动资源配置</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2" @click="$router.push('/action/history')">
                <Icon icon="mdi:history" />
                <span>查看历史行动</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 最新行动蓝图 -->
    <section class="py-12 bg-linear-to-b from-white to-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:file-document-multiple" class="text-blue-600 text-2xl" />
            <span><span class="text-blue-500">行动</span>蓝图</span>
          </h2>
          <el-button type="primary" link @click="$router.push('/action/blueprints')">
            <template #icon><Icon icon="mdi:arrow-right" /></template>
            查看全部蓝图
          </el-button>
        </div>

        <div v-loading="loadingBlueprints" :element-loading-text="'加载中...'" class="min-h-[200px]">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
            <div 
              v-for="(blueprint, index) in commonBlueprints" 
              :key="index"
              class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow flex flex-col"
            >
          <div class="mb-4">
            <h3 class="text-xl font-bold text-gray-900 mb-4">{{ blueprint.title }}</h3>
            <div class="flex items-center gap-2 flex-wrap">
              <el-tag 
                class="border-0" 
                :style="{ backgroundColor: blueprint.taskTypeTagColor, color: blueprint.taskTypeTagTextColor }"
              >
                {{ blueprint.taskType }}
              </el-tag>
              <el-tag 
                v-if="blueprint.isTemplate"
                type="warning"
                class="border-0"
              >
                模板
              </el-tag>
            </div>
          </div>

            <div class="space-y-3 mb-6 flex-1">
              <div class="flex items-start space-x-3">
                <Icon icon="mdi:target" class="text-blue-500 text-lg mt-0.5 shrink-0" />
                <div class="flex-1">
                  <p class="text-sm text-gray-500 mb-1">任务目标</p>
                  <p class="text-sm font-medium text-gray-900">{{ blueprint.taskGoal }}</p>
                </div>
              </div>

              <div class="flex items-start space-x-3">
                <Icon icon="mdi:server-network" class="text-green-500 text-lg mt-0.5 shrink-0" />
                <div class="flex-1">
                  <p class="text-sm text-gray-500 mb-1">资源分配</p>
                  <p class="text-sm font-medium text-gray-900">{{ blueprint.resourceAllocation }}</p>
                </div>
              </div>

              <div class="flex items-start space-x-3">
                <Icon icon="mdi:format-list-numbered" class="text-purple-500 text-lg mt-0.5 shrink-0" />
                <div class="flex-1">
                  <p class="text-sm text-gray-500 mb-1">行动步骤</p>
                  
                  <div class="flex items-center flex-wrap gap-2 text-sm font-medium text-gray-900">
                    <span>{{ blueprint.branchCount }} 个分支，共{{ blueprint.stepCount }} 个步骤</span>
                    <div @click="viewBlueprint(blueprint)" class="text-blue-500 cursor-pointer hover:text-blue-600 transition-colors">
                      查看
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex items-start space-x-3">
                <Icon icon="mdi:calendar-clock" class="text-amber-500 text-lg mt-0.5 shrink-0" />
                <div class="flex-1">
                  <p class="text-sm text-gray-500 mb-1">执行期限</p>
                  <p class="text-sm font-medium text-gray-900">{{ blueprint.executionDeadline }}</p>
                </div>
              </div>
            </div>

            <div class="pt-4 border-t border-gray-200 flex flex-col gap-2 mt-auto">
              <el-button 
                type="primary" 
                class="w-full ml-0!" 
                @click="createActionFromBlueprint(blueprint)"
              >
                <template #icon><Icon icon="mdi:rocket-launch" /></template>
                立即执行行动
              </el-button>
              <el-button 
                plain 
                class="w-full ml-0!" 
                @click="createBranchVersion(blueprint)"
              >
                <template #icon><Icon icon="mdi:source-branch" /></template>
                从此蓝图创建分支
              </el-button>
              <el-button 
                plain 
                class="w-full ml-0! text-red-500! border-red-500! " 
                @click="removeFromCommonBlueprints(index)"
              >
                <template #icon><Icon icon="mdi:delete-outline" /></template>
                删除该蓝图
              </el-button>
            </div>
          </div>
          </div>

          <div v-if="!loadingBlueprints && commonBlueprints.length === 0" class="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-300">
            <Icon icon="mdi:file-document-outline" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">暂无行动蓝图</p>
            <p class="text-gray-400 text-sm">创建新蓝图后，将显示在这里</p>
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
          <el-button type="primary" link @click="$router.push('/action/history')">
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
                    <h3 class="text-lg font-bold text-gray-900 mb-2 line-clamp-1">{{ action.name }}</h3>
                    <p class="text-sm text-gray-600 line-clamp-2 mb-3">{{ action.description }}</p>
                  </div>
                  <div class="ml-3 shrink-0">
                    <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center animate-pulse">
                      <Icon icon="mdi:loading" class="text-blue-600 text-2xl animate-spin" />
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
                  <el-button type="warning" link size="small" @click="pauseAction(action.id)">
                    <template #icon><Icon icon="mdi:pause" /></template>
                    暂停
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
      @submit="handleParamsSubmit"
    />
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import BlueprintFlowDialog from '@/components/action/BlueprintFlowDialog.vue'
import TemplateParamsDialog from '@/components/action/template/TemplateParamsDialog.vue'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'

export default {
  name: 'Action',
  components: {
    Header,
    Icon,
    BlueprintFlowDialog,
    TemplateParamsDialog
  },
  data() {
    return {
      blueprintDialogVisible: false,
      selectedBlueprintId: null,
      templateParamsDialogVisible: false,
      selectedBlueprintForRun: null,
      loadingRunningActions: false,
      loadingBlueprints: false,
      // 占位数据：模拟正在执行的行动，等待后端API完成
      runningActions: [
        {
          id: 'action-001',
          name: '社交媒体舆情监控',
          description: '监控Twitter、Reddit等平台的技术讨论趋势和热点话题',
          startTime: new Date(Date.now() - 2 * 3600 * 1000),
          duration: 2 * 3600 * 1000,
          progress: 45,
          completedSteps: 5,
          totalSteps: 11
        },
        {
          id: 'action-002',
          name: '技术论坛情报收集',
          description: '收集Stack Overflow、GitHub等平台的技术漏洞和安全信息',
          startTime: new Date(Date.now() - 5 * 3600 * 1000),
          duration: 5 * 3600 * 1000,
          progress: 78,
          completedSteps: 7,
          totalSteps: 9
        },
        {
          id: 'action-003',
          name: '新闻媒体事件追踪',
          description: '追踪全球主要新闻媒体的网络安全相关报道和事件',
          startTime: new Date(Date.now() - 30 * 60 * 1000),
          duration: 30 * 60 * 1000,
          progress: 12,
          completedSteps: 1,
          totalSteps: 8
        }
      ],
      commonBlueprints: []
    }
  },
  
  methods: {
    async createActionFromBlueprint(blueprint) {
      if (!blueprint || !blueprint.id) {
        this.$message.error('蓝图ID不存在')
        return
      }

      if (blueprint.isTemplate) {
        this.templateParamsDialogVisible = true
        this.selectedBlueprintForRun = blueprint
      } else {
        await this.runBlueprint(blueprint.id, null)
      }
    },

    async runBlueprint(blueprintId, params) {
      try {
        const data = { blueprint_id: blueprintId }
        if (params) {
          data.params = params
        }

        const response = await actionApi.runAction(data)

        if (response.code === 0 && response.data && response.data.action_id) {
          this.$message.success('行动已创建并开始执行')
          this.$router.push(`/action/${response.data.action_id}`)
        } else {
          this.$message.error(response.message || '创建行动失败')
        }
      } catch (error) {
        console.error('创建行动失败:', error)
        this.$message.error(error.message || '创建行动失败，请稍后重试')
      }
    },

    async handleParamsSubmit(params) {
      await this.runBlueprint(this.selectedBlueprintForRun.id, params)
      this.templateParamsDialogVisible = false
    },
    
    // 占位方法：创建蓝图分支版本，等待后端API完成
    createBranchVersion(blueprint) {
      this.$message.info(`创建分支版本功能开发中...`)
    },
    
    removeFromCommonBlueprints(index) {
      this.$confirm('确定要删除此蓝图吗？', '确认删除', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.commonBlueprints.splice(index, 1)
        this.$message.success('已删除')
      }).catch(() => {
        this.$message.info('已取消删除')
      })
    },

    viewSteps(blueprintId) {
      this.$message.error(`[尚未实现] 查看步骤: ${blueprintId}`)
    },

    formatImplementationPeriod(seconds) {
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
    },

    async fetchCommonBlueprints() {
      this.loadingBlueprints = true
      try {
        const result = await getPaginatedData(
          actionApi.getBlueprintsBaseInfo,
          { page: 1, page_size: 6 }
        )
        
        this.commonBlueprints = (result.items || []).map(item => {
          return {
            id: item.id,
            title: item.name || '',
            taskType: item.type || '尚未实现',
            taskTypeTagColor: item.type_tag_color || '#dbeafe',
            taskTypeTagTextColor: item.type_text_color || '#1e40af',
            taskGoal: item.target || '',
            resourceAllocation: '未配置',
            executionDeadline: this.formatImplementationPeriod(item.implementation_period),
            branchCount: item.branches || 0,
            stepCount: item.steps || 0,
            isTemplate: item.is_template || false
          }
        })
      } catch (error) {
        this.$message.error('获取行动蓝图失败')
        this.commonBlueprints = []
      } finally {
        this.loadingBlueprints = false
      }
    },

    formatTime(date) {
      if (!date) return '未知'
      const d = new Date(date)
      return d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    },

    formatDuration(ms) {
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
    },

    viewActionDetail(actionId) {
      this.$router.push(`/action/${actionId}`)
    },

    // 占位方法：暂停行动，等待后端API完成
    pauseAction(actionId) {
      this.$confirm('确定要暂停此行动吗？', '确认暂停', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.$message.success('行动已暂停')
      }).catch(() => {
        this.$message.info('已取消暂停')
      })
    },

    // 占位方法：停止行动，等待后端API完成
    stopAction(actionId) {
      this.$confirm('确定要停止此行动吗？此操作不可恢复。', '确认停止', {
        confirmButtonText: '确定停止',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.$message.success('行动已停止')
      }).catch(() => {
        this.$message.info('已取消停止')
      })
    },

    handleBlueprintDialogOpen() {
      this.blueprintDialogVisible = true
    },

    handleBlueprintDialogClose() {
      this.blueprintDialogVisible = false
    },

    async viewBlueprint(blueprint) {
      if (!blueprint || !blueprint.id) {
        this.$message.error('蓝图ID不存在')
        return
      }
      this.selectedBlueprintId = blueprint.id
      this.blueprintDialogVisible = true
    },
  },
  
  mounted() {
    this.fetchCommonBlueprints()
  }
}
</script>


