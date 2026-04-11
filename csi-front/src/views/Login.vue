<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <el-card class="w-full max-w-md">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-bold text-gray-900">系统登录</span>
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

defineOptions({ name: 'Login' })

const router = useRouter()
const route = useRoute()

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
      permissions: payload.permissions || []
    })

    const redirect = route.query.redirect
    await router.push(redirect ? String(redirect) : '/')
  } catch {
  } finally {
    loading.value = false
  }
}
</script>

