/** 后端统一响应封装：fastapi-amis-admin 的 BaseApiOut */
export interface ApiEnvelope<T> {
  status: number
  msg: string
  data: T
  code?: number | null
}

/** 列表响应：BaseApiOut<ItemListSchema> */
export interface ListResult<T = Record<string, unknown>> {
  items: T[]
  total?: number | null
  query?: Record<string, string> | null
  filters?: Record<string, unknown> | null
}
