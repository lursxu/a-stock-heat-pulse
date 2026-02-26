<template>
  <div>
    <div class="card">
      <h3>🚨 告警历史</h3>
      <table>
        <tr><th>时间</th><th>股票</th><th>热度</th><th>Z-Score</th><th>涨跌幅</th><th>量比</th></tr>
        <tr v-for="a in items" :key="a.id">
          <td>{{ a.ts }}</td>
          <td>{{ a.name }}({{ a.code }})</td>
          <td>{{ a.total_heat?.toFixed(3) }}</td>
          <td class="tag-red">{{ a.zscore?.toFixed(1) }}</td>
          <td :class="(a.change_pct||0)>=0?'tag-red':'tag-green'">{{ a.change_pct?.toFixed(2) }}%</td>
          <td>{{ a.volume_ratio?.toFixed(2) }}</td>
        </tr>
      </table>
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetch()">上一页</button>
        <span style="font-size:13px;line-height:28px">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-sm" :disabled="page>=totalPages" @click="page++;fetch()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const items = ref([])
const page = ref(1)
const totalPages = ref(1)

async function fetch() {
  const { data } = await axios.get('/api/alerts', { params: { page: page.value, size: 50 } })
  items.value = data.items
  totalPages.value = Math.max(1, Math.ceil(data.total / 50))
}

onMounted(fetch)
</script>
