<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, authHeaders } from '../api'

const exams = ref<any[]>([])
const courses = ref<any[]>([])
const dialogOpen = ref(false)
const planForm = ref({ course_id: null as number | null, exam_date: '' })
const creating = ref(false)

async function load() {
  try {
    const [r, c] = await Promise.all([api.reviews(), api.courses()])
    exams.value = r.items || []
    courses.value = c.items || []
  } catch { /* api 层已提示 */ }
}

async function toggleTask(exam: any, task: any) {
  const d = await api.toggleReviewTask(task.task_id, !task.done)
  const idx = exams.value.findIndex(e => e.exam_id === exam.exam_id)
  if (idx >= 0) exams.value[idx] = d
  if (!task.done) ElMessage.success('完成一项，继续保持 🌸')
}

async function createPlan() {
  if (!planForm.value.course_id || !planForm.value.exam_date)
    return ElMessage.warning('请选择课程与考试日期')
  creating.value = true
  try {
    await api.post('/api/review/plan', {
      course_id: planForm.value.course_id,
      exam_date: planForm.value.exam_date,
    })
    ElMessage.success('复习计划已生成 🌸')
    dialogOpen.value = false
    load()
  } catch { /* api 层已提示 */ } finally { creating.value = false }
}

async function removeExam(exam: any) {
  await ElMessageBox.confirm(`删除「${exam.course_name}」的复习计划？`, '删除', { type: 'warning' })
  await api.delete(`/api/review/${exam.exam_id}`)
  load()
}

async function downloadMd(exam: any) {
  ElMessage.info('正在导出 Markdown…')
  await api.exportFile(`/api/export/review-${exam.exam_id}.md`, `${exam.course_name}-复习计划.md`)
  ElMessage.success('Markdown 导出成功 ✅')
}

async function printPdf(exam: any) {
  ElMessage.info('正在生成打印页面…')
  const resp = await fetch(`/api/export/review-print?exam_id=${exam.exam_id}`, { headers: authHeaders() })
  if (resp.status === 401) { ElMessage.error('登录已过期，请重新登录'); location.reload(); return }
  if (!resp.ok) { ElMessage.error(`生成失败（${resp.status}）`); return }
  const html = await resp.text()
  const w = window.open('', '_blank')
  if (!w) { ElMessage.error('请允许弹出窗口以使用打印功能'); return }
  w.document.write(html)
  w.document.close()
}

const today = new Date().toISOString().slice(0, 10)

onMounted(load)
</script>

<template>
  <div class="review-wrap">
    <div class="toolbar glass-panel">
      <div class="hint">基于课程资料自动提取知识树 → 按剩余天数智能排期 → 完成打勾后自动调整后续计划</div>
      <div style="flex:1" />
      <el-button type="primary" @click="dialogOpen = true">
        ＋ 生成新计划
      </el-button>
    </div>

    <div v-if="!exams.length && !courses.length" style="padding:40px">
      <el-empty description="还没有课程资料。先到「资料库」上传课件，我才能提取知识树哦 🌱" />
    </div>

    <div v-if="!exams.length && courses.length" style="padding:40px">
      <el-empty description="还没有复习计划。点击右上角「＋ 生成新计划」开始 📝" />
    </div>

    <div v-for="exam in exams" :key="exam.exam_id" class="exam-card glass-card">
      <div class="e-head">
        <div class="e-title">📝 {{ exam.course_name }}</div>
        <div class="e-date">考试：{{ exam.exam_date }}</div>
        <div class="e-ops">
          <el-button size="small" @click="downloadMd(exam)">⬇ Markdown</el-button>
          <el-button size="small" @click="printPdf(exam)">🖨 打印/PDF</el-button>
          <el-button size="small" type="danger" text @click="removeExam(exam)">删除</el-button>
        </div>
      </div>

      <div class="progress-row petal-progress">
        <el-progress :percentage="exam.progress.percent" :stroke-width="14"
                     :format="() => `${exam.progress.done_points}/${exam.progress.total_points} 知识点`" />
      </div>

      <div class="days">
        <div v-for="t in exam.days" :key="t.task_id" class="day glass-panel"
             :class="{ done: t.done, today: t.date === today }">
          <div class="day-head" @click="toggleTask(exam, t)">
            <el-checkbox :model-value="t.done" @change="toggleTask(exam, t)" @click.stop />
            <span class="day-date">{{ t.date.slice(5) }}</span>
            <span class="day-week">{{ t.weekday }}</span>
            <span class="day-count">{{ t.topics.length }} 个知识点</span>
          </div>
          <ul class="points">
            <li v-for="(p, i) in t.topics" :key="i">
              <b>{{ p.chapter }}</b> · {{ p.point || p.section }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogOpen" title="生成复习计划" width="420">
      <el-alert v-if="!courses.length" type="warning" :closable="false" show-icon
                title="暂无课程资料" description="请先到「资料库」上传课件，我才能提取知识树生成计划 🌱"
                style="margin-bottom:16px" />
      <el-form label-width="80">
        <el-form-item label="课程">
          <el-select v-model="planForm.course_id" style="width:100%" placeholder="选择课程" :disabled="!courses.length">
            <el-option v-for="c in courses" :key="c.id" :label="`${c.name}（${c.file_count}份资料）`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试日期">
          <el-date-picker v-model="planForm.exam_date" type="date" value-format="YYYY-MM-DD"
                          style="width:100%" placeholder="选择日期" :disabled="!courses.length" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!courses.length" @click="createPlan">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.review-wrap { flex: 1; min-height: 0; overflow-y: auto; display: grid; gap: 18px; padding: 4px 8px 8px; }
.toolbar {
  display: flex; align-items: center; gap: 12px; padding: 14px 22px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,.95);
  border-radius: var(--r-full);
  box-shadow: 0 6px 20px rgba(123,75,154,.07);
  flex-shrink: 0;
}
.hint { font-size: 13.5px; color: var(--ink-2); font-weight: 500; }
.hint::before {
  content: '💡'; margin-right: 6px;
}

