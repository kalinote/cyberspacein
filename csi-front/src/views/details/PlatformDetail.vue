<template>
    <div>
        <Header />

        <!-- 顶部标题区域 -->
        <section class="relative overflow-hidden bg-linear-to-br from-white to-blue-50 pt-12 pb-8">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <el-button type="primary" link @click="$router.back()" class="mb-6">
                    <template #icon>
                        <Icon icon="mdi:arrow-left" />
                    </template>
                    返回
                </el-button>
                <div class="flex items-start space-x-6">
                    <div
                        class="w-20 h-20 bg-white rounded-2xl shadow-lg border border-gray-200 flex items-center justify-center overflow-hidden">
                        <img v-if="platformDetail.logo" :src="platformDetail.logo" :alt="platformDetail.name"
                            class="w-full h-full object-contain" />
                        <Icon v-else icon="mdi:web" class="text-blue-600 text-4xl" />
                    </div>
                    <div class="flex-1">
                        <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-2">
                            {{ platformDetail.name }}
                        </h1>
                        <p class="text-gray-600 mb-4">{{ platformDetail.uuid }}</p>
                        <div class="flex flex-wrap items-center gap-3">
                            <el-tag :type="getStatusType(platformDetail.status)" size="default">
                                {{ platformDetail.status }}
                            </el-tag>
                            <el-tag type="primary" size="default">
                                {{ platformDetail.type }}
                            </el-tag>
                            <el-tag type="primary" size="default">
                                {{ platformDetail.netType }}
                            </el-tag>
                            <el-link v-if="platformDetail.url" :href="platformDetail.url" target="_blank" type="primary"
                                class="text-sm">
                                <template #icon>
                                    <Icon icon="mdi:open-in-new" />
                                </template>
                                访问平台
                            </el-link>
                        </div>
                    </div>
                </div>
            </div>
            <div
                class="absolute top-10 right-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20">
            </div>
            <div
                class="absolute bottom-10 left-10 w-64 h-64 bg-cyan-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20">
            </div>
        </section>

        <!-- 统计信息卡片 -->
        <section class="py-8 bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div
                        class="bg-linear-to-br from-blue-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                            <Icon icon="mdi:database" class="text-blue-600 text-2xl" />
                        </div>
                        <div>
                            <p class="text-sm text-gray-500">数据总量</p>
                            <p class="text-2xl font-bold text-gray-900">
                                {{ statistics.totalData.toLocaleString() }}
                            </p>
                        </div>
                    </div>

                    <div
                        class="bg-linear-to-br from-green-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                            <Icon icon="mdi:run" class="text-green-600 text-2xl" />
                        </div>
                        <div>
                            <p class="text-sm text-gray-500">相关行动</p>
                            <p class="text-2xl font-bold text-gray-900">
                                {{ statistics.related_actions.toLocaleString() }}
                            </p>
                        </div>
                    </div>

                    <div
                        class="bg-linear-to-br from-amber-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                            <Icon icon="mdi:clock-outline" class="text-amber-600 text-2xl" />
                        </div>
                        <div>
                            <p class="text-sm text-gray-500">最后更新</p>
                            <p class="text-lg font-bold text-gray-900">
                                {{ statistics.lastUpdate }}
                            </p>
                        </div>
                    </div>

                    <div
                        class="bg-linear-to-br from-purple-50 to-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center space-x-4">
                        <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                            <Icon icon="mdi:trending-up" class="text-purple-600 text-2xl" />
                        </div>
                        <div>
                            <p class="text-sm text-gray-500">今日新增</p>
                            <p class="text-2xl font-bold text-gray-900">
                                {{ statistics.todayNew.toLocaleString() }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 平台详细信息 -->
        <section class="py-12 bg-gray-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <!-- 左侧：基本信息 -->
                    <div class="lg:col-span-2 space-y-6">
                        <!-- 平台描述 -->
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                            <h2 class="text-2xl font-bold text-gray-900 mb-4 flex items-center">
                                <Icon icon="mdi:information" class="text-blue-600 mr-2" />
                                平台<span class="text-blue-500">简介</span>
                            </h2>
                            <p class="text-gray-600 leading-relaxed">
                                {{ platformDetail.description }}
                            </p>
                        </div>

                        <!-- 数据趋势图表 -->
                        <div
                            class="bg-linear-to-br from-white to-blue-50 rounded-xl p-6 shadow-sm border border-gray-100">
                            <div class="flex justify-between items-center mb-6">
                                <h2 class="text-xl font-bold text-gray-900">
                                    数据采集<span class="text-blue-500">趋势</span>
                                </h2>
                                <el-radio-group v-model="currentRange" @change="switchRange" size="small">
                                    <el-radio-button label="7d">7天</el-radio-button>
                                    <el-radio-button label="30d">30天</el-radio-button>
                                    <el-radio-button label="90d">90天</el-radio-button>
                                </el-radio-group>
                            </div>
                            <div class="h-80">
                                <div id="trend-chart" class="w-full h-full"></div>
                            </div>
                        </div>

                        <!-- 分类统计 -->
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                            <div class="p-6">
                                <h2 class="text-xl font-bold text-gray-900 mb-4">
                                    数据<span class="text-blue-500">分类统计</span>
                                </h2>
                                <div class="space-y-4">
                                    <div v-for="category in categoryStats" :key="category.name"
                                        class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                                        <div class="flex items-center space-x-3">
                                            <div :class="['w-3 h-3 rounded-full', category.color]"></div>
                                            <span class="font-medium text-gray-900">{{
                                                category.name
                                            }}</span>
                                        </div>
                                        <div class="flex items-center space-x-4">
                                            <span class="text-gray-600">{{ category.count.toLocaleString() }}条</span>
                                            <span class="text-sm text-gray-500">{{ category.percentage }}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 右侧：详细信息 -->
                    <div class="space-y-6">
                        <!-- 平台属性 -->
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                            <h3 class="text-lg font-bold text-gray-900 mb-4">
                                平台<span class="text-blue-500">属性</span>
                            </h3>
                            <div class="space-y-4">
                                <div>
                                    <p class="text-sm text-gray-500 mb-1">平台类型</p>
                                    <p class="font-medium text-gray-900">
                                        {{ platformDetail.type }}
                                    </p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500 mb-1">分类</p>
                                    <p class="font-medium text-gray-900">
                                        {{ platformDetail.category }}
                                    </p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500 mb-1">子分类</p>
                                    <p class="font-medium text-gray-900">
                                        {{ platformDetail.subCategory }}
                                    </p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500 mb-1">创建时间</p>
                                    <p class="font-medium text-gray-900">
                                        {{ platformDetail.createdAt }}
                                    </p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500 mb-1">更新时间</p>
                                    <p class="font-medium text-gray-900">
                                        {{ platformDetail.updatedAt }}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <!-- 标签 -->
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                            <h3 class="text-lg font-bold text-gray-900 mb-4">
                                平台<span class="text-blue-500">标签</span>
                            </h3>
                            <div class="flex flex-wrap gap-2">
                                <el-tag v-for="tag in platformDetail.tags" :key="tag" type="primary" size="default">
                                    {{ tag }}
                                </el-tag>
                            </div>
                        </div>

                        <!-- 操作按钮 -->
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                            <h3 class="text-lg font-bold text-gray-900 mb-4">
                                快速<span class="text-blue-500">操作</span>
                            </h3>
                            <div class="space-y-3">
                                <button @click="refreshData"
                                    class="w-full bg-blue-500 hover:bg-blue-600 text-white py-3 rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                                    <Icon icon="mdi:refresh" />
                                    <span>刷新数据</span>
                                </button>
                                <button @click="exportData"
                                    class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2">
                                    <Icon icon="mdi:download" />
                                    <span>导出数据</span>
                                </button>
                                <button @click="configurePlatform"
                                    class="w-full border-2 border-gray-200 text-gray-600 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2">
                                    <Icon icon="mdi:cog" />
                                    <span>配置平台</span>
                                </button>
                                <button @click="createAction"
                                    class="w-full bg-yellow-400 hover:bg-yellow-500 text-yellow-900 py-3 rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                                    <Icon icon="mdi:plus" />
                                    <span>创建专项行动</span>
                                </button>
                                <button
                                    class="w-full bg-red-400 hover:bg-red-500 text-red-900 py-3 rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                                    <Icon icon="mdi:security" />
                                    <span>标记零信任</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 平台快照时间线 -->
        <section class="py-12 bg-white border-b border-gray-100">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <h2 class="text-2xl font-bold text-gray-900 mb-10 flex items-center">
                    <Icon icon="mdi:history" class="text-blue-600 mr-2 text-2xl" />
                    平台<span class="text-blue-500">快照</span>时间线
                </h2>
                <div class="relative py-4">
                    <!-- 时间轴线 -->
                    <div class="absolute top-14 left-0 w-full h-0.5 bg-blue-100"></div>
                    <!-- 滚动容器 -->
                    <div class="flex overflow-x-auto space-x-8 pb-8 px-4 scrollbar-thin scrollbar-thumb-blue-100 scrollbar-track-transparent">
                        <div v-for="(snap, index) in snapshots" :key="index" class="flex-none flex flex-col items-center group relative min-w-[160px] w-[160px]">
                            <!-- 时间点 -->
                            <div class="mb-2 bg-white px-3 py-1 rounded-full border border-blue-200 text-blue-600 font-medium text-xs shadow-sm z-10 group-hover:border-blue-400 group-hover:bg-blue-50 transition-colors">
                                {{ snap.date }}
                            </div>
                            <!-- 节点圆点 -->
                            <div class="w-3 h-3 rounded-full border-2 border-white bg-blue-300 z-10 shadow-sm mb-4 group-hover:bg-blue-600 group-hover:scale-125 transition-all duration-300"></div>
                            <!-- 图片卡片 -->
                            <div class="w-full bg-white p-1.5 rounded-lg border border-gray-200 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 group-hover:border-blue-200">
                                <div class="relative aspect-video rounded-md overflow-hidden bg-gray-100">
                                    <el-image
                                        :src="snap.image"
                                        :preview-src-list="snapshotPreviewList"
                                        :initial-index="index"
                                        fit="cover"
                                        class="w-full h-full"
                                        loading="lazy"
                                        preview-teleported
                                        hide-on-click-modal
                                    >
                                        <template #placeholder>
                                            <div class="w-full h-full flex items-center justify-center text-gray-400">
                                                <Icon icon="mdi:image-outline" class="text-lg" />
                                            </div>
                                        </template>
                                    </el-image>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 平台资源管理 -->
        <section class="py-12 bg-gray-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between items-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                        <Icon icon="mdi:server-network" class="text-blue-600 text-2xl" />
                        <span>平台<span class="text-blue-500">资源</span>管理</span>
                    </h2>
                    <el-button type="primary" link>
                        <template #icon>
                            <Icon icon="mdi:settings" />
                        </template>
                        资源配置
                    </el-button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div
                        class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 border border-blue-100 shadow-sm cursor-pointer">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center space-x-3">
                                <div
                                    class="w-12 h-12 bg-linear-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
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

                    <div
                        class="bg-linear-to-br from-amber-50 to-white rounded-2xl p-6 border border-amber-100 shadow-sm cursor-pointer">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center space-x-3">
                                <div
                                    class="w-12 h-12 bg-linear-to-br from-amber-500 to-orange-400 rounded-xl flex items-center justify-center">
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

                    <div
                        class="bg-linear-to-br from-purple-50 to-white rounded-2xl p-6 border border-purple-100 shadow-sm cursor-pointer">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center space-x-3">
                                <div
                                    class="w-12 h-12 bg-linear-to-br from-purple-500 to-pink-400 rounded-xl flex items-center justify-center">
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

        <!-- 关联情报 -->
        <section class="py-12 bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="mb-8 flex flex-col sm:flex-row sm:items-center justify-between">
                    <div>
                        <h2 class="text-2xl font-bold text-gray-900 mb-2">关联<span class="text-blue-500">情报</span></h2>
                        <p class="text-gray-600">共 <span class="font-bold text-blue-600">{{ relatedIntelligence.length }}</span> 条相关情报</p>
                    </div>
                    <div class="flex items-center space-x-4 mt-4 sm:mt-0">
                        <div class="flex items-center">
                            <span class="text-gray-700 mr-2">排序:</span>
                            <el-select v-model="intelligenceSortBy" placeholder="选择排序" size="default" style="width: 140px">
                                <el-option label="相关度" value="relevance" />
                                <el-option label="时间最新" value="time" />
                                <el-option label="优先级最高" value="priority" />
                            </el-select>
                        </div>
                    </div>
                </div>

                <div class="space-y-6">
                    <div v-for="item in relatedIntelligence" :key="item.id"
                        class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
                        <div class="flex justify-between items-start mb-4">
                            <div class="flex flex-wrap items-center gap-2">
                                <el-tag :type="item.categoryType" size="small">{{ item.category }}</el-tag>
                                <el-tag :type="item.priorityType" size="small">{{ item.priority }}</el-tag>
                                <el-tag v-if="item.nsfw" type="danger" size="small">NSFW</el-tag>
                            </div>
                            <span class="text-sm text-gray-500 shrink-0">{{ item.date }}</span>
                        </div>
                        <h3 class="text-lg font-bold text-gray-900 mb-3">{{ item.title }}</h3>
                        <p class="text-gray-600 mb-4">{{ item.description }}</p>
                        <div class="flex flex-wrap gap-2 mb-4">
                            <el-tag v-for="tag in item.tags" :key="tag" size="small" type="info" effect="plain">
                                {{ tag }}
                            </el-tag>
                        </div>
                        <div class="flex justify-between items-center text-sm text-gray-500">
                            <span>来源: <router-link :to="`/details/platform/${item.platform_id}`" class="text-blue-600 hover:text-blue-800 items-center underline">
                                <span class="font-medium">{{ item.platform }}</span>
                            </router-link></span>
                            <span>作者: <router-link :to="`/user/${item.author_id}`" class="text-blue-600 hover:text-blue-800 items-center underline">
                                <span class="font-medium">{{ item.author }}</span>
                            </router-link></span>
                            <div class="flex items-center space-x-4">
                                <span class="flex items-center">
                                    <Icon icon="mdi:eye" class="mr-1" /> {{ item.views }}
                                </span>
                                <el-button type="primary" link>
                                    <template #icon><Icon icon="mdi:bookmark-outline" /></template>
                                    收藏
                                </el-button>
                                <a :href="`/info/${item.id}`" class="text-blue-600 hover:text-blue-800 flex items-center">
                                    查看详情 <Icon icon="mdi:arrow-right" class="ml-1" />
                                </a>
                            </div>
                        </div>
                    </div>

                    <div class="flex justify-center mt-8">
                        <el-pagination
                            v-model:current-page="intelligenceCurrentPage"
                            :page-size="intelligencePageSize"
                            :total="intelligenceTotalResults"
                            layout="prev, pager, next"
                            background
                        />
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
    name: "PlatformDetail",
    components: {
        Header,
        Icon,
    },
    props: {
        id: {
            type: String,
            required: false,
        },
    },
    computed: {
        platformId() {
            return this.id || this.$route.params.id;
        },
        snapshotPreviewList() {
            return this.snapshots.map((s) => s.image);
        },
    },

    data() {
        return {
            currentRange: "7d",
            trendChart: null,
            // TODO: 从接口获取平台详情数据
            platformDetail: {
                uuid: "fb5bebe1b7df48e6606fdffed2cf8b14",
                name: "Bilibili",
                description:
                    "Bilibili是一个中国的视频分享平台，用户可以在上面观看和上传各种类型的视频。平台以弹幕评论系统为特色，用户可以在观看视频时发送实时评论，这些评论会以弹幕的形式显示在视频画面上。Bilibili主要面向年轻用户群体，内容涵盖动画、游戏、音乐、科技、生活等多个领域。",
                type: "视频网站",
                status: "正常",
                netType: "明网",
                createdAt: "2025-01-01",
                updatedAt: "2025-01-01",
                url: "https://www.bilibili.com",
                logo: "https://www.bilibili.com/favicon.ico",
                tags: ["视频分享", "二次元", "弹幕", "社交媒体"],
                category: "娱乐",
                subCategory: "视频",
            },
            // TODO: 从接口获取平台统计信息（数据总量、采集次数、最后更新、今日新增）
            statistics: {
                totalData: 125430,
                related_actions: 3420,
                lastUpdate: "2小时前",
                todayNew: 1250,
            },
            // TODO: 从接口获取数据趋势数据（根据时间范围：7天、30天、90天）
            trendData: {
                "7d": {
                    dates: ["01-09", "01-10", "01-11", "01-12", "01-13", "01-14", "01-15"],
                    values: [1200, 1350, 1420, 1380, 1520, 1280, 1250],
                },
                "30d": {
                    dates: ["12-17", "12-18", "12-19", "12-20", "12-21", "12-22", "12-23", "12-24", "12-25", "12-26", "12-27", "12-28", "12-29", "12-30", "12-31", "01-01", "01-02", "01-03", "01-04", "01-05", "01-06", "01-07", "01-08", "01-09", "01-10", "01-11", "01-12", "01-13", "01-14", "01-15"],
                    values: [8500, 9200, 8800, 9500, 9100, 9300, 8700, 9600, 8900, 9400, 9200, 8800, 9500, 9100, 9300, 8700, 9600, 8900, 9400, 9200, 8800, 9500, 9100, 9300, 8700, 9600, 8900, 9400, 9200, 8800],
                },
                "90d": {
                    dates: ["10-18", "10-19", "10-20", "10-21", "10-22", "10-23", "10-24", "10-25", "10-26", "10-27", "10-28", "10-29", "10-30", "10-31", "11-01", "11-02", "11-03", "11-04", "11-05", "11-06", "11-07", "11-08", "11-09", "11-10", "11-11", "11-12", "11-13", "11-14", "11-15", "11-16", "11-17", "11-18", "11-19", "11-20", "11-21", "11-22", "11-23", "11-24", "11-25", "11-26", "11-27", "11-28", "11-29", "11-30", "12-01", "12-02", "12-03", "12-04", "12-05", "12-06", "12-07", "12-08", "12-09", "12-10", "12-11", "12-12", "12-13", "12-14", "12-15", "12-16", "12-17", "12-18", "12-19", "12-20", "12-21", "12-22", "12-23", "12-24", "12-25", "12-26", "12-27", "12-28", "12-29", "12-30", "12-31", "01-01", "01-02", "01-03", "01-04", "01-05", "01-06", "01-07", "01-08", "01-09", "01-10", "01-11", "01-12", "01-13", "01-14", "01-15"],
                    values: [35000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000, 42000, 48000, 45000, 46000, 47000, 44000, 49000, 43000, 50000],
                },
            },
            // TODO: 从接口获取数据分类统计数据
            categoryStats: [
                {
                    name: "视频内容",
                    count: 45230,
                    percentage: 36,
                    color: "bg-blue-500",
                },
                {
                    name: "用户评论",
                    count: 38240,
                    percentage: 30,
                    color: "bg-green-500",
                },
                {
                    name: "弹幕数据",
                    count: 25120,
                    percentage: 20,
                    color: "bg-purple-500",
                },
                {
                    name: "其他数据",
                    count: 16840,
                    percentage: 14,
                    color: "bg-amber-500",
                },
            ],
            // TODO: 从接口获取平台快照数据
            snapshots: [
                {
                    date: "2024-01-01",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
                {
                    date: "2024-03-15",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
                {
                    date: "2024-06-20",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
                {
                    date: "2024-09-10",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
                {
                    date: "2024-12-25",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
                {
                    date: "2025-01-01",
                    image: "https://www.horosama.com/api/image_all/anime/1080p/pc/1D7777CC99E23305868038B5DD305e02.jpg",
                },
            ],
            // TODO: 从接口获取关联情报数据
            relatedIntelligence: [
                {
                    id: 1,
                    category: "视频内容",
                    categoryType: "primary",
                    priority: "中",
                    priorityType: "",
                    date: "2025-01-15 14:30:22",
                    title: "B站UP主发布最新科技评测视频，引发广泛讨论",
                    description: "知名科技UP主发布了关于最新智能手机的深度评测视频，视频时长45分钟，详细分析了各项性能指标和使用体验，获得了大量用户的关注和讨论。",
                    tags: ["科技", "评测", "视频", "B站"],
                    platform: "Bilibili",
                    platform_id: "fb5bebe1b7df48e6606fdffed2cf8b14",
                    author: "科技评测君",
                    author_id: "test_author_0001",
                    views: 125430,
                    nsfw: false,
                },
                {
                    id: 2,
                    category: "用户评论",
                    categoryType: "success",
                    priority: "低",
                    priorityType: "info",
                    date: "2025-01-15 10:15:33",
                    title: "用户对B站新功能的反馈和建议",
                    description: "大量用户对B站最新推出的功能进行了讨论，主要集中在界面优化、播放体验和社区互动等方面，整体反馈较为积极。",
                    tags: ["用户反馈", "功能更新", "社区"],
                    platform: "Bilibili",
                    platform_id: "fb5bebe1b7df48e6606fdffed2cf8b14",
                    author: "B站用户",
                    author_id: "test_author_0002",
                    views: 8920,
                    nsfw: false,
                },
                {
                    id: 3,
                    category: "弹幕数据",
                    categoryType: "warning",
                    priority: "中",
                    priorityType: "",
                    date: "2025-01-14 18:45:11",
                    title: "热门视频弹幕数据分析报告",
                    description: "对近期热门视频的弹幕数据进行了深度分析，发现用户互动频率显著提升，弹幕内容质量也有所改善，体现了社区活跃度的增长。",
                    tags: ["弹幕", "数据分析", "热门视频"],
                    platform: "Bilibili",
                    platform_id: "fb5bebe1b7df48e6606fdffed2cf8b14",
                    author: "数据分析师",
                    author_id: "test_author_0003",
                    views: 6540,
                    nsfw: false,
                },
                {
                    id: 4,
                    category: "视频内容",
                    categoryType: "primary",
                    priority: "高",
                    priorityType: "warning",
                    date: "2025-01-14 09:20:45",
                    title: "B站年度盛典活动正式启动",
                    description: "B站宣布年度盛典活动正式启动，将评选出年度最佳UP主、最佳视频等多个奖项，吸引了大量创作者和用户的关注。",
                    tags: ["年度盛典", "活动", "UP主"],
                    platform: "Bilibili",
                    platform_id: "fb5bebe1b7df48e6606fdffed2cf8b14",
                    author: "B站官方",
                    author_id: "test_author_0004",
                    views: 21560,
                    nsfw: false,
                },
                {
                    id: 5,
                    category: "用户评论",
                    categoryType: "success",
                    priority: "中",
                    priorityType: "",
                    date: "2025-01-13 16:30:28",
                    title: "B站社区讨论热点话题汇总",
                    description: "本周B站社区讨论的热点话题主要集中在二次元文化、游戏攻略、生活分享等领域，用户参与度持续上升。",
                    tags: ["社区", "热点", "讨论"],
                    platform: "Bilibili",
                    platform_id: "fb5bebe1b7df48e6606fdffed2cf8b14",
                    author: "社区观察员",
                    author_id: "test_author_0005",
                    views: 18340,
                    nsfw: false,
                },
            ],
            intelligenceSortBy: "relevance",
            intelligenceCurrentPage: 1,
            intelligencePageSize: 5,
            intelligenceTotalResults: 25,
        };
    },
    mounted() {
        this.loadPlatformDetail();
        this.initChart();
    },
    beforeUnmount() {
        if (this.trendChart) {
            this.trendChart.dispose();
        }
        window.removeEventListener("resize", this.handleResize);
    },
    methods: {
        // TODO: 调用接口获取平台详情数据
        // 接口示例: GET /api/platforms/{platformId}
        loadPlatformDetail() {
            console.log("加载平台详情:", this.platformId);
        },
        getStatusType(status) {
            const statusMap = {
                正常: "success",
                异常: "danger",
                维护中: "warning",
                已停用: "info",
            };
            return statusMap[status] || "info";
        },
        switchRange(range) {
            this.updateChart();
        },
        initChart() {
            this.$nextTick(() => {
                const chartDom = document.getElementById("trend-chart");
                if (!chartDom) return;

                this.trendChart = echarts.init(chartDom);
                this.updateChart();

                this.handleResize = () => {
                    this.trendChart?.resize();
                };
                window.addEventListener("resize", this.handleResize);
            });
        },
        updateChart() {
            if (!this.trendChart) return;

            const data = this.trendData[this.currentRange];
            const dateCount = data.dates.length;
            let labelInterval = 0;
            if (dateCount > 30) {
                labelInterval = Math.floor(dateCount / 15);
            } else if (dateCount > 7) {
                labelInterval = Math.floor(dateCount / 10);
            }

            const option = {
                grid: {
                    left: "3%",
                    right: "4%",
                    bottom: "15%",
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
                        rotate: 45,
                        interval: labelInterval,
                        formatter: (value) => {
                            return value;
                        },
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
                            if (value >= 1000) {
                                return (value / 1000).toFixed(1) + "k";
                            }
                            return value;
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
                        return `${params[0].name
                            }<br/>数据量: <b>${value.toLocaleString()}条</b>`;
                    },
                },
            };

            this.trendChart.setOption(option);
        },
        refreshData() {
            this.$notify({
                title: "刷新数据",
                message: "正在刷新平台数据，请稍候...",
                type: "info",
                position: "top-right",
                duration: 3000,
            });
        },
        exportData() {
            this.$notify({
                title: "导出数据",
                message: "正在准备导出数据，请稍候...",
                type: "info",
                position: "top-right",
                duration: 3000,
            });
        },
        configurePlatform() {
            this.$notify({
                title: "配置平台",
                message: "正在打开平台配置页面...",
                type: "info",
                position: "top-right",
                duration: 3000,
            });
            // 路由示例: this.$router.push(`/platforms/${this.platformId}/config`)
        },
        createAction() {
            this.$notify({
                title: "创建专项行动",
                message: "正在打开创建专项行动页面...",
                type: "info",
                position: "top-right",
                duration: 3000,
            });
            // 路由示例: this.$router.push(`/action/create`)
        },
    },
};
</script>
