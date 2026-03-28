<template>
  <el-card shadow="never">
    <template #header><span style="font-weight:600">AI 关键词生成工具</span></template>

    <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" style="max-width:600px">
      <el-form-item label="产品名称" prop="product_name_cn">
        <el-input v-model="form.product_name_cn" placeholder="如：防水运动手表" />
      </el-form-item>
      <el-form-item label="产品属性">
        <el-input
          v-model="form.attributes"
          placeholder="如：防水50米，GPS，心率监测，续航7天"
          type="textarea"
          :rows="2"
        />
      </el-form-item>
      <el-form-item label="目标用户">
        <el-input v-model="form.target_user" placeholder="如：25-40岁健身爱好者，男性为主" />
      </el-form-item>
      <el-form-item label="价格区间">
        <el-input v-model="form.price_range" placeholder="如：2000-5000卢布" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="generate">
          AI 生成关键词
        </el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>

    <el-divider v-if="keywords.length" />

    <template v-if="keywords.length">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
        <span style="font-weight:600; color:#303133">生成结果（{{ keywords.length }} 个关键词）</span>
        <el-button size="small" @click="copyAll">一键复制全部俄语关键词</el-button>
      </div>
      <KeywordTable :keywords="keywords" :show-difficulty="true" :show-copy="true" />
    </template>
  </el-card>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { suggestKeywords } from '@/api/index.js'
import KeywordTable from '@/components/KeywordTable.vue'

const formRef = ref(null)
const loading = ref(false)
const keywords = ref([])

const form = reactive({
  product_name_cn: '',
  attributes: '',
  target_user: '',
  price_range: '',
})

const rules = {
  product_name_cn: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
}

async function generate() {
  await formRef.value.validate()
  loading.value = true
  keywords.value = []
  try {
    const result = await suggestKeywords({
      product_name_cn: form.product_name_cn,
      attributes: form.attributes,
      target_user: form.target_user,
      price_range: form.price_range,
    })
    keywords.value = result.keywords || []
    if (!keywords.value.length) {
      ElMessage.warning('未生成关键词，请检查输入')
    }
  } finally {
    loading.value = false
  }
}

async function copyAll() {
  const text = keywords.value.map((k) => k.ru).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制所有俄语关键词')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function resetForm() {
  formRef.value.resetFields()
  keywords.value = []
}
</script>
