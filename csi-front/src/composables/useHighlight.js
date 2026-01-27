import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { highlightApi } from '@/api/highlight'

export function useHighlight(options = {}) {
  const {
    entityType,
    getData,
    reloadData,
    withDialog = true,
    defaultReason = '用户手动标记重点'
  } = options

  const showHighlightDialog = ref(false)
  const highlightLoading = ref(false)
  const highlightForm = ref({
    reason: ''
  })

  const isPriorityTarget = computed(() => {
    const data = getData?.()
    return data?.is_highlighted === true
  })

  const togglePriorityTarget = async () => {
    const data = getData?.()
    if (!data) return

    if (data.is_highlighted) {
      await cancelHighlight()
    } else {
      if (withDialog) {
        highlightForm.value.reason = ''
        showHighlightDialog.value = true
      } else {
        await setHighlightDirect(defaultReason)
      }
    }
  }

  const setHighlightDirect = async (reason) => {
    const data = getData?.()
    if (!data?.uuid) return

    highlightLoading.value = true
    try {
      const response = await highlightApi.setHighlight(entityType, data.uuid, {
        is_highlighted: true,
        highlight_reason: reason
      })

      if (response.code === 0) {
        ElMessage.success('已设置为重点目标')
        if (reloadData) {
          await reloadData()
        }
        return true
      } else {
        ElMessage.error(response.message || '设置重点目标失败')
        return false
      }
    } catch (err) {
      console.error('设置重点目标失败:', err)
      ElMessage.error('设置重点目标失败，请稍后重试')
      return false
    } finally {
      highlightLoading.value = false
    }
  }

  const confirmSetHighlight = async () => {
    const reason = highlightForm.value.reason?.trim() || defaultReason
    const success = await setHighlightDirect(reason)
    if (success) {
      showHighlightDialog.value = false
    }
  }

  const cancelHighlight = async () => {
    const data = getData?.()
    if (!data?.uuid) return

    highlightLoading.value = true
    try {
      const response = await highlightApi.setHighlight(entityType, data.uuid, {
        is_highlighted: false
      })

      if (response.code === 0) {
        ElMessage.success('已取消重点目标')
        if (reloadData) {
          await reloadData()
        }
      } else {
        ElMessage.error(response.message || '取消重点目标失败')
      }
    } catch (err) {
      console.error('取消重点目标失败:', err)
      ElMessage.error('取消重点目标失败，请稍后重试')
    } finally {
      highlightLoading.value = false
    }
  }

  const toggleHighlightForItem = async (item, itemEntityType) => {
    if (!item || !item.uuid) return

    item._highlightLoading = true

    try {
      const isHighlighted = item.is_highlighted
      const type = itemEntityType || entityType
      const requestData = isHighlighted
        ? { is_highlighted: false }
        : { is_highlighted: true, highlight_reason: defaultReason }

      const response = await highlightApi.setHighlight(type, item.uuid, requestData)

      if (response.code === 0) {
        item.is_highlighted = !isHighlighted
        ElMessage.success(isHighlighted ? '已取消重点目标' : '已设置为重点目标')
        return true
      } else {
        ElMessage.error(response.message || (isHighlighted ? '取消重点目标失败' : '设置重点目标失败'))
        return false
      }
    } catch (err) {
      console.error('操作重点目标失败:', err)
      ElMessage.error('操作失败，请稍后重试')
      return false
    } finally {
      item._highlightLoading = false
    }
  }

  return {
    showHighlightDialog,
    highlightLoading,
    highlightForm,
    isPriorityTarget,
    togglePriorityTarget,
    confirmSetHighlight,
    cancelHighlight,
    toggleHighlightForItem
  }
}
