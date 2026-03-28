<template>
  <el-table :data="keywords" border stripe style="width: 100%">
    <el-table-column label="俄语关键词" prop="ru" min-width="200" />
    <el-table-column label="中文" prop="cn" min-width="150" />
    <el-table-column label="类型" prop="type" width="90">
      <template #default="{ row }">
        <el-tag size="small" :type="typeTagMap[row.type] || 'info'">{{ row.type }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="难度" prop="difficulty" width="80" v-if="showDifficulty">
      <template #default="{ row }">
        <el-tag size="small" :type="diffTagMap[row.difficulty] || 'info'">
          {{ row.difficulty }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="理由" prop="reason" min-width="200" />
    <el-table-column label="复制" width="80" v-if="showCopy">
      <template #default="{ row }">
        <el-button size="small" @click="copyText(row.ru)" text>复制</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ElMessage } from 'element-plus'

defineProps({
  keywords: { type: Array, default: () => [] },
  showDifficulty: { type: Boolean, default: false },
  showCopy: { type: Boolean, default: false },
})

const typeTagMap = {
  '核心词': 'primary',
  '长尾词': 'success',
  '场景词': 'warning',
}

const diffTagMap = {
  '低': 'success',
  '中': 'warning',
  '高': 'danger',
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>
