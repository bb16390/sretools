import { createRouter, createWebHistory } from 'vue-router'

import { getToken } from '@/api/http'
import AdminLayout from '@/layouts/AdminLayout.vue'
import CrudPage from '@/components/CrudPage.vue'
import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import FileUploadView from '@/views/FileUploadView.vue'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    public?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      component: AdminLayout,
      redirect: '/home',
      children: [
        { path: 'home', name: 'home', component: HomeView, meta: { title: '概览' } },
        {
          path: 'pages',
          name: 'nav-pages',
          component: CrudPage,
          props: { resourceKey: 'nav-page' },
          meta: { title: '页面管理' },
        },
        {
          path: 'collector/datasources',
          name: 'data-sources',
          component: CrudPage,
          props: { resourceKey: 'data-source' },
          meta: { title: '数据源' },
        },
        {
          path: 'collector/tasks',
          name: 'collector-tasks',
          component: CrudPage,
          props: { resourceKey: 'collector-task' },
          meta: { title: '采集任务' },
        },
        {
          path: 'system/users',
          name: 'users',
          component: CrudPage,
          props: { resourceKey: 'user' },
          meta: { title: '用户' },
        },
        {
          path: 'system/roles',
          name: 'roles',
          component: CrudPage,
          props: { resourceKey: 'role' },
          meta: { title: '角色' },
        },
        {
          path: 'system/login-history',
          name: 'login-history',
          component: CrudPage,
          props: { resourceKey: 'login-history' },
          meta: { title: '登录记录' },
        },
        {
          path: 'system/casbin-rules',
          name: 'casbin-rules',
          component: CrudPage,
          props: { resourceKey: 'casbin-rule' },
          meta: { title: '权限规则' },
        },
        {
          path: 'tools/file-upload',
          name: 'file-upload',
          component: FileUploadView,
          meta: { title: '文件上传' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
      meta: { title: '页面不存在', public: true },
    },
  ],
})

router.beforeEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - SRE Tools` : 'SRE Tools 管理台'
  const loggedIn = Boolean(getToken())

  if (to.meta.public) {
    if (to.name === 'login' && loggedIn) {
      return { path: '/home' }
    }
    return true
  }

  if (!loggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
