<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormItemRule,
  type FormRules,
} from 'element-plus'

import { crudApi } from '@/api/crud'
import { ApiError, request } from '@/api/http'
import {
  getResource,
  type ColumnDef,
  type ExtraAction,
  type FormField,
} from '@/config/resources'
import { formatDateTime, formatJson, isEmptyValue } from '@/utils/format'

const props = defineProps<{ resourceKey: string }>()

const resource = computed(() => getResource(props.resourceKey))

const rows = ref<Record<string, any>[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const perPage = ref(10)
const orderBy = ref('')
const orderDir = ref<'asc' | 'desc'>('asc')
const filterModel = reactive<Record<string, any>>({})
const filterExpanded = ref(false)
const selectedRows = ref<Record<string, any>[]>([])
const extraActionLoading = ref('')

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<string | number | null>(null)
const formRef = ref<FormInstance>()
const formModel = reactive<Record<string, any>>({})
const submitting = ref(false)

const canCreate = computed(() => !resource.value.readOnly && resource.value.canCreate !== false)
const canEdit = computed(() => !resource.value.readOnly && resource.value.canEdit !== false)
const canDelete = computed(() => !resource.value.readOnly && resource.value.canDelete !== false)

const activeFields = computed<FormField[]>(() =>
  resource.value.formFields.filter((field) =>
    dialogMode.value === 'create' ? !field.onlyEdit : !field.onlyCreate,
  ),
)

const visibleFilters = computed(() => {
  const filters = resource.value.filters ?? []
  return filterExpanded.value ? filters : filters.slice(0, 3)
})

const formRules = computed<FormRules>(() => {
  const rules: FormRules = {}
  for (const field of activeFields.value) {
    const fieldRules: FormItemRule[] = []
    const required = field.required || (dialogMode.value === 'create' && field.requiredOnCreate)
    if (required) {
      fieldRules.push({
        required: true,
        message: `请输入${field.label}`,
        trigger: field.type === 'select' ? 'change' : 'blur',
      })
    }
    if (field.type === 'json') {
      fieldRules.push({
        validator: (_rule, value, callback) => {
          if (isEmptyValue(value)) {
            callback()
            return
          }
          try {
            JSON.parse(String(value))
            callback()
          } catch {
            callback(new Error(`${field.label} 必须是合法 JSON`))
          }
        },
        trigger: 'blur',
      })
    }
    if (fieldRules.length) {
      rules[field.key] = fieldRules
    }
  }
  return rules
})

function notifyError(error: unknown): void {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      ElMessage.error('没有权限：当前账号缺少该资源或操作的权限（后端 status=401）')
    } else {
      ElMessage.error(error.message)
    }
    return
  }
  if (error instanceof Error) {
    ElMessage.error(error.message)
    return
  }
  ElMessage.error('操作失败')
}

function enumLabel(column: ColumnDef, value: unknown): string {
  const option = column.options?.find((item) => item.value === value)
  if (option) {
    return option.label
  }
  return isEmptyValue(value) ? '-' : String(value)
}

function resetFilterModel(): void {
  for (const key of Object.keys(filterModel)) {
    delete filterModel[key]
  }
  for (const field of resource.value.filters ?? []) {
    filterModel[field.key] = undefined
  }
}

function buildFilters(): Record<string, unknown> {
  const filters: Record<string, unknown> = {}
  for (const field of resource.value.filters ?? []) {
    const value = filterModel[field.key]
    if (isEmptyValue(value)) {
      continue
    }
    if (field.type === 'select') {
      filters[field.key] = value
      continue
    }
    if (field.type === 'number') {
      const num = Number(value)
      if (!Number.isNaN(num)) {
        filters[field.key] = num
      }
      continue
    }
    filters[field.key] = field.operator ? `${field.operator}${value}` : value
  }
  return filters
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await crudApi.list(resource.value.apiBase, {
      page: page.value,
      perPage: perPage.value,
      orderBy: orderBy.value || undefined,
      orderDir: orderDir.value,
      filters: buildFilters(),
    })
    rows.value = data.items ?? []
    total.value = data.total ?? rows.value.length
    selectedRows.value = []
  } catch (error) {
    rows.value = []
    total.value = 0
    notifyError(error)
  } finally {
    loading.value = false
  }
}

function search(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  resetFilterModel()
  page.value = 1
  void load()
}

function handlePageChange(value: number): void {
  page.value = value
  void load()
}

function handleSizeChange(value: number): void {
  perPage.value = value
  page.value = 1
  void load()
}

