// Composables
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('@/views/Home.vue'), meta:{ transition: 'fade'} },
  { path: '/control', name: 'Control', component: () => import('@/views/Control.vue'), meta:{ transition: 'fade'} },
]

const router = createRouter({
  // ✅ Vite-friendly: base from import.meta.env (or just createWebHistory())
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router

