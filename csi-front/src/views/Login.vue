<template>
  <main v-if="isMobile" class="mobile-login">
    <header><img :src="brandLogoUrl" alt="CyberSpaceIN" /><h1>登录工作空间</h1><p>查看情报、跟进行动与管理资料</p></header>
    <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
      <el-form-item label="用户名"><el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" autocapitalize="none" :spellcheck="false" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" autocomplete="current-password" show-password placeholder="请输入密码" /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="loading" :disabled="!form.username.trim() || !form.password">登录</el-button>
    </el-form>
  </main>
  <div v-else class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <el-card class="w-full max-w-md">
      <template #header>
        <div class="flex flex-col items-center gap-3">
          <img
            :src="brandLogoUrl"
            alt="CyberSpaceIN"
            width="260"
            height="50"
            class="h-[50px] w-65 max-w-full object-cover"
          />
        </div>
      </template>

      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="w-full" :loading="loading" @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { setAuth } from '@/stores/auth'
import { useMobileViewport } from '@/composables/useMobileViewport'

defineOptions({ name: 'Login' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const route = useRoute()
const brandLogoUrl = `${import.meta.env.BASE_URL}brand/cyberspacein-logo.png`

const devUser = import.meta.env.VITE_DEV_LOGIN_USERNAME
const devPass = import.meta.env.VITE_DEV_LOGIN_PASSWORD

const form = reactive({
  username: import.meta.env.DEV && devUser ? String(devUser) : '',
  password: import.meta.env.DEV && devPass ? String(devPass) : ''
})

const loading = ref(false)

async function handleLogin() {
  if (loading.value) return
  const username = form.username?.trim()
  const password = form.password

  if (!username || !password) return

  loading.value = true
  try {
    const res = await authApi.login({ username, password })
    const payload = res.data || {}
    setAuth({
      accessToken: payload.access_token,
      user: payload.user,
      permissions: payload.permissions || [],
      authorizationVersion: payload.authorization_version,
      sessionId: payload.session_id,
      sessionExpiresAt: payload.session_expires_at
    })

    const redirect = route.query.redirect
    await router.push(redirect ? String(redirect) : '/')
  } catch {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.mobile-login { min-height: 100dvh; padding: max(56px, env(safe-area-inset-top)) 24px max(32px, env(safe-area-inset-bottom)); background: linear-gradient(155deg, #eff6ff, white 55%); }
.mobile-login header { margin-bottom: 36px; }
.mobile-login img { width: 230px; max-width: 100%; height: auto; margin-bottom: 36px; }
.mobile-login h1 { font-size: 26px; font-weight: 750; color: #0f172a; }
.mobile-login p { font-size: 14px; color: #64748b; margin-top: 10px; line-height: 1.7; }
.mobile-login :deep(.el-form-item) { margin-bottom: 24px; }
.mobile-login :deep(.el-input__wrapper) { min-height: 50px; border-radius: 12px; }
.mobile-login :deep(input) { font-size: 16px; }
.mobile-login .el-button { width: 100%; min-height: 50px; font-size: 16px; border-radius: 12px; margin-top: 8px; }
</style>

