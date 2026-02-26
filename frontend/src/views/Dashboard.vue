<template>
  <div>
    <!-- Status Bar -->
    <div class="status-bar">
      <span><span class="status-dot" :class="statusColor"></span></span>
      <span>监控 <b>{{ status.stock_count }}</b> 只</span>
      <span class="text-dim">|</span>
      <span>最后更新 <b>{{ status.latest_heat_ts || '-' }}</b></span>
      <span class="text-dim">|</span>
      <span>下次扫描 <b>{{ nextScanDisplay }}</b></span>
      <span v-if="Object.keys(status.running_jobs||{}).length" class="text-dim">|</span>
      <span v-for="(v, k) in (status.running_jobs||{})" :key="k" class="tag tag-bg-orange">
        ⏳ {{ k }} {{ v.progress || '' }}
      </span>
      <span style="margin-left:auto">
        <button class="btn btn-sm btn-primary" :disabled="scanRunning" @click="triggerScan">
          {{ scanRunning ? '扫描中...' : '▶ 立即扫描' }}
        </button>
      </span>
    </div>

    <!-- Stat Cards -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent)">{{ status.stock_count || 0 }}</div>
        <div class="stat-label">监控股票</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--red)">{{ status.today_anomalies || 0 }}</div>
        <div class="stat-label">今日异常</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--green)">{{ status.today_scans || 0 }}</div>
        <div class="stat-label">今日扫描</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--orange)">{{ ranking.length }}</div>
        <div class="stat-label">当前排行</div>
      </div>
    </div>

    <div class="grid-2">
      <!-- Left: Ranking Table -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">📊 热度排行榜</span>
          <div class="flex gap-8 items-center">
            <select v-model="sortField" @change="fetchRanking" class="btn-sm" style="padding:3px 8px">
              <option value="total_heat">综合热度</option>
              <option value="trade_heat">交易热度</option>
              <option value="zscore">Z-Score</option>
              <option value="change_pct">涨跌幅</option>
              <option value="volume_ratio">量比</option>
              <option value="amount">成交额</option>
              <option value="turnover_rate">换手率</option>
            </select>
          </div>
        </div>
        <table>
          <tr>
            <th>#</th>
            <th>股票</th>
            <th>综合热度</th>
            <th>涨跌幅</th>
            <th>量比</th>
            <th>换手率</th>
            <th>成交额</th>
            <th>操作</th>
          </tr>
          <tr v-for="(item, i) in ranking" :key="item.code" @click="selectedCode = item.code" style="cursor:pointer">
            <td>
              <span v-if="i<3" :style="{color:['#ffd700','#c0c0c0','#cd7f32'][i], fontWeight:700}">{{ i+1 }}</span>
              <span v-else class="text-dim">{{ i+1 }}</span>
            </td>
            <td>
              <div style="font-weight:600">{{ item.name }}</div>
              <div class="text-dim text-sm">{{ item.code }}</div>
            </td>
            <td><span class="tag tag-bg-blue">{{ item.total_heat?.toFixed(3) }}</span></td>
            <td :class="(item.change_pct||0)>=0?'tag-red':'tag-green'">{{ (item.change_pct||0).toFixed(2) }}%</td>
            <td>{{ (item.volume_ratio||0).toFixed(2) }}</td>
            <td>{{ (item.turnover_rate||0).toFixed(2) }}%</td>
            <td class="text-dim">{{ formatAmount(item.amount) }}</td>
            <td><button class="btn btn-sm" @click.stop="selectedCode = item.code">📈</button></td>
          </tr>
        </table>
        <div class="pagination">
          <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetchRanking()">‹</button>
          <span class="text-dim text-sm">{{ page }} / {{ totalPages }}</span>
          <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetchRanking()">›</button>
        </div>
      </div>

      <!-- Right: Chart + Anomalies -->
      <div>
        <!-- Heat Trend Chart -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">📈 热度趋势 {{ selectedCode ? '- ' + selectedCode : '' }}</span>
            <div class="flex gap-8">
              <button v-for="h in [6,12,24,48]" :key="h" class="btn btn-sm" :class="{' btn-primary': chartHours===h}" @click="chartHours=h; renderChart()">{{ h }}h</button>
            </div>
          </div>
          <div v-if="!selectedCode" class="text-dim" style="text-align:center;padding:40px 0">点击排行榜中的股票查看趋势</div>
          <div v-else ref="chartEl" style="width:100%;height:300px"></div>
        </div>

        <!-- Anomaly Cards -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">🚨 异常突破 ({{ anomalies.length }})</span>
          </div>
          <div v-if="!anomalies.length" class="text-dim" style="text-align:center;padding:20px 0">暂无异常</div>
          <div class="anomaly-cards">
            <div v-for="a in anomalies.slice(0, 12)" :key="a.code" class="anomaly-card" @click="selectedCode = a.code">
              <div class="flex items-center gap-8" style="margin-bottom:6px">
                <span style="font-weight:700">{{ a.name }}</span>
                <span class="text-dim text-sm">{{ a.code }}</span>
                <span class="tag tag-bg-red" style="margin-left:auto">Z {{ a.zscore?.toFixed(1) }}</span>
              </div>
              <div class="flex gap-16 text-sm">
                <span>热度 <b class="tag-red">{{ a.total_heat?.toFixed(3) }}</b></span>
                <span :class="(a.change_pct||0)>=0?'tag-red':'tag-green'">{{ (a.change_pct||0).toFixed(2) }}%</span>
                <span>量比 {{ (a.volume_ratio||0).toFixed(2) }}</span>
              </div>
              <div v-if="a.anomaly_type==='box_breakout'" class="text-sm mt-8">
                <span class="tag tag-bg-orange">箱体突破</span>
                <span class="text-dim"> 突破 {{ a.breakout?.toFixed(1) }}x IQR</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Heat TreeMap -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">🗺️ 热度地图 (Top 100)</span>
      </div>
      <div ref="treemapEl" style="width:100%;height:400px"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted, onUnmounted, watch, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const wsData = inject('wsData')
