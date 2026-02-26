<template>
  <div>
    <div style="display:flex;gap:12px;margin-bottom:16px">
      <div class="card" style="flex:1;text-align:center"><div style="font-size:24px;color:#1890ff">{{ stats.stocks }}</div><div style="font-size:12px;color:#999">监控股票数</div></div>
      <div class="card" style="flex:1;text-align:center"><div style="font-size:24px;color:#f5222d">{{ stats.anomalies }}</div><div style="font-size:12px;color:#999">今日异常</div></div>
      <div class="card" style="flex:1;text-align:center"><div style="font-size:24px;color:#52c41a">{{ stats.scans }}</div><div style="font-size:12px;color:#999">今日扫描次数</div></div>
    </div>

    <div class="card">
      <h3>📊 热度排行榜 <button class="btn btn-sm" @click="triggerScan" style="margin-left:12px">手动扫描</button></h3>
      <HeatRanking :items="ranking" @select="selectedCode = $event" />
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetchRanking()">上一页</button>
        <span style="font-size:13px;line-height:28px">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetchRanking()">下一页</button>
      </div>
    </div>
    <div class="card" v-if="selectedCode">
      <h3>📈 热度趋势 - {{ selectedCode }}</h3>
      <HeatChart :code="selectedCode" />
    </div>
    <div class="card" v-if="anomalies.length">
      <h3>🚨 最新异常 ({{ anomalies.length }})</h3>
      <table>
        <tr><th>股票</th><th>热度</th><th>Z-Score</th><th>涨跌幅</th><th>量比</th></tr>
        <tr v-for="a in anomalies" :key="a.code">
          <td>{{ a.name }}({{ a.code }})</td>
          <td>{{ a.total_heat?.toFixed(3) }}</td>
          <td class="tag-red">{{ a.zscore?.toFixed(1) }}</td>
          <td :class="(a.change_pct||0)>=0?'tag-red':'tag-green'">{{ a.change_pct?.toFixed(2) }}%</td>
          <td>{{ a.volume_ratio?.toFixed(2) }}</td>
        </tr>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import HeatRanking from '../components/HeatRanking.vue'
import HeatChart from '../components/HeatChart.vue'

const ranking = ref([])
const anomalies = ref([])
const selectedCode = ref('')
const page = ref(1)
const totalPages = ref(1)
const stats = ref({ stocks: 0, anomalies: 0, scans: 0 })
let ws = null

async function fetchRanking() {
  const { data } = await axios.get('/api/heat/ranking', { params: { page: page.value, size: 50 } })
  ranking.value = data.items
  totalPages.value = Math.max(1, Math.ceil(data.total / 50))
}

async function fetchStats() {
  try {
    const { data: stockData } = await axios.get('/api/stocks')
    stats.value.stocks = stockData.total
    const { data: alertData } = await axios.get('/api/alerts', { params: { size: 1 } })
    stats.value.anomalies = alertData.total
    const { data: jobData } = await axios.get('/api/jobs/logs', { params: { job_name: 'collect_trade', size: 1 } })
    stats.value.scans = jobData.total
  } catch {}
}

async function triggerScan() {
  await axios.post('/api/jobs/full_scan/trigger')
  setTimeout(() => { fetchRanking(); fetchStats() }, 5000)
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws`)
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'update') {
      if (msg.ranking) ranking.value = msg.ranking
      if (msg.anomalies) anomalies.value = msg.anomalies
    }
  }
  ws.onclose = () => setTimeout(connectWs, 3000)
}

onMounted(() => { fetchRanking(); fetchStats(); connectWs() })
onUnmounted(() => { if (ws) ws.close() })
</script>
