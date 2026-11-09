/**
 * 现有 amis ModelAdmin 到前端资源页面的映射。
 * 所有 apiBase 均来自实测路由（master 服务，site_path=/admin）。
 */

export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'switch'
  | 'select'
  | 'json'
  | 'password'

export type ColumnType = 'text' | 'number' | 'bool' | 'enum' | 'datetime' | 'json'

export interface SelectOption {
  label: string
  value: string | number | boolean
}

export interface FormField {
  key: string
  label: string
  type?: FieldType
  required?: boolean
  /** 仅新建时必填（例如用户密码） */
  requiredOnCreate?: boolean
  onlyCreate?: boolean
  onlyEdit?: boolean
  placeholder?: string
  help?: string
  options?: SelectOption[]
  span?: number
  rows?: number
}

export interface ColumnDef {
  key: string
  label: string
  type?: ColumnType
  options?: SelectOption[]
  width?: number
  minWidth?: number
  sortable?: boolean
}

export interface FilterField {
  key: string
  label: string
  type?: 'text' | 'select' | 'number'
  options?: SelectOption[]
  /** 文本过滤操作符，如 [~] 模糊匹配、[=] 精确匹配 */
  operator?: string
  placeholder?: string
}

export interface ExtraAction {
  label: string
  method: 'get' | 'post'
  url: string
  confirm?: string
}

export interface CrudResource {
  key: string
  title: string
  description?: string
  apiBase: string
  columns: ColumnDef[]
  formFields: FormField[]
  filters?: FilterField[]
  filterHint?: string
  defaults?: Record<string, unknown>
  orderBy?: string
  orderDir?: 'asc' | 'desc'
  readOnly?: boolean
  canCreate?: boolean
  canEdit?: boolean
  canDelete?: boolean
  /** 新建时附带的 query 参数（如 NavPage 的 parent_id） */
  createQuery?: (values: Record<string, unknown>) => Record<string, string>
  /** 不放入请求体的字段 */
  payloadExclude?: string[]
  extraActions?: ExtraAction[]
}

const boolOptions: SelectOption[] = [
  { label: '是', value: true },
  { label: '否', value: false },
]

export const navPageTypeOptions: SelectOption[] = [
  { label: '页面分组', value: 1 },
  { label: 'Amis 页面 API', value: 2 },
  { label: 'Amis 页面', value: 3 },
  { label: '页面链接', value: 4 },
  { label: 'Iframe 页面', value: 5 },
  { label: '自定义页面', value: 6 },
]

const tabsModeOptions: SelectOption[] = [
  { label: 'line', value: 'line' },
  { label: 'card', value: 'card' },
  { label: 'radio', value: 'radio' },
  { label: 'vertical', value: 'vertical' },
  { label: 'chrome', value: 'chrome' },
  { label: 'simple', value: 'simple' },
  { label: 'strong', value: 'strong' },
  { label: 'tiled', value: 'tiled' },
]

export const collectorTypeOptions: SelectOption[] = [
  { label: '数据库', value: 0 },
  { label: 'Kafka', value: 1 },
  { label: 'HTTP', value: 2 },
  { label: 'WebSocket', value: 3 },
]

export const databaseTypeOptions: SelectOption[] = [
  { label: 'Oracle', value: 0 },
  { label: 'MySQL', value: 1 },
  { label: 'PostgreSQL', value: 2 },
  { label: 'SQLite', value: 3 },
  { label: 'InfluxDB', value: 4 },
  { label: 'Redis', value: 5 },
  { label: 'SQL Server', value: 6 },
  { label: 'Elasticsearch', value: 7 },
  { label: 'ClickHouse', value: 8 },
]

const taskStatusOptions: SelectOption[] = [
  { label: '已确认', value: 0 },
  { label: '待确认', value: 1 },
  { label: '运行中', value: 2 },
  { label: '暂停', value: 3 },
  { label: '停止', value: 4 },
  { label: '错误', value: 5 },
]

const execStatusOptions: SelectOption[] = [
  { label: '成功', value: 0 },
  { label: '失败', value: 1 },
  { label: '运行中', value: 2 },
]

const dataSourceStatusOptions: SelectOption[] = [
  { label: '已确认', value: 0 },
  { label: '待确认', value: 1 },
  { label: '错误', value: 2 },
]

