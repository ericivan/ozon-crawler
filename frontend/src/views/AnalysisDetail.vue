<template>
  <div v-loading="loading">
    <el-empty v-if="!loading && !data" description="暂无分析数据" />

    <template v-if="data">
      <!-- Header -->
      <el-page-header @back="$router.back()" style="margin-bottom: 20px">
        <template #content>
          <span style="font-size:16px; font-weight:600">
            {{ data.task.keyword_ru }}
            <el-tag size="small" type="info" style="margin-left:8px">{{ data.task.keyword_cn }}</el-tag>
          </span>
        </template>
      </el-page-header>

      <template v-for="analysis in data.analyses" :key="analysis.id">
        <el-row :gutter="20" style="margin-bottom: 20px">
          <!-- Summary Card -->
          <el-col :span="16">
            <el-card shadow="never">
              <template #header><span style="font-weight:600">综合分析摘要</span></template>
              <p style="line-height:1.8; color:#606266">{{ analysis.summary || '暂无摘要' }}</p>
            </el-card>
          </el-col>

          <!-- Score Card -->
          <el-col :span="8">
            <el-card shadow="never" style="text-align:center">
              <div style="margin-bottom:12px">
                <div style="font-size:12px; color:#909399; margin-bottom:4px">竞争强度</div>
                <CompetitionBadge :level="analysis.competition_level" />
              </div>
              <div style="margin-bottom:12px">
                <div style="font-size:12px; color:#909399; margin-bottom:8px">机会评分</div>
                <el-progress
                  type="dashboard"
                  :percentage="(analysis.opportunity_score || 0) * 10"
                  :color="scoreColor(analysis.opportunity_score)"
                >
                  <template #default>
                    <span style="font-size:20px; font-weight:700">{{ analysis.opportunity_score }}</span>
                    <span style="font-size:12px; color:#909399">/10</span>
                  </template>
                </el-progress>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- Price Analysis -->
        <el-card shadow="never" style="margin-bottom: 20px" v-if="analysis.price_analysis">
          <template #header><span style="font-weight:600">价格带分析</span></template>
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="price-stat">
                <div class="price-stat-label">最低价</div>
                <div class="price-stat-value">{{ formatPrice(analysis.price_analysis.min) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="price-stat">
                <div class="price-stat-label">最高价</div>
                <div class="price-stat-value">{{ formatPrice(analysis.price_analysis.max) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="price-stat">
                <div class="price-stat-label">主流价格区间</div>
                <div class="price-stat-value" style="font-size:14px">{{ analysis.price_analysis.sweet_spot }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="price-stat">
                <div class="price-stat-label">薄弱竞争区间</div>
                <div class="price-stat-value" style="font-size:14px">{{ analysis.price_analysis.weak_zone }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- Gap Opportunities -->
        <el-card shadow="never" style="margin-bottom: 20px" v-if="analysis.gap_opportunities?.length">
          <template #header><span style="font-weight:600">缺口机会方向</span></template>
          <el-timeline>
            <el-timeline-item
              v-for="(gap, idx) in analysis.gap_opportunities"
              :key="idx"
              :type="difficultyTypeMap[gap.entry_difficulty] || 'primary'"
            >
              <strong>{{ gap.direction }}</strong>
              <span style="margin-left:8px">
                <el-tag size="small" :type="difficultyTypeMap[gap.entry_difficulty]">
                  入场难度：{{ gap.entry_difficulty }}
                </el-tag>
              </span>
              <p style="margin-top:4px; color:#606266; font-size:13px">{{ gap.reason }}</p>
            </el-timeline-item>
          </el-timeline>
        </el-card>

        <!-- Keywords Recommend -->
        <el-card shadow="never" style="margin-bottom: 20px" v-if="analysis.keywords_recommend?.length">
          <template #header><span style="font-weight:600">推荐关键词</span></template>
          <KeywordTable :keywords="analysis.keywords_recommend" />
        </el-card>

        <!-- Action Conclusion -->
        <el-card shadow="never" style="margin-bottom: 20px">
          <template #header><span style="font-weight:600">入场建议</span></template>
          <el-alert
            :title="analysis.action_conclusion || '暂无建议'"
            :type="conclusionAlertMap[analysis.action_conclusion] || 'info'"
            :closable="false"
            show-icon
            style="margin-bottom: 12px"
          />
          <el-descriptions :column="1" border>
            <el-descriptions-item label="建议原因">
              {{ analysis.action_reason || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="下一步行动">
              {{ analysis.next_step || '—' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getAnalysisByTask } from '@/api/index.js'
import CompetitionBadge from '@/components/CompetitionBadge.vue'
import KeywordTable from '@/components/KeywordTable.vue'

const route = useRoute()
const loading = ref(false)
const data = ref(null)

const difficultyTypeMap = { '低': 'success', '中': 'warning', '高': 'danger' }
const conclusionAlertMap = { '入场': 'success', '观望': 'warning', '放弃': 'error' }

function scoreColor(score) {
  if (!score) return '#909399'
  if (score >= 8) return '#67c23a'
  if (score >= 5) return '#e6a23c'
  return '#f56c6c'
}

function formatPrice(v) {
  if (v == null) return '—'
  return `¥ ${Number(v).toLocaleString()}`
}

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getAnalysisByTask(route.params.id)
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.price-stat { text-align: center; padding: 16px; }
.price-stat-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.price-stat-value { font-size: 20px; font-weight: 600; color: #303133; }
</style>
