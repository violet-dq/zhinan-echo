<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import VuePdfEmbed from 'vue-pdf-embed'
import * as mammoth from 'mammoth'
import { api } from '../api'

const files = ref<any[]>([])
const courses = ref<any[]>([])
const filterCourse = ref<number | null>(null)
const uploading = ref(false)
const detail = ref<any>(null)
const showDetail = ref(false)
const detailTab = ref('preview')
const dragOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const editOpen = ref(false)
const editSaving = ref(false)
const editForm = ref({ id: 0, filename: '', course_name: '', type: '' })
const typeOptions = ['课件', '试题', '笔记', '论文', '资料']

function openEdit(f: any) {
  editForm.value = { id: f.id, filename: f.filename, course_name: f.course === '未分类' ? '' : f.course, type: f.type || '资料' }
  editOpen.value = true
}

async function saveEdit() {
  editSaving.value = true
  try {
    await api.patch(`/api/files/${editForm.value.id}`, {
      course_name: editForm.value.course_name,
      tags: { type: editForm.value.type },
    })
    ElMessage.success('归档已更新，索引同步重建中 ✅')
    editOpen.value = false
    load()
  } catch { /* api 层已提示 */ } finally { editSaving.value = false }
}

const typeIcon: Record<string, string> = {
  pdf: '📕', docx: '📘', pptx: '📗', txt: '📄', md: '📄', jpg: '🖼️', jpeg: '🖼️', png: '🖼️',
}

// 文件类型分类，决定预览方式
function ftypeOf(f: any): string {
  return ((f.file_type) || (f.filename || '').split('.').pop() || '').toLowerCase()
}
const isPdf = (f: any) => ftypeOf(f) === 'pdf'
const isImage = (f: any) => ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ftypeOf(f))
const isTextLike = (f: any) => ['txt', 'md', 'markdown'].includes(ftypeOf(f))
const isDocx = (f: any) => ftypeOf(f) === 'docx'
const isPptx = (f: any) => ftypeOf(f) === 'pptx'
const canInlinePreview = (f: any) => isPdf(f) || isImage(f) || isTextLike(f) || isDocx(f) || isPptx(f)

const previewUrl = computed(() => detail.value ? api.previewUrl(detail.value.id) : '')
const downloadUrl = computed(() => detail.value ? api.downloadUrl(detail.value.id) : '')

// Word 文档 HTML 预览
const docxHtml = ref('')
const docxLoading = ref(false)

async function loadDocxPreview() {
  if (!detail.value) return
  docxLoading.value = true
  docxHtml.value = ''
  try {
    const resp = await fetch(previewUrl.value)
    if (!resp.ok) throw new Error('加载失败')
    const arrayBuffer = await resp.arrayBuffer()
    const result = await mammoth.convertToHtml({ arrayBuffer })
    docxHtml.value = result.value || '<p>（文档内容为空）</p>'
  } catch { /* 静默失败，用户可切到解析文本 tab */ }
  finally { docxLoading.value = false }
}

async function load() {
  const [f, c] = await Promise.all([api.files(filterCourse.value || undefined), api.courses()])
  files.value = f.items
  courses.value = c.items
}

async function onUpload(fileList: FileList | File[]) {
  const list = Array.from(fileList)
  if (!list.length) return
  uploading.value = true
  const form = new FormData()
  list.forEach(f => form.append('files', f))
  try {
    const d = await api.upload('/api/files/upload', form)
    d.results.forEach((r: any) => r.ok
      ? ElMessage.success(`「${r.filename}」已解析归档 ✅`)
      : ElMessage.error(`「${r.filename}」：${r.error}`))
    await load()
  } finally { uploading.value = false }
}

function onFileInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files) onUpload(t.files)
  t.value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  if (e.dataTransfer?.files) onUpload(e.dataTransfer.files)
}

async function openDetail(id: number) {
  detail.value = await api.fileDetail(id)
  // 根据文件类型自动切到最合适的 Tab
  detailTab.value = canInlinePreview(detail.value) ? 'preview' : 'content'
  showDetail.value = true
  // Word 文档自动加载 HTML 预览
  if (isDocx(detail.value)) loadDocxPreview()
}

async function removeFile(f: any) {
  await ElMessageBox.confirm(`确定删除「${f.filename}」？其索引与向量将一并移除。`, '删除资料', { type: 'warning' })
  await api.deleteFile(f.id)
  ElMessage.success('已删除')
  load()
}

