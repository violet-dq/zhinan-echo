<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const props = defineProps<{
  modelValue: boolean
  nickname: string
  avatar: string
  username: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'update:nickname', v: string): void
  (e: 'update:avatar', v: string): void
  (e: 'logout'): void
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => emit('update:modelValue', v))

const nick = ref(props.nickname)
const avatar = ref(props.avatar)
const email = ref('')
const loading = ref(false)

// 密码
const showPw = ref(false)
const pwForm = ref({ old_password: '', new_password: '', confirm: '' })
const pwLoading = ref(false)

watch(() => props.nickname, (v) => { nick.value = v })
watch(() => props.avatar, (v) => { avatar.value = v })

async function onOpen() {
  try {
    const p = await api.profile()
    nick.value = p.nickname || p.username
    avatar.value = p.avatar || ''
    email.value = p.email || ''
  } catch { /* ignore */ }
}
watch(visible, (v) => { if (v) onOpen() })

function pickAvatar() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = () => {
    const f = input.files?.[0]
    if (!f) return
    if (f.size > 500 * 1024) {
      ElMessage.warning('头像请小于 500KB')
      return
    }
    const reader = new FileReader()
    reader.onload = () => { avatar.value = reader.result as string }
    reader.readAsDataURL(f)
  }
  input.click()
}

async function saveProfile() {
  loading.value = true
  try {
    const res = await api.updateProfile({
      nickname: nick.value,
      email: email.value,
      avatar: avatar.value,
    })
    emit('update:nickname', res.nickname || nick.value)
    emit('update:avatar', res.avatar || avatar.value)
    ElMessage.success('资料已更新')
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function changePassword() {
  if (!pwForm.value.old_password || !pwForm.value.new_password) {
    ElMessage.warning('请填写原密码和新密码'); return
  }
  if (pwForm.value.new_password !== pwForm.value.confirm) {
    ElMessage.error('两次输入的新密码不一致'); return
  }
  if (pwForm.value.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位'); return
  }
  pwLoading.value = true
  try {
    await api.changePassword(pwForm.value.old_password, pwForm.value.new_password)
    ElMessage.success('密码修改成功')
    pwForm.value = { old_password: '', new_password: '', confirm: '' }
    showPw.value = false
  } finally {
    pwLoading.value = false
  }
}

function doLogout() {
  visible.value = false
  emit('logout')
}
</script>

<template>
  <el-dialog v-model="visible" title="个人信息" width="440px" :close-on-click-modal="false">
    <div class="profile-wrap">
      <!-- 头像 -->
      <div class="avatar-section" @click="pickAvatar">
        <div class="avatar-circle">
          <img v-if="avatar" :src="avatar" alt="头像" />
          <span v-else>{{ (nick || 'U')[0] }}</span>
        </div>
        <div class="avatar-hint">点击更换头像</div>
      </div>

      <!-- 基本信息 -->
      <div class="form-row">
        <label>用户名</label>
        <el-input :model-value="props.username" disabled />
      </div>
      <div class="form-row">
        <label>昵称</label>
        <el-input v-model="nick" placeholder="请输入昵称" maxlength="32" />
      </div>
      <div class="form-row">
        <label>邮箱</label>
        <el-input v-model="email" placeholder="选填" />
      </div>

      <el-button
        type="primary"
        :loading="loading"
        @click="saveProfile"
        round
        style="width:100%;margin-top:8px"
      >
        保存资料
      </el-button>

      <el-divider />

      <!-- 改密码 -->
      <div class="pw-toggle" @click="showPw = !showPw">
        <span>修改密码</span>
        <el-icon :size="16" :style="{ transform: showPw ? 'rotate(180deg)' : '' }">
          <ArrowDown />
        </el-icon>
      </div>
      <div v-if="showPw" class="pw-form">
        <div class="form-row">
          <label>原密码</label>
          <el-input v-model="pwForm.old_password" type="password" show-password />
        </div>
        <div class="form-row">
          <label>新密码</label>
          <el-input v-model="pwForm.new_password" type="password" show-password />
        </div>
        <div class="form-row">
          <label>确认新密码</label>
          <el-input v-model="pwForm.confirm" type="password" show-password />
        </div>
        <el-button
          type="primary"
          :loading="pwLoading"
          @click="changePassword"
          round
          style="width:100%"
        >
          确认修改
        </el-button>
      </div>

      <el-divider />

      <el-button type="danger" plain round style="width:100%" @click="doLogout">
        <el-icon><SwitchButton /></el-icon> 退出登录
      </el-button>
    </div>
  </el-dialog>
</template>

<style scoped>
.profile-wrap { padding: 4px 4px 0; }
.avatar-section {
  text-align: center;
  margin-bottom: 20px;
  cursor: pointer;
}
.avatar-circle {
  width: 80px; height: 80px;
  border-radius: 50%;
  margin: 0 auto 8px;
  background: linear-gradient(135deg, var(--brand-4), var(--brand));
  color: #fff;
  font-size: 32px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
  box-shadow: var(--sh-btn);
  border: 3px solid #fff;
}
.avatar-circle img { width: 100%; height: 100%; object-fit: cover; }
.avatar-hint { font-size: 12px; color: var(--ink-3); }

.form-row { margin-bottom: 14px; }
.form-row label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 6px;
}
.pw-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 8px 0;
  color: var(--ink-1);
  font-weight: 600;
}
.pw-form {
  padding-top: 8px;
  animation: slide .2s ease;
}
@keyframes slide {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
