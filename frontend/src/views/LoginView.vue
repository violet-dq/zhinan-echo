<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, setToken } from '../api'
import EchoLogo from '../components/EchoLogo.vue'

const emit = defineEmits<{ (e: 'authed'): void }>()
const isRegister = ref(false)
const loading = ref(false)
const form = reactive({ username: 'demo1', password: 'echo123456', nickname: '' })

async function submit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const data = isRegister.value
      ? await api.register(form.username, form.password, form.nickname || form.username)
      : await api.login(form.username, form.password)
    setToken(data.token)
    ElMessage.success(`${isRegister.value ? '注册' : '登录'}成功，欢迎回来`)
    emit('authed')
  } catch { /* api 层已提示 */ } finally { loading.value = false }
}

const fill = (u: string) => { form.username = u; form.password = 'echo123456' }

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div class="login-page">
    <!-- 顶部栏：Logo + 主导航 + 开始使用 -->
    <header class="top-nav">
      <div class="top-brand">
        <div class="logo-badge">
          <EchoLogo :size="30" />
        </div>
        <div class="brand-text">
          <span class="zhinan">知南</span>
          <span class="sub-name">学习管理智能体</span>
        </div>
      </div>
      <nav class="top-links">
        <span @click="scrollTo('intro-library')">资料整理</span>
        <span @click="scrollTo('intro-ddl')">DDL规划</span>
        <span @click="scrollTo('intro-review')">复习规划</span>
      </nav>
      <button class="btn-cta primary" @click="submit">开始使用</button>
    </header>

    <!-- 主体：左侧介绍 + 右侧登录卡片 -->
    <section class="hero">
      <div class="hero-left">
        <h1 class="hero-title">让复习不再从翻文件夹开始</h1>
        <p class="hero-sub">把本地资料变成可检索、可追踪、可复习的学习系统</p>
        <div class="hero-cta">
          <button class="btn-cta primary">挂载文件夹</button>
          <button class="btn-cta ghost">查看演示</button>
        </div>
        <div class="hero-tags">
          <span class="chip-tag">本地索引</span>
          <span class="chip-tag">自动标签</span>
          <span class="chip-tag">智能提醒</span>
        </div>
        <div class="hero-features">
          <div class="feat">
            <div class="feat-icon">📚</div>
            <div>
              <div class="feat-title">资料索引</div>
              <div class="feat-desc">扫描本地文件夹，建立课程目录</div>
            </div>
          </div>
          <div class="feat">
            <div class="feat-icon">📅</div>
            <div>
              <div class="feat-title">DDL 看板</div>
              <div class="feat-desc">自动识别通知，统一管理截止日期</div>
            </div>
          </div>
          <div class="feat">
            <div class="feat-icon">🔍</div>
            <div>
              <div class="feat-title">智能检索</div>
              <div class="feat-desc">用自然语言定位资料内容</div>
            </div>
          </div>
          <div class="feat">
            <div class="feat-icon">📈</div>
            <div>
              <div class="feat-title">复习规划</div>
              <div class="feat-desc">根据考试日期生成每日计划</div>
            </div>
          </div>
        </div>
      </div>

      <div class="hero-right">
        <div class="login-card surface-solid">
          <div class="card-head">
            <div class="logo-wrap">
              <EchoLogo :size="56" />
            </div>
            <h2 class="card-title">{{ isRegister ? '加入知南' : '欢迎回来' }}</h2>
            <p class="card-slogan">知南而行，必有回响</p>
          </div>

          <form class="login-form" @submit.prevent="submit">
            <label class="field">
              <span class="field-label">用户名</span>
              <input v-model="form.username" class="field-input" placeholder="请输入用户名" />
            </label>
            <label class="field">
              <span class="field-label">密码</span>
              <input v-model="form.password" type="password" class="field-input" placeholder="请输入密码"
                     @keyup.enter="submit" />
            </label>
            <label class="field" v-if="isRegister">
              <span class="field-label">昵称（可选）</span>
              <input v-model="form.nickname" class="field-input" placeholder="显示名，默认同用户名" />
            </label>

            <button type="submit" class="btn-cta primary submit-btn" :disabled="loading">
              <span v-if="!loading">{{ isRegister ? '注册并进入' : '立即登录' }}</span>
              <span v-else>正在进入…</span>
            </button>
          </form>

          <div class="switch-row">
            <span v-if="!isRegister">还没有账号？</span>
            <span v-else>已经有账号？</span>
            <a class="switch-link" @click="isRegister = !isRegister">
              {{ isRegister ? '去登录' : '注册一个' }}
            </a>
          </div>

          <div class="divider"><span>演示账号</span></div>

          <div class="demo-accounts">
            <button class="demo-chip" @click="fill('demo1')">
              <div class="demo-name">demo1</div>
              <div class="demo-desc">完整演示库</div>
            </button>
            <button class="demo-chip" @click="fill('demo2')">
              <div class="demo-name">demo2</div>
              <div class="demo-desc">计组课程</div>
            </button>
            <button class="demo-chip" @click="fill('demo3')">
              <div class="demo-name">demo3</div>
              <div class="demo-desc">空白新用户</div>
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 功能介绍区 ===== -->
    <section id="intro-library" class="intro-section">
      <div class="intro-body">
        <div class="intro-visual library-visual">
          <div class="visual-icon">📚</div>
        </div>
        <div class="intro-text">
          <div class="intro-tag">资料整理</div>
          <h2 class="intro-title">一键导入，智能归档</h2>
          <p class="intro-desc">将本地课件、笔记、论文拖拽上传，系统自动解析全文、智能分类到对应课程、生成关键词标签、建立语义向量索引，支持用自然语言精准检索内容。</p>
          <div class="intro-points">
            <div class="ip-item"><span class="ip-dot"></span>支持 PDF / Word / PPT / 图片 / Markdown</div>
            <div class="ip-item"><span class="ip-dot"></span>全文语义检索，不只是文件名匹配</div>
            <div class="ip-item"><span class="ip-dot"></span>自动课程分类与关键词提取</div>
            <div class="ip-item"><span class="ip-dot"></span>在线预览：PDF 用 pdf.js，Word 转 HTML</div>
          </div>
        </div>
      </div>
    </section>

    <section id="intro-ddl" class="intro-section">
      <div class="intro-body">
        <div class="intro-text">
          <div class="intro-tag">DDL 规划</div>
          <h2 class="intro-title">截止日期，一目了然</h2>
          <p class="intro-desc">对话中说出"下周三交作业"即可自动创建 DDL，支持 OCR 识别通知截图中的截止日期，按紧急程度排优先级矩阵，到期前智能提醒，可导出 .ics 同步到手机日历。</p>
          <div class="intro-points">
            <div class="ip-item"><span class="ip-dot"></span>自然语言添加："下周三交数据结构实验报告"</div>
            <div class="ip-item"><span class="ip-dot"></span>OCR 识别课程通知截图中的截止日期</div>
            <div class="ip-item"><span class="ip-dot"></span>四象限优先级矩阵，聚焦最紧急任务</div>
            <div class="ip-item"><span class="ip-dot"></span>导出 .ics 日历文件，手机同步提醒</div>
          </div>
        </div>
        <div class="intro-visual ddl-visual">
          <div class="visual-icon">📅</div>
        </div>
      </div>
    </section>

    <section id="intro-review" class="intro-section">
      <div class="intro-body">
        <div class="intro-visual review-visual">
          <div class="visual-icon">📈</div>
        </div>
        <div class="intro-text">
          <div class="intro-tag">复习规划</div>
          <h2 class="intro-title">考试倒计时，每日有计划</h2>
          <p class="intro-desc">输入考试日期，系统从资料中提取知识点构建知识树，按遗忘曲线和可用天数智能排期，生成每日复习任务清单，完成后自动调整进度，支持导出 Markdown 随时查看。</p>
          <div class="intro-points">
            <div class="ip-item"><span class="ip-dot"></span>自动提取知识点，构建知识树</div>
            <div class="ip-item"><span class="ip-dot"></span>按遗忘曲线智能排期，每日定量</div>
            <div class="ip-item"><span class="ip-dot"></span>勾选完成自动调整后续计划</div>
            <div class="ip-item"><span class="ip-dot"></span>导出 Markdown 或打印 PDF</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex; flex-direction: column;
  padding: 28px 56px 10px;
  overflow: auto;
}

