<template>
  <div>
    <div class="card" v-if="cfg">
      <div class="card-header">
        <span class="card-title">⚙️ 系统配置</span>
        <button class="btn btn-primary btn-sm" @click="save">💾 保存配置</button>
      </div>

      <!-- Scanner -->
      <div class="form-section">
        <div class="form-section-title">扫描设置</div>
        <div class="form-row">
          <label>扫描间隔(分钟)</label>
          <input v-model.number="cfg.scanner.interval_minutes" type="number" />
          <span class="form-hint">交易时段(9:00-15:00)内的扫描频率</span>
        </div>
        <div class="form-row">
          <label>舆情采集Top N</label>
          <input v-model.number="cfg.scanner.top_n_for_sentiment" type="number" />
          <span class="form-hint">仅对交易热度前N的股票采集舆情</span>
        </div>
      </div>

      <!-- Detection -->
      <div class="form-section">
        <div class="form-section-title">异常检测</div>
        <div class="form-row">
          <label>Z-Score 阈值</label>
          <input v-model.number="cfg.detection.zscore_threshold" type="number" step="0.1" />
          <span class="form-hint">越小越敏感，推荐 2.0~3.0</span>
        </div>
        <div class="form-row">
          <label>滑动窗口大小</label>
          <input v-model.number="cfg.detection.window_size" type="number" />
          <span class="form-hint">用于计算均值和标准差的历史数据点数</span>
        </div>
        <div class="form-row">
          <label>最小数据点数</label>
          <input v-model.number="cfg.detection.min_data_points" type="number" />
          <span class="form-hint">少于此数量的股票不参与异常检测</span>
        </div>
      </div>

      <!-- Heat Weights -->
      <div class="form-section">
        <div class="form-section-title">热度权重</div>
        <div class="form-row">
          <label>交易热度权重</label>
          <input v-model.number="cfg.heat_weights.trade" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>舆情热度权重</label>
          <input v-model.number="cfg.heat_weights.sentiment" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>量比权重</label>
          <input v-model.number="cfg.heat_weights.volume_ratio" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>换手率权重</label>
          <input v-model.number="cfg.heat_weights.turnover_rate" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>成交额权重</label>
          <input v-model.number="cfg.heat_weights.amount_change" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>股吧权重</label>
          <input v-model.number="cfg.heat_weights.guba_weight" type="number" step="0.1" />
        </div>
        <div class="form-row">
          <label>雪球权重</label>
          <input v-model.number="cfg.heat_weights.xueqiu_weight" type="number" step="0.1" />
        </div>
      </div>

      <!-- Alert -->
      <div class="form-section">
        <div class="form-section-title">告警推送</div>
        <div class="form-row">
          <label>告警去重(分钟)</label>
          <input v-model.number="cfg.alert.dedup_minutes" type="number" />
          <span class="form-hint">同一股票在此时间内不重复告警</span>
        </div>
        <div class="form-row">
          <label>Webhook 类型</label>
          <select v-model="cfg.alert.webhook_type">
            <option value="feishu">飞书</option>
            <option value="dingtalk">钉钉</option>
          </select>
        </div>
        <div class="form-row">
          <label>Webhook URL</label>
          <input v-model="cfg.alert.webhook_url" style="max-width:500px" placeholder="留空则不推送" />
        </div>
      </div>

      <!-- Data -->
      <div class="form-section">
        <div class="form-section-title">数据管理</div>
        <div class="form-row">
          <label>数据保留(天)</label>
          <input v-model.number="cfg.data.retention_days" type="number" />
          <span class="form-hint">超过此天数的历史数据将被自动清理</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import axios from 'axios'

const toast = inject('toast')
const cfg = ref(null)

async function load() {
  const { data } = await axios.get('/api/config')
  cfg.value = data
}

async function save() {
  try {
    await axios.put('/api/config', cfg.value)
    toast('配置已保存', 'ok')
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

onMounted(load)
</script>
