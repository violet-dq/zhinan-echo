<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, authHeaders } from '../api'

const items = ref<any[]>([])
const doneItems = ref<any[]>([])
const courses = ref<any[]>([])
const loading = ref(false)
const viewMode = ref<'list' | 'matrix'>('list')
const addOpen = ref(false)
const extractOpen = ref(false)
const extractText = ref('')
const extracting = ref(false)
const addForm = ref({ id: null as number | null, title: '', due: '', priority: 'medium', course_id: null as number | null })
const submitting = ref(false)
const flashTaskId = ref<number | null>(null)

const prioMap: Record<string, any> = { high: 'danger', medium: 'warning', low: 'info' }

async function load(silent = false) {
  loading.value = true
  try {
    const [p, d, c] = await Promise.all([api.ddls('pending'), api.ddls('done'), api.courses()])
    items.value = p.items
    doneItems.value = d.items
    courses.value = c.items
    if (!silent) ElMessage.success({ message: `已刷新：${p.items.length} 项待办`, duration: 1500 })
  } finally { loading.value = false }
}

const grouped = computed(() => {
  const now = new Date()
  const groups: Record<string, any[]> = { 今天: [], 明天: [], 本周: [], 更远: [] }
  for (const it of items.value) {
    const due = new Date(it.due_at)
    const days = Math.floor((due.setHours(0, 0, 0, 0) - now.setHours(0, 0, 0, 0)) / 86400000)
    if (days <= 0) groups.今天.push(it)
    else if (days === 1) groups.明天.push(it)
    else if (days <= 7) groups.本周.push(it)
    else groups.更远.push(it)
  }
  return groups
})

const matrix = computed(() => {
  const now = new Date()
  return items.value.map(it => {
    const days = Math.floor((new Date(it.due_at).getTime() - now.getTime()) / 86400000)
    const urgency = days <= 1 ? 3 : days <= 3 ? 2 : days <= 7 ? 1 : 0
    const importance = it.priority === 'high' ? 3 : it.priority === 'medium' ? 2 : 1
    return { ...it, urgency, importance, days }
  })
})

const fmt = (iso: string) => (iso || '').replace('T', ' ').slice(0, 16)

async function markDone(it: any) {
  await api.updateDdl(it.id, { status: 'done' })
  ElMessage.success(`「${it.title}」已完成 🎉`)
  load()
}

async function remove(it: any) {
  await ElMessageBox.confirm(`确定删除「${it.title}」？`, '删除', { type: 'warning' })
  await api.deleteDdl(it.id)
  load()
}

function fmtLocal(d: any): string {
  const dt = new Date(d)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}T${p(dt.getHours())}:${p(dt.getMinutes())}`
}

function openEdit(it: any) {
  addForm.value = {
    id: it.id,
    title: it.title,
    due: it.due_at ? new Date(it.due_at) : '',
    priority: it.priority,
    course_id: it.course_id,
  }
  addOpen.value = true
}

async function submitAdd() {
  if (!addForm.value.title || !addForm.value.due) return ElMessage.warning('请填写任务名和截止时间')
  submitting.value = true
  try {
    const payload = {
      title: addForm.value.title,
      due_at: fmtLocal(addForm.value.due),
      priority: addForm.value.priority,
      course_id: addForm.value.course_id,
    }
    let createdId: number
    if (addForm.value.id) {
      const updated = await api.updateDdl(addForm.value.id, payload)
      createdId = updated.id
      ElMessage.success('已保存修改 ✏️')
    } else {
      const created = await api.addDdl(payload)
      createdId = created.id
      ElMessage.success('已添加，将按 7天/3天/1天/1小时 分档提醒 ⏰')
    }
    addOpen.value = false
    addForm.value = { id: null, title: '', due: '', priority: 'medium', course_id: null }
    await load(true)
    // 新任务可能落在靠下的分组（如"更远"），自动滚动定位并高亮，避免"看不见"
    flashTaskId.value = createdId
    nextTick(() => {
      document.querySelector(`[data-ddl-id="${created.id}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
    setTimeout(() => (flashTaskId.value = null), 3000)
  } finally { submitting.value = false }
}

async function submitExtract() {
  if (!extractText.value.trim()) return
  extracting.value = true
  try {
    const d = await api.extractDdl(extractText.value)
    d.count ? ElMessage.success(`识别到 ${d.count} 条截止任务 ✅`) : ElMessage.warning(d.message)
    extractOpen.value = false
    extractText.value = ''
    load()
  } finally { extracting.value = false }
}

async function onOcr(e: Event) {
  const t = e.target as HTMLInputElement
  const file = t.files?.[0]
  t.value = ''
  if (!file) return
  const form = new FormData()
  form.append('image', file)
  const loading = ElMessage({ message: 'OCR 识别中…', duration: 0 })
  try {
    const d = await api.ocrDdl(form)
    ElMessage.success(d.message)
    load()
  } catch { /* api 层已提示 */ } finally { loading.close() }
}

