import { http, request } from './http'

export interface LoginResult {
  id: number
  username: string
  nickname?: string
  email?: string | null
  avatar?: string
  token_type: string
  access_token: string
}

export interface UserInfo {
  id: number
  username: string
  nickname?: string
  email?: string | null
  avatar?: string
  is_active?: boolean
}

/** 清除旧 amis 后台写入的 Authorization Cookie。 */
function clearLegacyAuthCookie(): void {
  // 旧后台用 Cookie 维持会话。若该 Cookie 仍有效，/form/login/api 会
  // 直接返回“用户已登录!”且不带 access_token，新前端就拿不到 Bearer Token。
  // 这里先清掉旧 Cookie，确保始终按账号密码换取新 Token。
  document.cookie = 'Authorization=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
}

export const authApi = {
  /**
   * 现有 amis 登录表单的 JSON 提交地址。
   * 也支持 OAuth2 的 POST /admin/auth/gettoken（form 表单），此处使用 JSON 版本。
   */
  login(username: string, password: string) {
    clearLegacyAuthCookie()
    return request<LoginResult>({
      method: 'post',
      url: '/admin/auth/form/login/api',
      data: { username, password },
      // 携带旧 Token 时后端会直接返回“用户已登录”而不下发新 Token，
      // 因此登录请求必须匿名发送。
      skipAuth: true,
    })
  },

  userinfo() {
    return request<UserInfo>({ method: 'get', url: '/admin/auth/userinfo' })
  },

  /**
   * 后端登出接口返回 307 跳转到 /admin，不是 JSON。
   * 这里只关心令牌是否被销毁，因此忽略响应内容。
   */
  async logout(): Promise<void> {
    await http.get('/admin/auth/logout', {
      validateStatus: () => true,
    })
  },
}
