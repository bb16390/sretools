import { request } from './http'
import type { ListResult } from './types'

export interface ListParams {
  page: number
  perPage: number
  showTotal?: boolean
  orderBy?: string
  orderDir?: 'asc' | 'desc'
  filters?: Record<string, unknown>
}

/**
 * fastapi-amis-admin 的 ModelAdmin 通用 CRUD：
 *   POST   {base}/list?page&perPage&showTotal&orderBy&orderDir
 *   GET    {base}/item/{id}
 *   POST   {base}/item
 *   PUT    {base}/item/{id}
 *   DELETE {base}/item/{id}   （支持逗号分隔多个 id）
 */
export const crudApi = {
  list<T = Record<string, unknown>>(apiBase: string, params: ListParams) {
    return request<ListResult<T>>({
      method: 'post',
      url: `${apiBase}/list`,
      params: {
        page: params.page,
        perPage: params.perPage,
        showTotal: params.showTotal ?? true,
        orderBy: params.orderBy || undefined,
        orderDir: params.orderBy ? params.orderDir || 'asc' : undefined,
      },
      data: params.filters ?? {},
    })
  },

  read<T = Record<string, unknown>>(apiBase: string, id: string | number) {
    return request<T>({ method: 'get', url: `${apiBase}/item/${id}` })
  },

  create<T = unknown>(
    apiBase: string,
    data: Record<string, unknown>,
    query?: Record<string, string>,
  ) {
    return request<T>({
      method: 'post',
      url: `${apiBase}/item`,
      params: query,
      data,
    })
  },

  update(apiBase: string, id: string | number, data: Record<string, unknown>) {
    return request<number>({
      method: 'put',
      url: `${apiBase}/item/${id}`,
      data,
    })
  },

  remove(apiBase: string, ids: Array<string | number> | string | number) {
    const value = Array.isArray(ids) ? ids.join(',') : ids
    return request<number>({ method: 'delete', url: `${apiBase}/item/${value}` })
  },
}
