<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, clearToken } from '../api'
import ChatPanel from '../components/ChatPanel.vue'
import LibraryView from '../components/LibraryView.vue'
import DdlBoard from '../components/DdlBoard.vue'
import ReviewView from '../components/ReviewView.vue'
import DashboardView from '../components/DashboardView.vue'
import SettingsView from '../components/SettingsView.vue'
import UserProfile from '../components/UserProfile.vue'
import EchoLogo from '../components/EchoLogo.vue'

const emit = defineEmits<{ (e: 'logout'): void }>()
const view = ref<'dashboard' | 'chat' | 'library' | 'ddl' | 'review' | 'settings'>('dashboard')
const nickname = ref(localStorage.getItem('echo_nickname') || '同学')
const avatar = ref('')
const username = ref('')
const llmEnabled = ref(false)
const notis = ref<any[]>([])
const unread = ref(0)
const showNotis = ref(false)
const showProfile = ref(false)

const menu = [
  { key: 'dashboard', label: '主页', icon: 'HomeFilled' },
  { key: 'chat', label: '对话助教', icon: 'ChatDotRound' },
  { key: 'library', label: '资料索引', icon: 'Collection' },
  { key: 'ddl', label: 'DDL看板', icon: 'AlarmClock' },
  { key: 'review', label: '复习计划', icon: 'Notebook' },
  { key: 'settings', label: '系统设置', icon: 'Setting' },
]
let timer: any = null

async function pollNotis() {
  try {
    const d = await api.notifications()
    notis.value = d.items
    unread.value = d.unread
  } catch { /* 静默 */ }
}
async function openNotis() {
  showNotis.value = true
  if (unread.value) {
    await api.readNotifications().catch(() => {})
    unread.value = 0
  }
}
function switchView(k: any) {
  view.value = k
}

onMounted(async () => {
  pollNotis()
  timer = setInterval(pollNotis, 30000)
  try {
    const me = await api.get('/api/auth/me')
    nickname.value = me.nickname || me.username
    username.value = me.username
    avatar.value = me.avatar || ''
    llmEnabled.value = me.llm_enabled
    localStorage.setItem('echo_nickname', nickname.value)
  } catch { /* ignore */ }
  // 加载并应用用户主题/字体设置
  try {
    const s = await api.userSettings()
    document.body.setAttribute('data-theme', s.theme || 'echo')
  } catch { /* ignore */ }
})
onUnmounted(() => clearInterval(timer))

function logout() {
  clearToken()
  localStorage.removeItem('echo_nickname')
  emit('logout')
}
</script>

