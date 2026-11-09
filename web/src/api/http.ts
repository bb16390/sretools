import axios, { type AxiosRequestConfig } from 'axios'

import type { ApiEnvelope } from './types'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 跳过自动附加 Bearer Token（用于登录等需要匿名身份的请求）。 */
    skipAuth?: boolean
  }
}

const TOKEN_KEY = 'sretools.token'

export class ApiError extends Error {
  status: number

  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

let unauthorizedHandler: (() => void) | null = null

/** 仅处理 HTTP 401（未登录/令牌失效），业务层 status=401 表示“无权限” */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30_000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token && !config.skipAuth) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken()
      unauthorizedHandler?.()
    }
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string' ? detail : error.message || '网络请求失败'
    return Promise.reject(new ApiError(message, error.response?.status ?? -1))
  },
)

/**
 * 发起请求并拆解 BaseApiOut 封装。
 * - status === 401：后端“无路由权限”，抛错但不清除登录态
 * - 其它非 0：抛业务错误
 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await http.request<ApiEnvelope<T>>(config)
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new ApiError('后端返回格式异常')
  }
  if (body.status === 401) {
    throw new ApiError(body.msg || '没有权限访问该资源', 401)
  }
  if (body.status !== 0) {
    throw new ApiError(body.msg || '请求失败', body.status)
  }
  return body.data
}

export { http }
