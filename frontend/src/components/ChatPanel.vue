<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import MessageCards from './MessageCards.vue'
import EchoLogo from './EchoLogo.vue'

const emit = defineEmits<{ (e: 'jump', v: string): void }>()

interface Msg { role: string; content: string; cards: any[] }
const messages = ref<Msg[]>([])
const input = ref('')
const sending = ref(false)
const sessionId = ref<number | null>(null)
const sessions = ref<any[]>([])
const listEl = ref<HTMLElement>()
const dash = ref<any>({ today_ddl: [], week_ddl_count: 0, files_count: 0, reviews: [] })
const drawerOpen = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const currentTitle = computed(() => {
  if (!sessionId.value) return '新对话'
  const s = sessions.value.find(x => x.id === sessionId.value)
  return s?.title || '对话'
})

const WELCOME: Msg = {
  role: 'assistant',
  content: '你好呀，我是知南·Echo\n你的学习我可以帮上忙——记 DDL、查资料、做复习计划，直接用一句话告诉我就好。',
  cards: [],
}

const suggestions = [
  '下周有哪些DDL？',
  '帮我记一下：算法作业8月20号晚上10点截止',
  '二叉树有哪些遍历方式？',
  '我8月30号考数据结构，帮我生成复习计划',
]

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

function formatTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400 && d.getDate() === now.getDate()) return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  if (diff < 172800) return '昨天'
  return `${d.getMonth() + 1}/${d.getDate()}`
}

async function loadSessions() {
  try { sessions.value = await api.chatSessions() } catch { /* ignore */ }
}

async function openSession(s: any) {
  if (sending.value || s.id === sessionId.value) return
  sessionId.value = s.id
  try {
    const msgs = await api.chatMessages(s.id)
    messages.value = (msgs || []).map((m: any) => ({ role: m.role, content: m.content, cards: m.cards || [] }))
  } catch {
    messages.value = [{ ...WELCOME }]
  }
  scrollBottom()
}

function newSession() {
  if (sending.value) return
  sessionId.value = null
  messages.value = [{ ...WELCOME }]
}

async function send(text?: string) {
  const msg = (text ?? input.value).trim()
  if (!msg || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg, cards: [] })
  sending.value = true
  scrollBottom()
  try {
    const d = await api.chat(msg, sessionId.value)
    sessionId.value = d.session_id
    messages.value.push({ role: 'assistant', content: d.reply, cards: d.cards || [] })
    dash.value = await api.dashboard()
    loadSessions()
  } catch {
    messages.value.push({ role: 'assistant', content: '请求失败了 😥 请稍后再试一次。', cards: [] })
  } finally {
    sending.value = false
    scrollBottom()
  }
}

// ============ 直接上传文件（不走 AI，避免 DSML 工具调用标记泄露） ============
async function pickAndUpload() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const t = e.target as HTMLInputElement
  if (!t.files || !t.files.length) return
  const list = Array.from(t.files)
  t.value = ''
  uploading.value = true
  // 先在对话里插入一条「用户上传了 X 个文件」的轻量提示
  const names = list.map(f => f.name).join('、')
  messages.value.push({
    role: 'user', content: `上传文件：${names}`, cards: [],
  })
  scrollBottom()
  const form = new FormData()
  list.forEach(f => form.append('files', f))
  try {
    const d = await api.upload('/api/files/upload', form)
    const okFiles: any[] = []
    d.results.forEach((r: any) => {
      if (r.ok) okFiles.push(r.file)
      else ElMessage.error(`「${r.filename}」：${r.error}`)
    })
    if (okFiles.length) {
      ElMessage.success(`已入库 ${okFiles.length} 份资料 ✅`)
      messages.value.push({
        role: 'assistant',
        content: `已入库 ${okFiles.length} 份资料 📚 已自动解析全文、打标签、建立语义索引。`
          + `下面是这次上传的文件，可以预览或下载：`,
        cards: [{ type: 'files', data: { items: okFiles.map(f => ({
          id: f.id, filename: f.filename, course: f.course,
          file_type: f.file_type, chunks: f.chunk_count,
        })) } }],
      })
      dash.value = await api.dashboard()
    } else {
      messages.value.push({
        role: 'assistant',
        content: '这次没有文件成功入库 😥 可以换一份支持的格式（PDF/Word/PPT/TXT/Markdown/图片）再试。',
        cards: [],
      })
    }
  } catch {
    messages.value.push({
      role: 'assistant',
      content: '上传失败了 😥 请稍后再试，或改用「资料库」面板的拖拽上传。',
      cards: [],
    })
  } finally {
    uploading.value = false
    scrollBottom()
  }
}

