<template>
  <div>
    <!-- Status Bar -->
    <div class="status-bar">
      <span><span class="status-dot" :class="statusColor"></span></span>
      <span>监控 <b class="font-mono">{{ status.stock_count }}</b> 只</span>
      <span class="text-muted">·</span>
      <span>更新 <b>{{ formatTs(status.latest_heat_ts) }}</b></span>
      <span class="text-muted">·</span>
      <span>下次 <b>{{ nextScanDisplay }}</b></span>
      <template v-for="(v, k) in (status.running_jobs||{})" :key="k">
        <span class="tag tag-bg-orange">⏳ {{ k }} {{ v.progress || '' }}</span>
      </template>
      <span style="margin-left:auto">
        <button class="btn btn-primary btn-sm" :disabled="scanRunning" @click="triggerScan">
          {{ scanRunning ? '⏳ 扫描中...' : '▶ 立即扫描' }}
        </button>
      </span>
    </div>

    <!-- Stat Cards -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent-hover)">{{ status.stock_count || 0 }}</div>
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
          <select v-model="sortField" @change="fetchRanking" class="btn btn-sm" style="padding:5px 10px;min-width:100px">
            <option value="total_heat">综合热度</option>
            <option value="trade_heat">交易热度</option>
            <option value="zscore">Z-Score</option>
            <option value="change_pct">涨跌幅</option>
            <option value="volume_ratio">量比</option>
            <option value="amount">成交额</option>
            <option value="turnover_rate">换手率</option>
          </select>
        </div>
        <table>
          <tr>
            <th>#</th><th>股票</th><th>热度</th><th>涨跌幅</th><th>量比</th><th>换手</th><th>成交额</th>
          </tr>
          <tr v-for="(item, i) in ranking" :key="item.code" @click="selectedCode = item.code" style="cursor:pointer">
            <td>
              <span v-if="i<3" class="rank-badge" :style="{background:['linear-gradient(135deg,#fbbf24,#f59e0b)','linear-gradient(135deg,#94a3b8,#64748b)','linear-gradient(135deg,#d97706,#b45309)'][i]}">{{ i+1 }}</span>
              <span v-else class="text-muted font-mono">{{ i+1 }}</span>
            </td>
            <td>
              <div style="font-weight:600;font-size:13px">{{ item.name }}</div>
              <div class="text-muted text-xs font-mono">{{ item.code }}</div>
            </td>
            <td><span class="tag tag-bg-blue font-mono">{{ item.total_heat?.toFixed(3) }}</span></td>
            <td><span :class="['font-mono',(item.change_pct||0)>=0?'tag-red':'tag-green']">{{ (item.change_pct||0) >= 0 ? '+' : '' }}{{ (item.change_pct||0).toFixed(2) }}%</span></td>
            <td class="font-mono">{{ (item.volume_ratio||0).toFixed(2) }}</td>
            <td class="font-mono text-dim">{{ (item.turnover_rate||0).toFixed(2) }}%</td>
            <td class="font-mono text-dim">{{ formatAmount(item.amount) }}</td>
          </tr>
        </table>
        <div class="pagination">
          <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetchRanking()">‹ 上页</button>
          <span class="text-dim text-sm font-mono">{{ page }} / {{ totalPages }}</span>
          <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetchRanking()">下页 ›</button>
        </div>
      </div>

      <!-- Right Column -->
      <div>
        <!-- Heat Trend Chart -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">📈 热度趋势 <span v-if="selectedCode" class="tag tag-bg-cyan" style="margin-left:8px">{{ selectedCode }}</span></span>
            <div class="flex gap-4">
              <button v-for="h in [6,12,24,48]" :key="h" class="btn btn-sm" :class="{'btn-primary': chartHours===h}" @click="chartHours=h; renderChart()">{{ h }}h</button>
            </div>
          </div>
          <div v-if="!selectedCode" class="text-dim" style="text-align:center;padding:48px 0;font-size:13px">👆 点击排行榜中的股票查看趋势</div>
          <div v-else ref="chartEl" style="width:100%;height:300px"></div>
        </div>

        <!-- Anomaly Cards -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">🚨 异常突破</span>
            <span class="tag tag-bg-red font-mono">{{ anomalies.length }}</span>
          </div>
          <div v-if="!anomalies.length" class="text-dim" style="text-align:center;padding:24px 0">暂无异常</div>
          <div class="anomaly-cards">
            <div v-for="a in anomalies.slice(0, 12)" :key="a.code" class="anomaly-card" @click="selectedCode = a.code">
              <div class="flex items-center gap-8" style="margin-bottom:8px">
                <span style="font-weight:700;font-size:14px">{{ a.name }}</span>
                <span class="text-muted text-xs font-mono">{{ a.code }}</span>
                <span class="tag tag-bg-red font-mono" style="margin-left:auto">Z {{ a.zscore?.toFixed(1) }}</span>
              </div>
              <div class="flex gap-16 text-sm">
                <span>热度 <b class="tag-red font-mono">{{ a.total_heat?.toFixed(3) }}</b></span>
                <span :class="['font-mono',(a.change_pct||0)>=0?'tag-red':'tag-green']">{{ (a.change_pct||0)>=0?'+':'' }}{{ (a.change_pct||0).toFixed(2) }}%</span>
                <span class="text-dim">量比 <span class="font-mono">{{ (a.volume_ratio||0).toFixed(2) }}</span></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Heat TreeMap -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">🗺️ 热度地图</span>
        <span class="text-dim text-sm">Top 100</span>
      </div>
      <div ref="treemapEl" style="width:100%;height:420px"></div>
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
let chart = null, treemap = null, refreshTimer = null
const scanRunning = ref(false)
const statusColor = ref('green')
const nextScanDisplay = ref('-')

