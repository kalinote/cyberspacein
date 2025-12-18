<template>
  <div>
    <Header />
    
    <section class="bg-linear-to-br from-red-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-red-500">告警</span>信息中心</h1>
            <p class="text-gray-600 text-lg mb-6">实时监控系统运行状态，及时发现并处理告警事件，保障系统稳定运行。</p>
            <div class="flex flex-wrap gap-4">
              <div class="bg-white rounded-xl p-4 shadow-sm border border-red-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:alert-circle" class="text-red-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">总告警数</p>
                  <p class="text-xl font-bold text-gray-900">{{ alertStats.total }}</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-red-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:alert" class="text-amber-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">正在告警</p>
                  <p class="text-xl font-bold text-gray-900">{{ alertStats.active }}</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-red-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:check-circle" class="text-green-600 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">已恢复</p>
                  <p class="text-xl font-bold text-gray-900">{{ alertStats.recovered }}</p>
                </div>
              </div>
              <div class="bg-white rounded-xl p-4 shadow-sm border border-red-100 flex items-center space-x-3">
                <div class="w-10 h-10 bg-red-200 rounded-lg flex items-center justify-center">
                  <Icon icon="mdi:skull" class="text-red-700 text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">致命告警</p>
                  <p class="text-xl font-bold text-red-700">{{ alertStats.critical }}</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-red-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">告警规则管理</h3>
            <div class="space-y-4">
              <button class="w-full bg-red-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2">
                <Icon icon="mdi:plus-circle-outline" />
                <span>新建告警规则</span>
              </button>
              <button class="w-full border-2 border-red-200 text-red-600 py-3 rounded-lg font-medium hover:bg-red-50 transition-colors flex items-center justify-center space-x-2">
                <Icon icon="mdi:content-copy" />
                <span>从模板创建规则</span>
              </button>
              <button class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                <Icon icon="mdi:cog" />
                <span>查看告警规则</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="py-12 bg-white">
      <div class="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Icon icon="mdi:bell-alert" class="text-red-600 text-2xl" />
            <span>告警列表</span>
          </h2>
          <div class="flex space-x-2">
            <el-select v-model="filterLevel" placeholder="筛选等级" clearable style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="一般" value="info" />
              <el-option label="重要" value="warning" />
              <el-option label="严重" value="error" />
              <el-option label="致命" value="critical" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="自动恢复" value="auto_recovered" />
              <el-option label="手动恢复" value="manual_recovered" />
              <el-option label="告警中" value="alerting" />
            </el-select>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-gray-100 p-6">
          <el-table :data="filteredAlerts" stripe style="width: 100%" class="
          [&_.el-table__row]:transition-all 
          [&_.el-table__row]:duration-200 
          [&_.el-table__row]:ease-in-out
          [&_.el-table__row:hover]:bg-blue-50!
          [&_.el-table__row:hover]:scale-[1.01]
          [&_.el-table__cell]:px-4!
          [&_.el-table__header_.el-table__cell]:px-4!
          ">
          <el-table-column prop="name" label="告警名称" min-width="180">
            <template #default="scope">
              <div class="flex items-center space-x-2">
                <Icon :icon="getAlertIcon(scope.row.level)" :class="getAlertIconClass(scope.row.level)" class="text-xl shrink-0" />
                <span class="font-medium">{{ scope.row.name }}</span>
              </div>
            </template>
          </el-table-column>

          <!-- TODO: 这里增加跳转，跳转到对应资源管理页面 -->
          <el-table-column prop="resource" label="关联资源" min-width="180">
            <template #default="scope">
              <span class="text-gray-600">{{ scope.row.resource }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="detail" label="详细信息" min-width="220">
            <template #default="scope">
              <span class="text-gray-600">{{ scope.row.detail }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="level" label="告警等级" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.level==='critical'" :type="getLevelTagType(scope.row.level)" class="font-bold bg-red-500! text-white!">
                {{ getLevelText(scope.row.level) }}
              </el-tag>
              <el-tag v-else :type="getLevelTagType(scope.row.level)">
                {{ getLevelText(scope.row.level) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="status" label="恢复状态" width="110">
            <template #default="scope">
              <el-tag :type="getStatusTagType(scope.row.status)">
                {{ getStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="triggeredAt" label="触发时间" width="170" sortable>
            <template #default="scope">
              <div class="text-sm text-gray-600 whitespace-nowrap">{{ scope.row.triggeredAt }}</div>
            </template>
          </el-table-column>

          <el-table-column prop="recoveredAt" label="恢复时间" width="170">
            <template #default="scope">
              <div class="text-sm text-gray-600 whitespace-nowrap">{{ scope.row.recoveredAt || '-' }}</div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="300" fixed="right">
            <template #default="scope">
              <div class="flex space-x-2 pr-2">
                <el-button 
                  v-if="scope.row.status === 'alerting'"
                  type="success" 
                  size="small" 
                  link
                  @click="recoverAlert(scope.row)"
                >
                  <Icon icon="mdi:check" class="mr-1" />恢复
                </el-button>
                <el-button 
                  v-if="scope.row.level !== 'critical'"
                  type="warning" 
                  size="small" 
                  link
                  @click="upgradeLevel(scope.row)"
                >
                  <Icon icon="mdi:arrow-up" class="mr-1" />提升
                </el-button>
                <el-button 
                  v-if="scope.row.level !== 'info'"
                  type="primary" 
                  size="small" 
                  link
                  @click="downgradeLevel(scope.row)"
                >
                  <Icon icon="mdi:arrow-down" class="mr-1" />降低
                </el-button>
                <el-button 
                  type="danger" 
                  size="small" 
                  link
                  @click="stopMonitoring(scope.row)"
                >
                  <Icon icon="mdi:stop-circle" class="mr-1" />停止监控
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import { ElMessage } from 'element-plus'

export default {
  name: 'Alert',
  components: {
    Header,
    Icon
  },
  data() {
    return {
      filterLevel: '',
      filterStatus: '',
      alerts: [
        {
          id: 1,
          name: '代理节点异常断开连接',
          resource: '代理网络 - 美东节点',
          detail: '代理节点 192.168.31.200:7890 异常断开连接超过10分钟',
          level: 'critical',
          status: 'alerting',
          triggeredAt: '2024-12-11 08:23:15',
          recoveredAt: null
        },
        {
          id: 2,
          name: '数据采集账号登录失败',
          resource: '采集账号 - Twitter账号#23',
          detail: '采集账号 Twitter账号#23 登录失败：账号密码错误',
          level: 'critical',
          status: 'alerting',
          triggeredAt: '2024-12-11 08:45:32',
          recoveredAt: null
        },
        {
          id: 3,
          name: '目标站点无法访问',
          resource: '目标站点 - darknet.forum.onion',
          detail: '目标站点 darknet.forum.onion 无法访问：返回状态码 401',
          level: 'critical',
          status: 'alerting',
          triggeredAt: '2024-12-11 09:12:47',
          recoveredAt: null
        },
        {
          id: 4,
          name: '行动执行即将超时',
          resource: '行动 - 社交媒体舆情监控',
          detail: '行动 社交媒体舆情监控 执行即将超时：剩余时间 300 秒',
          level: 'error',
          status: 'alerting',
          triggeredAt: '2024-12-11 10:05:18',
          recoveredAt: null
        },
        {
          id: 5,
          name: '代理网络剩余流量不足',
          resource: '代理网络 - 欧洲节点群',
          detail: '代理网络 欧洲节点群 剩余流量不足： 100 MB',
          level: 'warning',
          status: 'alerting',
          triggeredAt: '2024-12-11 10:28:53',
          recoveredAt: null
        },
        {
          id: 6,
          name: '沙盒容器CPU使用率过高',
          resource: '沙盒容器 - Container-042',
          detail: '沙盒容器 Container-042 CPU使用率过高：超过阈值 80%',
          level: 'error',
          status: 'alerting',
          triggeredAt: '2024-12-11 11:15:22',
          recoveredAt: null
        },
        {
          id: 7,
          name: '代理网络即将到期',
          resource: '代理网络 - 亚太节点组',
          detail: '代理网络 亚太节点组 即将到期：剩余时间 30 天',
          level: 'warning',
          status: 'alerting',
          triggeredAt: '2024-12-11 07:30:00',
          recoveredAt: null
        },
        {
          id: 8,
          name: '采集账号访问受限',
          resource: '采集账号 - Reddit账号#15',
          detail: '采集账号 Reddit账号#15 访问受限：返回状态码 403',
          level: 'warning',
          status: 'alerting',
          triggeredAt: '2024-12-11 09:45:12',
          recoveredAt: null
        },
        {
          id: 9,
          name: '数据采集速率下降',
          resource: '行动 - 技术论坛情报收集',
          detail: '数据采集速率下降：采集速率低于阈值 1000 条/分钟',
          level: 'warning',
          status: 'alerting',
          triggeredAt: '2024-12-11 10:52:38',
          recoveredAt: null
        },
        {
          id: 10,
          name: '存储空间使用率较高',
          resource: '系统资源 - 数据存储',
          detail: '存储空间使用率较高：使用率超过阈值 80%',
          level: 'warning',
          status: 'alerting',
          triggeredAt: '2024-12-11 11:30:45',
          recoveredAt: null
        },
        {
          id: 11,
          name: '代理节点响应延迟',
          resource: '代理网络 - 南美节点',
          detail: '代理节点 192.168.31.200:7890 响应延迟：超过阈值 2.0s',
          level: 'info',
          status: 'alerting',
          triggeredAt: '2024-12-11 08:15:20',
          recoveredAt: null
        },
        {
          id: 12,
          name: '数据解析格式异常',
          resource: '数据处理 - 解析器#3',
          detail: '数据解析格式异常：解析器#3 解析失败：格式不正确',
          level: 'info',
          status: 'alerting',
          triggeredAt: '2024-12-11 09:20:30',
          recoveredAt: null
        },
        {
          id: 13,
          name: '采集任务排队等待',
          resource: '任务调度 - 队列管理器',
          detail: '采集任务排队等待：队列管理器 任务队列满：等待时间 10 分钟',
          level: 'info',
          status: 'alerting',
          triggeredAt: '2024-12-11 10:35:15',
          recoveredAt: null
        },
        {
          id: 14,
          name: '目标站点响应缓慢',
          resource: '目标站点 - forum.techsec.com',
          detail: '目标站点 forum.techsec.com 响应缓慢：响应时间超过阈值 2.0s',
          level: 'warning',
          status: 'auto_recovered',
          triggeredAt: '2024-12-10 15:23:40',
          recoveredAt: '2024-12-10 16:12:15'
        },
        {
          id: 15,
          name: '代理节点连接不稳定',
          resource: '代理网络 - 非洲节点',
          detail: '代理节点 192.168.31.200:7890 连接不稳定：断开连接超过 10 分钟',
          level: 'error',
          status: 'manual_recovered',
          triggeredAt: '2024-12-10 14:18:25',
          recoveredAt: '2024-12-10 15:45:50'
        },
        {
          id: 16,
          name: '采集账号密码即将过期',
          resource: '采集账号 - Facebook账号#8',
          detail: '采集账号 Facebook账号#8 密码即将过期：剩余时间 30 天',
          level: 'warning',
          status: 'auto_recovered',
          triggeredAt: '2024-12-10 10:30:12',
          recoveredAt: '2024-12-10 11:05:33'
        },
        {
          id: 17,
          name: '数据库连接池耗尽',
          resource: '系统资源 - 数据库',
          detail: '数据库连接池耗尽：连接池已满，无法分配新连接',
          level: 'error',
          status: 'manual_recovered',
          triggeredAt: '2024-12-09 22:15:08',
          recoveredAt: '2024-12-09 22:48:20'
        },
        {
          id: 18,
          name: '网络带宽使用率高',
          resource: '系统资源 - 网络',
          detail: '网络带宽使用率高：使用率超过阈值 80%',
          level: 'info',
          status: 'auto_recovered',
          triggeredAt: '2024-12-09 18:42:30',
          recoveredAt: '2024-12-09 19:15:45'
        }
      ]
    }
  },
  computed: {
    alertStats() {
      const total = this.alerts.length
      const active = this.alerts.filter(a => a.status === 'alerting').length
      const recovered = this.alerts.filter(a => a.status !== 'alerting').length
      const critical = this.alerts.filter(a => a.level === 'critical' && a.status === 'alerting').length
      
      return {
        total,
        active,
        recovered,
        critical
      }
    },
    filteredAlerts() {
      // FIXME: 这个过滤应该是后端做，后续可以去掉
      let filtered = [...this.alerts]
      
      if (this.filterLevel) {
        filtered = filtered.filter(a => a.level === this.filterLevel)
      }
      
      if (this.filterStatus) {
        filtered = filtered.filter(a => a.status === this.filterStatus)
      }
      
      return filtered
    }
  },
  methods: {
    getAlertIcon(level) {
      const icons = {
        critical: 'mdi:alert-octagon',
        error: 'mdi:alert',
        warning: 'mdi:alert-circle',
        info: 'mdi:information'
      }
      return icons[level] || 'mdi:alert-circle'
    },
    getAlertIconClass(level) {
      const classes = {
        critical: 'text-red-600',
        error: 'text-orange-600',
        warning: 'text-amber-600',
        info: 'text-blue-600'
      }
      return classes[level] || 'text-gray-600'
    },
    getLevelText(level) {
      const texts = {
        critical: '致命',
        error: '严重',
        warning: '重要',
        info: '一般'
      }
      return texts[level] || level
    },
    getLevelTagType(level) {
      const types = {
        critical: 'danger',
        error: 'danger',
        warning: 'warning',
        info: 'primary'
      }
      return types[level] || 'info'
    },
    getStatusText(status) {
      const texts = {
        alerting: '告警中',
        auto_recovered: '自动恢复',
        manual_recovered: '手动恢复'
      }
      return texts[status] || status
    },
    getStatusTagType(status) {
      const types = {
        alerting: 'danger',
        auto_recovered: 'success',
        manual_recovered: 'success'
      }
      return types[status] || 'info'
    },
    recoverAlert(alert) {
      ElMessage.success(`已手动恢复告警：${alert.name}`)
      alert.status = 'manual_recovered'
      alert.recoveredAt = new Date().toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).replace(/\//g, '-')
    },
    upgradeLevel(alert) {
      const levels = ['info', 'warning', 'error', 'critical']
      const currentIndex = levels.indexOf(alert.level)
      if (currentIndex < levels.length - 1) {
        alert.level = levels[currentIndex + 1]
        ElMessage.warning(`已提升告警等级至：${this.getLevelText(alert.level)}`)
      }
    },
    downgradeLevel(alert) {
      const levels = ['info', 'warning', 'error', 'critical']
      const currentIndex = levels.indexOf(alert.level)
      if (currentIndex > 0) {
        alert.level = levels[currentIndex - 1]
        ElMessage.info(`已降低告警等级至：${this.getLevelText(alert.level)}`)
      }
    },
    stopMonitoring(alert) {
      ElMessage.error(`已停止该类告警监控：${alert.name}`)
    }
  }
}
</script>