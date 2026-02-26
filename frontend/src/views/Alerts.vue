<template>
  <div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">🚨 告警历史</span>
        <div class="flex gap-8 items-center">
          <input v-model="searchCode" placeholder="搜索股票代码..." @keyup.enter="page=1;fetch()" style="width:160px" />
          <button class="btn btn-sm" @click="page=1;fetch()">搜索</button>
          <button v-if="searchCode" class="btn btn-sm" @click="searchCode='';page=1;fetch()">清除</button>
        </div>
      </div>
      <table>
        <tr>
          <th>时间</th>
          <th>股票</th>
          <th>综合热度</th>
          <th>Z-Score</th>
          <th>涨跌幅</th>
          <th>量比</th>
          <th>操作</th>
        </tr>
        <tr v-for="a in items" :key="a.id" @click="showDetail(a)" style="cursor:pointer">
          <td class="text-sm">{{ a.ts }}</td>
          <td><b>{{ a.name }}</b> <span class="text-dim">{{ a.code }}</span></td>
          <td><span class="tag tag-bg-blue">{{ a.total_heat?.toFixed(3) }}</span></td>
          <td><span class="tag tag-bg-red">{{ a.zscore?.toFixed(1) }}</span></td>
          <td :class="(a.change_pct||0)>=0?'tag-red':'tag-green'">{{ (a.change_pct||0).toFixed(2) }}%</td>
          <td>{{ (a.volume_ratio||0).toFixed(2) }}</td>
          <td><button class="btn btn-sm" @click.stop="showDetail(a)">详情</button></td>
        </tr>
        <tr v-if="!items.length"><td colspan="7" class="text-dim" style="text-align:center;padding:20px">暂无告警记录</td></tr>
      </table>
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetch()">‹</button>
        <span class="text-dim text-sm">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetch()">›</button>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="detail" class="modal-overlay" @click.self="detail=null">
      <div class="modal" style="min-width:600px">
        <div class="modal-title">告警详情 - {{ detail.name }} ({{ detail.code }})</div>
        <div class="flex gap-16 mb-16">
          <div><span class="text-dim">时间</span><br/>{{ detail.ts }}</div>
          <div><span class="text-dim">Z-Score</span><br/><span class="tag-red" style="font-size:18px;font-weight:700">{{ detail.zscore?.toFixed(2) }}</span></div>
          <div><span class="text-dim">热度</span><br/>{{ detail.total_heat?.toFixed(4) }}</div>
          <div><span class="text-dim">涨跌幅</span><br/><span :class="(detail.change_pct||0)>=0?'tag-red':'tag-green'">{{ (detail.change_pct||0).toFixed(2) }}%</span></div>
          <div><span class="text-dim">量比</span><br/>{{ (detail.volume_ratio||0).toFixed(2) }}</div>
        </div>
        <div v-if="detail.trend?.length">
          <div class="text-dim mb-8">告警前后热度变化</div>
          <div ref="detailChartEl" style="width:100%;height:200px"></div>
        </div>
        <div class="flex gap-8 mt-16" style="justify-content:flex-end">
          <button class="btn" @click="detail=null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
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
  } catch {
    detail.value = alert
  }
}

function renderDetailChart() {
  if (!detail.value?.trend?.length || !detailChartEl.value) return
  if (detailChart) detailChart.dispose()
  detailChart = echarts.init(detailChartEl.value)
  const trend = detail.value.trend
  detailChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#2a3a4a', textStyle: { color: '#e0e6ed', fontSize: 11 } },
    grid: { top: 10, bottom: 24, left: 50, right: 20 },
    xAxis: { type: 'category', data: trend.map(d => d.ts?.slice(11, 16)), axisLine: { lineStyle: { color: '#2a3a4a' } }, axisLabel: { color: '#8899aa', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e2a3a' } }, axisLabel: { color: '#8899aa', fontSize: 10 } },
    series: [
      { type: 'line', data: trend.map(d => d.total_heat), smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#3b82f6' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } } }
    ]
  })
}

onMounted(fetch)
</script>