async function exportCsv() {
  ElMessage.info('正在导出 CSV…')
  await api.exportFile('/api/export/files.csv', 'zhinan-echo-files.csv')
  ElMessage.success('CSV 导出成功 ✅')
}
async function exportMd() {
  ElMessage.info('正在导出 Markdown…')
  await api.exportFile('/api/export/files.md', 'zhinan-echo-files.md')
  ElMessage.success('Markdown 导出成功 ✅')
}

onMounted(load)
</script>

<template>
  <div class="lib-wrap">
    <!-- 上传区 -->
    <div class="upload-zone glass-card" :class="{ drag: dragOver }"
         @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="onDrop">
      <div class="up-icon">{{ uploading ? '⏳' : '📤' }}</div>
      <div class="up-text">
        <b>拖拽资料到这里，或点击选择文件</b>
        <p>支持 PDF / Word / PPT / TXT / Markdown / 图片 · 自动解析全文、智能分类、生成标签、建立语义索引</p>
      </div>
      <input ref="fileInput" type="file" multiple hidden
             accept=".pdf,.docx,.pptx,.txt,.md,.markdown,.jpg,.jpeg,.png" @change="onFileInput" />
      <el-button type="primary" :loading="uploading" @click="fileInput?.click()">
        {{ uploading ? '解析入库中…' : '选择文件' }}
      </el-button>
    </div>

    <!-- 过滤 + 统计 -->
    <div class="toolbar glass-panel">
      <el-radio-group v-model="filterCourse" @change="load">
        <el-radio-button :value="null as any">全部（{{ files.length }}）</el-radio-button>
        <el-radio-button v-for="c in courses" :key="c.id" :value="c.id">
          {{ c.name }}（{{ c.file_count }}）
        </el-radio-button>
      </el-radio-group>
      <div style="flex:1" />
      <el-button size="small" @click="exportCsv">导出 CSV</el-button>
      <el-button size="small" @click="exportMd">导出 Markdown</el-button>
    </div>

    <!-- 文件卡片 -->
    <div class="file-grid">
      <div v-for="f in files" :key="f.id" class="file-card glass-panel">
        <div class="f-head">
          <span class="f-icon">{{ typeIcon[f.file_type] || '📄' }}</span>
          <div class="f-title" @click="openDetail(f.id)">{{ f.filename }}</div>
        </div>
        <div class="f-tags">
          <el-tag size="small">{{ f.course }}</el-tag>
          <el-tag size="small" type="warning" effect="plain">{{ f.type || '资料' }}</el-tag>
        </div>
        <div class="f-meta">
          <span>{{ f.size_kb }} KB · {{ f.chunk_count }} 块索引</span>
          <span class="f-actions">
            <el-button size="small" text @click="openDetail(f.id)" title="预览">👁️ 预览</el-button>
            <a :href="api.downloadUrl(f.id)" target="_blank" download title="下载原文件">
              <el-button size="small" text>⬇️ 下载</el-button>
            </a>
            <el-button size="small" text @click="openEdit(f)">✏️</el-button>
            <el-button size="small" text type="danger" @click="removeFile(f)">删除</el-button>
          </span>
        </div>
      </div>
      <el-empty v-if="!files.length" description="资料库还是空的，上传第一份资料吧 📂" style="grid-column: 1/-1" />
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetail" :title="detail?.filename" size="640px">
      <template v-if="detail">
        <div class="detail-toolbar">
          <a :href="downloadUrl" target="_blank" download class="dl-btn">
            ⬇️ 下载原文件
          </a>
          <span class="meta-text">{{ detail.size_kb }} KB · {{ detail.chunk_count }} 块索引 · {{ detail.course }}</span>
        </div>
        <el-tabs v-model="detailTab" class="detail-tabs">
          <el-tab-pane label="文件预览" name="preview">
            <div class="preview-area">
              <!-- PDF：pdf.js 统一渲染，不依赖浏览器内置阅读器 -->
              <VuePdfEmbed v-if="isPdf(detail)" :source="previewUrl" class="preview-pdf" />
              <!-- 图片 -->
              <img v-else-if="isImage(detail)" :src="previewUrl" class="preview-img" />
              <!-- 文本类：直接用预览接口拿原文（保留格式） -->
              <iframe v-else-if="isTextLike(detail)" :src="previewUrl"
                      class="preview-iframe" frameborder="0"></iframe>
              <!-- Word 文档：mammoth 转 HTML 渲染 -->
              <div v-else-if="isDocx(detail)" class="docx-preview">
                <div v-if="docxLoading" class="docx-loading">📄 正在解析 Word 文档…</div>
                <div v-else-if="docxHtml" class="docx-html" v-html="docxHtml"></div>
                <div v-else class="preview-fallback">
                  <p>Word 文档解析失败</p>
                  <p class="fb-hint">请下载原文件查看，或切换到「解析文本」标签</p>
                  <a :href="downloadUrl" target="_blank" download class="fb-download">⬇️ 下载原文件</a>
                </div>
              </div>
              <!-- PPT：显示提取的文本内容 -->
              <div v-else-if="isPptx(detail)" class="pptx-preview">
                <div class="pptx-hint">📋 PPT 课件提取内容（完整排版请下载原文件）</div>
                <div class="content-preview" style="max-height:60vh">{{ detail.content?.slice(0, 5000) }}{{ (detail.content?.length || 0) > 5000 ? '\n\n…（内容过长，已截断）' : '' }}</div>
              </div>
              <!-- 其他格式 -->
              <div v-else class="preview-fallback">
                <div class="fb-icon">📄</div>
                <p>{{ detail.file_type || '该' }} 格式暂不支持浏览器内嵌预览</p>
                <p class="fb-hint">可以下载原文件查看，或切换到「解析文本」标签看我提取出的内容</p>
                <a :href="downloadUrl" target="_blank" download class="fb-download">⬇️ 下载原文件</a>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="解析文本" name="content">
            <div class="content-preview">{{ detail.content?.slice(0, 3000) }}{{ (detail.content?.length || 0) > 3000 ? '\n\n…（内容过长，已截断）' : '' }}</div>
          </el-tab-pane>
          <el-tab-pane label="自动标签" name="tags">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="课程">{{ detail.course }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ detail.type }}</el-descriptions-item>
              <el-descriptions-item label="关键词">
                <el-tag v-for="k in detail.keywords" :key="k" size="small" style="margin:2px">{{ k }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="章节">
                <div v-for="(s, i) in detail.outline.slice(0, 15)" :key="i" class="sec-line">
                  · {{ s.title || s }}
                </div>
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

    <!-- 编辑归档 -->
    <el-dialog v-model="editOpen" :title="`编辑归档 · ${editForm.filename}`" width="420">
      <el-form label-width="64">
        <el-form-item label="课程">
          <el-select v-model="editForm.course_name" clearable filterable allow-create
                     default-first-option placeholder="选择或输入新课程名" style="width:100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="editForm.type">
            <el-radio v-for="t in typeOptions" :key="t" :value="t">{{ t }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-wrap { flex: 1; min-height: 0; display: grid; gap: 14px; overflow-y: auto; padding: 4px 8px 8px; }
.upload-zone {
  display: flex; align-items: center; gap: 18px; padding: 20px 26px;
  border: 2px dashed var(--brand-3);
  border-radius: 26px;
  background: linear-gradient(135deg, rgba(247,242,250,.82), rgba(232,213,240,.4));
  transition: all .2s;
}
body[data-theme="dark"] .upload-zone {
  background: linear-gradient(135deg, rgba(46,31,68,.82), rgba(74,48,102,.4));
  border-color: var(--brand-3);
}
body[data-theme="dark"] .upload-zone .up-text p { color: var(--ink-3); }
.upload-zone.drag {
  background: var(--brand-6); border-color: var(--brand);
  box-shadow: 0 10px 30px rgba(123,75,154,.14);
}
.up-icon { font-size: 40px; }
.up-text b { color: var(--brand); font-size: 16px; font-weight: 800; }
.up-text p { margin: 4px 0 0; font-size: 12.5px; color: var(--ink-2); }
.up-btn { margin-left: auto; cursor: pointer; }

.toolbar {
  display: flex; align-items: center; gap: 10px; padding: 12px 18px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,.95);
  border-radius: var(--r-full);
  box-shadow: 0 6px 20px rgba(123,75,154,.07);
}

.file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.file-card {
  padding: 18px; display: flex; flex-direction: column; gap: 10px;
  background: #fff;
  border: 1px solid var(--brand-5);
  border-radius: 24px;
  box-shadow: 0 6px 20px rgba(123,75,154,.06);
  transition: all .22s;
  position: relative; overflow: hidden;
}
.file-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 5px; border-radius: 5px 0 0 5px;
  background: linear-gradient(180deg, var(--brand-3), var(--brand-5));
}
.file-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 32px rgba(123,75,154,.14);
  border-color: var(--brand-4);
}
.f-head { display: flex; gap: 12px; align-items: center; }
.f-icon {
  font-size: 28px;
  width: 46px; height: 46px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 14px;
  background: var(--brand-6);
}
.f-title {
  font-weight: 700; cursor: pointer; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; color: var(--ink-1); font-size: 15px; flex: 1;
}
.f-title:hover { color: var(--brand); }
.f-tags { display: flex; gap: 6px; flex-wrap: wrap; padding-left: 4px; }
.f-meta {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 12px; color: var(--ink-3);
  padding: 8px 10px; background: var(--brand-6); border-radius: 16px;
  margin-top: 2px;
}
.f-actions { display: flex; align-items: center; gap: 2px; flex-wrap: wrap; }
.f-actions a { text-decoration: none; }

