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
          <div
            v-loading="overviewSummaryLoading"
            class="flex flex-wrap justify-center gap-4 mb-12"
          >
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
                <p class="text-xl font-bold text-gray-900">{{ formatSummaryNumber(dataSummary.total) }}</p>
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
                <p class="text-xl font-bold text-gray-900">{{ formatSummaryNumber(dataSummary.todayNew) }}</p>
              </div>
            </div>

            <div
              class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center space-x-3"
            >
              <div
                class="w-10 h-10 bg-cyan-100 rounded-lg flex items-center justify-center"
              >
                <Icon icon="mdi:cloud-download-outline" class="text-cyan-600 text-xl" />
              </div>
              <div>
                <p class="text-sm text-gray-500">今日采集</p>
                <p class="text-xl font-bold text-gray-900">{{ formatSummaryNumber(dataSummary.todayCrawl) }}</p>
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
            v-loading="overviewTrendLoading"
            class="bg-linear-to-br from-white to-blue-50 rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-xl font-bold text-gray-900">情报数量趋势</h3>
              <el-radio-group v-model="currentRange" @change="onTrendRangeChange" size="small">
                <el-radio-button label="trend30d">30天</el-radio-button>
                <el-radio-button label="trend90d">90天</el-radio-button>
                <el-radio-button label="trend1y">1年</el-radio-button>
              </el-radio-group>
            </div>

            <div class="h-60">
              <div id="trend-chart" class="w-full h-full"></div>
            </div>

            <div
              class="grid grid-cols-2 gap-4 mt-3 pt-3 border-t border-gray-100"
            >
              <div class="text-center">
                <p class="text-sm text-gray-500">首尾变化率</p>
                <p
                  class="text-2xl font-bold"
                  :class="trendChangeRateClass"
                >
                  {{ trendChangeDisplay }}
                </p>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500">日均数量</p>
                <p class="text-2xl font-bold text-gray-900">
                  {{ trendDailyDisplay }}
                </p>
              </div>
            </div>
          </div>

          <!-- 来源分布图表 -->
          <div
            v-loading="overviewPlatformLoading"
            class="bg-linear-to-br from-white to-blue-50 rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-xl font-bold text-gray-900">情报来源分布</h3>
              <span class="text-sm text-gray-500"
                >数据源:
                <span class="font-bold text-gray-900">{{ platformSourceCount }}个</span></span
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

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";
import Header from "@/components/Header.vue";
import { overviewApi } from "@/api/overview";

defineOptions({ name: "Home" });

const RANGE_CONFIG = {
  trend30d: { n: 30, unit: "day" },
  trend90d: { n: 90, unit: "day" },
  trend1y: { n: 12, unit: "month" }
};

const PIE_COLORS = [
  "#3b82f6",
  "#06b6d4",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#6366f1",
  "#84cc16",
  "#64748b",
  "#0ea5e9"
];

const currentRange = ref("trend30d");
const statsTimeRange = ref("week");

const intelligenceStats = ref([
  { category: "网络安全", count: "3,842", percentage: "24%", trend: "+8.2%", status: "已分析", colorClass: "bg-blue-500", trendClass: "text-green-600", trendIcon: "mdi:trending-up", statusType: "primary" },
  { category: "市场动态", count: "2,956", percentage: "18%", trend: "+5.7%", status: "处理中", colorClass: "bg-green-500", trendClass: "text-green-600", trendIcon: "mdi:trending-up", statusType: "success" },
  { category: "政策法规", count: "1,874", percentage: "12%", trend: "-1.3%", status: "已归档", colorClass: "bg-purple-500", trendClass: "text-gray-600", trendIcon: "mdi:minus", statusType: "" },
  { category: "技术发展", count: "2,431", percentage: "15%", trend: "+12.4%", status: "待审核", colorClass: "bg-amber-500", trendClass: "text-green-600", trendIcon: "mdi:trending-up", statusType: "warning" }
]);

const overviewSummaryLoading = ref(false);
const overviewTrendLoading = ref(false);
const overviewPlatformLoading = ref(false);
let trendFetchGeneration = 0;
const trendChangeDisplay = ref("—");
const trendDailyDisplay = ref("—");
const trendChangeRateRaw = ref(null);
const platformSourceCount = ref(0);
const platformDistribution = ref([]);

const ALARM_PLACEHOLDER = 47;

