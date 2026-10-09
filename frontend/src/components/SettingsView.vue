<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const emit = defineEmits<{ (e: 'logout'): void }>()

const active = ref('appearance')
const loading = ref(false)
const saving = ref(false)

// 设置表单
const form = ref({
  theme: 'echo',
  download_path: '',
  notify_ddl: true,
  notify_sound: true,
  llm_api_base: '',
  llm_api_key: '',
  llm_model: '',
  llm_api_key_set: false,
})

// 密码表单
const pwForm = ref({ old_password: '', new_password: '', confirm: '' })
const pwLoading = ref(false)

const themes = [
  { key: 'echo', label: '二月兰', desc: '默认紫色', color: 'linear-gradient(135deg,#7B4B9A,#C9A8E0)' },
  { key: 'light', label: '纯净白', desc: '简洁白底', color: 'linear-gradient(135deg,#F9FAFB,#D1D5DB)' },
  { key: 'dark', label: '深邃黑', desc: '暗色护眼', color: 'linear-gradient(135deg,#1A1226,#4A3066)' },
  { key: 'summer', label: '夏季暖阳', desc: '暖橙黄', color: 'linear-gradient(135deg,#E8743B,#FCE6C4)' },
  { key: 'winter', label: '冬季雪花', desc: '冰蓝白', color: 'linear-gradient(135deg,#3A7CA5,#D4E7F2)' },
]

// 立即应用主题（预览）
function applyTheme() {
  document.body.setAttribute('data-theme', form.value.theme)
}
watch(() => form.value.theme, applyTheme)

onMounted(async () => {
  try {
    const s = await api.userSettings()
    Object.assign(form.value, s)
    applyTheme()
  } catch { /* ignore */ }
})

// 选择下载文件夹：优先用 File System Access API，降级用 webkitdirectory input
async function pickFolder() {
  // 方案 1：Chromium 浏览器的 showDirectoryPicker
  if ((window as any).showDirectoryPicker) {
    try {
      const handle = await (window as any).showDirectoryPicker()
      form.value.download_path = handle.name
      return
    } catch { /* 用户取消 */ }
  }
  // 方案 2：input[webkitdirectory] 降级
  const input = document.createElement('input')
  input.type = 'file'
  input.setAttribute('webkitdirectory', '')
  input.onchange = () => {
    const f = input.files?.[0]
    if (f) {
      // webkitRelativePath 形如 "文件夹名/..."，取第一段
      const rel = (f as any).webkitRelativePath || f.name
      form.value.download_path = rel.split('/')[0] || rel
    }
  }
  input.click()
}

