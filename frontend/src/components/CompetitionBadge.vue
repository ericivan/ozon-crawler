<template>
  <el-tag :type="tagType" size="small" effect="dark">
    {{ level }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  level: {
    type: String,
    default: '',
  },
})

const tagType = computed(() => {
  switch (props.level) {
    case '低': return 'success'   // green
    case '中': return 'warning'   // yellow
    case '高': return 'danger'    // red
    default:   return 'info'
  }
})
</script>
