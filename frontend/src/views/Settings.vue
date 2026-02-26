<template>
  <div class="card">
    <h3>⚙️ 系统配置</h3>
    <div v-if="cfg">
      <div class="form-row"><label>扫描间隔(分钟)</label><input v-model.number="cfg.scanner.interval_minutes" type="number" /></div>
      <div class="form-row"><label>Z-Score 阈值</label><input v-model.number="cfg.detection.zscore_threshold" type="number" step="0.1" /></div>
      <div class="form-row"><label>滑动窗口大小</label><input v-model.number="cfg.detection.window_size" type="number" /></div>
      <div class="form-row"><label>最小数据点数</label><input v-model.number="cfg.detection.min_data_points" type="number" /></div>
      <div class="form-row"><label>交易热度权重</label><input v-model.number="cfg.heat_weights.trade" type="number" step="0.1" /></div>
      <div class="form-row"><label>舆情热度权重</label><input v-model.number="cfg.heat_weights.sentiment" type="number" step="0.1" /></div>
      <div class="form-row"><label>告警去重(分钟)</label><input v-model.number="cfg.alert.dedup_minutes" type="number" /></div>
      <div class="form-row">
        <label>Webhook 类型</label>
        <select v-model="cfg.alert.webhook_type"><option value="feishu">飞书</option><option value="dingtalk">钉钉</option></select>
      </div>
      <div class="form-row"><label>Webhook URL</label><input v-model="cfg.alert.webhook_url" style="max-width:500px" /></div>
      <div class="form-row"><label>数据保留(天)</label><input v-model.number="cfg.data.retention_days" type="number" /></div>
      <div class="form-row"><label></label><button class="btn" @click="save">保存配置</button><span v-if="saved" style="color:#52c41a;margin-left:8px;font-size:13px">✓ 已保存</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const cfg = ref(null)
const saved = ref(false)

async function load() {
  const { data } = await axios.get('/api/config')
  cfg.value = data
}

async function save() {
  await axios.put('/api/config', cfg.value)
  saved.value = true
  setTimeout(() => saved.value = false, 2000)
}

onMounted(load)
</script>