/* 详情抽屉：工具条 + 预览区 */
.detail-toolbar {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 14px; margin-bottom: 10px;
  background: var(--brand-6); border-radius: 16px;
  border: 1px solid var(--brand-5);
}
.detail-toolbar .dl-btn {
  display: inline-block; padding: 7px 16px; border-radius: 22px;
  background: var(--brand); color: #fff; text-decoration: none;
  font-size: 13px; font-weight: 600; transition: all .18s;
}
.detail-toolbar .dl-btn:hover { background: var(--brand-dark); transform: translateY(-1px); }
.detail-toolbar .meta-text { font-size: 12px; color: var(--ink-3); }

.detail-tabs :deep(.el-tabs__header) { margin: 0 0 10px; }
.preview-area { min-height: 60vh; display: flex; align-items: center; justify-content: center; }
.preview-iframe {
  width: 100%; height: 72vh;
  border: 1px solid var(--brand-5); border-radius: 14px;
  background: #fff;
}
.preview-img {
  max-width: 100%; max-height: 72vh;
  border-radius: 14px; border: 1px solid var(--brand-5);
  box-shadow: 0 6px 20px rgba(123,75,154,.1);
}
/* PDF pdf.js 渲染容器 */
.preview-pdf {
  width: 100%; max-height: 72vh; overflow-y: auto;
  border: 1px solid var(--brand-5); border-radius: 14px;
  background: #fff; padding: 8px;
}
/* Word 文档 HTML 预览 */
.docx-preview { width: 100%; }
.docx-html {
  max-height: 72vh; overflow-y: auto; padding: 24px;
  background: #fff; border: 1px solid var(--brand-5); border-radius: 14px;
  color: #333; line-height: 1.8; font-size: 14px;
}
.docx-html :deep(h1) { font-size: 20px; margin: 16px 0 8px; color: #2B1C3A; }
.docx-html :deep(h2) { font-size: 17px; margin: 14px 0 6px; color: #4B2B7A; }
.docx-html :deep(h3) { font-size: 15px; margin: 12px 0 4px; color: #615070; }
.docx-html :deep(p) { margin: 6px 0; }
.docx-html :deep(table) { border-collapse: collapse; width: 100%; margin: 10px 0; }
.docx-html :deep(td), .docx-html :deep(th) { border: 1px solid #ddd; padding: 6px 10px; }
.docx-html :deep(img) { max-width: 100%; border-radius: 8px; }
.docx-html :deep(ul), .docx-html :deep(ol) { padding-left: 24px; margin: 6px 0; }
.docx-loading { text-align: center; padding: 60px 20px; color: var(--ink-3); font-size: 15px; }
/* PPT 提取内容预览 */
.pptx-preview { width: 100%; }
.pptx-hint {
  padding: 10px 14px; margin-bottom: 8px;
  background: var(--brand-6); border-radius: 12px;
  font-size: 12.5px; color: var(--ink-2);
}
.preview-fallback {
  text-align: center; padding: 40px 20px; color: var(--ink-2);
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.preview-fallback .fb-icon { font-size: 56px; }
.preview-fallback .fb-hint { font-size: 12px; color: var(--ink-3); margin: 0; }
.preview-fallback .fb-download {
  display: inline-block; padding: 8px 18px; border-radius: 22px;
  background: var(--brand); color: #fff; text-decoration: none;
  font-size: 13.5px; font-weight: 600; transition: all .18s; margin-top: 8px;
}
.preview-fallback .fb-download:hover { background: var(--brand-dark); transform: translateY(-1px); }

.content-preview {
  white-space: pre-wrap; font-size: 13px; line-height: 1.85;
  background: var(--brand-6); padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--brand-5);
  color: var(--ink-1);
  max-height: 72vh; overflow-y: auto;
}
.sec-line { font-size: 13px; padding: 2px 0; color: var(--ink-2); }
</style>
