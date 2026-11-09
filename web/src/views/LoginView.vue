<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMessage = ref('')

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    const target = typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/home'
    router.replace(target)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? error.message : '登录失败，请检查网络或后端服务'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="login-intro">
        <span class="brand-mark">SR</span>
        <h1>SRE Tools</h1>
        <p>运维采集与网关管理控制台</p>
        <ul>
          <li>与现有 amis 后台共用账号体系</li>
          <li>页面、数据源、采集任务统一管理</li>
          <li>Vue 3 前端，可与旧后台并行使用</li>
        </ul>
      </div>

      <div class="login-card">
        <h2>账号登录</h2>
        <p class="login-subtitle">使用 amis 管理后台的账号密码登录</p>

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
          class="login-error"
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              :prefix-icon="User"
              placeholder="请输入用户名"
              autocomplete="username"
              autofocus
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              :prefix-icon="Lock"
              type="password"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button type="primary" :loading="loading" class="login-button" @click="submit">
            登录
          </el-button>
        </el-form>

        <div class="login-footer">
          <el-link href="/admin/" target="_blank" type="primary" underline="never">
            返回旧版 amis 后台
          </el-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 32px 20px;
  background:
    radial-gradient(circle at 15% 15%, rgba(59, 130, 246, 0.35), transparent 45%),
    radial-gradient(circle at 85% 80%, rgba(6, 182, 212, 0.3), transparent 45%),
    #0f172a;
}

.login-panel {
  display: flex;
  width: 100%;
  max-width: 920px;
  min-height: 480px;
  overflow: hidden;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.35);
}

.login-intro {
  display: flex;
  flex: 1 1 46%;
  flex-direction: column;
  justify-content: center;
  padding: 48px 40px;
  color: #e2e8f0;
  background: linear-gradient(160deg, #1d2939, #1e3a8a 60%, #0e7490);
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  color: #fff;
  font-weight: 700;
}

.login-intro h1 {
  margin: 0 0 8px;
  font-size: 30px;
  letter-spacing: 1px;
}

.login-intro p {
  margin: 0 0 24px;
  color: #cbd5e1;
}

.login-intro ul {
  margin: 0;
  padding-left: 18px;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 2;
}

.login-card {
  flex: 1 1 54%;
  padding: 52px 44px;
}

.login-card h2 {
  margin: 0 0 6px;
  font-size: 22px;
}

.login-subtitle {
  margin: 0 0 22px;
  color: #909399;
  font-size: 13px;
}

.login-error {
  margin-bottom: 18px;
}

.login-button {
  width: 100%;
  margin-top: 8px;
}

.login-footer {
  margin-top: 22px;
  font-size: 13px;
  text-align: right;
}

@media (max-width: 760px) {
  .login-panel {
    max-width: 460px;
    min-height: auto;
  }

  .login-intro {
    display: none;
  }

  .login-card {
    padding: 36px 28px;
  }
}
</style>