function handleSortChange(payload: {
  prop: string
  order: 'ascending' | 'descending' | null
}): void {
  if (!payload.order || !payload.prop) {
    orderBy.value = ''
    orderDir.value = 'asc'
  } else {
    orderBy.value = payload.prop
    orderDir.value = payload.order === 'ascending' ? 'asc' : 'desc'
  }
  page.value = 1
  void load()
}

function handleSelectionChange(selection: Record<string, any>[]): void {
  selectedRows.value = selection
}

function resetForm(values: Record<string, any> = {}): void {
  for (const key of Object.keys(formModel)) {
    delete formModel[key]
  }
  const initial: Record<string, any> = { ...(resource.value.defaults ?? {}) }
  for (const field of resource.value.formFields) {
    if (field.type === 'switch' && initial[field.key] === undefined) {
      initial[field.key] = false
    }
  }
  Object.assign(formModel, initial, values)
}

async function openCreate(): Promise<void> {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

async function openEdit(row: Record<string, any>): Promise<void> {
  const id = row.id
  if (id === undefined || id === null) {
    ElMessage.error('该记录缺少 id，无法编辑')
    return
  }
  dialogMode.value = 'edit'
  editingId.value = id

  let detail: Record<string, any> = { ...row }
  try {
    const data = await crudApi.read<Record<string, any>>(resource.value.apiBase, id)
    if (data) {
      detail = data
    }
  } catch (error) {
    // 无读详情权限时退回列表行数据，保存时后端仍会做最终校验
    if (!(error instanceof ApiError && error.status === 401)) {
      ElMessage.warning('读取详情失败，已使用列表数据回填')
    }
  }

  resetForm(detail)
  for (const field of resource.value.formFields) {
    if (field.type === 'password') {
      formModel[field.key] = ''
    }
  }
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const field of activeFields.value) {
    if (resource.value.payloadExclude?.includes(field.key)) {
      continue
    }
    const value = formModel[field.key]
    if (field.type === 'password') {
      if (isEmptyValue(value) || value === '**********') {
        continue
      }
      payload[field.key] = value
      continue
    }
    if (field.type === 'switch') {
      payload[field.key] = Boolean(value)
      continue
    }
    if (field.type === 'json') {
      const text = String(value ?? '')
      if (text.trim()) {
        try {
          JSON.parse(text)
        } catch {
          throw new ApiError(`${field.label} 不是合法 JSON`)
        }
      }
      payload[field.key] = text
      continue
    }
    if (field.type === 'number') {
      if (isEmptyValue(value)) {
        continue
      }
      const num = Number(value)
      if (!Number.isNaN(num)) {
        payload[field.key] = num
      }
      continue
    }
    if (isEmptyValue(value)) {
      continue
    }
    payload[field.key] = typeof value === 'string' ? value.trim() : value
  }
  return payload
}

async function submitForm(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  let payload: Record<string, unknown>
  try {
    payload = buildPayload()
  } catch (error) {
    notifyError(error)
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const query = resource.value.createQuery?.(formModel)
      await crudApi.create(resource.value.apiBase, payload, query)
      ElMessage.success('新建成功')
    } else {
      if (editingId.value === null) {
        throw new ApiError('缺少记录 ID')
      }
      await crudApi.update(resource.value.apiBase, editingId.value, payload)
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    notifyError(error)
  } finally {
    submitting.value = false
  }
}