/* ====== 顶部栏 ====== */
.top-nav {
  display: flex; align-items: center; gap: 24px;
  padding-bottom: 28px;
}
.top-brand { display: flex; align-items: center; gap: 12px; }
.logo-badge {
  width: 44px; height: 44px; border-radius: 14px;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 18px rgba(123,75,154,.32);
}
.brand-text { display: flex; align-items: baseline; gap: 10px; }
.zhinan { font-size: 24px; font-weight: 800; color: var(--ink-1); letter-spacing: 2px; }
.sub-name { font-size: 14px; color: var(--ink-2); letter-spacing: 1px; }
.top-links { flex: 1; display: flex; justify-content: center; gap: 48px; }
.top-links span {
  font-size: 15px; color: var(--ink-1); font-weight: 500; cursor: pointer;
  padding: 6px 4px; border-bottom: 2px solid transparent; transition: all .15s;
}
.top-links span:hover { color: var(--brand); border-bottom-color: var(--brand-3); }

/* ====== 主区 ====== */
.hero { flex: 1; display: grid; grid-template-columns: 1.1fr 1fr; gap: 48px; align-items: center; padding-bottom: 24px; }
.hero-left { padding-right: 10px; }
.hero-title {
  font-size: 46px; line-height: 1.18; font-weight: 800; color: var(--ink-1);
  margin: 0 0 18px; letter-spacing: 0.5px;
}
.hero-sub {
  font-size: 17px; line-height: 1.7; color: var(--ink-2); margin: 0 0 28px; max-width: 520px;
}
.hero-cta { display: flex; gap: 14px; margin-bottom: 22px; }
.hero-tags { display: flex; gap: 10px; margin-bottom: 42px; }
.chip-tag {
  display: inline-flex; align-items: center;
  height: 38px; padding: 0 20px; border-radius: var(--r-full);
  background: rgba(255,255,255,.88); border: 1px solid var(--brand-5);
  color: var(--brand); font-weight: 600; font-size: 14px; letter-spacing: 0.5px;
}