<template>
  <div class="layout">
    <!-- ========== 左侧：深紫渐变侧边栏 ========== -->
    <aside class="sidebar">
      <div class="side-brand">
        <div class="logo-square">
          <EchoLogo :size="30" />
        </div>
        <div class="brand-text">
          <div class="name">知南</div>
        </div>
      </div>

      <nav class="side-menu">
        <div
          v-for="m in menu"
          :key="m.key"
          class="menu-item"
          :class="{ active: view === m.key, disabled: m.disabled }"
          @click="switchView(m.key)"
        >
          <el-icon :size="18"><component :is="m.icon" /></el-icon>
          <span class="menu-label">{{ m.label }}</span>
          <div class="active-bar" v-if="view === m.key"></div>
        </div>
      </nav>

      <div class="side-footer">
        <div class="mode-tag" :class="llmEnabled ? 'llm' : 'local'">
          <span class="mode-dot"></span>
          {{ llmEnabled ? 'LLM 已接入' : '本地规则模式' }}
        </div>
        <div class="user-row" @click="showProfile = true">
          <div class="avatar-wrap">
            <div class="avatar">
              <img v-if="avatar" :src="avatar" alt="头像" />
              <span v-else>{{ nickname[0] }}</span>
            </div>
          </div>
          <div class="user-info">
            <div class="nick">{{ nickname }}</div>
            <div class="user-tag">同学</div>
          </div>
          <div class="logout-btn" title="退出登录" @click.stop="logout">
            <el-icon :size="16"><SwitchButton /></el-icon>
          </div>
        </div>
      </div>
    </aside>

    <!-- ========== 主内容区 ========== -->
    <main class="main">
      <div class="content">
        <DashboardView v-if="view === 'dashboard'" @jump="switchView" />
        <ChatPanel v-show="view === 'chat'" @jump="switchView" />
        <LibraryView v-if="view === 'library'" />
        <DdlBoard v-if="view === 'ddl'" />
        <ReviewView v-if="view === 'review'" />
        <SettingsView v-if="view === 'settings'" @logout="logout" />
      </div>
    </main>

    <!-- ========== 移动端底部 Tab ========== -->
    <nav class="mobile-tabs">
      <div
        v-for="m in menu.filter(x => !x.disabled)"
        :key="m.key"
        class="mtab"
        :class="{ active: view === m.key }"
        @click="switchView(m.key)"
      >
        <el-icon :size="20"><component :is="m.icon" /></el-icon>
        <span>{{ m.label }}</span>
      </div>
    </nav>

    <!-- ========== 通知抽屉 ========== -->
    <el-drawer v-model="showNotis" title="🔔 主动提醒" size="400px" :destroy-on-close="true">
      <div v-if="!notis.length" class="empty-noti">
        <div class="empty-icon">🍃</div>
        <div class="empty-text">暂无提醒，安心学习</div>
      </div>
      <div v-for="n in notis" :key="n.id" class="noti-item">
        <div class="noti-title" :class="n.level">{{ n.title }}</div>
        <div class="noti-body">{{ n.body }}</div>
        <div class="noti-time">{{ (n.created_at || '').replace('T', ' ').slice(0, 16) }}</div>
      </div>
    </el-drawer>

    <!-- ========== 浮动：通知入口（内容区右上角） ========== -->
    <div class="noti-float" @click="openNotis">
      <el-badge :value="unread" :hidden="!unread" :max="99" class="noti-badge">
        <div class="noti-btn">
          <el-icon :size="20"><Bell /></el-icon>
        </div>
      </el-badge>
    </div>

    <!-- ========== 用户信息弹窗 ========== -->
    <UserProfile
      v-model="showProfile"
      v-model:nickname="nickname"
      v-model:avatar="avatar"
      :username="username"
      @logout="logout"
    />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
  padding: 18px;
  gap: 18px;
  position: relative;
  overflow: hidden;
}

/* ============ 侧边栏：主题渐变 + 大圆角卡片感 ============ */
.sidebar {
  width: 236px;
  display: flex; flex-direction: column;
  padding: 22px 14px 18px;
  background: var(--sb-bg);
  border-radius: 28px;
  box-shadow: var(--sb-shadow);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}
.sidebar::after {
  /* 顶部光晕装饰 */
  content: '';
  position: absolute; top: -80px; right: -60px;
  width: 240px; height: 240px; border-radius: 50%;
  background: var(--sb-glow);
  pointer-events: none;
}

.side-brand {
  display: flex; align-items: center; gap: 12px;
  padding: 4px 8px 26px;
  position: relative; z-index: 1;
}
.logo-square {
  width: 42px; height: 42px; border-radius: 13px;
  background: var(--sb-logo-bg);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(0,0,0,.28),
              0 1px 0 rgba(255,255,255,.2) inset;
}
.brand-text .name {
  font-weight: 800; color: var(--sb-text); font-size: 22px; letter-spacing: 2px;
}

/* 菜单 */
.side-menu {
  flex: 1;
  display: flex; flex-direction: column; gap: 4px;
  position: relative; z-index: 1;
  padding-top: 4px;
}
.menu-item {
  position: relative;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  cursor: pointer;
  color: var(--sb-text-muted);
  font-size: 14.5px; font-weight: 500;
  transition: all .22s ease;
}
.menu-item:hover {
  background: var(--sb-hover-bg);
  color: var(--sb-text);
}
.menu-item.active {
  background: var(--sb-active-bg);
  color: var(--sb-text);
  font-weight: 600;
  box-shadow: 0 2px 0 rgba(255,255,255,.1) inset,
              0 8px 20px rgba(0,0,0,.18);
}
.menu-item.disabled {
  opacity: .45; cursor: not-allowed; pointer-events: none;
}
.active-bar {
  position: absolute; left: -14px; top: 50%; transform: translateY(-50%);
  width: 4px; height: 22px; border-radius: 0 3px 3px 0;
  background: var(--sb-bar);
}
.menu-label { flex: 1; }

