<template>
  <div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">🚨 告警历史</span>
        <div class="flex gap-8 items-center">
          <input v-model="searchCode" placeholder="搜索代码或名称..." @keyup.enter="page=1;fetch()" style="width:180px" />
          <button class="btn btn-sm btn-primary" @click="page=1;fetch()">搜索</button>
          <button v-if="searchCode" class="btn btn-sm" @click="searchCode='';page=1;fetch()">✕</button>
        </div>
      </div>
      <table>
        <tr>
          <th>时间</th><th>股票</th><th>热度</th><th>Z-Score</th><th>涨跌幅</th><th>量比</th><th></th>
        </tr>
        <tr v-for="a in items" :key="a.id" @click="showDetail(a)" style="cursor:pointer">
          <td class="text-sm text-dim font-mono">{{ a.ts?.slice(5,16) }}</td>
          <td><b>{{ a.name }}</b> <span class="text-muted text-xs font-mono">{{ a.code }}</span></td>
          <td><span class="tag tag-bg-blue font-mono">{{ a.total_heat?.toFixed(3) }}</span></td>
          <td><span class="tag tag-bg-red font-mono">{{ a.zscore?.toFixed(1) }}</span></td>
          <td><span :class="['font-mono',(a.change_pct||0)>=0?'tag-red':'tag-green']">{{ (a.change_pct||0)>=0?'+':'' }}{{ (a.change_pct||0).toFixed(2) }}%</span></td>
          <td class="font-mono">{{ (a.volume_ratio||0).toFixed(2) }}</td>
          <td><button class="btn btn-sm" @click.stop="showDetail(a)">详情</button></td>
        </tr>
        <tr v-if="!items.length"><td colspan="7" class="text-dim" style="text-align:center;padding:32px">暂无告警记录</td></tr>
      </table>
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetch()">‹</button>
        <span class="text-dim text-sm font-mono">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetch()">›</button>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="detail" class="modal-overlay" @click.self="detail=null">
      <div class="modal" style="min-width:620px">
        <div class="modal-title">{{ detail.name }} <span class="text-dim font-mono" style="font-size:13px">{{ detail.code }}</span></div>
        <div class="flex gap-16 mb-16" style="flex-wrap:wrap">
          <div><span class="text-muted text-xs">时间</span><br/><span class="font-mono">{{ detail.ts }}</span></div>
          <div><span class="text-muted text-xs">Z-Score</span><br/><span class="tag-red font-mono" style="font-size:22px;font-weight:800">{{ detail.zscore?.toFixed(2) }}</span></div>
          <div><span class="text-muted text-xs">热度</span><br/><span class="font-mono">{{ detail.total_heat?.toFixed(4) }}</span></div>
          <div><span class="text-muted text-xs">涨跌幅</span><br/><span :class="['font-mono',(detail.change_pct||0)>=0?'tag-red':'tag-green']">{{ (detail.change_pct||0).toFixed(2) }}%</span></div>
          <div><span class="text-muted text-xs">量比</span><br/><span class="font-mono">{{ (detail.volume_ratio||0).toFixed(2) }}</span></div>
        </div>
        <div v-if="detail.trend?.length">
          <div class="text-dim mb-8 text-sm">告警前后热度变化</div>
          <div ref="detailChartEl" style="width:100%;height:220px"></div>
        </div>
        <div class="flex gap-8 mt-16" style="justify-content:flex-end">
          <button class="btn" @click="detail=null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const items = ref([])
const page = ref(1)
const totalPages = ref(1)
const searchCode = ref('')
const detail = ref(null)
const detailChartEl = ref(null)
let detailChart = null

async function fetch() {
  const params = { page: page.value, size: 50 }
  if (searchCode.value) params.code = searchCode.value
  const { data } = await axios.get('/api/alerts', { params })
  items.value = data.items
  totalPages.value = Math.max(1, Math.ceil(data.total / 50))
}

async function showDetail(alert) {
  try {
    const { data } = await axios.get(`/api/alerts/${alert.id}`)
    detail.value = data
    await nextTick()
    renderDetailChart()
  } catch { detail.value = alert }
}

function renderDetailChart() {
  if (!detail.value?.trend?.length || !detailChartEl.value) return
  if (detailChart) detailChart.dispose()
  detailChart = echarts.init(detailChartEl.value)
  const trend = detail.value.trend
  detailChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,.95)', borderColor: '#1e293b', textStyle: { color: '#e2e8f0', fontSize: 11 } },
    grid: { top: 10, bottom: 24, left: 50, right: 20 },
    xAxis: { type: 'category', data: trend.map(d => d.ts?.slice(11, 16)), axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
    series: [{
      type: 'line', data: trend.map(d => d.total_heat), smooth: true, symbol: 'none',
      lineStyle: { width: 2.5 }, itemStyle: { color: '#6366f1' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(99,102,241,.3)' }, { offset: 1, color: 'rgba(99,102,241,0)' }] } }
    }]
  })
}

onMounted(fetch)
</script>
