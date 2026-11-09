<script setup lang="ts">
import { onMounted, ref, type Component } from 'vue'
import { DataLine, Document, Timer, User } from '@element-plus/icons-vue'

import { crudApi } from '@/api/crud'
import { getResource } from '@/config/resources'
import { useAuthStore } from '@/stores/auth'

interface StatCard {
  resourceKey: string
  label: string
  path: string
  value: number | null
}

const auth = useAuthStore()
const loading = ref(false)
const failedCount = ref(0)

const cards = ref<StatCard[]>([
  { resourceKey: 'nav-page', label: '管理页面', path: '/pages', value: null },
  { resourceKey: 'data-source', label: '数据源', path: '/collector/datasources', value: null },
  { resourceKey: 'collector-task', label: '采集任务', path: '/collector/tasks', value: null },
  { resourceKey: 'user', label: '用户', path: '/system/users', value: null },
])

const cardIcons: Record<string, Component> = {
  'nav-page': Document,
  'data-source': DataLine,
  'collector-task': Timer,
  user: User,
}

const apiBase = import.meta.env.VITE_API_BASE || '同源（开发期由 Vite 代理到后端）'

async function loadStats(): Promise<void> {
  loading.value = true
  failedCount.value = 0
  await Promise.all(
    cards.value.map(async (card) => {
      try {
        const resource = getResource(card.resourceKey)
        const data = await crudApi.list(resource.apiBase, { page: 1, perPage: 1 })
        card.value = data.total ?? data.items.length
      } catch {
        card.value = null
        failedCount.value += 1
      }
    }),
  )
  loading.value = false
}

onMounted(loadStats)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h2>概览</h2>
        <p>Vue 3 管理台，与现有FastAPI + amis 后台共用同一套接口和账号。</p>
      </div>
      <el-button :loading="loading" @click="loadStats">刷新统计</el-button>
    </div>

    <el-alert
      v-if="failedCount > 0"
      type="warning"
      show-icon
      :closable="false"
      class="permission-alert"
      :title="`有 ${failedCount} 项统计加载失败，通常是当前账号缺少对应页面的权限（后端 status=401）`"
    />

    <el-row :gutter="16">
      <el-col v-for="card in cards" :key="card.resourceKey" :xs="12" :sm="12" :md="6">
        <router-link :to="card.path" class="stat-card">
          <div class="stat-icon">
            <el-icon :size="20"><component :is="cardIcons[card.resourceKey]" /></el-icon>
          </div>
          <div>
            <div class="stat-value">
              <span v-if="card.value !== null">{{ card.value }}</span>
              <span v-else class="text-muted">—</span>
            </div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </router-link>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="info-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="info-card">
          <template #header>当前账号</template>
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="用户名">
              {{ auth.user?.username || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="昵称">
              {{ auth.user?.nickname || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="邮箱">
              {{ auth.user?.email || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="API 前缀">
              <span class="mono">{{ apiBase }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="info-card">
          <template #header>迁移说明</template>
          <ul class="migration-list">
            <li>已迁移：页面管理、数据源、采集任务、用户、角色、登录记录、权限规则、文件上传。</li>
            <li>旧版 amis 后台保留在 <code>/admin/</code>，可随时对照。</li>
            <li>Gateway 管理页在后端未注册，MCP 暂无管理界面，未纳入本次迁移。</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.permission-alert {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.stat-card:hover {
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
  transform: translateY(-2px);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: #eff6ff;
  color: #2563eb;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
}

.stat-label {
  margin-top: 2px;
  color: #909399;
  font-size: 13px;
}

.info-row {
  margin-top: 8px;
}

.info-card {
  margin-bottom: 16px;
}

.migration-list {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
  line-height: 2;
}

code {
  padding: 1px 5px;
  border-radius: 4px;
  background: #f2f3f5;
}
</style>