.exam-card {
  padding: 22px 24px;
  background: rgba(255,255,255,.94);
  border: 1px solid var(--brand-5);
  border-radius: 28px;
  box-shadow: 0 8px 26px rgba(123,75,154,.08);
  position: relative;
  flex-shrink: 0;
}
.exam-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 6px;
  background: linear-gradient(180deg, var(--brand), var(--brand-4));
  border-radius: 6px 0 0 6px;
}
.e-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.e-title {
  font-size: 18px; font-weight: 800; color: var(--ink-1);
  display: inline-flex; align-items: center; gap: 8px;
}
.e-title::before {
  content: '📝'; font-size: 18px;
}
.e-date {
  font-size: 13.5px; color: var(--ink-1);
  background: var(--brand-6); padding: 5px 14px; border-radius: var(--r-full);
  border: 1px solid var(--brand-5);
  font-weight: 600;
}
.e-ops { margin-left: auto; display: flex; gap: 6px; }
.progress-row { margin: 18px 0 20px; }

.days {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}
.day {
  padding: 14px 16px;
  transition: all .2s;
  background: #fff;
  border: 1px solid var(--brand-5);
  border-radius: 22px;
  box-shadow: 0 4px 14px rgba(123,75,154,.04);
  position: relative;
}
body[data-theme="dark"] .day {
  background: rgba(26,18,38,0.92);
  border-color: rgba(201,168,224,0.12);
}
body[data-theme="dark"] .day-date { color: #F0EAF5; }
body[data-theme="dark"] .day-week { color: var(--ink-2); }
body[data-theme="dark"] .day-count {
  background: rgba(201,168,224,0.12);
  color: var(--brand);
}
body[data-theme="dark"] .day-head { border-bottom-color: rgba(201,168,224,0.12); }
.day::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--brand-3), var(--brand-5));
  border-radius: 4px 0 0 4px;
}
.day:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(123,75,154,.10);
}
.day.done { opacity: .6; }
.day.today {
  border-color: var(--brand-3);
  box-shadow: 0 0 0 3px rgba(201,168,224,.35),
              0 8px 22px rgba(123,75,154,.12);
}
.day.done::before { opacity: .5; }
.day-head {
  display: flex; align-items: center; gap: 10px; cursor: pointer;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--brand-5);
  margin-bottom: 10px;
}
.day-date { font-weight: 800; font-size: 15px; color: var(--ink-1); }
.day-week { font-size: 12px; color: var(--ink-3); }
.day-count {
  margin-left: auto; font-size: 11.5px; color: var(--brand);
  background: var(--brand-6); padding: 3px 10px; border-radius: var(--r-full);
  font-weight: 600;
}
.points {
  margin: 0; padding-left: 8px;
  font-size: 13px; line-height: 2; color: var(--ink-2);
  list-style: none;
}
.points li { position: relative; padding-left: 16px; }
.points li::before {
  content: '•'; position: absolute; left: 0; top: 0;
  color: var(--brand-3); font-size: 16px; font-weight: 700;
}
.points b { color: var(--brand); font-weight: 700; }
.day.done .points { text-decoration: line-through; color: var(--ink-3); }
</style>
