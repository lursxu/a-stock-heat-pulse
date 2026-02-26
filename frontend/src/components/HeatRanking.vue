<template>
  <table>
    <tr><th>排名</th><th>股票</th><th>综合热度</th><th>交易热度</th><th>舆情热度</th><th>涨跌幅</th><th>量比</th><th>操作</th></tr>
    <tr v-for="(item, i) in items" :key="item.code">
      <td>{{ i + 1 }}</td>
      <td>{{ item.name }}({{ item.code }})</td>
      <td>{{ item.total_heat?.toFixed(3) }}</td>
      <td>{{ item.trade_heat?.toFixed(3) }}</td>
      <td>{{ item.sentiment_heat?.toFixed(3) }}</td>
      <td :class="(item.change_pct||0)>=0?'tag-red':'tag-green'">{{ item.change_pct?.toFixed(2) }}%</td>
      <td>{{ item.volume_ratio?.toFixed(2) }}</td>
      <td><button class="btn btn-sm" @click="$emit('select', item.code)">趋势</button></td>
    </tr>
  </table>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
defineEmits(['select'])
</script>
