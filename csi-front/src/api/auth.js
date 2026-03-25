import { request } from '@/utils/request'

export const authApi = {
  login(data) {
    return request.post('/auth/login', data)
  },
  logout() {
    // 后端 logout 无 body 也能工作，这里传空对象以匹配 axios post 签名
    return request.post('/auth/logout', {})
  },
  me() {
    return request.get('/auth/me')
  }
}

