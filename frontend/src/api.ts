/* API 封装：统一 token、错误提示 */
import { ElMessage } from 'element-plus'

const BASE = import.meta.env.DEV ? '' : ''   // 开发模式走 vite proxy，生产同源

export let token = localStorage.getItem('echo_token') || ''

export function setToken(t: string) {
  token = t
  localStorage.setItem('echo_token', t)
}

export function clearToken() {
  token = ''
  localStorage.removeItem('echo_token')
}

async function request(method: string, path: string, body?: any, isForm = false) {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!isForm && body !== undefined) headers['Content-Type'] = 'application/json'
  const resp = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : (isForm ? body : JSON.stringify(body)),
  })
  if (resp.status === 401) {
    clearToken()
    location.reload()
    throw new Error('未登录')
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const msg = data.detail || `请求失败（${resp.status}）`
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    throw new Error(msg)
  }
  return data
}

export const api = {
  get: (p: string) => request('GET', p),
  post: (p: string, b?: any) => request('POST', p, b),
  patch: (p: string, b?: any) => request('PATCH', p, b),
  delete: (p: string) => request('DELETE', p),
  upload: (p: string, form: FormData) => request('POST', p, form, true),

  login: (username: string, password: string) =>
    request('POST', '/api/auth/login', { username, password }),
  register: (username: string, password: string, nickname: string) =>
    request('POST', '/api/auth/register', { username, password, nickname }),

  chat: (message: string, sessionId: number | null) =>
    request('POST', '/api/chat', { message, session_id: sessionId }),
  chatSessions: async () => {
    const d = await request('GET', '/api/chat/sessions')
    return Array.isArray(d) ? d : (d.items || [])
  },
  chatMessages: (sessionId: number) => request('GET', `/api/chat/sessions/${sessionId}/messages`),
  dashboard: () => request('GET', '/api/dashboard'),

  files: (courseId?: number) =>
    request('GET', `/api/files${courseId ? `?course_id=${courseId}` : ''}`),
  fileDetail: (id: number) => request('GET', `/api/files/${id}`),
  deleteFile: (id: number) => request('DELETE', `/api/files/${id}`),
  // 带 token 的预览/下载 URL：可直接塞给 iframe.src / img.src / <a download>
  previewUrl: (id: number) => `/api/files/${id}/preview?token=${encodeURIComponent(token)}`,
  downloadUrl: (id: number) => `/api/files/${id}/download?token=${encodeURIComponent(token)}`,

  // 导出文件（带 JWT 认证，fetch 拿 blob 后触发下载）
  exportFile: async (path: string, filename: string) => {
    const resp = await fetch(BASE + path, { headers: { Authorization: `Bearer ${token}` } })
    if (resp.status === 401) { clearToken(); location.reload(); throw new Error('未登录') }
    if (!resp.ok) { ElMessage.error(`导出失败（${resp.status}）`); throw new Error(`导出失败（${resp.status}）`) }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  courses: () => request('GET', '/api/courses'),
  ddls: (status = 'pending') => request('GET', `/api/ddl?status=${status}`),
  addDdl: (b: any) => request('POST', '/api/ddl', b),
  updateDdl: (id: number, b: any) => request('PATCH', `/api/ddl/${id}`, b),
  extractDdl: (text: string) => request('POST', '/api/ddl/extract', { text }),
  ocrDdl: (form: FormData) => request('POST', '/api/ddl/ocr', form, true),

  reviews: () => request('GET', '/api/review'),
  toggleReviewTask: (taskId: number, done: boolean) =>
    request('PATCH', `/api/review/tasks/${taskId}`, { done }),

  notifications: () => request('GET', '/api/notifications'),
  readNotifications: (id?: number) =>
    request('POST', '/api/notifications/read', id ? { id } : { all: true }),

  // 用户资料与设置
  profile: () => request('GET', '/api/user/profile'),
  updateProfile: (b: any) => request('PATCH', '/api/user/profile', b),
  changePassword: (old_password: string, new_password: string) =>
    request('POST', '/api/user/password', { old_password, new_password }),
  userSettings: () => request('GET', '/api/user/settings'),
  updateUserSettings: (b: any) => request('PATCH', '/api/user/settings', b),
}

export function authHeaders() {
  return { Authorization: `Bearer ${token}` }
}
