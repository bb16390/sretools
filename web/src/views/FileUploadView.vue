<script setup lang="ts">
import { reactive, ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadInstance, type UploadUserFile } from 'element-plus'

import { ApiError, request } from '@/api/http'

const form = reactive({ title: '', description: '' })
const fileList = ref<UploadUserFile[]>([])
const uploadRef = ref<UploadInstance>()
const uploading = ref(false)
const errorMessage = ref('')
const result = ref<Record<string, unknown> | null>(null)

function submit(): void {
  if (!form.title.trim()) {
    ElMessage.warning('请填写文件标题')
    return
  }
  const file = fileList.value[0]?.raw
  if (!file) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  const data = new FormData()
  data.append('title', form.title.trim())
  data.append('description', form.description)
  data.append('file', file)

  uploading.value = true
  errorMessage.value = ''
  result.value = null

  request<Record<string, unknown>>({
    method: 'post',
    url: '/api/file-upload/submit',
    data,
  })
    .then((response) => {
      result.value = response
      ElMessage.success('提交成功')
    })
    .catch((error: unknown) => {
      errorMessage.value =
        error instanceof ApiError ? error.message : '上传失败，请稍后重试'
    })
    .finally(() => {
      uploading.value = false
    })
}

function reset(): void {
  form.title = ''
  form.description = ''
  fileList.value = []
  uploadRef.value?.clearFiles()
  result.value = null
  errorMessage.value = ''
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h2>文件上传</h2>
        <p>对应旧后台 FileUploadApp，提交到后端 POST /api/file-upload/submit（单文件，最大 10MB）。</p>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="14">
        <el-card shadow="never">
          <el-form label-width="90px">
            <el-form-item label="标题" required>
              <el-input v-model="form.title" placeholder="请输入标题" maxlength="100" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="3"
                placeholder="请输入描述"
              />
            </el-form-item>
            <el-form-item label="文件">
              <el-upload
                ref="uploadRef"
                v-model:file-list="fileList"
                class="uploader"
                drag
                action="#"
                :auto-upload="false"
                :limit="1"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
                <template #tip>
                  <div class="el-upload__tip">仅提交一个文件，后端限制最大 10MB。</div>
                </template>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="uploading" @click="submit">提交</el-button>
              <el-button @click="reset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="10">
        <el-card shadow="never">
          <template #header>提交结果</template>
          <el-alert
            v-if="errorMessage"
            :title="errorMessage"
            type="error"
            :closable="false"
            show-icon
          />
          <pre v-else-if="result" class="result-json">{{ JSON.stringify(result, null, 2) }}</pre>
          <el-empty v-else description="提交后在此展示后端返回结果" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.uploader {
  width: 100%;
}

.upload-icon {
  margin-bottom: 8px;
  color: #a8abb2;
  font-size: 40px;
}

.result-json {
  max-height: 360px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border-radius: 8px;
  background: #f5f7fa;
  color: #303133;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
