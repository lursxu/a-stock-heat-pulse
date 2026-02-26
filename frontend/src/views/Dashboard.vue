<template>
  <div>
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
          <td :class="a.change_pct>=0?'tag-red':'tag-green'">{{ a.change_pct?.toFixed(2) }}%</td>
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
const total = ref(0)
const size = 50
const totalPages = ref(1)
let ws = null

async function fetchRanking() {
  const { data } = await axios.get('/api/heat/ranking', { params: { page: page.value, size } })
  ranking.value = data.items
  total.value = data.total
  totalPages.value = Math.max(1, Math.ceil(data.total / size))
}

async function triggerScan() {
  await axios.post('/api/job/trigger')
  setTimeout(fetchRanking, 3000)
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

onMounted(() => { fetchRanking(); connectWs() })
onUnmounted(() => { if (ws) ws.close() })
</script>