const toast = inject('toast')

const status = ref({ stock_count: 0, today_anomalies: 0, today_scans: 0, running_jobs: {} })
const ranking = ref([])
const anomalies = ref([])
const selectedCode = ref('')
const page = ref(1)
const totalPages = ref(1)
const sortField = ref('total_heat')
const chartHours = ref(24)
const chartEl = ref(null)
const treemapEl = ref(null)
let chart = null, treemap = null
let refreshTimer = null

const scanRunning = ref(false)
const statusColor = ref('green')

function formatAmount(v) {
  if (!v) return '-'
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
  return v.toFixed(0)
}

const nextScanDisplay = ref('-')

async function fetchStatus() {
  try {
    const { data } = await axios.get('/api/status')
    status.value = data
    statusColor.value = data.recent_errors?.length ? 'orange' : 'green'
    if (data.running_jobs && Object.keys(data.running_jobs).length) {
      scanRunning.value = 'full_scan' in data.running_jobs
    } else {
      scanRunning.value = false
    }
    if (data.next_scan) {
      const d = new Date(data.next_scan)
      nextScanDisplay.value = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
  } catch {}
}

async function fetchRanking() {
  const { data } = await axios.get('/api/heat/ranking', { params: { page: page.value, size: 50, sort: sortField.value } })
  ranking.value = data.items
  totalPages.value = Math.max(1, Math.ceil(data.total / 50))
}

async function triggerScan() {
  scanRunning.value = true
  try {
    await axios.post('/api/jobs/full_scan/trigger')
    toast('扫描任务已触发', 'info')
  } catch (e) {
    toast(e.response?.data?.detail || '触发失败', 'error')
    scanRunning.value = false
  }
}

async function renderChart() {
  if (!selectedCode.value) return
  await nextTick()
  const { data } = await axios.get(`/api/heat/trend/${selectedCode.value}`, { params: { hours: chartHours.value } })
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#2a3a4a', textStyle: { color: '#e0e6ed', fontSize: 11 } },
    legend: { data: ['综合热度', '交易热度', '舆情热度', 'Z-Score'], textStyle: { color: '#8899aa', fontSize: 11 }, top: 0 },
    grid: { top: 30, bottom: 24, left: 50, right: 50 },
    xAxis: { type: 'category', data: data.map(d => d.ts?.slice(11, 16)), axisLine: { lineStyle: { color: '#2a3a4a' } }, axisLabel: { color: '#8899aa', fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '热度', nameTextStyle: { color: '#8899aa', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a3a' } }, axisLabel: { color: '#8899aa', fontSize: 10 } },
      { type: 'value', name: 'Z-Score', nameTextStyle: { color: '#8899aa', fontSize: 10 }, splitLine: { show: false }, axisLabel: { color: '#8899aa', fontSize: 10 } }
    ],
    series: [
      { name: '综合热度', type: 'line', data: data.map(d => d.total_heat), smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#3b82f6' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } } },
      { name: '交易热度', type: 'line', data: data.map(d => d.trade_heat), smooth: true, lineStyle: { width: 1.5 }, itemStyle: { color: '#10b981' } },
      { name: '舆情热度', type: 'line', data: data.map(d => d.sentiment_heat), smooth: true, lineStyle: { width: 1.5 }, itemStyle: { color: '#f59e0b' } },
      { name: 'Z-Score', type: 'line', yAxisIndex: 1, data: data.map(d => d.zscore), smooth: true, lineStyle: { type: 'dashed', width: 1.5 }, itemStyle: { color: '#ef4444' } },
    ],
  })
}

async function renderTreemap() {
  const { data } = await axios.get('/api/heat/ranking', { params: { page: 1, size: 100, sort: 'total_heat' } })
  if (!treemapEl.value) return
  if (!treemap) treemap = echarts.init(treemapEl.value)
  const items = data.items.map(d => ({
    name: d.name || d.code,
    value: d.total_heat || 0,
    code: d.code,
    change_pct: d.change_pct || 0,
    itemStyle: { color: (d.change_pct || 0) >= 0 ? `rgba(239,68,68,${Math.min(0.9, 0.2 + Math.abs(d.change_pct || 0) / 10)})` : `rgba(16,185,129,${Math.min(0.9, 0.2 + Math.abs(d.change_pct || 0) / 10)})` }
  }))
  treemap.setOption({
    tooltip: {
      formatter: p => `<b>${p.data.name}</b> (${p.data.code})<br/>热度: ${p.data.value?.toFixed(3)}<br/>涨跌: ${p.data.change_pct?.toFixed(2)}%`
    },
    series: [{
      type: 'treemap', data: items, roam: false, nodeClick: false,
      breadcrumb: { show: false },
      label: { show: true, formatter: '{b}\n{c}', fontSize: 10, color: '#fff' },
      itemStyle: { borderColor: '#0f1923', borderWidth: 1, gapWidth: 1 },
      levels: [{ itemStyle: { borderColor: '#0f1923', borderWidth: 2, gapWidth: 2 } }]
    }]
  })
  treemap.on('click', p => { if (p.data?.code) selectedCode.value = p.data.code })
}

watch(selectedCode, renderChart)

// React to WS updates
watch(() => wsData.value.anomalies, v => { if (v?.length) anomalies.value = v }, { deep: true })
watch(() => wsData.value.runningJobs, v => {
  status.value.running_jobs = v
  scanRunning.value = v && 'full_scan' in v
}, { deep: true })

onMounted(async () => {
  await fetchStatus()
  await fetchRanking()
  await renderTreemap()
  // Refresh every 30s
  refreshTimer = setInterval(() => { fetchStatus(); fetchRanking() }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (chart) chart.dispose()
  if (treemap) treemap.dispose()
})
</script>
