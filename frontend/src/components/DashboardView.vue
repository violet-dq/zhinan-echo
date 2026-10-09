<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import EchoLogo from './EchoLogo.vue'

const emit = defineEmits<{ (e: 'jump', key: string): void }>()

const nickname = ref(localStorage.getItem('echo_nickname') || '同学')
const loading = ref(true)
const data = ref<any>({
  today_ddl: [],
  week_ddl_count: 0,
  files_count: 0,
  reviews: [],
  recent_files: [],
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayStr = computed(() => {
  const d = new Date()
  const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${w}`
})

const quickEntries = [
  { key: 'chat', label: '对话助教', desc: '用自然语言问答资料', icon: 'ChatDotRound', color: '#7B4B9A' },
  { key: 'library', label: '资料索引', desc: '浏览课程文档', icon: 'Collection', color: '#A87BC5' },
  { key: 'ddl', label: 'DDL看板', desc: '管理截止日期', icon: 'AlarmClock', color: '#E85F77' },
  { key: 'review', label: '复习计划', desc: '每日复习任务', icon: 'Notebook', color: '#E6A23C' },
]

onMounted(async () => {
  try {
    data.value = await api.dashboard()
  } catch { /* 静默 */ } finally { loading.value = false }
})

function priorityLabel(p: string) {
  return { high: '高', medium: '中', low: '低' }[p] || '中'
}
function priorityColor(p: string) {
  return { high: '#E85F77', medium: '#E6A23C', low: '#67C23A' }[p] || '#E6A23C'
}
</script>

<template>
  <div class="dashboard">
    <!-- ===== 欢迎横幅 ===== -->
    <section class="hero surface-solid">
      <div class="hero-left">
        <div class="greet-row">
          <div class="logo-chip">
            <EchoLogo :size="26" />
          </div>
          <div class="greet-text">
            <div class="greet">{{ greeting }}，{{ nickname }} 👋</div>
            <div class="date">{{ todayStr }}</div>
          </div>
        </div>
        <h2 class="hero-title">知南而行，必有回响</h2>
        <p class="hero-sub">今天也一起把资料、DDL 和复习安排得井井有条吧。</p>
      </div>
      <div class="hero-right">
        <div class="hero-stat">
          <div class="stat-num">{{ data.today_ddl.length }}</div>
          <div class="stat-label">今日待办 DDL</div>
        </div>
        <div class="hero-illust">🌸</div>
      </div>
    </section>

    <!-- ===== 统计卡片 ===== -->
    <section class="stats">
      <div class="stat-card surface-solid" @click="emit('jump', 'ddl')">
        <div class="sc-icon" style="background:linear-gradient(135deg,#FFB3C1,#E85F77)">
          <el-icon :size="22"><AlarmClock /></el-icon>
        </div>
        <div class="sc-body">
          <div class="sc-num">{{ data.today_ddl.length }}</div>
          <div class="sc-label">今日 DDL</div>
        </div>
      </div>
      <div class="stat-card surface-solid" @click="emit('jump', 'ddl')">
        <div class="sc-icon" style="background:linear-gradient(135deg,#FFD79B,#E6A23C)">
          <el-icon :size="22"><Calendar /></el-icon>
        </div>
        <div class="sc-body">
          <div class="sc-num">{{ data.week_ddl_count }}</div>
          <div class="sc-label">本周 DDL</div>
        </div>
      </div>
      <div class="stat-card surface-solid" @click="emit('jump', 'library')">
        <div class="sc-icon" style="background:linear-gradient(135deg,#C9A8E0,#7B4B9A)">
          <el-icon :size="22"><Collection /></el-icon>
        </div>
        <div class="sc-body">
          <div class="sc-num">{{ data.files_count }}</div>
          <div class="sc-label">资料总数</div>
        </div>
      </div>
      <div class="stat-card surface-solid" @click="emit('jump', 'review')">
        <div class="sc-icon" style="background:linear-gradient(135deg,#A8E6CF,#67C23A)">
          <el-icon :size="22"><Notebook /></el-icon>
        </div>
        <div class="sc-body">
          <div class="sc-num">{{ data.reviews.length }}</div>
          <div class="sc-label">进行中考试</div>
        </div>
      </div>
    </section>

    <!-- ===== 快速入口 ===== -->
    <section class="quick">
      <div class="section-title">
        <span class="st-bar"></span>
        <h3>快速入口</h3>
      </div>
      <div class="quick-grid">
        <div
          v-for="q in quickEntries"
          :key="q.key"
          class="quick-card surface-solid"
          @click="emit('jump', q.key)"
        >
          <div class="qc-icon" :style="{ background: q.color }">
            <el-icon :size="22" color="#fff"><component :is="q.icon" /></el-icon>
          </div>
          <div class="qc-label">{{ q.label }}</div>
          <div class="qc-desc">{{ q.desc }}</div>
        </div>
      </div>
    </section>

    <!-- ===== 双栏：今日DDL + 复习进度/最近资料 ===== -->
    <section class="two-col">
      <!-- 今日 DDL -->
      <div class="col-card surface-solid">
        <div class="card-head">
          <h3>📌 今日 DDL</h3>
          <a class="more-link" @click="emit('jump', 'ddl')">查看全部 →</a>
        </div>
        <div v-if="loading" class="empty">加载中…</div>
        <div v-else-if="!data.today_ddl.length" class="empty">
          <div class="empty-icon">🍃</div>
          <div>今天没有 DDL，安心学习～</div>
        </div>
        <div v-else class="ddl-list">
          <div v-for="d in data.today_ddl" :key="d.id" class="ddl-item">
            <div class="ddl-dot" :style="{ background: priorityColor(d.priority) }"></div>
            <div class="ddl-main">
              <div class="ddl-title">{{ d.title }}</div>
              <div class="ddl-meta">
                <el-tag :color="priorityColor(d.priority)" effect="light" size="small">
                  {{ priorityLabel(d.priority) }}优先级
                </el-tag>
                <span class="ddl-time">{{ d.due_at }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右列 -->
      <div class="right-col">
        <!-- 复习进度 -->
        <div class="col-card surface-solid">
          <div class="card-head">
            <h3>📈 复习进度</h3>
            <a class="more-link" @click="emit('jump', 'review')">去复习 →</a>
          </div>
          <div v-if="loading" class="empty">加载中…</div>
          <div v-else-if="!data.reviews.length" class="empty">
            <div class="empty-icon">📚</div>
            <div>暂无考试，去复习计划添加考试吧</div>
          </div>
          <div v-else class="review-list">
            <div v-for="r in data.reviews" :key="r.exam_id" class="review-item">
              <div class="rv-top">
                <span class="rv-course">{{ r.course_name }}</span>
                <span class="rv-days" :class="{ urgent: r.days_to_exam <= 3 }">
                  {{ r.days_to_exam > 0 ? `还有 ${r.days_to_exam} 天` : '今天考试' }}
                </span>
              </div>
              <div class="rv-bar">
                <div class="rv-bar-inner" :style="{ width: r.percent + '%' }"></div>
              </div>
              <div class="rv-bottom">
                <span>{{ r.exam_date }} 考试</span>
                <span class="rv-percent">{{ r.percent }}%</span>
              </div>
              <div v-if="r.today_topics.length" class="rv-today">
                <span class="rv-today-label">今日任务：</span>
                <span class="rv-topics">{{ r.today_topics.slice(0, 3).join('、') }}{{ r.today_topics.length > 3 ? '…' : '' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 最近资料 -->
        <div class="col-card surface-solid">
          <div class="card-head">
            <h3>📄 最近资料</h3>
            <a class="more-link" @click="emit('jump', 'library')">更多 →</a>
          </div>
          <div v-if="loading" class="empty">加载中…</div>
          <div v-else-if="!data.recent_files.length" class="empty">
            <div class="empty-icon">📂</div>
            <div>还没有资料，去资料库上传吧</div>
          </div>
          <div v-else class="file-list">
            <div v-for="f in data.recent_files" :key="f.id" class="file-item">
              <div class="file-icon">
                <el-icon :size="18"><Document /></el-icon>
              </div>
              <div class="file-main">
                <div class="file-name">{{ f.filename }}</div>
                <div class="file-course">{{ f.course }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  display: grid;
  gap: 18px;
  padding: 4px 2px 18px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

/* ===== 欢迎横幅 ===== */
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30px 36px;
  gap: 24px;
  position: relative;
  flex-shrink: 0;
}
.hero::after {
  content: '';
  position: absolute;
  right: -40px; top: -40px;
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(201,168,224,.25), transparent 70%);
  pointer-events: none;
  z-index: -1;
}
.greet-row { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.logo-chip {
  width: 46px; height: 46px; border-radius: 14px;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(123,75,154,.3);
}
.greet { font-size: 22px; font-weight: 700; color: var(--ink-1); }
.date { font-size: 13px; color: var(--ink-3); margin-top: 2px; }
.hero-title {
  margin: 0 0 8px;
  font-size: 30px; font-weight: 800;
  background: linear-gradient(135deg, var(--brand), var(--brand-3));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: 1px;
}
.hero-sub { margin: 0; font-size: 14.5px; color: var(--ink-2); line-height: 1.7; }
.hero-right { display: flex; align-items: center; gap: 30px; }
.hero-stat { text-align: center; }
.stat-num { font-size: 48px; font-weight: 800; color: var(--brand); line-height: 1; }
.stat-label { font-size: 13px; color: var(--ink-3); margin-top: 6px; }
.hero-illust { font-size: 72px; opacity: .85; }

/* ===== 统计卡片 ===== */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  flex-shrink: 0;
}
.quick { flex-shrink: 0; }
.stat-card {
  display: flex; align-items: center; gap: 16px;
  padding: 20px 22px;
  cursor: pointer;
  transition: all .2s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--sh-card-hover);
}
.sc-icon {
  width: 52px; height: 52px; border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
  box-shadow: 0 6px 14px rgba(0,0,0,.12);
}
.sc-num { font-size: 28px; font-weight: 800; color: var(--ink-1); line-height: 1; }
.sc-label { font-size: 13px; color: var(--ink-3); margin-top: 6px; }

/* ===== 快速入口 ===== */
.section-title {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px;
}
.st-bar {
  width: 4px; height: 18px; border-radius: 3px;
  background: linear-gradient(180deg, var(--brand), var(--brand-3));
}
.section-title h3 { margin: 0; font-size: 17px; font-weight: 700; color: var(--ink-1); }
.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.quick-card {
  display: flex; flex-direction: column;
  padding: 22px 20px;
  cursor: pointer;
  transition: all .2s;
  align-items: flex-start;
}
.quick-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--sh-card-hover);
}
.qc-icon {
  width: 48px; height: 48px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 14px;
  box-shadow: 0 6px 14px rgba(0,0,0,.15);
}
.qc-label { font-size: 16px; font-weight: 700; color: var(--ink-1); }
.qc-desc { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; }

/* ===== 双栏 ===== */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  flex-shrink: 0;
}
.col-card { padding: 22px 24px; }
.card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.card-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink-1); }
.more-link { font-size: 13px; color: var(--brand); cursor: pointer; font-weight: 500; }
.more-link:hover { text-decoration: underline; }

.empty {
  display: flex; flex-direction: column; align-items: center;
  padding: 30px 20px;
  color: var(--ink-3); font-size: 13.5px;
}
.empty-icon { font-size: 36px; margin-bottom: 8px; }

/* DDL 列表 */
.ddl-list { display: flex; flex-direction: column; gap: 10px; }
.ddl-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  background: var(--brand-7);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,.6);
}
.ddl-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 0 3px rgba(0,0,0,.05); }
.ddl-main { flex: 1; min-width: 0; }
.ddl-title { font-weight: 600; color: var(--ink-1); font-size: 14px; }
.ddl-meta { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
.ddl-time { font-size: 12.5px; color: var(--ink-3); }

/* 右列 */
.right-col { display: flex; flex-direction: column; gap: 16px; }

/* 复习列表 */
.review-list { display: flex; flex-direction: column; gap: 14px; }
.review-item {
  padding: 14px 16px;
  background: var(--brand-7);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,.6);
}
.rv-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rv-course { font-weight: 700; color: var(--ink-1); font-size: 14px; }
.rv-days { font-size: 12.5px; font-weight: 600; color: var(--brand); }
.rv-days.urgent { color: #E85F77; }
.rv-bar {
  height: 8px; border-radius: 999px;
  background: rgba(168,123,197,.15);
  overflow: hidden;
}
.rv-bar-inner {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--brand-3), var(--brand));
  transition: width .6s ease;
}
.rv-bottom { display: flex; justify-content: space-between; margin-top: 6px; font-size: 12px; color: var(--ink-3); }
.rv-percent { font-weight: 700; color: var(--brand); }
.rv-today { margin-top: 10px; font-size: 12.5px; color: var(--ink-2); }
.rv-today-label { color: var(--brand); font-weight: 600; }
.rv-topics { color: var(--ink-2); }

/* 文件列表 */
.file-list { display: flex; flex-direction: column; gap: 8px; }
.file-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  transition: background .15s;
}
.file-item:hover { background: var(--brand-7); }
.file-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--brand-6); color: var(--brand);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.file-main { flex: 1; min-width: 0; }
.file-name { font-size: 13.5px; font-weight: 600; color: var(--ink-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.file-course { font-size: 12px; color: var(--ink-3); margin-top: 2px; }

/* 响应式 */
@media (max-width: 1100px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .quick-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .hero { flex-direction: column; align-items: flex-start; padding: 24px 20px; }
  .hero-right { width: 100%; justify-content: space-between; }
  .stat-num { font-size: 36px; }
  .hero-illust { display: none; }
}
</style>