async function save() {
  saving.value = true
  try {
    // API key：若已设置且输入框为空，不覆盖；若输入了新值则更新
    const payload: any = {
      theme: form.value.theme,
      download_path: form.value.download_path,
      notify_ddl: form.value.notify_ddl,
      notify_sound: form.value.notify_sound,
      llm_api_base: form.value.llm_api_base,
      llm_model: form.value.llm_model,
    }
    if (form.value.llm_api_key) {
      payload.llm_api_key = form.value.llm_api_key
    }
    const res = await api.updateUserSettings(payload)
    if (res.settings) {
      form.value.llm_api_key_set = res.settings.llm_api_key_set
      form.value.llm_api_key = ''
    }
    ElMessage.success('设置已保存')
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  if (!pwForm.value.old_password || !pwForm.value.new_password) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (pwForm.value.new_password !== pwForm.value.confirm) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }
  if (pwForm.value.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  pwLoading.value = true
  try {
    await api.changePassword(pwForm.value.old_password, pwForm.value.new_password)
    ElMessage.success('密码修改成功')
    pwForm.value = { old_password: '', new_password: '', confirm: '' }
  } finally {
    pwLoading.value = false
  }
}

const tabs = [
  { key: 'appearance', label: '外观', icon: 'Brush' },
  { key: 'download', label: '下载', icon: 'Download' },
  { key: 'notify', label: '通知', icon: 'Bell' },
  { key: 'ai', label: '智能', icon: 'Cpu' },
  { key: 'security', label: '安全', icon: 'Lock' },
]
</script>

<template>
  <div class="settings-page">
    <div class="settings-header">
      <h2>系统设置</h2>
      <p>个性化你的知南·Echo 体验</p>
    </div>

    <div class="settings-body">
      <!-- 左侧 Tab -->
      <nav class="settings-tabs">
        <div
          v-for="t in tabs"
          :key="t.key"
          class="stab"
          :class="{ active: active === t.key }"
          @click="active = t.key"
        >
          <el-icon :size="18"><component :is="t.icon" /></el-icon>
          <span>{{ t.label }}</span>
        </div>
      </nav>

      <!-- 右侧内容 -->
      <div class="settings-content">
        <!-- 外观 -->
        <div v-if="active === 'appearance'" class="panel">
          <div class="section">
            <div class="sec-title">皮肤主题</div>
            <div class="theme-grid">
              <div
                v-for="th in themes"
                :key="th.key"
                class="theme-card"
                :class="{ active: form.theme === th.key }"
                @click="form.theme = th.key"
              >
                <div class="theme-preview" :style="{ background: th.color }"></div>
                <div class="theme-label">{{ th.label }}</div>
                <div class="theme-desc">{{ th.desc }}</div>
                <div v-if="form.theme === th.key" class="theme-check">
                  <el-icon><Check /></el-icon>
                </div>
              </div>
            </div>
          </div>

        </div>

        <!-- 下载 -->
        <div v-if="active === 'download'" class="panel">
          <div class="section">
            <div class="sec-title">下载路径</div>
            <p class="sec-desc">选择文件下载时的默认保存文件夹。</p>
            <div class="folder-picker">
              <div class="folder-display" @click="pickFolder">
                <el-icon :size="18"><FolderOpened /></el-icon>
                <span v-if="form.download_path" class="folder-path">{{ form.download_path }}</span>
                <span v-else class="folder-placeholder">点击选择文件夹</span>
              </div>
              <el-button v-if="form.download_path" text type="primary" @click="form.download_path = ''">
                <el-icon><Close /></el-icon> 清除
              </el-button>
            </div>
          </div>
        </div>

        <!-- 通知 -->
        <div v-if="active === 'notify'" class="panel">
          <div class="section">
            <div class="switch-row">
              <div>
                <div class="sec-title" style="margin-bottom:0">DDL 主动提醒</div>
                <p class="sec-desc">在截止日前 7 天 / 3 天 / 1 天 / 1 小时推送提醒</p>
              </div>
              <el-switch v-model="form.notify_ddl" />
            </div>
          </div>
          <div class="section">
            <div class="switch-row">
              <div>
                <div class="sec-title" style="margin-bottom:0">通知声音</div>
                <p class="sec-desc">收到新提醒时播放提示音</p>
              </div>
              <el-switch v-model="form.notify_sound" />
            </div>
          </div>
        </div>

        <!-- 智能（LLM API） -->
        <div v-if="active === 'ai'" class="panel">
          <div class="section">
            <div class="sec-title">LLM API 配置</div>
            <p class="sec-desc">自定义大模型接口，留空则使用系统默认配置。</p>

            <div class="form-row">
              <label>API Base URL</label>
              <el-input
                v-model="form.llm_api_base"
                placeholder="https://api.deepseek.com/v1"
                clearable
              />
            </div>

            <div class="form-row">
              <label>API Key</label>
              <el-input
                v-model="form.llm_api_key"
                :placeholder="form.llm_api_key_set ? '已设置，留空则不修改' : '请输入 API Key'"
                type="password"
                show-password
                clearable
              />
              <div v-if="form.llm_api_key_set" class="hint">当前已配置自定义 Key</div>
            </div>

            <div class="form-row">
              <label>模型名称</label>
              <el-input
                v-model="form.llm_model"
                placeholder="deepseek-chat"
                clearable
              />
            </div>
          </div>
        </div>

        <!-- 安全 -->
        <div v-if="active === 'security'" class="panel">
          <div class="section">
            <div class="sec-title">修改密码</div>
            <div class="form-row">
              <label>原密码</label>
              <el-input v-model="pwForm.old_password" type="password" show-password placeholder="请输入原密码" />
            </div>
            <div class="form-row">
              <label>新密码</label>
              <el-input v-model="pwForm.new_password" type="password" show-password placeholder="至少 6 位" />
            </div>
            <div class="form-row">
              <label>确认新密码</label>
              <el-input v-model="pwForm.confirm" type="password" show-password placeholder="再次输入新密码" />
            </div>
            <el-button type="primary" :loading="pwLoading" @click="changePassword" round>
              确认修改
            </el-button>
          </div>
        </div>

        <!-- 保存按钮（除安全外都显示） -->
        <div v-if="active !== 'security'" class="save-bar">
          <el-button type="primary" :loading="saving" @click="save" round>
            <el-icon><Check /></el-icon> 保存设置
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255,255,255,.88);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255,255,255,.9);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-card);
  padding: 28px 32px;
  overflow: hidden;
}
.settings-header { margin-bottom: 24px; }
.settings-header h2 {
  margin: 0 0 4px;
  color: var(--ink-1);
  font-size: 22px;
  font-weight: 800;
}
.settings-header p { margin: 0; color: var(--ink-3); font-size: 13px; }

