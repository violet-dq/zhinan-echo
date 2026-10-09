<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const props = defineProps<{ cards: any[] }>()
const emit = defineEmits<{ (e: 'jump', v: string): void; (e: 'uploaded', v: any[]): void }>()

const fmtDue = (iso: string) => (iso || '').replace('T', ' ').slice(5, 16)
const prioMap: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }

const typeIcon: Record<string, string> = {
  pdf: '📕', docx: '📘', pptx: '📗', txt: '📄', md: '📄',
  jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️',
}

// 预览支持的格式：PDF / 图片可浏览器原生渲染；其他用文本回退
function isPdf(t: string) { return (t || '').toLowerCase() === 'pdf' }
function isImage(t: string) {
  const x = (t || '').toLowerCase()
  return ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(x)
}

// ============ 内嵌上传组件（upload_guide 卡片） ============
const guideDrag = ref(false)
const guideUploading = ref(false)
const guideInput = ref<HTMLInputElement | null>(null)

async function guideUpload(list: FileList | File[]) {
  const arr = Array.from(list)
  if (!arr.length) return
  guideUploading.value = true
  const form = new FormData()
  arr.forEach(f => form.append('files', f))
  try {
    const d = await api.upload('/api/files/upload', form)
    const ok: any[] = []
    d.results.forEach((r: any) => {
      if (r.ok) { ok.push(r.file); ElMessage.success(`「${r.filename}」已入库 ✅`) }
      else ElMessage.error(`「${r.filename}」：${r.error}`)
    })
    if (ok.length) emit('uploaded', ok)
  } catch { /* api 层已提示 */ } finally {
    guideUploading.value = false
  }
}

function onGuideInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files) guideUpload(t.files)
  t.value = ''
}

function onGuideDrop(e: DragEvent) {
  guideDrag.value = false
  if (e.dataTransfer?.files) guideUpload(e.dataTransfer.files)
}

// 预览弹窗（共享）
const previewFile = ref<any>(null)
const showPreview = ref(false)
function openPreview(f: any) {
  previewFile.value = f
  showPreview.value = true
}
function closePreview() { showPreview.value = false }
</script>

