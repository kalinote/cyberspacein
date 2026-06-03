import { ref, watch } from 'vue'

const STORAGE_KEY = 'csi_agent_auto_approve'

function readStoredAutoApprove() {
    try {
        return localStorage.getItem(STORAGE_KEY) === '1'
    } catch {
        return false
    }
}

const autoApprove = ref(readStoredAutoApprove())

watch(autoApprove, (value) => {
    try {
        localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
    } catch {
        // ignore
    }
})

/**
 * 控制 Agent 工具调用是否自动通过审批（全局偏好，各入口共享）
 */
export function useAgentAutoApprove() {
    return { autoApprove }
}

export function getAgentAutoApproveValue() {
    return Boolean(autoApprove.value)
}