.settings-body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 24px;
  overflow: hidden;
}

/* Tabs */
.settings-tabs {
  width: 120px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stab {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 14px;
  color: var(--ink-2);
  cursor: pointer;
  transition: all .2s;
  font-size: 14px;
  font-weight: 500;
}
.stab:hover { background: var(--brand-6); color: var(--brand); }
.stab.active {
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  box-shadow: var(--sh-btn);
}

/* Content */
.settings-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 8px;
}
.panel { padding-bottom: 20px; }
.section {
  padding: 20px 0;
  border-bottom: 1px solid var(--brand-5);
}
.section:last-child { border-bottom: none; }
.sec-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-1);
  margin-bottom: 12px;
}
.sec-desc {
  font-size: 12.5px;
  color: var(--ink-3);
  margin: 0 0 12px;
  line-height: 1.6;
}

/* Theme grid */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 14px;
}
.theme-card {
  position: relative;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255,255,255,.7);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all .2s;
  text-align: center;
}
.theme-card:hover { transform: translateY(-2px); }
.theme-card.active { border-color: var(--brand); box-shadow: var(--sh-btn); }
.theme-preview {
  width: 100%;
  height: 60px;
  border-radius: 12px;
  margin-bottom: 10px;
}
.theme-label { font-weight: 700; color: var(--ink-1); font-size: 14px; }
.theme-desc { font-size: 11.5px; color: var(--ink-3); margin-top: 2px; }
.theme-check {
  position: absolute; top: 8px; right: 8px;
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--brand); color: #fff;
  display: flex; align-items: center; justify-content: center;
}

/* Switch row */
.folder-picker {
  display: flex;
  align-items: center;
  gap: 12px;
}
.folder-display {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: var(--r-full);
  background: rgba(255,255,255,.95);
  border: 2px dashed var(--brand-4);
  cursor: pointer;
  transition: all .2s;
  color: var(--ink-1);
}
.folder-display:hover {
  border-color: var(--brand);
  background: #fff;
  box-shadow: var(--sh-btn);
}
.folder-path {
  font-size: 14px;
  font-weight: 600;
  color: var(--brand);
  word-break: break-all;
}
.folder-placeholder {
  font-size: 14px;
  color: var(--ink-3);
}

/* Switch row */
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

/* Form rows */
.form-row { margin-bottom: 16px; }
.form-row label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 6px;
}
.hint { font-size: 12px; color: var(--brand-3); margin-top: 6px; }

/* Save bar */
.save-bar {
  position: sticky;
  bottom: 0;
  padding-top: 16px;
  background: linear-gradient(180deg, transparent, rgba(255,255,255,.95) 40%);
}
body[data-theme="dark"] .save-bar {
  background: linear-gradient(180deg, transparent, rgba(26,18,38,.95) 40%);
}

@media (max-width: 768px) {
  .settings-page { padding: 18px; border-radius: 22px; }
  .settings-body { flex-direction: column; }
  .settings-tabs {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
  }
  .stab { flex-shrink: 0; }
  .theme-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