<template>
  <div class="cards">
    <!-- DDL 列表卡片 -->
    <div v-for="(card, idx) in cards" :key="card.type + '-' + idx" class="card-inner">
      <template v-if="card.type === 'ddl_list' && card.data.items?.length">
        <div class="card-title" @click="emit('jump', 'ddl')">📋 待办清单 · 点击查看看板</div>
        <div v-for="it in card.data.items.slice(0, 8)" :key="it.id" class="row ddl-row">
          <el-tag :type="prioMap[it.priority] || 'info'" size="small" effect="dark">
            {{ it.days_left <= 1 ? '急' : it.priority === 'high' ? '高' : it.priority === 'low' ? '低' : '中' }}
          </el-tag>
          <span class="ddl-title">{{ it.title }}</span>
          <span class="ddl-due">⏰ {{ fmtDue(it.due_at) }}</span>
        </div>
      </template>

      <template v-else-if="card.type === 'ddl_added'">
        <div class="card-title ok">✅ 已加入看板</div>
        <div class="row">
          <span>{{ card.data.title }}</span>
          <span class="ddl-due">⏰ {{ fmtDue(card.data.due_at) }}</span>
        </div>
      </template>

      <template v-else-if="card.type === 'sources'">
        <div class="card-title" @click="emit('jump', 'library')">📖 引用来源 · 点击打开资料库</div>
        <div v-for="(s, i) in card.data.sources" :key="i" class="src-row">{{ s }}</div>
      </template>

      <!-- 文件列表卡片：新增预览+下载按钮 -->
      <template v-else-if="card.type === 'files'">
        <div class="card-title" @click="emit('jump', 'library')">📚 相关资料 · 点击打开资料库</div>
        <div v-for="f in card.data.items.slice(0, 6)" :key="f.id" class="file-line">
          <span class="f-icon-sm">{{ typeIcon[f.file_type || (f.filename||'').split('.').pop()?.toLowerCase()] || '📄' }}</span>
          <span class="ddl-title" :title="f.filename">{{ f.filename }}</span>
          <el-tag v-if="f.course" size="small" effect="plain" style="margin-left:auto">{{ f.course }}</el-tag>
          <button v-if="f.id" class="mini-btn" @click="openPreview({ id: f.id, filename: f.filename, file_type: (f.filename||'').split('.').pop() })" title="预览">👁️</button>
          <a v-if="f.id" class="mini-btn" :href="api.downloadUrl(f.id)" target="_blank" download title="下载">⬇️</a>
        </div>
      </template>

      <!-- 内嵌上传引导卡片：直接在对话里选/拖文件 -->
      <template v-else-if="card.type === 'upload_guide'">
        <div class="card-title">📤 上传资料到资料库</div>
        <div class="guide-zone" :class="{ drag: guideDrag }"
             @dragover.prevent="guideDrag = true"
             @dragleave="guideDrag = false"
             @drop.prevent="onGuideDrop"
             @click="guideInput?.click()">
          <div class="guide-icon">{{ guideUploading ? '⏳' : '📎' }}</div>
          <div class="guide-text">
            <b>{{ guideUploading ? '解析入库中…' : '点击选择 / 拖拽文件到这里' }}</b>
            <p>{{ card.data.tip }}</p>
          </div>
          <input ref="guideInput" type="file" multiple hidden
                 accept=".pdf,.docx,.pptx,.txt,.md,.markdown,.jpg,.jpeg,.png,.gif,.webp"
                 @change="onGuideInput" />
        </div>
        <div v-if="card.data.recent?.length" class="recent-row">
          <span class="recent-label">最近上传：</span>
          <span v-for="r in card.data.recent" :key="r.id" class="recent-chip"
                @click="openPreview({ id: r.id, filename: r.filename, file_type: (r.filename||'').split('.').pop() })">
            📄 {{ r.filename }}
          </span>
        </div>
      </template>

      <template v-else-if="card.type === 'review_plan'">
        <div class="card-title" @click="emit('jump', 'review')">📝 {{ card.data.course_name }} 复习计划 · 点击查看全部</div>
        <div class="row">
          <span>考试：{{ card.data.exam_date }}</span>
          <span style="margin-left:auto">
            进度 {{ card.data.progress?.done_points ?? 0 }}/{{ card.data.progress?.total_points ?? 0 }}
          </span>
        </div>
        <div class="days-preview">
          <span v-for="(d, i) in card.data.days.slice(0, 7)" :key="i" class="day-chip"
                :class="{ done: d.done, today: i === 0 }">
            {{ d.date }}
          </span>
        </div>
      </template>
    </div>
  </div>

  <!-- ============ 预览弹窗（共享） ============ -->
  <el-dialog v-model="showPreview" :title="previewFile?.filename" width="80%" top="6vh"
             @close="closePreview" class="preview-dialog">
    <div v-if="previewFile" class="preview-body">
      <!-- PDF：iframe 内嵌 -->
      <iframe v-if="isPdf(previewFile.file_type)"
              :src="api.previewUrl(previewFile.id)"
              class="preview-iframe" frameborder="0"></iframe>
      <!-- 图片 -->
      <img v-else-if="isImage(previewFile.file_type)"
           :src="api.previewUrl(previewFile.id)"
           class="preview-img" />
      <!-- 其他格式：提示下载或去资料库看全文 -->
      <div v-else class="preview-fallback">
        <div class="fb-icon">📄</div>
        <p>该格式不支持浏览器内嵌预览</p>
        <p class="fb-hint">可在「资料库」查看解析后的文本内容，或直接下载原文件</p>
        <a :href="api.downloadUrl(previewFile.id)" target="_blank" download class="fb-download">
          ⬇️ 下载原文件
        </a>
        <el-button type="primary" plain size="small" @click="emit('jump', 'library'); closePreview()">
          打开资料库查看
        </el-button>
      </div>
    </div>
    <template #footer>
      <a v-if="previewFile" :href="api.downloadUrl(previewFile.id)" target="_blank" download class="dl-link">
        <el-button type="primary">⬇️ 下载原文件</el-button>
      </a>
      <el-button @click="closePreview">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.cards { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.card-inner {
  background: rgba(255,255,255,.92); border-radius: 12px; padding: 10px 12px;
  border: 1px solid rgba(168,123,197,.35); color: #3d2b4f; font-size: 13px;
}
.card-title { font-weight: 700; color: var(--orchid-main); margin-bottom: 6px; cursor: pointer; }
.card-title.ok { color: #2e7d32; }
.row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.ddl-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ddl-due { margin-left: auto; color: #8a7599; font-size: 12px; flex-shrink: 0; }
.src-row { padding: 3px 0; color: #6a5580; font-size: 12px; }
.days-preview { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.day-chip {
  padding: 2px 8px; border-radius: 10px; background: var(--orchid-petal);
  color: var(--orchid-main); font-size: 11px;
}
.day-chip.today { outline: 2px solid var(--orchid-main); }
.day-chip.done { background: #d7eed9; color: #2e7d32; }

/* 文件行 */
.file-line {
  display: flex; align-items: center; gap: 8px; padding: 5px 0;
  border-bottom: 1px dashed rgba(168,123,197,.2);
}
.file-line:last-child { border-bottom: none; }
.f-icon-sm { font-size: 16px; flex-shrink: 0; }
.mini-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 8px;
  background: var(--brand-6); border: 1px solid var(--brand-5);
  cursor: pointer; font-size: 13px; text-decoration: none;
  color: var(--brand); transition: all .15s;
}
.mini-btn:hover { background: var(--brand-5); transform: translateY(-1px); }

/* 上传引导卡片 */
.guide-zone {
  display: flex; align-items: center; gap: 12px;
  padding: 16px; margin-top: 4px;
  border: 2px dashed var(--brand-3); border-radius: 14px;
  background: linear-gradient(135deg, rgba(247,242,250,.6), rgba(232,213,240,.3));
  cursor: pointer; transition: all .2s;
}
.guide-zone:hover, .guide-zone.drag {
  background: var(--brand-6); border-color: var(--brand);
  box-shadow: 0 4px 14px rgba(123,75,154,.14);
}
.guide-icon { font-size: 26px; }
.guide-text b { color: var(--brand); font-size: 13.5px; font-weight: 700; display: block; }
.guide-text p { margin: 2px 0 0; font-size: 11.5px; color: var(--ink-3); }
.recent-row {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 8px; padding-top: 6px; border-top: 1px dashed rgba(168,123,197,.2);
}
.recent-label { font-size: 11.5px; color: var(--ink-3); }
.recent-chip {
  font-size: 11.5px; color: var(--brand); cursor: pointer;
  padding: 2px 8px; border-radius: 10px; background: var(--brand-6);
  transition: all .15s;
}
.recent-chip:hover { background: var(--brand-5); }

/* 预览弹窗 */
.preview-dialog :deep(.el-dialog__body) { padding: 0 16px 12px; }
.preview-body { min-height: 50vh; display: flex; align-items: center; justify-content: center; }
.preview-iframe { width: 100%; height: 70vh; border: 1px solid var(--brand-5); border-radius: 12px; }
.preview-img { max-width: 100%; max-height: 70vh; border-radius: 12px; border: 1px solid var(--brand-5); }
.preview-fallback {
  text-align: center; padding: 40px 20px; color: var(--ink-2);
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.fb-icon { font-size: 56px; }
.fb-hint { font-size: 12px; color: var(--ink-3); margin: 0; }
.fb-download {
  display: inline-block; padding: 8px 18px; border-radius: 22px;
  background: var(--brand); color: #fff; text-decoration: none;
  font-size: 13.5px; font-weight: 600; transition: all .18s;
}
.fb-download:hover { background: var(--brand-dark); transform: translateY(-1px); }
.dl-link { text-decoration: none; }
</style>