const dataSummary = ref({
  total: 0,
  todayNew: 0,
  todayCrawl: 0,
  alarm: ALARM_PLACEHOLDER,
  lastUpdate: "—"
});

function formatSummaryNumber(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toLocaleString();
}

function formatLatestEditAt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${y}-${m}-${day} ${h}:${min}:${s}`;
}

async function fetchSummaryStatus() {
  overviewSummaryLoading.value = true;
  try {
    const res = await overviewApi.getSummaryStatus();
    const d = res?.data;
    if (!d) {
      dataSummary.value = {
        total: 0,
        todayNew: 0,
        todayCrawl: 0,
        alarm: ALARM_PLACEHOLDER,
        lastUpdate: "—"
      };
      return;
    }
    dataSummary.value = {
      total: d.total_doc_count ?? 0,
      todayNew: d.today_new_count ?? 0,
      todayCrawl: d.today_crawl_count ?? 0,
      alarm: ALARM_PLACEHOLDER,
      lastUpdate: formatLatestEditAt(d.latest_last_edit_at)
    };
  } catch {
    dataSummary.value = {
      total: 0,
      todayNew: 0,
      todayCrawl: 0,
      alarm: ALARM_PLACEHOLDER,
      lastUpdate: "—"
    };
  } finally {
    overviewSummaryLoading.value = false;
  }
}

const latestIntelligence = ref([
  { id: 1, category: "网络安全", tagType: "primary", tagClass: "", time: "2小时前", title: "新型钓鱼攻击模式在亚太地区活跃", description: "监测发现针对金融行业的针对性攻击，涉及新型社会工程学手段...", sourceIcon: "mdi:source-repository", sourceName: "威胁情报库", sourceBgColor: "bg-blue-100", sourceIconColor: "text-blue-600", priority: "高优先级", priorityColor: "text-amber-500" },
  { id: 2, category: "市场动态", tagType: "success", tagClass: "", time: "5小时前", title: "科技行业并购活动Q3增长显著", description: "人工智能与数据安全领域成为投资热点，多家初创公司获得大额融资...", sourceIcon: "mdi:finance", sourceName: "商业数据源", sourceBgColor: "bg-green-100", sourceIconColor: "text-green-600", priority: "中优先级", priorityColor: "text-blue-500" },
  { id: 3, category: "政策法规", tagType: "", tagClass: "bg-purple-50! text-purple-700!", time: "1天前", title: "多国更新数据隐私保护法规", description: "欧盟、美国及亚太地区相继出台或修订数据跨境传输相关规定...", sourceIcon: "mdi:scale-balance", sourceName: "政策数据库", sourceBgColor: "bg-purple-100", sourceIconColor: "text-purple-600", priority: "中优先级", priorityColor: "text-blue-500" }
]);

const metrics = ref({
  report: { count: 312, percent: 78, trend: "+5.2%", color: "#3b82f6" },
  security: { score: 94, percent: 94, status: "稳定", color: "#10b981" },
  speed: { time: 2.3, percent: 65, status: "需优化", color: "#f59e0b" }
});

const trendChart = ref(null);
const sourceChart = ref(null);
const reportChart = ref(null);
const securityChart = ref(null);
const speedChart = ref(null);

const trendChangeRateClass = computed(() => {
  const v = trendChangeRateRaw.value;
  if (v == null) return "text-gray-500";
  if (v > 0) return "text-green-600";
  if (v < 0) return "text-red-600";
  return "text-gray-900";
});

function formatBucketLabel(periodStart, unit) {
  const d = new Date(periodStart);
  if (Number.isNaN(d.getTime())) return String(periodStart);
  if (unit === "month") {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  if (unit === "week") {
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatChangeRatePercent(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

async function fetchNewDataStatus() {
  const rangeKey = currentRange.value;
  const cfg = RANGE_CONFIG[rangeKey];
  if (!cfg) return;
  const myGen = ++trendFetchGeneration;
  overviewTrendLoading.value = true;
  try {
    const res = await overviewApi.getNewDataStatus({ n: cfg.n, unit: cfg.unit });
    if (myGen !== trendFetchGeneration) return;
    if (currentRange.value !== rangeKey) return;
    const data = res?.data;
    if (!data) {
      trendChangeDisplay.value = "—";
      trendDailyDisplay.value = "—";
      trendChangeRateRaw.value = null;
      applyTrendChartOption([], [], cfg.unit);
      return;
    }
    const buckets = Array.isArray(data.buckets) ? data.buckets : [];
    const labels = buckets.map((b) => formatBucketLabel(b.period_start, data.unit || cfg.unit));
    const values = buckets.map((b) => Number(b.doc_count) || 0);
    trendChangeRateRaw.value =
      data.change_rate_percent == null ? null : Number(data.change_rate_percent);
    trendChangeDisplay.value = formatChangeRatePercent(data.change_rate_percent);
    const avg = data.average_daily;
    trendDailyDisplay.value =
      avg == null ? "—" : `${Number(avg).toLocaleString()}条`;
    applyTrendChartOption(labels, values, data.unit || cfg.unit);
  } catch {
    if (myGen !== trendFetchGeneration) return;
    if (currentRange.value !== rangeKey) return;
    trendChangeDisplay.value = "—";
    trendDailyDisplay.value = "—";
    trendChangeRateRaw.value = null;
    applyTrendChartOption([], [], cfg.unit);
  } finally {
    if (myGen === trendFetchGeneration) overviewTrendLoading.value = false;
  }
}

function applyTrendChartOption(labels, values, unit) {
  if (!trendChart.value) return;
  const hasData = labels.length > 0;
  const manyDayLabels = unit === "day" && labels.length > 20;
  const option = {
    grid: {
      left: 12,
      right: 10,
      top: 24,
      bottom: manyDayLabels ? 40 : 26,
      containLabel: true
    },
    xAxis: {
      type: "category",
      data: hasData ? labels : [],
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: {
        color: "#6b7280",
        fontSize: 11,
        margin: 6,
        rotate: manyDayLabels ? 45 : 0
      }
    },
    yAxis: {
      type: "value",
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: {
        color: "#6b7280",
        fontSize: 12,
        formatter: (val) => {
          if (val >= 1000) return `${(val / 1000).toFixed(val >= 10000 ? 0 : 1)}k`;
          return String(val);
        }
      },
      splitLine: { lineStyle: { color: "#f3f4f6", type: "dashed" } }
    },
    series: [
      {
        data: hasData ? values : [],
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 3, color: "#3b82f6" },
        itemStyle: { color: "#3b82f6", borderColor: "#ffffff", borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
            { offset: 1, color: "rgba(59, 130, 246, 0.05)" }
          ])
        }
      }
    ],
    tooltip: {
      trigger: "axis",
      triggerOn: "mousemove|click",
      axisPointer: {
        type: "cross",
        snap: true,
        label: {
          show: true,
          precision: 0,
          backgroundColor: "rgba(59, 130, 246, 0.9)",
          color: "#fff"
        },
        crossStyle: { color: "#93c5fd", width: 1, type: "dashed" }
      },
      backgroundColor: "rgba(255, 255, 255, 0.95)",
      borderColor: "#e5e7eb",
      borderWidth: 1,
      textStyle: { color: "#1f2937" },
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        const v = p?.value ?? 0;
        const num = Number(v);
        const label = p?.axisValueLabel ?? p?.name ?? "";
        return `${label}<br/>数量（纵坐标）: <b>${Number.isFinite(num) ? num.toLocaleString() : v}</b> 条`;
      }
    }
  };
  if (!hasData) {
    option.graphic = [
      {
        type: "text",
        left: "center",
        top: "middle",
        style: { text: "暂无趋势数据", fill: "#9ca3af", fontSize: 14 }
      }
    ];
  } else {
    option.graphic = [];
  }
  trendChart.value.setOption(option, true);
  requestAnimationFrame(() => trendChart.value?.resize());
}

async function fetchPlatformStatus() {
  overviewPlatformLoading.value = true;
  try {
    const res = await overviewApi.getPlatformStatus();
    const data = res?.data;
    const rows = Array.isArray(data?.by_platform) ? data.by_platform : [];
    platformDistribution.value = rows.map((r, i) => ({
      name: r.platform ?? "",
      value: Number(r.doc_count) || 0,
      color: PIE_COLORS[i % PIE_COLORS.length]
    }));
    platformSourceCount.value = rows.length;
    applySourceChartOption();
  } catch {
    platformDistribution.value = [];
    platformSourceCount.value = 0;
    applySourceChartOption();
  } finally {
    overviewPlatformLoading.value = false;
  }
}

function applySourceChartOption() {
  if (!sourceChart.value) return;
  const data = platformDistribution.value;
  const hasData = data.some((d) => d.value > 0);
  const option = {
    tooltip: {
      trigger: "item",
      formatter: (p) => {
        const n = p?.name ?? "";
        const c = p?.value ?? 0;
        const pct = p?.percent != null ? p.percent.toFixed(1) : "0";
        return `${n}<br/>文档数: ${Number(c).toLocaleString()} (${pct}%)`;
      }
    },
    legend: {
      orient: "vertical",
      left: "60%",
      top: "center",
      textStyle: { color: "#6b7280", fontSize: 12 },
      itemGap: 15,
      formatter: (name) => {
        const item = data.find((d) => d.name === name);
        if (!item) return name;
        return `${name}: ${Number(item.value).toLocaleString()}`;
      }
    },
    series: [
      {
        name: "情报来源分布",
        type: "pie",
        radius: ["40%", "70%"],
        center: ["30%", "50%"],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: "bold" } },
        labelLine: { show: false },
        data: hasData
          ? data.map((item) => ({
              name: item.name,
              value: item.value,
              itemStyle: { color: item.color }
            }))
          : []
      }
    ]
  };
  if (!hasData) {
    option.graphic = [
      {
        type: "text",
        left: "center",
        top: "middle",
        style: { text: "暂无分布数据", fill: "#9ca3af", fontSize: 14 }
      }
    ];
  } else {
    option.graphic = [];
  }
  sourceChart.value.setOption(option, true);
}

function getStatusClass(type) {
      const statusMap = {
        primary: 'bg-blue-100 text-blue-700',
        success: 'bg-green-100 text-green-700',
        warning: 'bg-amber-100 text-amber-700',
        '': 'bg-purple-100 text-purple-700'
      }
      return statusMap[type] || 'bg-gray-100 text-gray-700'
    }

function onTrendRangeChange() {
  fetchNewDataStatus();
}

function setMetricsCharts() {
      const m = metrics.value;

      if (reportChart.value) {
        reportChart.value.setOption({ grid: { left: 0, right: 0, top: 0, bottom: 0 }, xAxis: { show: false }, yAxis: { show: false }, series: [{ type: "bar", data: [m.report.percent], barWidth: "100%", itemStyle: { color: m.report.color, borderRadius: 4 }, label: { show: false } }] });
      }

      if (securityChart.value) {
        securityChart.value.setOption({ grid: { left: 0, right: 0, top: 0, bottom: 0 }, xAxis: { show: false }, yAxis: { show: false }, series: [{ type: "bar", data: [m.security.percent], barWidth: "100%", itemStyle: { color: m.security.color, borderRadius: 4 }, label: { show: false } }] });
      }

      if (speedChart.value) {
        speedChart.value.setOption({ grid: { left: 0, right: 0, top: 0, bottom: 0 }, xAxis: { show: false }, yAxis: { show: false }, series: [{ type: "bar", data: [m.speed.percent], barWidth: "100%", itemStyle: { color: m.speed.color, borderRadius: 4 }, label: { show: false } }] });
      }
    }

let resizeHandler = null;

function initCharts() {
  nextTick(() => {
    const trendEl = document.getElementById("trend-chart");
    const sourceEl = document.getElementById("source-chart");
    if (trendEl) trendChart.value = echarts.init(trendEl);
    if (sourceEl) sourceChart.value = echarts.init(sourceEl);
    reportChart.value = echarts.init(document.getElementById("report-chart"));
    securityChart.value = echarts.init(document.getElementById("security-chart"));
    speedChart.value = echarts.init(document.getElementById("speed-chart"));

    applyTrendChartOption([], [], "day");
    applySourceChartOption();
    setMetricsCharts();

    Promise.all([fetchNewDataStatus(), fetchPlatformStatus()]).catch(() => {});

    resizeHandler = () => {
      trendChart.value?.resize();
      sourceChart.value?.resize();
      reportChart.value?.resize();
      securityChart.value?.resize();
      speedChart.value?.resize();
    };
    window.addEventListener("resize", resizeHandler);
  });
}

onMounted(() => {
  fetchSummaryStatus();
  initCharts();
});

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener("resize", resizeHandler);
  }
  trendChart.value?.dispose();
  sourceChart.value?.dispose();
  reportChart.value?.dispose();
  securityChart.value?.dispose();
  speedChart.value?.dispose();
});
</script>
