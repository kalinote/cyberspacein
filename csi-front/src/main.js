import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import './assets/css/style.css'
import App from './App.vue'
import router from './router'
import { refreshAuthContext } from '@/services/authContext'
import { registerPermissionRefresher } from '@/utils/request'
import { getAuthState } from '@/stores/auth'

registerPermissionRefresher(refreshAuthContext)
window.addEventListener('focus', () => {
    if (getAuthState().accessToken) refreshAuthContext().catch(() => {})
})

const app = createApp(App)

app.use(router)
app.use(ElementPlus)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

app.mount('#app')