.hero-features {
  display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
  max-width: 540px;
}
.feat {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 20px 22px;
  background: rgba(255,255,255,.92);
  border: 1px solid var(--brand-5);
  border-radius: 22px;
  box-shadow: var(--sh-card);
}
.feat-icon { font-size: 22px; flex-shrink: 0; }
.feat-title { font-weight: 700; color: var(--ink-1); font-size: 15px; margin-bottom: 4px; }
.feat-title::before {
  content: ''; display: inline-block;
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--brand); margin-right: 8px; vertical-align: middle;
}
.feat-desc { font-size: 13px; color: var(--ink-2); line-height: 1.55; }

/* ====== 登录卡片 ====== */
.hero-right { display: flex; justify-content: center; }
.login-card {
  width: 430px;
  padding: 36px 38px 30px;
}
.card-head { text-align: center; margin-bottom: 28px; }
.logo-wrap {
  width: 84px; height: 84px; margin: 0 auto 16px;
  border-radius: 24px;
  background: linear-gradient(135deg, var(--brand-6), var(--brand-5));
  display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(255,255,255,.9);
  box-shadow: 0 8px 24px rgba(201,168,224,.32);
}
.card-title { margin: 0 0 4px; font-size: 24px; color: var(--ink-1); font-weight: 800; }
.card-slogan { margin: 0; font-size: 13px; color: var(--ink-3); letter-spacing: 1px; }

.login-form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; color: var(--ink-2); font-weight: 500; padding-left: 4px; }
.field-input {
  height: 50px; padding: 0 22px;
  border-radius: var(--r-full);
  border: 1.5px solid rgba(168,123,197,.22);
  background: rgba(255,255,255,.95);
  color: var(--ink-1);
  font-size: 14.5px; font-family: inherit;
  outline: none; transition: all .2s;
}
.field-input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(201,168,224,.38);
  background: #fff;
}
.field-input::placeholder { color: var(--ink-3); }

