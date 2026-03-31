// src/api/client.ts
// Єдиний Axios instance — всі API виклики йдуть через нього

import axios, { AxiosError } from 'axios'
import { toast } from 'sonner'

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

// ── Request interceptor: додає Authorization header ───────────────────────────
client.interceptors.request.use((config) => {
  // TODO: отримати токен з useAuthStore, коли буде реальна авторизація
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Response interceptor: глобальна обробка помилок ──────────────────────────
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail ?? error.message

    if (status === 401) {
      toast.error('Сесія закінчилась — увійдіть знову')
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    } else if (status === 403) {
      toast.error('Доступ заборонено')
    } else if (status === 404) {
      // 404 обробляються локально в хуках
    } else if (status === 409) {
      // Конфлікт — обробляється локально
    } else if (status && status >= 500) {
      toast.error(`Помилка сервера (${status}): ${detail}`)
    } else if (!error.response) {
      toast.error('Немає з\'єднання з сервером')
    }

    return Promise.reject(error)
  }
)