// MessageCards 上传成功后回写一条 assistant 消息
function onCardsUploaded(files: any[]) {
  if (!files.length) return
  messages.value.push({
    role: 'assistant',
    content: `已入库 ${files.length} 份资料 📚 已自动解析全文、打标签、建立语义索引。`,
    cards: [{ type: 'files', data: { items: files.map(f => ({
      id: f.id, filename: f.filename, course: f.course,
      file_type: f.file_type, chunks: f.chunk_count,
    })) } }],
  })
  scrollBottom()
}

onMounted(async () => {
  messages.value = [{ ...WELCOME }]
  loadSessions()
  try { dash.value = await api.dashboard() } catch { /* ignore */ }
  scrollBottom()
})
</script>

<template>
  <div class="chat-wrap">

    <!-- ========== 会话工具条 ========== -->
    <div class="session-bar">
      <button class="sess-btn new" @click="newSession" :disabled="sending" title="开始新对话">
        <el-icon :size="16"><Plus /></el-icon>
        <span>新对话</span>
      </button>
      <div class="sess-title" :title="currentTitle">{{ currentTitle }}</div>
      <button class="sess-btn hist" @click="drawerOpen = true" title="历史会话">
        <el-icon :size="16"><Clock /></el-icon>
        <span>历史</span>
      </button>
    </div>

    <!-- ========== 历史会话抽屉 ========== -->
    <el-drawer v-model="drawerOpen" title="历史会话" direction="ltr" size="320px" :with-header="true">
      <div class="drawer-sessions">
        <div v-if="!sessions.length" class="empty-tip">还没有历史会话，发一条消息开始吧 🌿</div>
        <div v-for="s in sessions" :key="s.id"
             class="session-item" :class="{ active: s.id === sessionId }"
             @click="openSession(s); drawerOpen = false">
          <div class="s-icon"><el-icon :size="15"><ChatDotRound /></el-icon></div>
          <div class="s-main">
            <div class="s-title">{{ s.title || '未命名对话' }}</div>
            <div class="s-time">{{ formatTime(s.created_at || s.updated_at) }}</div>
          </div>
          <el-icon v-if="s.id === sessionId" class="s-check" :size="14"><Check /></el-icon>
        </div>
      </div>
    </el-drawer>

    <!-- ========== 快捷数据卡片（顶部） ========== -->
    <div class="stats-row">
      <!-- 今日DDL -->
      <div class="stat-card" @click="emit('jump', 'ddl')">
        <div class="stat-icon" :class="dash.today_ddl.length ? 'urgent' : ''">
          <el-icon :size="18"><List /></el-icon>
        </div>
        <div class="stat-main">
          <div class="stat-num">{{ dash.today_ddl.length }}</div>
          <div class="stat-label">今日DDL</div>
        </div>
        <div class="stat-sub">本周还有 {{ dash.week_ddl_count }} 项</div>
      </div>

      <!-- 复习进度 cards -->
      <div class="stat-card" v-for="r in dash.reviews.slice(0, 2)" :key="r.exam_id" @click="emit('jump', 'review')">
        <div class="stat-icon progress">
          <el-icon :size="18"><Medal /></el-icon>
        </div>
        <div class="stat-main">
          <div class="stat-num">{{ r.percent }}%</div>
          <div class="stat-label">{{ r.course_name }}</div>
        </div>
        <div class="stat-sub">{{ r.days_to_exam }} 天后考试</div>
      </div>

      <!-- 资料数 -->
      <div class="stat-card" @click="emit('jump', 'library')">
        <div class="stat-icon lib">
          <el-icon :size="18"><FolderOpened /></el-icon>
        </div>
        <div class="stat-main">
          <div class="stat-num">{{ dash.files_count }}</div>
          <div class="stat-label">近期资料</div>
        </div>
        <div class="stat-sub">随时问我内容</div>
      </div>
    </div>

    <!-- ========== 消息列表（大圆角卡片容器） ========== -->
    <div class="msg-list surface" ref="listEl">
      <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
        <div v-if="m.role === 'assistant'" class="avatar agent">
          <EchoLogo :size="26" />
        </div>
        <div class="bubble" :class="m.role">
          <div class="bubble-text">{{ m.content }}</div>
          <MessageCards v-if="m.cards?.length" :cards="m.cards"
                        @jump="emit('jump', $event)"
                        @uploaded="onCardsUploaded" />
        </div>
        <div v-if="m.role === 'user'" class="avatar user">{{ '我' }}</div>
      </div>

      <div v-if="sending || uploading" class="msg-row assistant">
        <div class="avatar agent"><EchoLogo :size="26" /></div>
        <div class="bubble agent typing">{{ uploading ? '正在上传并解析入库' : 'Echo 正在思考' }}
          <span class="dots"><i></i><i></i><i></i></span>
        </div>
      </div>
    </div>

    <!-- ========== 建议 chips ========== -->
    <div class="suggest-row" v-if="messages.length <= 2">
      <div
        v-for="s in suggestions"
        :key="s"
        class="suggest-chip"
        @click="send(s)"
      >
        <span class="q-dot">💡</span>
        <span class="q-text">{{ s }}</span>
      </div>
    </div>

    <!-- ========== 输入区：上传按钮 + 胶囊大输入框 + 圆按钮发送 ========== -->
    <div class="input-wrap">
      <div class="input-bar">
        <button class="upload-btn" :disabled="sending || uploading" @click="pickAndUpload" title="上传课件">
          <el-icon :size="20"><Upload /></el-icon>
          <span class="upload-label">上传课件</span>
        </button>
        <input ref="fileInput" type="file" multiple hidden
               accept=".pdf,.docx,.pptx,.txt,.md,.markdown,.jpg,.jpeg,.png,.gif,.webp"
               @change="onFileChange" />
        <input
          v-model="input"
          type="text"
          class="chat-input"
          placeholder="用一句话描述你想做的事"
          @keyup.enter="send()"
          :disabled="sending"
        />
        <button class="send-btn" :disabled="sending || uploading || !input.trim()" @click="send()">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path d="M5 12h12m0 0l-4-4m4 4l-4 4" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <p class="hint">支持：「帮我记 DDL / 查资料 / 生成复习计划」，点左侧上传课件 🌿</p>
    </div>
  </div>
