<template>
    <div>
        <Header />

        <!-- 英雄区域 -->
        <section class="bg-linear-to-br from-blue-50 to-white py-12">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div class="lg:col-span-2">
                        <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">智能体</span>配管中心</h1>
                        <p class="text-gray-600 text-lg mb-6">统一管理智能体，从资源调配、提示词模板到分析引擎的全流程控制平台。</p>
                        <div class="flex flex-wrap gap-4">
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:user-circle" class="text-blue-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">人格设定</p>
                                    <p class="text-xl font-bold text-gray-900">10</p>
                                </div>
                            </div>
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:file-document-multiple" class="text-green-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">提示词模板</p>
                                    <p class="text-xl font-bold text-gray-900">5</p>
                                </div>
                            </div>
                            <div
                                class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                                    <Icon icon="mdi:brain" class="text-amber-600 text-xl" />
                                </div>
                                <div>
                                    <p class="text-sm text-gray-500">分析引擎</p>
                                    <p class="text-xl font-bold text-gray-900">2</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4">快速创建智能体</h3>
                        <div class="space-y-4">
                            <button
                                class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2"
                                @click="$router.push('/action/new')">
                                <Icon icon="mdi:rocket-launch-outline" />
                                <span>新建标准智能体</span>
                            </button>
                            <button
                                class="w-full bg-cyan-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2">
                                <Icon icon="mdi:brain" />
                                <span>配置分析引擎</span>
                            </button>
                            <button
                                class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2">
                                <Icon icon="mdi:file-document-multiple" />
                                <span>从模板创建智能体</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        
    </div>
</template>

<script>
import Header from '@/components/Header.vue'
import { Icon } from '@iconify/vue'

export default {
    name: 'AgentMonitor',
    components: {
        Header,
        Icon
    }
}
</script>