const navPage: CrudResource = {
  key: 'nav-page',
  title: '页面管理',
  description: '对应 master/index/admin.py 的 NavPageAdmin（system_page 表）',
  apiBase: '/admin/NavPageAdmin',
  orderBy: 'id',
  orderDir: 'desc',
  filterHint:
    '后端仅开放 visible / is_custom / is_group / is_active / is_locked / parent_id 过滤，页面名称暂不支持服务端搜索。',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'label', label: '页面名称', minWidth: 140 },
    { key: 'icon', label: '图标', width: 150 },
    { key: 'url', label: '页面路径', minWidth: 170 },
    { key: 'desc', label: '描述', minWidth: 140 },
    { key: 'visible', label: '可见', type: 'bool', width: 80 },
    { key: 'is_active', label: '激活', type: 'bool', width: 80 },
    { key: 'is_locked', label: '锁定', type: 'bool', width: 80 },
    { key: 'unique_id', label: '标识', width: 150 },
    { key: 'update_time', label: '更新时间', type: 'datetime', width: 170 },
  ],
  filters: [
    { key: 'visible', label: '是否可见', type: 'select', options: boolOptions },
    { key: 'is_active', label: '是否激活', type: 'select', options: boolOptions },
    { key: 'is_locked', label: '是否锁定', type: 'select', options: boolOptions },
    { key: 'is_custom', label: '是否自定义', type: 'select', options: boolOptions },
    { key: 'is_group', label: '是否分组', type: 'select', options: boolOptions },
    { key: 'parent_id', label: '上级菜单 ID', type: 'number', placeholder: '精确匹配' },
  ],
  defaults: {
    type: 6,
    icon: 'fa fa-flash',
    visible: true,
    is_locked: false,
    page_schema: '{}',
  },
  formFields: [
    {
      key: 'type',
      label: '页面类型',
      type: 'select',
      required: true,
      options: navPageTypeOptions,
      span: 12,
    },
    { key: 'label', label: '页面名称', required: true, span: 12, placeholder: '最多 20 个字符' },
    { key: 'icon', label: '页面图标', span: 12, placeholder: '如 fa fa-flash' },
    { key: 'url', label: '页面路径', span: 12, placeholder: '如 /admin/page/home' },
    { key: 'desc', label: '页面描述', type: 'textarea', rows: 2 },
    { key: 'visible', label: '是否可见', type: 'switch', span: 8 },
    { key: 'is_locked', label: '是否锁定', type: 'switch', span: 8 },
    {
      key: 'tabsMode',
      label: '分组展示模式',
      type: 'select',
      options: tabsModeOptions,
      span: 8,
    },
    {
      key: 'parent_id',
      label: '上级菜单 ID',
      type: 'number',
      onlyCreate: true,
      span: 12,
      help: '新建时作为 query 参数 parent_id 提交',
    },
    {
      key: 'page_schema',
      label: '页面配置',
      type: 'json',
      rows: 8,
      help: 'JSON 字符串，对应 amis PageSchema',
    },
  ],
  createQuery: (values) => ({
    parent_id: values.parent_id === undefined || values.parent_id === null ? '' : String(values.parent_id),
  }),
  payloadExclude: ['parent_id'],
}

const dataSource: CrudResource = {
  key: 'data-source',
  title: '数据源',
  description: '对应 apps/collector/admin.py 的 DataSourceAdmin（t_data_source 表）',
  apiBase: '/admin/collector/DataSourceAdmin',
  orderBy: 'id',
  orderDir: 'desc',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'node', label: '节点', minWidth: 120 },
    { key: 'name', label: '数据源名称', minWidth: 150 },
    { key: 'collector_type', label: '采集器类型', type: 'enum', options: collectorTypeOptions, width: 120 },
    { key: 'database_type', label: '数据库类型', type: 'enum', options: databaseTypeOptions, width: 130 },
    { key: 'status', label: '状态', type: 'enum', options: dataSourceStatusOptions, width: 100 },
    { key: 'url', label: '连接串', minWidth: 220 },
    { key: 'username', label: '用户名', width: 130 },
  ],
  filters: [
    { key: 'node', label: '节点', operator: '[~]' },
    { key: 'name', label: '名称', operator: '[~]' },
    { key: 'collector_type', label: '采集器类型', type: 'select', options: collectorTypeOptions },
    { key: 'database_type', label: '数据库类型', type: 'select', options: databaseTypeOptions },
    { key: 'status', label: '状态', type: 'select', options: dataSourceStatusOptions },
  ],
  defaults: { collector_type: 0, database_type: 0, status: 1 },
  formFields: [
    { key: 'node', label: '节点', required: true, span: 12 },
    { key: 'name', label: '数据源名称', required: true, span: 12 },
    { key: 'collector_type', label: '采集器类型', type: 'select', required: true, options: collectorTypeOptions, span: 12 },
    { key: 'database_type', label: '数据库类型', type: 'select', required: true, options: databaseTypeOptions, span: 12 },
    { key: 'status', label: '数据源状态', type: 'select', required: true, options: dataSourceStatusOptions, span: 12 },
    { key: 'url', label: '连接串', required: true, span: 12 },
    { key: 'username', label: '用户名', required: true, span: 12 },
    {
      key: 'password',
      label: '密码',
      type: 'password',
      requiredOnCreate: true,
      span: 12,
      help: '编辑时留空表示不修改',
    },
  ],
}

