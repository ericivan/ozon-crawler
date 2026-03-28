import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import Keywords from '@/views/Keywords.vue'
import AnalysisDetail from '@/views/AnalysisDetail.vue'
import KwTool from '@/views/KwTool.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '选品总览' } },
  { path: '/keywords', name: 'Keywords', component: Keywords, meta: { title: '关键词管理' } },
  { path: '/analysis/:id', name: 'AnalysisDetail', component: AnalysisDetail, meta: { title: '分析详情' } },
  { path: '/kw-tool', name: 'KwTool', component: KwTool, meta: { title: '关键词工具' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'Ozon 分析'} - Ozon 选品系统`
})

export default router