</template>

<style scoped>
.chat-wrap {
  flex: 1;
  min-height: 0;
  display: flex; flex-direction: column;
  gap: 12px;
  padding: 8px 10px 4px;
}

/* ========== 会话工具条 ========== */
.session-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 0 4px;
  flex-shrink: 0;
}
.sess-btn {
  display: flex; align-items: center; gap: 5px;
  height: 34px; padding: 0 14px;
  border-radius: var(--r-full);
  font-size: 13px; font-weight: 600;
  cursor: pointer; flex-shrink: 0;
  font-family: inherit;
  transition: all .18s;
  border: none;
}
.sess-btn.new {
  background: var(--brand); color: #fff;
}
.sess-btn.new:hover:not(:disabled) {
  background: var(--brand-dark); transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(123,75,154,.24);
}
.sess-btn.new:disabled { opacity: .5; cursor: not-allowed; }
.sess-btn.hist {
  background: rgba(255,255,255,.7); color: var(--brand);
  border: 1px solid var(--brand-4);
}
.sess-btn.hist:hover {
  background: var(--brand-6); border-color: var(--brand-3);
}
.sess-title {
  flex: 1; min-width: 0;
  font-size: 14px; font-weight: 600; color: var(--ink-1);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  text-align: center;
  padding: 0 8px;
}