const collectorTask: CrudResource = {
  key: 'collector-task',
  title: '采集任务',
  description: '对应 apps/collector/admin.py 的 CollectorTaskAdmin（t_collector_task 表）',
  apiBase: '/admin/collector/CollectorTaskAdmin',
  orderBy: 'id',
  orderDir: 'desc',
  filterHint:
    'job_id、last_run_time 等运行期字段由后端自动生成，无需在表单中填写。',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'name', label: '任务名称', minWidth: 150 },
    { key: 'collector_type', label: '采集器类型', type: 'enum', options: collectorTypeOptions, width: 120 },
    { key: 'status', label: '状态', type: 'enum', options: taskStatusOptions, width: 100 },
    { key: 'exec_status', label: '执行状态', type: 'enum', options: execStatusOptions, width: 100 },
    { key: 'subsystem_id', label: '子系统 ID', width: 100 },
    { key: 'worker_id', label: '工作节点', width: 130 },
    { key: 'last_run_time', label: '上次执行', width: 170 },
    { key: 'total_run_count', label: '总次数', width: 90 },
    { key: 'total_failed_count', label: '失败次数', width: 90 },
    { key: 'update_time', label: '更新时间', type: 'datetime', width: 170 },
  ],
  filters: [
    { key: 'name', label: '任务名称', operator: '[~]' },
    { key: 'id', label: '任务 ID', type: 'number' },
    { key: 'collector_type', label: '采集器类型', type: 'select', options: collectorTypeOptions },
    { key: 'status', label: '状态', type: 'select', options: taskStatusOptions },
  ],
  defaults: { collector_type: 0, status: 1, exec_status: 2, timeout: 30, conf: '{}' },
  formFields: [
    { key: 'name', label: '任务名称', required: true, span: 12 },
    { key: 'collector_type', label: '采集器类型', type: 'select', required: true, options: collectorTypeOptions, span: 12 },
    { key: 'status', label: '任务状态', type: 'select', required: true, options: taskStatusOptions, span: 12 },
    { key: 'exec_status', label: '执行状态', type: 'select', required: true, options: execStatusOptions, span: 12 },
    { key: 'data_source_id', label: '数据源 ID', type: 'number', required: true, span: 12 },
    { key: 'subsystem_id', label: '子系统 ID', type: 'number', required: true, span: 12 },
    { key: 'url', label: '连接串', required: true, span: 12 },
    { key: 'username', label: '用户名', required: true, span: 12 },
    {
      key: 'password',
      label: '密码',
      type: 'password',
      requiredOnCreate: true,
      span: 12,
      help: '编辑时留空表示不修改',
    },
    { key: 'worker_id', label: '工作节点', span: 12 },
    { key: 'timeout', label: '超时时间（秒）', type: 'number', span: 12 },
    {
      key: 'transform_script',
      label: '转换脚本',
      type: 'textarea',
      rows: 5,
      placeholder: 'Python 脚本',
    },
    { key: 'conf', label: '配置项', type: 'json', rows: 10 },
  ],
}

const user: CrudResource = {
  key: 'user',
  title: '用户',
  description: '对应 fastapi_user_auth 的 UserAdmin（auth_user 表）',
  apiBase: '/admin/auth/UserAdmin',
  orderBy: 'id',
  orderDir: 'desc',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'username', label: '用户名', minWidth: 130 },
    { key: 'nickname', label: '昵称', minWidth: 120 },
    { key: 'email', label: '邮箱', minWidth: 170 },
    { key: 'is_active', label: '启用', type: 'bool', width: 80 },
    { key: 'create_time', label: '创建时间', type: 'datetime', width: 170 },
  ],
  filters: [
    { key: 'username', label: '用户名', operator: '[~]' },
    { key: 'nickname', label: '昵称', operator: '[~]' },
    { key: 'email', label: '邮箱', operator: '[~]' },
    { key: 'is_active', label: '是否启用', type: 'select', options: boolOptions },
  ],
  defaults: { is_active: true },
  formFields: [
    { key: 'username', label: '用户名', required: true, onlyCreate: true, span: 12 },
    {
      key: 'password',
      label: '密码',
      type: 'password',
      requiredOnCreate: true,
      span: 12,
      help: '编辑时留空表示不修改',
    },
    { key: 'nickname', label: '昵称', span: 12 },
    { key: 'email', label: '邮箱', span: 12 },
    { key: 'avatar', label: '头像地址', span: 12 },
    { key: 'is_active', label: '是否启用', type: 'switch', span: 12 },
  ],
}

