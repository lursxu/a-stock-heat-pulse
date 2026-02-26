<template>
  <div>
    <div class="card">
      <h3>⏱️ 任务管理</h3>
      <p style="font-size:13px;color:#999;margin-bottom:12px">可手动触发任务，也可通过定时规则自动执行。首次使用请先执行「基础数据同步」。</p>

      <table>
        <tr><th>任务</th><th>说明</th><th>定时规则</th><th>下次执行</th><th>最近状态</th><th>操作</th></tr>
        <tr v-for="t in taskList" :key="t.id">
          <td style="font-weight:600">{{ t.label }}</td>
          <td style="font-size:12px;color:#666">{{ t.desc }}</td>
          <td>{{ getJobTrigger(t.id) }}</td>
          <td>{{ getJobNextRun(t.id) }}</td>
          <td>
            <span v-if="getLastLog(t.id)" :class="getLastLog(t.id).status==='ok'?'tag-green':'tag-red'">
              {{ getLastLog(t.id).status }} ({{ getLastLog(t.id).duration_sec }}s)
            </span>
            <span v-else style="color:#999">未执行</span>
          </td>
          <td>
            <button class="btn btn-sm" :disabled="running[t.id]" @click="trigger(t.id)">
              {{ running[t.id] ? '执行中...' : '立即执行' }}
            </button>
          </td>
        </tr>
      </table>
    </div>

    <div class="card">
      <h3>📋 执行日志</h3>
      <div style="margin-bottom:10px">
        <select v-model="filterJob" @change="page=1;fetchLogs()">
          <option value="">全部任务</option>
          <option v-for="t in taskList" :key="t.id" :value="t.logName">{{ t.label }}</option>
        </select>
      </div>
      <table>
        <tr><th>时间</th><th>任务</th><th>状态</th><th>耗时</th><th>信息</th></tr>
        <tr v-for="l in logs" :key="l.id">
          <td style="white-space:nowrap">{{ l.ts }}</td>
          <td>{{ labelMap[l.job_name] || l.job_name }}</td>
          <td :class="l.status==='ok'?'tag-green':'tag-red'">{{ l.status }}</td>
          <td>{{ l.duration_sec }}s</td>
          <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ l.message }}</td>
        </tr>
        <tr v-if="!logs.length"><td colspan="5" style="text-align:center;color:#999">暂无记录</td></tr>
      </table>
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetchLogs()">上一页</button>
        <span style="font-size:13px;line-height:28px">{{ page }}</span>
        <button class="btn btn-sm" @click="page++;fetchLogs()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const taskList = [
  { id: 'sync_basic', logName: 'sync_basic', label: '基础数据同步', desc: '同步全A股股票列表，首次使用必须先执行' },
  { id: 'collect_trade', logName: 'collect_trade', label: '交易行情采集', desc: '采集全A股实时行情（量比、换手率、成交额等）' },
  { id: 'collect_sentiment', logName: 'collect_sentiment', label: '舆情数据采集', desc: '采集股吧+雪球讨论热度（仅Top N股票）' },
  { id: 'calc_heat', logName: 'calc_heat', label: '热度计算', desc: '综合交易+舆情数据计算热度分' },
  { id: 'detect_anomaly', logName: 'detect_anomaly', label: '异常检测+告警', desc: 'Z-Score异常检测并推送告警' },
  { id: 'full_scan', logName: 'full_scan', label: '完整扫描', desc: '依次执行：行情采集→热度计算→舆情采集→热度计算→异常检测' },
  { id: 'cleanup', logName: 'cleanup', label: '数据清理', desc: '清理超过保留期限的历史数据' },
]

const labelMap = {}
taskList.forEach(t => { labelMap[t.logName] = t.label })

const jobs = ref([])
const jobLogs = ref([])
const logs = ref([])
const filterJob = ref('')
const page = ref(1)
const running = reactive({})

function getJobTrigger(id) {
  const j = jobs.value.find(j => j.id === id)
  return j ? j.trigger : '-'
}
function getJobNextRun(id) {
  const j = jobs.value.find(j => j.id === id)
  return j?.next_run || '-'
}
function getLastLog(id) {
  const t = taskList.find(t => t.id === id)
  return jobLogs.value.find(l => l.job_name === t?.logName)
}

async function fetchJobs() {
  const { data } = await axios.get('/api/jobs')
  jobs.value = data.jobs
  jobLogs.value = data.logs
}

async function fetchLogs() {
  const params = { page: page.value, size: 50 }
  if (filterJob.value) params.job_name = filterJob.value
  const { data } = await axios.get('/api/jobs/logs', { params })
  logs.value = data.items
}

async function trigger(id) {
  running[id] = true
  try {
    await axios.post(`/api/jobs/${id}/trigger`)
    // Poll for completion
    const poll = setInterval(async () => {
      await fetchJobs()
      await fetchLogs()
      running[id] = false
      clearInterval(poll)
    }, 3000)
  } catch {
    running[id] = false
  }
}

onMounted(() => { fetchJobs(); fetchLogs() })
</script>
