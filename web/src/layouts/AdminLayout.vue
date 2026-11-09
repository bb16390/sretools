<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Coin,
  DataLine,
  Document,
  Expand,
  Fold,
  HomeFilled,
  List,
  Lock,
  Timer,
  UploadFilled,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapsed = ref(false)

const currentTitle = computed(() => route.meta.title ?? '')
const userInitial = computed(() => auth.displayName.slice(0, 1).toUpperCase())

onMounted(() => {
  if (!auth.user) {
    auth.fetchUser().catch(() => {
      // 令牌可能已失效，交由全局 401 处理
    })
  }
})

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await auth.logout()
  } catch {
    ElMessage.warning('登出接口未正常返回，本地登录态已清除')
  }
  router.replace({ name: 'login' })
}

function onCommand(command: string): void {
  if (command === 'logout') {
    void handleLogout()
  }
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="aside">
      <div class="brand">
        <span class="brand-mark">SR</span>
        <span v-show="!collapsed" class="brand-text">SRE Tools</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        background-color="#1d2939"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
        class="menu"
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <template #title>概览</template>
        </el-menu-item>
        <el-menu-item index="/pages">
          <el-icon><Document /></el-icon>
          <template #title>页面管理</template>
        </el-menu-item>
        <el-sub-menu index="collector">
          <template #title>
            <el-icon><DataLine /></el-icon>
            <span>数据采集</span>
          </template>
          <el-menu-item index="/collector/datasources">
            <el-icon><Coin /></el-icon>
            <template #title>数据源</template>
          </el-menu-item>
          <el-menu-item index="/collector/tasks">
            <el-icon><Timer /></el-icon>
            <template #title>采集任务</template>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Lock /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/system/users">
            <el-icon><User /></el-icon>
            <template #title>用户</template>
          </el-menu-item>
          <el-menu-item index="/system/roles">
            <el-icon><UserFilled /></el-icon>
            <template #title>角色</template>
          </el-menu-item>
          <el-menu-item index="/system/login-history">
            <el-icon><List /></el-icon>
            <template #title>登录记录</template>
          </el-menu-item>
          <el-menu-item index="/system/casbin-rules">
            <el-icon><Lock /></el-icon>
            <template #title>权限规则</template>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/tools/file-upload">
          <el-icon><UploadFilled /></el-icon>
          <template #title>文件上传</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button text class="collapse-btn" @click="collapsed = !collapsed">
            <el-icon :size="18">
              <Fold v-if="!collapsed" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>SRE Tools</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-link href="/admin/" target="_blank" type="primary" underline="never">
            旧版 amis 后台
          </el-link>
          <el-dropdown @command="onCommand">
            <span class="user-entry">
              <el-avatar :size="26" class="user-avatar">{{ userInitial }}</el-avatar>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}

.aside {
  display: flex;
  flex-direction: column;
  background: #1d2939;
  transition: width 0.2s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 56px;
  padding: 0 16px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  font-size: 13px;
  font-weight: 700;
}

.menu {
  flex: 1;
  border-right: none;
}

.menu :deep(.el-menu-item.is-active) {
  background: #2563eb;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  padding: 4px;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #303133;
  cursor: pointer;
  outline: none;
}

.user-avatar {
  background: #2563eb;
  font-size: 12px;
}

.user-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main {
  padding: 20px;
  background: #f5f7fa;
}

@media (max-width: 768px) {
  .user-name {
    display: none;
  }

  .header-right {
    gap: 10px;
  }
}
</style>
