<template>
  <div>
    <!-- Add Task Form -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <template #header><span style="font-weight:600">新建关键词任务</span></template>
      <el-form :model="form" :rules="rules" ref="formRef" inline>
        <el-form-item label="中文关键词" prop="keyword_cn">
          <el-input v-model="form.keyword_cn" placeholder="如：防水运动手表" style="width:200px" />
        </el-form-item>
        <el-form-item label="俄语关键词" prop="keyword_ru">
          <el-input v-model="form.keyword_ru" placeholder="如：умные часы водонепроницаемые" style="width:280px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="adding" @click="addTask">添加任务</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Task List -->
    <el-card shadow="never">
      <template #header>
        <div style="display:flex; align-items:center; justify-content:space-between">
          <span style="font-weight:600">任务列表</span>
          <el-button size="small" @click="fetchTasks" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tasks" stripe border style="width:100%">
        <el-table-column label="中文关键词" prop="keyword_cn" min-width="150" />
        <el-table-column label="俄语关键词" prop="keyword_ru" min-width="220" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status] || 'info'" size="small">
              {{ statusLabelMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              text
              :loading="scrapingIds.has(row.id)"
              :disabled="row.status === 'running'"
              @click="triggerScrapeTask(row)"
            >
              触发抓取
            </el-button>
            <el-popconfirm
              title="确定删除该任务及其所有数据？"
              @confirm="deleteTaskItem(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTasks, createTask, deleteTask, triggerScrape } from '@/api/index.js'

const tasks = ref([])
const loading = ref(false)
const adding = ref(false)
const scrapingIds = ref(new Set())
const formRef = ref(null)

const form = reactive({ keyword_cn: '', keyword_ru: '' })
const rules = {
  keyword_cn: [{ required: true, message: '请输入中文关键词', trigger: 'blur' }],
  keyword_ru: [{ required: true, message: '请输入俄语关键词', trigger: 'blur' }],
}

const statusTagMap = {
  pending: 'info',
  running: 'warning',
  done: 'success',
  failed: 'danger',
}
const statusLabelMap = {
  pending: '待处理',
  running: '进行中',
  done: '已完成',
  failed: '失败',
}

async function fetchTasks() {
  loading.value = true
  try {
    tasks.value = await getTasks()
  } finally {
    loading.value = false
  }
}

async function addTask() {
  await formRef.value.validate()
  adding.value = true
  try {
    await createTask({ keyword_cn: form.keyword_cn, keyword_ru: form.keyword_ru })
    ElMessage.success('任务创建成功')
    form.keyword_cn = ''
    form.keyword_ru = ''
    await fetchTasks()
  } finally {
    adding.value = false
  }
}

async function deleteTaskItem(id) {
  await deleteTask(id)
  ElMessage.success('删除成功')
  await fetchTasks()
}

async function triggerScrapeTask(row) {
  scrapingIds.value.add(row.id)
  try {
    await triggerScrape(row.id)
    ElMessage.success('抓取任务已触发，后台处理中...')
    setTimeout(fetchTasks, 2000)
  } finally {
    scrapingIds.value.delete(row.id)
  }
}

function formatDate(str) {
  if (!str) return '—'
  return new Date(str).toLocaleString('zh-CN')
}

onMounted(fetchTasks)
</script>