/* ========== 历史抽屉会话列表 ========== */
.drawer-sessions { padding: 4px 0; }
.empty-tip {
  text-align: center; color: var(--ink-3); font-size: 13px;
  padding: 40px 16px;
}
.session-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; cursor: pointer;
  border-radius: 10px; transition: all .16s;
  margin: 2px 8px;
}
.session-item:hover { background: var(--brand-6); }
.session-item.active { background: var(--brand-5); }
.s-icon { color: var(--brand); flex-shrink: 0; }
.session-item.active .s-icon { color: var(--brand-dark); }
.s-main { flex: 1; min-width: 0; }
.s-title {
  font-size: 13.5px; color: var(--ink-1); font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.s-time { font-size: 11.5px; color: var(--ink-3); margin-top: 2px; }
.s-check { color: var(--brand); flex-shrink: 0; }

/* ============ 顶部统计卡片 ============ */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  flex-shrink: 0;
}
.stat-card {
  position: relative;
  padding: 18px 18px 16px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255,255,255,.95);
  border-radius: 26px;
  box-shadow: 0 8px 26px rgba(123,75,154,.08);
  cursor: pointer;
  transition: all .22s ease;
  overflow: hidden;
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto auto;
  column-gap: 14px;
  row-gap: 4px;
  align-items: start;
}
.stat-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 5px;
  background: linear-gradient(180deg, var(--brand-3), var(--brand-5));
  border-radius: 6px 0 0 6px;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 34px rgba(123,75,154,.14);
  border-color: var(--brand-5);
}
.stat-icon {
  grid-row: 1 / span 3;
  grid-column: 1;
  width: 42px; height: 42px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  background: var(--brand-6);
  color: var(--brand);
}
.stat-icon.urgent {
  background: linear-gradient(135deg, #FFB3BE, #FF879A);
  color: #fff;
}
.stat-icon.progress {
  background: linear-gradient(135deg, #C9A8E0, #A87BC5);
  color: #fff;
}
.stat-icon.lib {
  background: linear-gradient(135deg, #FFE0B3, #FFC27A);
  color: #7A4A0A;
}

.stat-main { grid-column: 2; }
.stat-num {
  font-size: 28px; font-weight: 800;
  color: var(--ink-1); line-height: 1.1;
  letter-spacing: -0.5px;
}
.stat-icon.urgent ~ .stat-main .stat-num { color: #E85F77; }
.stat-label {
  font-size: 14px; color: var(--ink-2); font-weight: 600; margin-top: 4px;
}
.stat-sub {
  grid-column: 2;
  font-size: 12px; color: var(--ink-3);
}

/* ============ 消息列表 ============ */
.msg-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 26px;
  display: flex; flex-direction: column; gap: 18px;
}
.msg-row {
  display: flex; gap: 12px; align-items: flex-start;
}
.msg-row.user { justify-content: flex-end; }

.avatar {
  width: 36px; height: 36px; border-radius: 50%;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.avatar.agent {
  background: linear-gradient(135deg, #F7F2FA, #E8D5F0);
  border: 2px solid #fff;
  box-shadow: 0 4px 12px rgba(123,75,154,.15);
}
.avatar.user {
  background: linear-gradient(135deg, var(--brand-3), var(--brand));
  color: #fff; font-weight: 700; font-size: 14px;
  box-shadow: 0 4px 12px rgba(123,75,154,.3);
}

.bubble {
  max-width: 72%;
  padding: 14px 18px;
  font-size: 14.5px; line-height: 1.8;
  word-break: break-word;
  white-space: pre-wrap;
}
.bubble.user {
  background: linear-gradient(135deg, #E8D5F0 0%, #F3EAFA 100%);
  color: #3A2260;
  border: 1px solid rgba(201,168,224,.35);
  border-radius: 22px 22px 6px 22px;
  box-shadow: 0 4px 14px rgba(201,168,224,.25);
}
.bubble.agent {
  background: #fff;
  color: var(--ink-1);
  border: 1px solid var(--brand-5);
  border-radius: 22px 22px 22px 6px;
  box-shadow: 0 4px 14px rgba(123,75,154,.06);
}
.bubble.agent a { color: var(--brand); }

.typing { color: var(--ink-3); font-style: italic; }
.dots i {
  display: inline-block; width: 5px; height: 5px; margin-left: 3px;
  border-radius: 50%;
  background: var(--brand-3);
  animation: blink 1.2s infinite;
}
.dots i:nth-child(2) { animation-delay: .2s; }
.dots i:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%, 80%, 100% { opacity: .25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }

/* ============ 建议 chips ============ */
.suggest-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  flex-shrink: 0;
}
.suggest-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: rgba(255,255,255,.88);
  border: 1.5px solid var(--brand-5);
  border-radius: 22px;
  cursor: pointer;
  transition: all .18s;
  font-size: 14px;
  color: var(--ink-2);
}
.suggest-chip:hover {
  background: var(--brand-6);
  border-color: var(--brand-3);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(123,75,154,.1);
  color: var(--brand);
}
.q-dot { font-size: 16px; }
.q-text { line-height: 1.4; }

/* ============ 输入区 ============ */
.input-wrap {
  flex-shrink: 0;
  display: flex; flex-direction: column; gap: 6px;
  margin-bottom: 6px;
}
.input-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 7px 7px 10px;
  background: rgba(255,255,255,.96);
  border: 1.5px solid var(--brand-5);
  border-radius: var(--r-full);
  box-shadow: 0 8px 26px rgba(123,75,154,.10);
  backdrop-filter: blur(14px);
  transition: all .2s;
}
.input-bar:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(201,168,224,.4), 0 12px 30px rgba(123,75,154,.14);
}
.upload-btn {
  display: flex; align-items: center; gap: 6px;
  height: 40px; padding: 0 16px;
  border-radius: var(--r-full);
  background: var(--brand-6);
  border: 1px solid var(--brand-4);
  color: var(--brand);
  font-size: 13.5px; font-weight: 600;
  cursor: pointer; flex-shrink: 0;
  font-family: inherit;
  transition: all .18s;
}
.upload-btn:hover:not(:disabled) {
  background: var(--brand-5);
  border-color: var(--brand-3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(123,75,154,.16);
}
.upload-btn:disabled { opacity: .5; cursor: not-allowed; }
.upload-label { white-space: nowrap; }
.chat-input {
  flex: 1;
  height: 46px;
  border: none; background: transparent; outline: none;
  font-size: 15px; color: var(--ink-1);
  font-family: inherit;
  min-width: 0;
}
.chat-input::placeholder { color: var(--ink-3); }
.chat-input:disabled { opacity: .5; cursor: not-allowed; }

.send-btn {
  width: 52px; height: 52px; flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-2) 100%);
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 6px 18px rgba(123,75,154,.35);
  transition: all .18s;
}
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.03);
  box-shadow: 0 10px 24px rgba(123,75,154,.44);
}
.send-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.send-btn:disabled { opacity: .5; cursor: not-allowed; }

.hint {
  margin: 0; padding: 0 22px;
  font-size: 12px; color: var(--ink-3);
  letter-spacing: 0.2px;
}

/* 响应式 */
@media (max-width: 900px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .bubble { max-width: 86%; }
  .chat-wrap { padding: 4px; }
}
@media (max-width: 600px) {
  .msg-list { padding: 16px 12px; }
  .stat-num { font-size: 22px; }
  .upload-label { display: none; }
  .upload-btn { padding: 0 10px; }
  .sess-btn span { display: none; }
  .sess-btn { padding: 0 10px; }
}
</style>
