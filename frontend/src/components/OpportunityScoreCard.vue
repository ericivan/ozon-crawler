<template>
  <div class="score-card">
    <div class="score-label">机会分</div>
    <el-progress
      :percentage="percentage"
      :color="scoreColor"
      :stroke-width="12"
      :show-text="false"
      style="width: 100px"
    />
    <span class="score-value" :style="{ color: scoreColor }">{{ score }}/10</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: {
    type: Number,
    default: 0,
  },
})

const percentage = computed(() => (props.score || 0) * 10)

const scoreColor = computed(() => {
  if (props.score >= 8) return '#67c23a'
  if (props.score >= 5) return '#e6a23c'
  return '#f56c6c'
})
</script>

<style scoped>
.score-card {
  display: flex;
  align-items: center;
  gap: 8px;
}
.score-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}
.score-value {
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}
</style>