/* 底栏 */
.side-footer {
  border-top: 1px solid var(--sb-footer-border);
  padding-top: 14px;
  position: relative; z-index: 1;
}
.mode-tag {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px;
  font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
}
.mode-tag.local { background: var(--sb-hover-bg); color: var(--sb-text-muted); border: 1px solid var(--sb-footer-border); }
.mode-tag.llm   { background: rgba(144,238,144,.18); color: #9BE79B; border: 1px solid rgba(144,238,144,.28); }
.mode-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}
.user-row {
  display: flex; align-items: center; gap: 10px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 18px;
  background: var(--sb-user-bg);
  transition: background .15s;
  cursor: pointer;
}
.user-row:hover { background: var(--sb-hover-bg); }
.avatar-wrap { flex-shrink: 0; }
.avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--sb-avatar-bg);
  color: #fff; font-weight: 700; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.2);
  overflow: hidden;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar span { line-height: 1; }
.user-info { flex: 1; min-width: 0; }
.nick { color: var(--sb-text); font-size: 13.5px; font-weight: 600; }
.user-tag { color: var(--sb-text-dim); font-size: 11.5px; margin-top: 2px; }
.logout-btn {
  width: 32px; height: 32px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: var(--sb-text-dim); cursor: pointer;
  transition: all .15s;
}
.logout-btn:hover { background: rgba(255,100,120,.15); color: #FF8FA1; }

/* ============ 主区 ============ */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  /* 内容不铺满屏幕，与参考图一致留边呼吸感（外层已有 padding） */
}
.placeholder {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: rgba(255,255,255,.88);
  border-radius: 28px;
  color: var(--ink-2);
}
.placeholder h3 { color: var(--brand); margin: 0 0 6px; }

/* ============ 浮动通知入口（默认右侧隐藏，hover 弹出） ============ */
.noti-float {
  position: absolute; top: 32px; right: -30px;
  z-index: 20;
  transition: right .3s cubic-bezier(.4,0,.2,1);
}
.noti-float:hover {
  right: 20px;
}
.noti-btn {
  width: 46px; height: 46px; border-radius: 50%;
  background: rgba(255,255,255,.9);
  backdrop-filter: blur(14px);
  border: 1px solid var(--brand-5);
  color: var(--brand);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(123,75,154,.14);
  transition: all .15s;
}
.noti-float:hover .noti-btn {
  background: #fff;
  box-shadow: 0 10px 22px rgba(123,75,154,.2);
}
.noti-badge :deep(.el-badge__content) {
  top: 4px; right: 4px;
  font-size: 11px; min-width: 16px; height: 16px; padding: 0 4px;
}

/* ============ 通知抽屉 ============ */
.empty-noti {
  display: flex; flex-direction: column; align-items: center;
  padding: 60px 20px;
  color: var(--ink-3);
}
.empty-icon { font-size: 44px; margin-bottom: 10px; }
.empty-text { font-size: 14px; }

.noti-item {
  padding: 16px 18px; margin-bottom: 12px;
  background: #fff;
  border: 1px solid var(--brand-5);
  border-radius: 20px;
  box-shadow: 0 4px 14px rgba(123,75,154,.06);
  border-left: 4px solid var(--brand-3);
}
.noti-title { font-weight: 700; color: var(--ink-1); font-size: 14.5px; margin-bottom: 4px; }
.noti-title.urgent { color: #E85F77; border-left-color: #E85F77; }
.noti-title.warning { color: #E6A23C; }
.noti-body { font-size: 13px; color: var(--ink-2); line-height: 1.6; }
.noti-time { font-size: 11.5px; color: var(--ink-3); margin-top: 8px; }

/* ============ 移动端 Tab ============ */
.mobile-tabs {
  display: none;
  position: fixed; left: 12px; right: 12px; bottom: 10px;
  z-index: 100;
  background: rgba(255,255,255,.94);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255,255,255,.9);
  border-radius: 26px;
  padding: 8px 4px calc(8px + env(safe-area-inset-bottom));
  justify-content: space-around;
  box-shadow: 0 10px 32px rgba(123,75,154,.18);
}
.mtab {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  font-size: 11px; color: var(--ink-3); cursor: pointer;
  padding: 6px 12px;
  border-radius: 16px; transition: all .15s;
}
.mtab.active {
  color: var(--brand); font-weight: 700;
  background: var(--brand-6);
}

@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-tabs { display: flex; }
  .layout { padding: 10px 10px calc(90px + env(safe-area-inset-bottom)); gap: 0; }
  .noti-float { top: 16px; right: -30px; }
  .noti-float:hover { right: 10px; }
}
</style>
