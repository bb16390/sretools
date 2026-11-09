import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi, type UserInfo } from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/http'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => Boolean(token.value))
  const displayName = computed(() => user.value?.nickname || user.value?.username || '未登录')

  async function login(username: string, password: string) {
    const result = await authApi.login(username, password)
    token.value = result.access_token
    setToken(result.access_token)
    user.value = {
      id: result.id,
      username: result.username,
      nickname: result.nickname,
      email: result.email,
      avatar: result.avatar,
    }
    return result
  }

  async function fetchUser(): Promise<UserInfo | null> {
    if (!token.value) {
      return null
    }
    const info = await authApi.userinfo()
    user.value = info
    return info
  }

  function clear(): void {
    token.value = null
    user.value = null
    clearToken()
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      clear()
    }
  }

  return { token, user, isLoggedIn, displayName, login, fetchUser, logout, clear }
})