.submit-btn { width: 100%; margin-top: 6px; height: 54px; }
.submit-btn:disabled { opacity: .7; cursor: not-allowed; }

.switch-row { text-align: center; margin-top: 14px; font-size: 13px; color: var(--ink-2); }
.switch-link { color: var(--brand); font-weight: 600; cursor: pointer; margin-left: 4px; }
.switch-link:hover { text-decoration: underline; }

.divider {
  display: flex; align-items: center; margin: 22px 0 16px;
  font-size: 12px; color: var(--ink-3); letter-spacing: 2px;
}
.divider::before, .divider::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, var(--brand-5), transparent);
}
.divider span { padding: 0 14px; }

.demo-accounts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.demo-chip {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 12px 8px;
  background: var(--brand-6);
  border: 1.5px solid transparent;
  border-radius: 20px;
  cursor: pointer; transition: all .15s;
  font-family: inherit;
}
.demo-chip:hover {
  background: var(--brand-5);
  border-color: var(--brand-3);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(123,75,154,.16);
}
.demo-name { font-weight: 700; color: var(--brand); font-size: 14px; }
.demo-desc { font-size: 11.5px; color: var(--ink-2); margin-top: 2px; }

/* 响应式 */
@media (max-width: 1080px) {
  .hero { grid-template-columns: 1fr; gap: 30px; }
  .hero-left { padding-right: 0; }
  .hero-title { font-size: 36px; }
  .intro-body { grid-template-columns: 1fr !important; gap: 24px; }
  .intro-visual { justify-self: center; }
}
@media (max-width: 768px) {
  .login-page { padding: 20px 16px 30px; }
  .top-links { display: none; }
  .hero-features { grid-template-columns: 1fr; }
  .hero-title { font-size: 30px; }
  .login-card { width: 100%; padding: 28px 24px; }
  .hero-cta { flex-wrap: wrap; }
  .intro-section { padding: 40px 20px; }
  .intro-title { font-size: 24px; }
}

/* ===== 功能介绍区 ===== */
.intro-section {
  padding: 64px 56px;
  scroll-margin-top: 20px;
}
.intro-body {
  display: grid;
  grid-template-columns: 0.7fr 1fr;
  gap: 48px;
  align-items: center;
  max-width: 1100px;
  margin: 0 auto;
}
/* 奇偶交替布局：DDL 区文字在左 */
.intro-section:nth-child(even) .intro-body {
  grid-template-columns: 1fr 0.7fr;
}

.intro-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 260px;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(247,242,250,.9), rgba(232,213,240,.5));
  border: 1px solid var(--brand-5);
  box-shadow: var(--sh-card);
}
.library-visual { background: linear-gradient(135deg, rgba(201,168,224,.18), rgba(168,123,197,.08)); }
.ddl-visual { background: linear-gradient(135deg, rgba(255,179,193,.15), rgba(232,95,119,.06)); }
.review-visual { background: linear-gradient(135deg, rgba(168,230,207,.15), rgba(103,194,58,.06)); }

.visual-icon { font-size: 96px; filter: drop-shadow(0 8px 20px rgba(123,75,154,.2)); }

.intro-text { padding: 8px 0; }
.intro-tag {
  display: inline-block;
  padding: 4px 16px;
  border-radius: var(--r-full);
  background: var(--brand-6);
  color: var(--brand);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1px;
  margin-bottom: 14px;
}
.intro-title {
  margin: 0 0 16px;
  font-size: 30px;
  font-weight: 800;
  color: var(--ink-1);
  letter-spacing: 0.5px;
}
.intro-desc {
  margin: 0 0 24px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-2);
  max-width: 560px;
}
.intro-points { display: flex; flex-direction: column; gap: 12px; }
.ip-item {
  display: flex; align-items: center; gap: 12px;
  font-size: 14px; color: var(--ink-1); font-weight: 500;
}
.ip-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-3), var(--brand));
  box-shadow: 0 0 0 3px rgba(168,123,197,.15);
}
</style>
