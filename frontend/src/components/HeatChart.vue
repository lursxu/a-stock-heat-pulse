<template>
  <div ref="chartEl" style="width:100%;height:350px"></div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const props = defineProps({ code: String })
const chartEl = ref(null)
let chart = null

async function render() {
  if (!props.code) return
  const { data } = await axios.get(`/api/heat/trend/${props.code}`, { params: { hours: 24 } })
  if (!chart) chart = echarts.init(chartEl.value)
  const ts = data.map(d => d.ts)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['综合热度', '交易热度', '舆情热度', 'Z-Score'] },
    xAxis: { type: 'category', data: ts },
    yAxis: [{ type: 'value', name: '热度' }, { type: 'value', name: 'Z-Score' }],
    series: [
      { name: '综合热度', type: 'line', data: data.map(d => d.total_heat), smooth: true },
      { name: '交易热度', type: 'line', data: data.map(d => d.trade_heat), smooth: true },
      { name: '舆情热度', type: 'line', data: data.map(d => d.sentiment_heat), smooth: true },
      { name: 'Z-Score', type: 'line', yAxisIndex: 1, data: data.map(d => d.zscore), smooth: true, lineStyle: { type: 'dashed' } },
    ],
  })
}

watch(() => props.code, render)
onMounted(render)
</script>
