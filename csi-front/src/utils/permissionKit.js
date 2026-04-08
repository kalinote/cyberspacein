import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { hasAllPermissions } from '@/stores/auth'

/**
 * 权限工具（统一全站权限验证的代码结构与行为）
 *
 * 目标口径：
 * - 无 view：入口隐藏
 * - 有 view 无 use：入口展示但禁用（并且点击/提交会提示“无权限执行该操作”，且不触发跳转/请求）
 * - 写操作：发请求前必须做二次拦截（不要只依赖 disabled）
 *
 * 推荐用法（页面/组件里）：
 *
 * 1) 按钮/操作入口（view 控可见，use 控可用）
 *    const { canView, canUse, guard } = makeViewUse(PERM.operations.xxx.addView, PERM.operations.xxx.addUse)
 *    <el-button v-if="canView" :disabled="!canUse" @click="() => guard(() => doSomething())">新增</el-button>
 *
 * 2) API 写操作二次拦截（函数内）
 *    if (!guardUse(PERM.operations.xxx.deleteUse)) return
 *    await api.delete(...)
 *
 * 3) 导航/路由入口（router-link）
 *    - 无 view：v-if 不渲染
 *    - 无 use：显示灰态，点击时阻止跳转并提示
 *    <router-link
 *      v-if="nav.canView"
 *      :to="nav.canUse ? '/search' : route.fullPath"
 *      :class="nav.canUse ? '...' : 'cursor-not-allowed ...'"
 *      @click="(e) => nav.guardNav(e)"
 *    >检索</router-link>
 *
 * 注意：
 * - 本工具不引入新依赖，仅复用 element-plus 的 ElMessage 与现有 hasAllPermissions。
 * - 提示文案统一为中文，便于全站一致。
 */

export const DEFAULT_NO_PERM_MESSAGE = '无权限执行该操作'

export function hasAll(codes = []) {
  if (!codes || codes.length === 0) return true
  return hasAllPermissions(codes)
}

export function hasPerm(code) {
  if (!code) return true
  return hasAllPermissions([code])
}

export function hasAny(codes = []) {
  if (!Array.isArray(codes) || codes.length === 0) return true
  return codes.some(code => Boolean(code) && hasPerm(code))
}

export function noPerm(message = DEFAULT_NO_PERM_MESSAGE) {
  ElMessage.error(message)
}

/**
 * 写操作前置拦截：无权限则提示并返回 false
 * @param {string} useCode
 * @param {string} [message]
 * @returns {boolean}
 */
export function guardUse(useCode, message = DEFAULT_NO_PERM_MESSAGE) {
  if (hasPerm(useCode)) return true
  noPerm(message)
  return false
}

/**
 * 创建一组 view/use 的统一标志与 guard
 * @param {string} viewCode
 * @param {string} useCode
 * @param {{message?: string}} [opts]
 */
export function makeViewUse(viewCode, useCode, opts = {}) {
  const message = opts?.message || DEFAULT_NO_PERM_MESSAGE
  const canView = computed(() => hasPerm(viewCode))
  const canUse = computed(() => hasPerm(useCode))

  function guard(run, overrideMessage) {
    if (!guardUse(useCode, overrideMessage || message)) return false
    run?.()
    return true
  }

  /**
   * 用于导航类点击：无 use 时阻止并提示
   * @param {MouseEvent} e
   */
  function guardNav(e) {
    if (canUse.value) return true
    try {
      e?.preventDefault?.()
      e?.stopPropagation?.()
    } catch {
      // 忽略
    }
    noPerm(message)
    return false
  }

  return {
    canView,
    canUse,
    guard,
    guardNav
  }
}