const role: CrudResource = {
  key: 'role',
  title: '角色',
  description: '对应 fastapi_user_auth 的 RoleAdmin（auth_role 表）',
  apiBase: '/admin/auth/RoleAdmin',
  orderBy: 'id',
  orderDir: 'desc',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'key', label: '角色标识', minWidth: 140 },
    { key: 'name', label: '角色名称', minWidth: 140 },
    { key: 'desc', label: '描述', minWidth: 200 },
  ],
  filters: [
    { key: 'key', label: '角色标识', operator: '[~]' },
    { key: 'name', label: '角色名称', operator: '[~]' },
  ],
  formFields: [
    { key: 'key', label: '角色标识', required: true, onlyCreate: true, span: 12 },
    { key: 'name', label: '角色名称', span: 12 },
    { key: 'desc', label: '描述', type: 'textarea', rows: 3 },
  ],
}

const loginHistory: CrudResource = {
  key: 'login-history',
  title: '登录记录',
  description: '只读：对应 LoginHistoryAdmin（auth_login_history 表）',
  apiBase: '/admin/auth/LoginHistoryAdmin',
  orderBy: 'create_time',
  orderDir: 'desc',
  readOnly: true,
  canCreate: false,
  canEdit: false,
  canDelete: false,
  columns: [
    { key: 'nickname', label: '昵称', width: 120 },
    { key: 'login_name', label: '登录名', width: 130 },
    { key: 'ip', label: 'IP', width: 140 },
    { key: 'login_status', label: '登录状态', width: 120 },
    { key: 'create_time', label: '时间', type: 'datetime', width: 170 },
    { key: 'user_agent', label: 'User-Agent', minWidth: 260 },
    { key: 'forwarded_for', label: '转发 IP', width: 140 },
    { key: 'ip_info', label: 'IP 信息', minWidth: 140 },
  ],
  filters: [
    { key: 'login_name', label: '登录名', operator: '[~]' },
    { key: 'ip', label: 'IP', operator: '[~]' },
    { key: 'login_status', label: '登录状态', operator: '[~]' },
    { key: 'user_agent', label: 'User-Agent', operator: '[~]' },
  ],
  formFields: [],
}

const casbinRule: CrudResource = {
  key: 'casbin-rule',
  title: '权限规则',
  description: '只读：对应 CasbinRuleAdmin（auth_casbin_rule 表）',
  apiBase: '/admin/auth/CasbinRuleAdmin',
  orderBy: 'id',
  orderDir: 'asc',
  readOnly: true,
  canCreate: false,
  canEdit: false,
  canDelete: false,
  columns: [
    { key: 'id', label: 'ID', width: 70 },
    { key: 'ptype', label: '类型', width: 80 },
    { key: 'v0', label: 'Subject', minWidth: 180 },
    { key: 'v1', label: 'Object', minWidth: 180 },
    { key: 'v2', label: 'Action', minWidth: 130 },
    { key: 'v3', label: 'Group', width: 110 },
    { key: 'v4', label: 'Effect', width: 100 },
    { key: 'v5', label: 'V5', width: 100 },
  ],
  filters: [
    { key: 'ptype', label: '类型', operator: '[~]' },
    { key: 'v0', label: 'Subject', operator: '[~]' },
    { key: 'v1', label: 'Object', operator: '[~]' },
    { key: 'v2', label: 'Action', operator: '[~]' },
  ],
  formFields: [],
  extraActions: [
    {
      label: '刷新权限',
      method: 'get',
      url: '/admin/auth/CasbinRuleAdmin/load_policy',
      confirm: '重新加载 Casbin 策略并刷新菜单缓存，确认继续？',
    },
  ],
}

const allResources: CrudResource[] = [
  navPage,
  dataSource,
  collectorTask,
  user,
  role,
  loginHistory,
  casbinRule,
]

const resourceMap = new Map(allResources.map((item) => [item.key, item]))

export function getResource(key: string): CrudResource {
  const resource = resourceMap.get(key)
  if (!resource) {
    throw new Error(`未知资源: ${key}`)
  }
  return resource
}

export { allResources }