async function removeRows(targets: Record<string, any>[]): Promise<void> {
  if (!targets.length) {
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${targets.length} 条记录？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  const ids = targets
    .map((row) => row.id)
    .filter((id): id is string | number => id !== undefined && id !== null)
  if (ids.length !== targets.length) {
    ElMessage.error('部分记录缺少 id，无法删除')
    return
  }

  try {
    await crudApi.remove(resource.value.apiBase, ids)
    ElMessage.success('删除成功')
    const maxPage = Math.max(1, Math.ceil((total.value - ids.length) / perPage.value))
    if (page.value > maxPage) {
      page.value = maxPage
    }
    await load()
  } catch (error) {
    notifyError(error)
  }
}

async function runExtraAction(action: ExtraAction): Promise<void> {
  if (action.confirm) {
    try {
      await ElMessageBox.confirm(action.confirm, '确认', {
        type: 'warning',
        confirmButtonText: '继续',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  extraActionLoading.value = action.label
  try {
    await request({ method: action.method, url: action.url })
    ElMessage.success(`${action.label}成功`)
    await load()
  } catch (error) {
    notifyError(error)
  } finally {
    extraActionLoading.value = ''
  }
}

onMounted(() => {
  orderBy.value = resource.value.orderBy ?? ''
  orderDir.value = resource.value.orderDir ?? 'asc'
  resetFilterModel()
  void load()
})

watch(
  () => props.resourceKey,
  () => {
    page.value = 1
    filterExpanded.value = false
    orderBy.value = resource.value.orderBy ?? ''
    orderDir.value = resource.value.orderDir ?? 'asc'
    resetFilterModel()
    void load()
  },
)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h2>{{ resource.title }}</h2>
        <p v-if="resource.description">{{ resource.description }}</p>
      </div>
      <div class="header-actions">
        <el-button
          v-for="action in resource.extraActions"
          :key="action.label"
          :loading="extraActionLoading === action.label"
          @click="runExtraAction(action)"
        >
          {{ action.label }}
        </el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">
          新建
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="resource.filterHint"
      type="info"
      :title="resource.filterHint"
      :closable="false"
      show-icon
      class="hint"
    />

    <el-card shadow="never">
      <el-form
        v-if="resource.filters?.length"
        inline
        class="filter-form"
        @submit.prevent="search"
      >
        <el-form-item v-for="field in visibleFilters" :key="field.key" :label="field.label">
          <el-select
            v-if="field.type === 'select'"
            v-model="filterModel[field.key]"
            clearable
            placeholder="全部"
            style="width: 150px"
          >
            <el-option
              v-for="option in field.options"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-input
            v-else
            v-model="filterModel[field.key]"
            clearable
            :placeholder="field.placeholder || '请输入'"
            style="width: 170px"
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="search">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button
            v-if="(resource.filters?.length ?? 0) > 3"
            link
            type="primary"
            @click="filterExpanded = !filterExpanded"
          >
            {{ filterExpanded ? '收起' : '展开' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="canDelete && selectedRows.length" class="bulk-bar">
        <span>已选 {{ selectedRows.length }} 条</span>
        <el-button type="danger" size="small" :icon="Delete" @click="removeRows(selectedRows)">
          批量删除
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="rows"
        :row-key="resource.readOnly ? undefined : 'id'"
        border
        stripe
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column v-if="canDelete" type="selection" width="44" />
        <el-table-column
          v-for="column in resource.columns"
          :key="column.key"
          :prop="column.key"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :sortable="column.sortable ? 'custom' : false"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-tag
              v-if="column.type === 'bool'"
              size="small"
              :type="row[column.key] ? 'success' : 'info'"
            >
              {{ row[column.key] ? '是' : '否' }}
            </el-tag>
            <span v-else-if="column.type === 'enum'">{{ enumLabel(column, row[column.key]) }}</span>
            <span v-else-if="column.type === 'datetime'">
              {{ formatDateTime(row[column.key]) }}
            </span>
            <span
              v-else-if="column.type === 'json'"
              class="table-json"
              :title="formatJson(row[column.key])"
            >
              {{ formatJson(row[column.key]) }}
            </span>
            <span v-else>{{ isEmptyValue(row[column.key]) ? '-' : row[column.key] }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="canEdit || canDelete" label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEdit" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" link type="danger" @click="removeRows([row])">
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" :image-size="70" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="perPage"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="`${dialogMode === 'create' ? '新建' : '编辑'}${resource.title}`"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="formModel" :rules="formRules" label-width="120px">
        <el-row :gutter="16">
          <el-col
            v-for="field in activeFields"
            :key="field.key"
            :span="field.span ?? 24"
          >
            <el-form-item :label="field.label" :prop="field.key">
              <el-switch v-if="field.type === 'switch'" v-model="formModel[field.key]" />
              <el-select
                v-else-if="field.type === 'select'"
                v-model="formModel[field.key]"
                clearable
                :placeholder="field.placeholder || '请选择'"
                style="width: 100%"
              >
                <el-option
                  v-for="option in field.options"
                  :key="String(option.value)"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="formModel[field.key]"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="formModel[field.key]"
                type="textarea"
                :rows="field.rows ?? 4"
                :placeholder="field.placeholder"
              />
              <el-input
                v-else-if="field.type === 'password'"
                v-model="formModel[field.key]"
                type="password"
                show-password
                :placeholder="field.placeholder || '请输入'"
              />
              <el-input
                v-else-if="field.type === 'json'"
                v-model="formModel[field.key]"
                type="textarea"
                :rows="field.rows ?? 8"
                class="mono"
                placeholder="{ }"
              />
              <el-input
                v-else
                v-model="formModel[field.key]"
                :placeholder="field.placeholder || '请输入'"
              />
              <div v-if="field.help" class="field-help">{{ field.help }}</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hint {
  margin-bottom: 16px;
}

.filter-form {
  margin-bottom: 4px;
}

.bulk-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 12px;
  border-radius: 6px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field-help {
  width: 100%;
  margin-top: 2px;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.table-json {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  color: #606266;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
</style>