function downloadIcs() {
  fetch('/api/export/ddl.ics', { headers: authHeaders() })
    .then(r => r.blob())
    .then(b => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = 'zhinan-echo-ddl.ics'
      a.click()
      URL.revokeObjectURL(a.href)
    })
  ElMessage.success('iCal 已下载，可导入手机日历 📅')
}

onMounted(() => load(true))
</script>

<template>
  <div class="ddl-wrap">
    <div class="toolbar glass-panel">
      <el-radio-group v-model="viewMode">
        <el-radio-button value="list">列表视图</el-radio-button>
        <el-radio-button value="matrix">优先级矩阵</el-radio-button>
      </el-radio-group>
      <div style="flex:1" />
      <el-button @click="extractOpen = true">📝 粘贴通知提取</el-button>
      <label><input type="file" hidden accept=".jpg,.jpeg,.png" @change="onOcr" />
        <el-button tag="span">🖼️ 截图 OCR</el-button>
      </label>
      <el-button type="primary" @click="addOpen = true">＋ 手动新增</el-button>
      <el-button @click="downloadIcs">⬇ 导出 iCal</el-button>
      <el-button :loading="loading" @click="load()">🔄 刷新</el-button>
    </div>
    <div v-loading="loading" style="min-height:200px; flex:1">

    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div v-for="(list, g) in grouped" :key="g" v-show="list.length" class="group">
        <div class="group-title" :class="{ urgent: g === '今天' }">{{ g }} <span>{{ list.length }}</span></div>
        <div class="ddl-item glass-card" v-for="it in list" :key="it.id"
             :data-ddl-id="it.id"
             :class="{ urgent: g === '今天', flash: it.id === flashTaskId }">
          <div class="d-main">
            <div class="d-title">
              <el-tag :type="prioMap[it.priority]" size="small" effect="dark">
                {{ it.priority === 'high' ? '高优' : it.priority === 'low' ? '低优' : '中优' }}
              </el-tag>
              {{ it.title }}
              <el-tag v-if="it.course" size="small" effect="plain">{{ it.course }}</el-tag>
            </div>
            <div class="d-detail" v-if="it.detail">{{ it.detail }}</div>
          </div>
          <div class="d-side">
            <div class="d-due">⏰ {{ fmt(it.due_at) }}</div>
            <div class="d-rel" :class="{ hot: it.days_left <= 1 }">{{ it.relative }}</div>
          </div>
          <div class="d-ops">
            <el-button size="small" type="success" plain round @click="markDone(it)">完成</el-button>
            <el-button size="small" text @click="openEdit(it)">✏️ 编辑</el-button>
            <el-button size="small" type="danger" text @click="remove(it)">删除</el-button>
          </div>
        </div>
      </div>
      <el-empty v-if="!items.length" description="没有待办任务，从容 🌿" />
    </template>

    <!-- 优先级矩阵视图 -->
    <template v-else>
      <div class="matrix glass-card">
        <div class="m-cell" v-for="q in [
            { name: '🔴 紧急且重要', match: (m:any) => m.urgency >= 2 && m.importance >= 2 },
            { name: '🟡 重要不紧急', match: (m:any) => m.urgency < 2 && m.importance >= 2 },
            { name: '🟠 紧急不重要', match: (m:any) => m.urgency >= 2 && m.importance < 2 },
            { name: '⚪ 不急不重要', match: (m:any) => m.urgency < 2 && m.importance < 2 }]"
            :key="q.name">
          <div class="m-head">{{ q.name }}</div>
          <div v-for="m in matrix.filter(q.match)" :key="m.id" class="m-item">
            {{ m.title }}<span class="m-due">{{ fmt(m.due_at) }}</span>
          </div>
          <div v-if="!matrix.filter(q.match).length" class="m-empty">—</div>
        </div>
      </div>
    </template>

    <!-- 已完成 -->
    <details v-if="doneItems.length" class="done-box glass-panel">
      <summary>已完成（{{ doneItems.length }}）</summary>
      <div v-for="d in doneItems" :key="d.id" class="done-row">✅ {{ d.title }} · {{ fmt(d.due_at) }}</div>
    </details>
    </div>

    <!-- 手动新增 -->
    <el-dialog v-model="addOpen" :title="addForm.id ? '编辑截止任务' : '新增截止任务'" width="460">
      <el-form label-width="80">
        <el-form-item label="任务名"><el-input v-model="addForm.title" placeholder="如：算法第3章作业" /></el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="addForm.due" type="datetime" style="width:100%"
                          placeholder="选择日期与时间" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="addForm.priority">
            <el-radio value="high">高</el-radio><el-radio value="medium">中</el-radio><el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="课程">
          <el-select v-model="addForm.course_id" clearable placeholder="可选" style="width:100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAdd">保存</el-button>
      </template>
    </el-dialog>

    <!-- 文本批量提取 -->
    <el-dialog v-model="extractOpen" title="粘贴通知文字，自动提取 DDL" width="560">
      <el-input v-model="extractText" type="textarea" :rows="7"
                placeholder='粘贴示例：&#10;各位同学：数据库第4次作业请于8月18日23:59前提交至学习通。&#10;软件工程中期报告8月22号下午5点截止。' />
      <template #footer>
        <el-button @click="extractOpen = false">取消</el-button>
        <el-button type="primary" :loading="extracting" @click="submitExtract">智能提取</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ddl-wrap { flex: 1; min-height: 0; overflow-y: auto; display: grid; gap: 16px; padding: 4px 8px 8px; }
