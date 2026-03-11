<template>
    <Header />

    <div class="editor-container">
        <div class="preview-area">
            <div class="video-wrapper">
                <video ref="videoPlayer" class="main-video" :src="videoSrc" @timeupdate="handleTimeUpdate"
                    @loadedmetadata="handleLoadedMetadata" @click="togglePlay"></video>

                <div class="controls-overlay" v-if="!isPlaying" @click="togglePlay">
                    <span class="play-icon">▶</span>
                </div>
            </div>
        </div>

        <div class="timeline-area">
            <div class="toolbar">
                <span>当前时间: {{ formattedTime }}</span>
                <button @click="togglePlay">{{ isPlaying ? "暂停" : "播放" }}</button>
            </div>

            <div class="tracks-container" ref="timelineContainer" @click="seekTimeline">
                <div class="cursor-line" :style="{ left: cursorPosition + '%' }"></div>

                <div v-for="track in tracks" :key="track.id" class="track-row" :class="track.type">
                    <div class="track-header">{{ track.name }}</div>
                    <div class="track-content">
                        <div class="clip" :style="{
                            left: track.clipStart + '%',
                            width: track.clipDuration + '%',
                        }">
                            {{ track.clipName }}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import Header from '@/components/Header.vue'

defineOptions({ name: 'SimpleVideoEditor' })

const videoPlayer = ref(null)
const timelineContainer = ref(null)
const videoSrc = ref('https://www.w3schools.com/html/mov_bbb.mp4')
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const tracks = ref([
    {
        id: 1,
        type: 'video-track',
        name: '视频轨道 1',
        clipName: 'Main_Camera.mp4',
        clipStart: 0,
        clipDuration: 80
    },
    {
        id: 2,
        type: 'audio-track',
        name: '音频轨道 1',
        clipName: 'BGM_Epic.mp3',
        clipStart: 10,
        clipDuration: 60
    },
    {
        id: 3,
        type: 'text-track',
        name: '字幕轨道',
        clipName: 'Subtitle_01',
        clipStart: 20,
        clipDuration: 30
    }
])

const cursorPosition = computed(() => {
    if (duration.value === 0) return 0
    return (currentTime.value / duration.value) * 100
})

const formattedTime = computed(() => {
    const minutes = Math.floor(currentTime.value / 60)
    const seconds = Math.floor(currentTime.value % 60)
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
})

function togglePlay() {
    const video = videoPlayer.value
    if (!video) return
    if (video.paused) {
        video.play()
        isPlaying.value = true
    } else {
        video.pause()
        isPlaying.value = false
    }
}

function handleTimeUpdate(event) {
    currentTime.value = event.target.currentTime
}

function handleLoadedMetadata(event) {
    duration.value = event.target.duration
}

function seekTimeline(event) {
    const timeline = timelineContainer.value
    if (!timeline || !videoPlayer.value) return
    const rect = timeline.getBoundingClientRect()
    const clickX = event.clientX - rect.left
    const width = rect.width
    const percentage = Math.max(0, Math.min(1, clickX / width))
    const newTime = percentage * duration.value
    videoPlayer.value.currentTime = newTime
    currentTime.value = newTime
}
</script>

<style scoped>
/* 整体深色布局 */
.editor-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background-color: #1e1e1e;
    color: #ccc;
    font-family: Arial, sans-serif;
}

/* 上半部分：预览 */
.preview-area {
    flex: 1;
    /* 占据剩余空间 */
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #000;
    border-bottom: 2px solid #333;
    overflow: hidden;
}

.video-wrapper {
    position: relative;
    max-width: 90%;
    max-height: 90%;
}

.main-video {
    max-width: 100%;
    max-height: 100%;
    display: block;
}

.controls-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    justify-content: center;
    align-items: center;
    background: rgba(0, 0, 0, 0.3);
    cursor: pointer;
}

.play-icon {
    font-size: 50px;
    color: white;
    opacity: 0.8;
}

/* 下半部分：时间轴 */
.timeline-area {
    height: 300px;
    /* 固定高度，或者使用 flex 比例 */
    background-color: #252526;
    display: flex;
    flex-direction: column;
}

.toolbar {
    padding: 10px;
    background-color: #333;
    display: flex;
    gap: 15px;
    align-items: center;
    border-bottom: 1px solid #444;
}

.tracks-container {
    flex: 1;
    position: relative;
    overflow-x: auto;
    /* 允许横向滚动（如果很长） */
    overflow-y: auto;
    padding: 10px 0;
}

/* 时间游标红线 */
.cursor-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background-color: #e53935;
    z-index: 10;
    pointer-events: none;
    /* 让点击事件穿透到下层 */
}

/* 轨道样式 */
.track-row {
    display: flex;
    height: 50px;
    border-bottom: 1px solid #383838;
    position: relative;
    margin-bottom: 5px;
}

.track-header {
    width: 100px;
    background-color: #2d2d2d;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    border-right: 1px solid #444;
    flex-shrink: 0;
    /* 防止被压缩 */
}

.track-content {
    flex: 1;
    position: relative;
    background-color: #1e1e1e;
}

/* 轨道内的素材片段 */
.clip {
    position: absolute;
    top: 5px;
    bottom: 5px;
    background-color: #3a6ea5;
    border-radius: 4px;
    border: 1px solid #4a8ecf;
    display: flex;
    align-items: center;
    padding-left: 5px;
    font-size: 11px;
    color: white;
    overflow: hidden;
    white-space: nowrap;
    cursor: pointer;
}

.track-row.audio-track .clip {
    background-color: #2e7d32;
    border-color: #43a047;
}

.track-row.text-track .clip {
    background-color: #8e24aa;
    border-color: #ba68c8;
}
</style>
