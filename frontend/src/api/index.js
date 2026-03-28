import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const http = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor
http.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

// Response interceptor
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

// ── Tasks ──────────────────────────────────────────────────────
export const getTasks = (status = '') =>
  http.get('/tasks', { params: status ? { status } : {} })

export const createTask = (data) => http.post('/tasks', data)

export const getTask = (id) => http.get(`/tasks/${id}`)

export const deleteTask = (id) => http.delete(`/tasks/${id}`)

// ── Analysis ──────────────────────────────────────────────────
export const getAnalysisList = (conclusion = '') =>
  http.get('/analysis', { params: conclusion ? { conclusion } : {} })

export const getAnalysisByTask = (taskId) => http.get(`/analysis/${taskId}`)

// ── Scrape ────────────────────────────────────────────────────
export const triggerScrape = (taskId) =>
  http.post('/scrape/trigger', { task_id: taskId })

// ── Keywords ─────────────────────────────────────────────────
export const suggestKeywords = (params) =>
  http.get('/keywords/suggest', { params })

export default http
