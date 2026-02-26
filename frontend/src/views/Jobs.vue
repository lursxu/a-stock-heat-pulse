<template>
  <div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">⏱️ 任务管理</span>
        <span class="text-dim text-sm">可手动触发任务，首次使用请先执行「基础数据同步」</span>
      </div>

      <table>
        <tr>
          <th>任务</th>
          <th>说明</th>
          <th>定时规则</th>
          <th>下次执行</th>
          <th>最近状态</th>
          <th>操作</th>
        </tr>
        <tr v-for="t in taskList" :key="t.id">
          <td style="font-weight:600">{{ t.label }}</td>
          <td class="text-dim text-sm">{{ t.desc }}</td>
          <td class="text-sm">{{ getJobTrigger(t.id) }}</td>
          <td class="text-sm">{{ getJobNextRun(t.id) }}</td>
          <td>
            <span v-if="isRunning(t.id)" class="tag tag-bg-orange">
              ⏳ 运行中 {{ runningInfo(t.id) }}
            </span>
            <span v-else-if="getLastLog(t.id)" :class="['tag', getLastLog(t.id).status==='ok'?'tag-bg-green':'tag-bg-red']">
              {{ getLastLog(t.id).status === 'ok' ? '✓' : '✗' }} {{ getLastLog(t.id).status }} ({{ getLastLog(t.id).duration_sec }}s)
            </span>
            <span v-else class="text-dim">未执行</span>
          </td>
          <td>
            <button class="btn btn-sm" :class="{'btn-primary': !isRunning(t.id)}" :disabled="isRunning(t.id)" @click="confirmTrigger(t)">
              {{ isRunning(t.id) ? '运行中' : '▶ 执行' }}
            </button>
          </td>
        </tr>
      </table>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">📋 执行日志</span>
        <div class="flex gap-8 items-center">
          <select v-model="filterJob" @change="page=1;fetchLogs()">
            <option value="">全部任务</option>
            <option v-for="t in taskList" :key="t.id" :value="t.logName">{{ t.label }}</option>
          </select>
        </div>
      </div>
      <table>
        <tr>
          <th>时间</th>
          <th>任务</th>
          <th>状态</th>
          <th>耗时</th>
          <th>信息</th>
        </tr>
        <tr v-for="l in logs" :key="l.id">
          <td class="text-sm" style="white-space:nowrap">{{ l.ts }}</td>
          <td>{{ labelMap[l.job_name] || l.job_name }}</td>
          <td><span :class="['tag', l.status==='ok'?'tag-bg-green':'tag-bg-red']">{{ l.status }}</span></td>
          <td>{{ l.duration_sec }}s</td>
          <td class="truncate" style="max-width:400px">{{ l.message }}</td>
        </tr>
        <tr v-if="!logs.length"><td colspan="5" class="text-dim" style="text-align:center;padding:20px">暂无记录</td></tr>
      </table>
      <div class="pagination">
        <button class="btn btn-sm" :disabled="page<=1" @click="page--;fetchLogs()">‹</button>
        <span class="text-dim text-sm">{{ page }}</span>
        <button class="btn btn-sm" @click="page++;fetchLogs()">›</button>
      </div>
    </div>

    <!-- Confirm Modal -->
    <div v-if="confirmTask" class="modal-overlay" @click.self="confirmTask=null">
      <div class="modal">
        <div class="modal-title">确认执行</div>
        <p style="margin-bottom:16px">确定要执行「{{ confirmTask.label }}」吗？</p>
        <p class="text-dim text-sm" style="margin-bottom:16px">{{ confirmTask.desc }}</p>
        <div class="flex gap-8" style="justify-content:flex-end">
          <button class="btn" @click="confirmTask=null">取消</button>
          <button class="btn btn-primary" @click="trigger(confirmTask.id); confirmTask=null">确认执行</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted, watch } from 'vue'
import axios from 'axios'

const toast = inject('toast')
const wsData = inject('wsData')

const taskList = [
  { id: 'sync_basic', logName: 'sync_basic', label: '基础数据同步', desc: '同步全A股股票列表，首次使用必须先执行' },
  { id: 'collect_trade', logName: 'collect_trade', label: '交易行情采集', desc: '采集全A股实时行情（量比、换手率、成交额等）' },
  { id: 'collect_sentiment', logName: 'collect_sentiment', label: '舆情数据采集', desc: '采集股吧+雪球讨论热度（仅Top N股票）' },
  { id: 'calc_heat', logName: 'calc_heat', label: '热度计算', desc: '综合交易+舆情数据计算热度分' },
  { id: 'detect_anomaly', logName: 'detect_anomaly', label: '异常检测+告警', desc: 'Z-Score异常检测 + 箱体突破检测' },
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
const confirmTask = ref(null)

function getJobTrigger(id) { return jobs.value.find(j => j.id === id)?.trigger || '-' }
function getJobNextRun(id) { return jobs.value.find(j => j.id === id)?.next_run?.slice(0, 19) || '-' }
function getLastLog(id) {
  const t = taskList.find(t => t.id === id)
  return jobLogs.value.find(l => l.job_name === t?.logName)
}
function isRunning(id) { return !!(wsData.value.runningJobs && wsData.value.runningJobs[id]) }
function runningInfo(id) {
  const j = wsData.value.runningJobs?.[id]
  return j?.progress || ''
}

function confirmTrigger(task) { confirmTask.value = task }

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
  try {
    await axios.post(`/api/jobs/${id}/trigger`)
    toast(`${labelMap[id] || id} 已触发`, 'info')
  } catch (e) {
    toast(e.response?.data?.detail || '执行失败', 'error')
  }
}

// Refresh when job completes
watch(() => wsData.value.runningJobs, () => { fetchJobs(); fetchLogs() }, { deep: true })

onMounted(() => { fetchJobs(); fetchLogs() })
</script>
