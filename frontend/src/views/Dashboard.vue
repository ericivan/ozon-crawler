<template>
  <div>
    <!-- Statistics Cards -->
    <el-row :gutter="20" style="margin-bottom: 24px">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Filter & Table -->
    <el-card shadow="never">
      <template #header>
        <div style="display:flex; align-items:center; justify-content:space-between">
          <span style="font-weight:600">分析结果列表</span>
          <el-select
            v-model="filterConclusion"
            placeholder="筛选入场建议"
            clearable
            style="width:150px"
            @change="fetchAnalysis"
          >
            <el-option label="入场" value="入场" />
            <el-option label="观望" value="观望" />
            <el-option label="放弃" value="放弃" />
          </el-select>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="analysisList"
        stripe
        border
        style="width:100%"
        @row-click="onRowClick"
        row-class-name="clickable-row"
      >
        <el-table-column label="关键词（俄）" prop="keyword_ru" min-width="180" />
        <el-table-column label="竞争强度" width="100" align="center">
          <template #default="{ row }">
            <CompetitionBadge :level="row.competition_level" />
          </template>
        </el-table-column>
        <el-table-column label="机会分" width="200" align="center">
          <template #default="{ row }">
            <OpportunityScoreCard :score="row.opportunity_score" />
          </template>
        </el-table-column>
        <el-table-column label="入场建议" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="conclusionTagMap[row.action_conclusion] || 'info'" size="small">
              {{ row.action_conclusion || '—' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分析摘要" prop="summary" min-width="250" show-overflow-tooltip />
        <el-table-column label="分析时间" width="160">
          <template #default="{ row }">{{ formatDate(row.analyzed_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click.stop="goDetail(row.task_id)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAnalysisList, getTasks } from '@/api/index.js'
import CompetitionBadge from '@/components/CompetitionBadge.vue'
import OpportunityScoreCard from '@/components/OpportunityScoreCard.vue'

const router = useRouter()
const loading = ref(false)
const analysisList = ref([])
const allTasks = ref([])
const filterConclusion = ref('')

const conclusionTagMap = {
  '入场': 'success',
  '观望': 'warning',
  '放弃': 'danger',
}

const statCards = computed(() => {
  const total = allTasks.value.length
  const analyzed = analysisList.value.length
  const enter = analysisList.value.filter((a) => a.action_conclusion === '入场').length
  const scores = analysisList.value
    .map((a) => a.opportunity_score)
    .filter((s) => s != null)
  const avg = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : '—'
  return [
    { label: '总任务数', value: total },
    { label: '已分析数', value: analyzed },
    { label: '入场建议数', value: enter },
    { label: '平均机会分', value: avg },
  ]
})

async function fetchAnalysis() {
  loading.value = true
  try {
    analysisList.value = await getAnalysisList(filterConclusion.value)
  } finally {
    loading.value = false
  }
}

async function fetchTasks() {
  allTasks.value = await getTasks()
}

function onRowClick(row) {
  goDetail(row.task_id)
}

function goDetail(taskId) {
  router.push(`/analysis/${taskId}`)
}

function formatDate(str) {
  if (!str) return '—'
  return new Date(str).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchAnalysis()
  fetchTasks()
})
</script>

<style scoped>
.stat-card { text-align: center; padding: 8px 0; }
.stat-value { font-size: 32px; font-weight: 700; color: #409eff; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
:deep(.clickable-row) { cursor: pointer; }
:deep(.clickable-row:hover td) { background-color: #ecf5ff !important; }
</style>