function formatAmount(v) {
  if (!v) return '-'
  return v >= 1e8 ? (v / 1e8).toFixed(1) + '亿' : v >= 1e4 ? (v / 1e4).toFixed(0) + '万' : v.toFixed(0)
}
function formatTs(ts) {
  if (!ts) return '-'
  return ts.slice(11, 16) || ts
}

async function fetchStatus() {
  try {
    const { data } = await axios.get('/api/status')
    status.value = data
    statusColor.value = data.recent_errors?.length ? 'orange' : 'green'
    scanRunning.value = !!(data.running_jobs && data.running_jobs.full_scan)
    if (data.next_scan) {
      nextScanDisplay.value = new Date(data.next_scan).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
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

const chartTheme = {
  tooltip: { backgroundColor: 'rgba(17,24,39,.95)', borderColor: '#1e293b', textStyle: { color: '#e2e8f0', fontSize: 11 } },
  grid: { top: 35, bottom: 24, left: 50, right: 50 },
  xAxisStyle: { axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
  yAxisStyle: { splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
}

async function renderChart() {
  if (!selectedCode.value) return
  await nextTick()
  const { data } = await axios.get(`/api/heat/trend/${selectedCode.value}`, { params: { hours: chartHours.value } })
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption({
    tooltip: { ...chartTheme.tooltip, trigger: 'axis' },
    legend: { data: ['综合热度', '交易热度', '舆情热度', 'Z-Score'], textStyle: { color: '#64748b', fontSize: 11 }, top: 0 },
    grid: chartTheme.grid,
    xAxis: { type: 'category', data: data.map(d => d.ts?.slice(11, 16)), ...chartTheme.xAxisStyle },
    yAxis: [
      { type: 'value', name: '热度', nameTextStyle: { color: '#64748b', fontSize: 10 }, ...chartTheme.yAxisStyle },
      { type: 'value', name: 'Z-Score', nameTextStyle: { color: '#64748b', fontSize: 10 }, splitLine: { show: false }, axisLabel: { color: '#64748b', fontSize: 10 } }
    ],
    series: [
      { name: '综合热度', type: 'line', data: data.map(d => d.total_heat), smooth: true, lineStyle: { width: 2.5 }, itemStyle: { color: '#6366f1' }, symbol: 'none', areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(99,102,241,.25)' }, { offset: 1, color: 'rgba(99,102,241,0)' }] } } },
      { name: '交易热度', type: 'line', data: data.map(d => d.trade_heat), smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#22c55e' }, symbol: 'none' },
      { name: '舆情热度', type: 'line', data: data.map(d => d.sentiment_heat), smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#f59e0b' }, symbol: 'none' },
      { name: 'Z-Score', type: 'line', yAxisIndex: 1, data: data.map(d => d.zscore), smooth: true, lineStyle: { type: 'dashed', width: 1.5 }, itemStyle: { color: '#ef4444' }, symbol: 'none' },
    ],
  })
}

async function renderTreemap() {
  const { data } = await axios.get('/api/heat/ranking', { params: { page: 1, size: 100, sort: 'total_heat' } })
  if (!treemapEl.value) return
  if (!treemap) treemap = echarts.init(treemapEl.value)
  treemap.setOption({
    tooltip: {
      backgroundColor: 'rgba(17,24,39,.95)', borderColor: '#1e293b', textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: p => `<b>${p.data.name}</b> <span style="opacity:.6">${p.data.code}</span><br/>热度 ${p.data.value?.toFixed(3)}<br/>涨跌 <span style="color:${(p.data.change_pct||0)>=0?'#ef4444':'#22c55e'}">${(p.data.change_pct||0).toFixed(2)}%</span>`
    },
    series: [{
      type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false },
      label: { show: true, formatter: '{b}\n{c}', fontSize: 10, color: '#fff', textShadowBlur: 2, textShadowColor: 'rgba(0,0,0,.5)' },
      itemStyle: { borderColor: '#0a0e17', borderWidth: 2, gapWidth: 2 },
      data: data.items.map(d => ({
        name: d.name || d.code, value: d.total_heat || 0, code: d.code, change_pct: d.change_pct || 0,
        itemStyle: { color: (d.change_pct||0) >= 0
          ? `rgba(239,68,68,${Math.min(.85, .15 + Math.abs(d.change_pct||0) / 8)})`
          : `rgba(34,197,94,${Math.min(.85, .15 + Math.abs(d.change_pct||0) / 8)})` }
      }))
    }]
  })
  treemap.on('click', p => { if (p.data?.code) selectedCode.value = p.data.code })
}

watch(selectedCode, renderChart)
watch(() => wsData.value.anomalies, v => { if (v?.length) anomalies.value = v }, { deep: true })
watch(() => wsData.value.runningJobs, v => {
  status.value.running_jobs = v
  scanRunning.value = !!(v && v.full_scan)
}, { deep: true })

onMounted(async () => {
  await fetchStatus()
  await fetchRanking()
  await renderTreemap()
  refreshTimer = setInterval(() => { fetchStatus(); fetchRanking() }, 30000)
})
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (chart) chart.dispose()
  if (treemap) treemap.dispose()
})
</script>

<style scoped>
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  color: #fff;
}
</style>