.toolbar {
  display: flex; align-items: center; gap: 10px; padding: 12px 18px; flex-wrap: wrap;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,.95);
  border-radius: var(--r-full);
  box-shadow: 0 6px 20px rgba(123,75,154,.07);
}
.group { margin-top: 6px; }
.group-title {
  font-weight: 800; color: var(--brand); margin-bottom: 10px;
  font-size: 15.5px; letter-spacing: 0.5px;
  display: inline-flex; align-items: center; gap: 8px;
}
.group-title::before {
  content: ''; display: inline-block;
  width: 6px; height: 20px; border-radius: 3px;
  background: linear-gradient(180deg, var(--brand), var(--brand-4));
}
.group-title span { color: var(--ink-3); font-weight: 500; font-size: 13px; }
.group-title.urgent { color: #E85F77; }
.group-title.urgent::before {
  background: linear-gradient(180deg, #E85F77, #FFB3BE);
}

.ddl-item {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 20px; margin-bottom: 10px;
  background: #fff;
  border: 1px solid var(--brand-5);
  border-radius: 24px;
  box-shadow: 0 6px 20px rgba(123,75,154,.06);
  position: relative; overflow: hidden;
  transition: all .2s;
}
.ddl-item::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 5px; border-radius: 5px 0 0 5px;
  background: linear-gradient(180deg, var(--brand-3), var(--brand-5));
}
.ddl-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(123,75,154,.12);
}
.ddl-item.urgent::before { background: linear-gradient(180deg, #E85F77, #FFB3BE); }
.ddl-item.flash { animation: flashNew 1s ease-in-out 3; }
@keyframes flashNew {
  0%, 100% { background: #fff; }
  50% { background: var(--brand-6); }
}
.d-main { flex: 1; min-width: 0; }
.d-title { font-weight: 700; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; color: var(--ink-1); font-size: 15px; }
.d-detail { font-size: 13px; color: var(--ink-2); margin-top: 5px; line-height: 1.55;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.d-side { text-align: right; }
.d-due { font-size: 13.5px; color: var(--ink-1); font-weight: 600; }
.d-rel { font-size: 12px; color: var(--ink-3); margin-top: 3px; }
.d-rel.hot { color: #E85F77; font-weight: 700; }
.d-ops { display: flex; gap: 4px; }

.matrix {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 20px;
  background: rgba(255,255,255,.92);
  border: 1px solid var(--brand-5);
  border-radius: 28px;
  box-shadow: 0 8px 24px rgba(123,75,154,.08);
}
body[data-theme="dark"] .matrix {
  background: rgba(26,18,38,0.90);
  border-color: rgba(201,168,224,0.12);
}
.m-cell {
  padding: 16px 18px;
  border-radius: 22px;
  background: var(--brand-6);
  border: 1px solid var(--brand-5);
}
.m-head { font-weight: 800; margin-bottom: 10px; font-size: 14.5px; color: var(--ink-1); }
.m-item {
  background: #fff; border-radius: var(--r-full); padding: 8px 14px;
  margin-bottom: 7px; font-size: 13px;
  display: flex; justify-content: space-between; gap: 10px; align-items: center;
  border: 1px solid var(--brand-5);
  color: var(--ink-1);
}
body[data-theme="dark"] .m-item {
  background: rgba(46,31,68,0.88);
  border-color: rgba(201,168,224,0.15);
}
.m-due { color: var(--ink-3); font-size: 12px; flex-shrink: 0; }
.m-empty { color: var(--ink-3); text-align: center; padding: 10px; font-size: 13px; }

.done-box {
  padding: 12px 22px; font-size: 13px;
  background: rgba(255,255,255,.88);
  border: 1px solid var(--brand-5);
  border-radius: 22px;
}
body[data-theme="dark"] .done-box {
  background: rgba(26,18,38,0.88);
  border-color: rgba(201,168,224,0.12);
  color: var(--ink-1);
}
.done-box summary { cursor: pointer; color: var(--ink-2); font-weight: 600; padding: 4px 0; }
.done-row { padding: 4px 0; color: var(--ink-3); text-decoration: line-through; }
</style>
