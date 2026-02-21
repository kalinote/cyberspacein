<template>
  <div>
    <Header />

    <!-- 英雄区域 -->
    <section
      class="relative overflow-hidden bg-linear-to-br from-white to-blue-50 pt-12 pb-16"
    >
      <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            系统<span class="text-blue-500">概览</span>
          </h1>
          <p class="text-xl text-gray-600 max-w-3xl mx-auto mb-8">
            实时监控、分析并展示来自全球数据源的情报信息，为您提供数据驱动的决策支持
          </p>

          <!-- 顶部总结数据 -->
          <div class="flex flex-wrap justify-center gap-4 mb-12">
            <div
              class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center space-x-3"
            >
              <div
                class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"
              >
                <Icon icon="mdi:database" class="text-blue-600 text-xl" />
              </div>
              <div>
                <p class="text-sm text-gray-500">数据总量</p>
                <p class="text-xl font-bold text-gray-900">{{ dataSummary.total }}</p>
              </div>
            </div>

            <div
              class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center space-x-3"
            >
              <div
                class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center"
              >
                <Icon icon="mdi:trending-up" class="text-green-600 text-xl" />
              </div>
              <div>
                <p class="text-sm text-gray-500">今日新增</p>
                <p class="text-xl font-bold text-gray-900">{{ dataSummary.today }}</p>
              </div>
            </div>

            <div
              class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center space-x-3"
            >
              <div
                class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center"
              >
                <Icon icon="mdi:alert-circle" class="text-amber-600 text-xl" />
              </div>
              <div>
                <p class="text-sm text-gray-500">待处理警报</p>
                <p class="text-xl font-bold text-gray-900">{{ dataSummary.alarm }}</p>
              </div>
            </div>

            <div
              class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center space-x-3"
            >
              <div
                class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center"
              >
                <Icon icon="mdi:clock" class="text-purple-600 text-xl" />
              </div>
              <div>
                <p class="text-sm text-gray-500">最新数据时间</p>
                <p class="text-xl font-bold text-gray-900">{{ dataSummary.lastUpdate }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="absolute inset-0 pointer-events-none z-0">
        <div class="absolute top-10 right-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply blur-3xl opacity-20"></div>
        <div class="absolute bottom-10 left-10 w-64 h-64 bg-cyan-200 rounded-full mix-blend-multiply blur-3xl opacity-20"></div>
      </div>
    </section>

    <!-- 数据概览 -->
    <section class="py-12 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-10">
          <h2 class="text-3xl font-bold text-gray-900 mb-2">
            数据<span class="text-blue-500">概览</span>
          </h2>
          <p class="text-gray-600">实时情报数据统计与趋势分析</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          <!-- 趋势图表 -->
          <div
            class="bg-linear-to-br from-white to-blue-50 rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-xl font-bold text-gray-900">情报数量趋势</h3>
              <el-radio-group v-model="currentRange" @change="switchRange" size="small">
                <el-radio-button label="trend30d">30天</el-radio-button>
                <el-radio-button label="trend90d">90天</el-radio-button>
                <el-radio-button label="trend1y">1年</el-radio-button>
              </el-radio-group>
            </div>

            <div class="h-80">
              <div id="trend-chart" class="w-full h-full"></div>
            </div>

            <div
              class="grid grid-cols-2 gap-6 mt-6 pt-6 border-t border-gray-100"
            >
              <div class="text-center">
                <p class="text-sm text-gray-500">周增长</p>
                <p class="text-2xl font-bold text-green-600">
                  {{ currentTrendData.weekGrowth }}
                </p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">日均数量</p>
                <p class="text-2xl font-bold text-gray-900">
                  {{ currentTrendData.dailyAvg }}
                </p>
              </div>
            </div>
          </div>

          <!-- 来源分布图表 -->
          <div
            class="bg-linear-to-br from-white to-blue-50 rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-xl font-bold text-gray-900">情报来源分布</h3>
              <span class="text-sm text-gray-500"
                >数据源:
                <span class="font-bold text-gray-900">147个</span></span
              >
            </div>

            <div class="h-80">
              <div id="source-chart" class="w-full h-full"></div>
            </div>
          </div>
        </div>

        <!-- 关键指标 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div
            class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex items-center justify-between mb-4">
              <div>
                <p class="text-sm text-gray-500 mb-1">情报报告生成</p>
                <p class="text-3xl font-bold text-gray-900">
                  <span>{{ metrics.report.count }}</span> 份
                </p>
              </div>
              <div
                class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center"
              >
                <Icon icon="mdi:file-document" class="text-blue-600 text-2xl" />
              </div>
            </div>
            <div class="flex items-center justify-between text-sm mb-2">
              <span class="text-gray-600">完成度</span>
              <span class="font-medium text-gray-900"
                >{{ metrics.report.percent }}%</span
              >
            </div>
            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div id="report-chart" class="h-full"></div>
            </div>
            <div class="mt-3 text-sm text-green-600">
              {{ metrics.report.trend }}
            </div>
          </div>

          <div
            class="bg-linear-to-br from-green-50 to-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex items-center justify-between mb-4">
              <div>
                <p class="text-sm text-gray-500 mb-1">系统安全状态</p>
                <p class="text-3xl font-bold text-gray-900">
                  <span>{{ metrics.security.score }}</span> 分
                </p>
              </div>
              <div
                class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center"
              >
                <Icon icon="mdi:shield-check" class="text-green-600 text-2xl" />
              </div>
            </div>
            <div class="flex items-center justify-between text-sm mb-2">
              <span class="text-gray-600">健康度</span>
              <span class="font-medium text-gray-900"
                >{{ metrics.security.percent }}%</span
              >
            </div>
            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div id="security-chart" class="h-full"></div>
            </div>
            <div class="mt-3 text-sm text-green-600">
              {{ metrics.security.status }}
            </div>
          </div>

          <div
            class="bg-linear-to-br from-amber-50 to-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex items-center justify-between mb-4">
              <div>
                <p class="text-sm text-gray-500 mb-1">数据处理速度</p>
                <p class="text-3xl font-bold text-gray-900">
                  <span>{{ metrics.speed.time }}</span> 秒
                </p>
              </div>
              <div
                class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center"
              >
                <Icon icon="mdi:speedometer" class="text-amber-600 text-2xl" />
              </div>
            </div>
            <div class="flex items-center justify-between text-sm mb-2">
              <span class="text-gray-600">效率</span>
              <span class="font-medium text-gray-900"
                >{{ metrics.speed.percent }}%</span
              >
            </div>
            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div id="speed-chart" class="h-full"></div>
            </div>
            <div class="mt-3 text-sm text-amber-600">
              {{ metrics.speed.status }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 最新情报 -->
    <section class="py-12 bg-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center mb-10">
          <div>
            <h2 class="text-3xl font-bold text-gray-900 mb-2">
              最新<span class="text-blue-500">情报</span>
            </h2>
            <p class="text-gray-600">实时更新的高质量情报信息</p>
          </div>
          <el-button type="primary" link @click="$router.push('/search')">
            查看更多
            <template #icon><Icon icon="mdi:arrow-right" /></template>
          </el-button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          <div
            v-for="item in latestIntelligence"
            :key="item.id"
            class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
          >
            <div class="p-5">
              <div class="flex justify-between items-start mb-3">
                <el-tag
                  :type="item.tagType"
                  :class="item.tagClass"
                  size="small"
                >
                  {{ item.category }}
                </el-tag>
                <span class="text-xs text-gray-500">{{ item.time }}</span>
              </div>
              <h3 class="font-bold text-gray-900 text-lg mb-2">
                {{ item.title }}
              </h3>
              <p class="text-gray-600 text-sm mb-4">
                {{ item.description }}
              </p>
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2">
                  <div
                    :class="[
                      'w-6 h-6 rounded-full flex items-center justify-center',
                      item.sourceBgColor
                    ]"
                  >
                    <Icon
                      :icon="item.sourceIcon"
                      :class="['text-xs', item.sourceIconColor]"
                    />
                  </div>
                  <span class="text-xs text-gray-500">{{ item.sourceName }}</span>
                </div>
                <div :class="['flex items-center space-x-1', item.priorityColor]">
                  <Icon icon="mdi:star" />
                  <span class="text-xs font-medium">{{ item.priority }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 情报分类统计表格 -->
        <div
          class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden"
        >
          <div class="p-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-gray-900">情报分类统计</h3>
              <el-radio-group v-model="statsTimeRange" size="small">
                <el-radio-button label="week">本周</el-radio-button>
                <el-radio-button label="month">本月</el-radio-button>
                <el-radio-button label="year">本年</el-radio-button>
              </el-radio-group>
            </div>

            <div class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-gray-200">
                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">分类</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">数量</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">占比</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">变化趋势</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">处理状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="stat in intelligenceStats" :key="stat.category" class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="py-3 px-4">
                      <div class="flex items-center">
                        <div :class="['w-2 h-2 rounded-full mr-2', stat.colorClass]"></div>
                        <span class="font-medium">{{ stat.category }}</span>
                      </div>
                    </td>
                    <td class="py-3 px-4">{{ stat.count }}</td>
                    <td class="py-3 px-4">{{ stat.percentage }}</td>
                    <td class="py-3 px-4">
                      <div :class="['flex items-center', stat.trendClass]">
                        <Icon :icon="stat.trendIcon" />
                        <span class="ml-1">{{ stat.trend }}</span>
                      </div>
                    </td>
                    <td class="py-3 px-4">
                      <span :class="['px-2 py-1 text-xs font-medium rounded-full', getStatusClass(stat.statusType)]">
                        {{ stat.status }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";
import Header from "@/components/Header.vue";

export default {
  name: "Home",
  components: {
    Header,
    Icon,
  },
  data() {
    return {
      currentRange: "trend30d",
      statsTimeRange: "week",

      intelligenceStats: [
        {
          category: "网络安全",
          count: "3,842",
          percentage: "24%",
          trend: "+8.2%",
          status: "已分析",
          colorClass: "bg-blue-500",
          trendClass: "text-green-600",
          trendIcon: "mdi:trending-up",
          statusType: "primary"
        },
        {
          category: "市场动态",
          count: "2,956",
          percentage: "18%",
          trend: "+5.7%",
          status: "处理中",
          colorClass: "bg-green-500",
          trendClass: "text-green-600",
          trendIcon: "mdi:trending-up",
          statusType: "success"
        },
        {
          category: "政策法规",
          count: "1,874",
          percentage: "12%",
          trend: "-1.3%",
          status: "已归档",
          colorClass: "bg-purple-500",
          trendClass: "text-gray-600",
          trendIcon: "mdi:minus",
          statusType: ""
        },
        {
          category: "技术发展",
          count: "2,431",
          percentage: "15%",
          trend: "+12.4%",
          status: "待审核",
          colorClass: "bg-amber-500",
          trendClass: "text-green-600",
          trendIcon: "mdi:trending-up",
          statusType: "warning"
        }
      ],

      trendData: {
        trend30d: {
          dates: [
            "1日",
            "3日",
            "5日",
            "7日",
            "9日",
            "11日",
            "13日",
            "15日",
            "17日",
            "19日",
            "21日",
            "23日",
            "25日",
            "27日",
            "29日",
          ],
          values: [
            7200, 7850, 8320, 7980, 8450, 9010, 9320, 9100, 8650, 8920, 9240,
            9560, 9880, 10120, 10450,
          ],
          weekGrowth: "+12.5%",
          dailyAvg: "8,742条",
        },
        trend90d: {
          dates: [
            "1月",
            "2月",
            "3月",
            "4月",
            "5月",
            "6月",
            "7日",
            "14日",
            "21日",
            "28日",
            "35日",
            "42日",
            "49日",
            "56日",
            "63日",
            "70日",
            "77日",
            "84日",
          ],
          values: [
            6200, 6580, 6920, 7350, 7810, 8020, 8320, 8450, 8620, 8910, 9020,
            9250, 9420, 9680, 9810, 10020, 10250, 10450,
          ],
          weekGrowth: "+8.3%",
          dailyAvg: "8,210条",
        },
        trend1y: {
          dates: [
            "1月",
            "2月",
            "3月",
            "4月",
            "5月",
            "6月",
            "7月",
            "8月",
            "9月",
            "10月",
            "11月",
            "12月",
          ],
          values: [
            5200, 5800, 6320, 6850, 7350, 7920, 8320, 8620, 9020, 9420, 9810,
            10450,
          ],
          weekGrowth: "+15.8%",
          dailyAvg: "7,850条",
        },
      },

      dataSummary: {
        total: 4202512,
        today: 12000,
        alarm: 47,
        lastUpdate: "2025-12-11 10:00:00",
      },

      latestIntelligence: [
        {
          id: 1,
          category: "网络安全",
          // TODO: 这里的样式还需要再考虑一下具体如何实现
          tagType: "primary",
          tagClass: "",
          time: "2小时前",
          title: "新型钓鱼攻击模式在亚太地区活跃",
          description: "监测发现针对金融行业的针对性攻击，涉及新型社会工程学手段...",
          sourceIcon: "mdi:source-repository",
          sourceName: "威胁情报库",
          sourceBgColor: "bg-blue-100",
          sourceIconColor: "text-blue-600",
          priority: "高优先级",
          priorityColor: "text-amber-500",
        },
        {
          id: 2,
          category: "市场动态",
          tagType: "success",
          tagClass: "",
          time: "5小时前",
          title: "科技行业并购活动Q3增长显著",
          description: "人工智能与数据安全领域成为投资热点，多家初创公司获得大额融资...",
          sourceIcon: "mdi:finance",
          sourceName: "商业数据源",
          sourceBgColor: "bg-green-100",
          sourceIconColor: "text-green-600",
          priority: "中优先级",
          priorityColor: "text-blue-500",
        },
        {
          id: 3,
          category: "政策法规",
          tagType: "",
          tagClass: "bg-purple-50! text-purple-700!",
          time: "1天前",
          title: "多国更新数据隐私保护法规",
          description: "欧盟、美国及亚太地区相继出台或修订数据跨境传输相关规定...",
          sourceIcon: "mdi:scale-balance",
          sourceName: "政策数据库",
          sourceBgColor: "bg-purple-100",
          sourceIconColor: "text-purple-600",
          priority: "中优先级",
          priorityColor: "text-blue-500",
        },
      ],

      sourceDistribution: [
        { name: "公开数据源", value: 42, color: "#3b82f6" },
        { name: "合作伙伴", value: 28, color: "#06b6d4" },
        { name: "内部采集", value: 18, color: "#10b981" },
        { name: "其他来源", value: 12, color: "#f59e0b" },
      ],

      metrics: {
        report: { count: 312, percent: 78, trend: "+5.2%", color: "#3b82f6" },
        security: { score: 94, percent: 94, status: "稳定", color: "#10b981" },
        speed: { time: 2.3, percent: 65, status: "需优化", color: "#f59e0b" },
      },

      trendChart: null,
      sourceChart: null,
      reportChart: null,
      securityChart: null,
      speedChart: null,
    };
  },

  computed: {
    currentTrendData() {
      return this.trendData[this.currentRange];
    },
  },

  methods: {
    getStatusClass(type) {
      const statusMap = {
        primary: 'bg-blue-100 text-blue-700',
        success: 'bg-green-100 text-green-700',
        warning: 'bg-amber-100 text-amber-700',
        '': 'bg-purple-100 text-purple-700'
      }
      return statusMap[type] || 'bg-gray-100 text-gray-700'
    },
    
    switchRange(range) {
      if (typeof range === 'string') {
        this.currentRange = range;
        this.setTrendChart(range);
      } else {
        this.setTrendChart(this.currentRange);
      }
    },

    setTrendChart(dataType) {
      if (!this.trendChart) return;

      const data = this.trendData[dataType];

      const option = {
        grid: {
          left: "3%",
          right: "4%",
          bottom: "10%",
          top: "10%",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: data.dates,
          axisLine: {
            lineStyle: {
              color: "#e5e7eb",
            },
          },
          axisLabel: {
            color: "#6b7280",
            fontSize: 12,
          },
        },
        yAxis: {
          type: "value",
          axisLine: {
            lineStyle: {
              color: "#e5e7eb",
            },
          },
          axisLabel: {
            color: "#6b7280",
            fontSize: 12,
            formatter: (value) => {
              return (value / 1000).toFixed(0) + "k";
            },
          },
          splitLine: {
            lineStyle: {
              color: "#f3f4f6",
              type: "dashed",
            },
          },
        },
        series: [
          {
            data: data.values,
            type: "line",
            smooth: true,
            symbol: "circle",
            symbolSize: 6,
            lineStyle: {
              width: 3,
              color: "#3b82f6",
            },
            itemStyle: {
              color: "#3b82f6",
              borderColor: "#ffffff",
              borderWidth: 2,
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.05)" },
              ]),
            },
          },
        ],
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderColor: "#e5e7eb",
          borderWidth: 1,
          textStyle: {
            color: "#1f2937",
          },
          formatter: (params) => {
            const value = params[0].value;
            return `${
              params[0].name
            }<br/>情报数量: <b>${value.toLocaleString()}条</b>`;
          },
        },
      };

      this.trendChart.setOption(option);
    },

    setSourceChart() {
      if (!this.sourceChart) return;

      const data = this.sourceDistribution;

      const option = {
        tooltip: {
          trigger: "item",
          formatter: "{a} <br/>{b}: {c}% ({d}%)",
        },
        legend: {
          orient: "vertical",
          left: "60%",
          top: "center",
          textStyle: {
            color: "#6b7280",
            fontSize: 12,
          },
          itemGap: 15,
          formatter: (name) => {
            const item = data.find((d) => d.name === name);
            return `${name}: ${item.value}%`;
          },
        },
        series: [
          {
            name: "情报来源分布",
            type: "pie",
            radius: ["40%", "70%"],
            center: ["30%", "50%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 8,
              borderColor: "#fff",
              borderWidth: 2,
            },
            label: {
              show: false,
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 14,
                fontWeight: "bold",
              },
            },
            labelLine: {
              show: false,
            },
            data: data.map((item) => ({
              name: item.name,
              value: item.value,
              itemStyle: {
                color: item.color,
              },
            })),
          },
        ],
      };

      this.sourceChart.setOption(option);
    },

    setMetricsCharts() {
      const metrics = this.metrics;

      if (this.reportChart) {
        this.reportChart.setOption({
          grid: { left: 0, right: 0, top: 0, bottom: 0 },
          xAxis: { show: false },
          yAxis: { show: false },
          series: [
            {
              type: "bar",
              data: [metrics.report.percent],
              barWidth: "100%",
              itemStyle: {
                color: metrics.report.color,
                borderRadius: 4,
              },
              label: { show: false },
            },
          ],
        });
      }

      if (this.securityChart) {
        this.securityChart.setOption({
          grid: { left: 0, right: 0, top: 0, bottom: 0 },
          xAxis: { show: false },
          yAxis: { show: false },
          series: [
            {
              type: "bar",
              data: [metrics.security.percent],
              barWidth: "100%",
              itemStyle: {
                color: metrics.security.color,
                borderRadius: 4,
              },
              label: { show: false },
            },
          ],
        });
      }

      if (this.speedChart) {
        this.speedChart.setOption({
          grid: { left: 0, right: 0, top: 0, bottom: 0 },
          xAxis: { show: false },
          yAxis: { show: false },
          series: [
            {
              type: "bar",
              data: [metrics.speed.percent],
              barWidth: "100%",
              itemStyle: {
                color: metrics.speed.color,
                borderRadius: 4,
              },
              label: { show: false },
            },
          ],
        });
      }
    },

    initCharts() {
      this.$nextTick(() => {
        this.trendChart = echarts.init(document.getElementById("trend-chart"));
        this.sourceChart = echarts.init(
          document.getElementById("source-chart")
        );
        this.reportChart = echarts.init(
          document.getElementById("report-chart")
        );
        this.securityChart = echarts.init(
          document.getElementById("security-chart")
        );
        this.speedChart = echarts.init(document.getElementById("speed-chart"));

        this.setTrendChart("trend30d");
        this.setSourceChart();
        this.setMetricsCharts();

        window.addEventListener("resize", () => {
          this.trendChart?.resize();
          this.sourceChart?.resize();
        });
      });
    },
  },

  mounted() {
    this.initCharts();
  },
};
</script>
