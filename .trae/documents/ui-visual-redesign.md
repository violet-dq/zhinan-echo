# 知南·Echo UI 视觉重设计计划

## Context（为什么改）

当前 UI 视觉偏单薄：背景是纯 CSS 线性渐变（`linear-gradient(160deg, #F7F2FA, #EFE4F7, #F7F2FA)`），无任何图案纹理，显得空旷；主题 Logo 直接使用 emoji `🌸`（[LoginView.vue#L31](file:///d:/ZHINAN_Echo2.0/frontend/src/views/LoginView.vue#L31)、[MainView.vue#L71](file:///d:/ZHINAN_Echo2.0/frontend/src/views/MainView.vue#L71)、[index.html](file:///d:/ZHINAN_Echo2.0/frontend/index.html) favicon 三处），缺乏品牌识别度与商业感。`frontend/src/assets/` 与 `frontend/public/` 均为空目录，无任何视觉素材。

本次改动将背景升级为「内联 SVG 二月兰花图案 + 渐变叠加」，并将 Logo 重设计为「抽象兰花 + E 字母」SVG 徽章，提升品牌感与商业调性，同时保持二月兰主题色系（#7B4B9A 系）不变、不引入额外图片资源请求。

## 设计决策（已与用户确认）

1. **背景**：内联 SVG 花朵图案（非 AI 生成图），叠加在现有渐变之上，矢量、零额外请求、与主题色完全统一。
2. **Logo**：抽象兰花四瓣形态 + Echo 首字母 E，紫色渐变徽章。

## 实现方案

### 1. 新增 Logo SVG 组件

**新建** `frontend/src/components/EchoLogo.vue`

抽象兰花 + E 字母徽章 SVG，支持 `size` prop（默认 40）：
- 外层：四瓣花瓣形态（用 4 个旋转 45°的椭圆 path，`fill="url(#petalGrad)"`，淡紫→主紫径向渐变）
- 内层：圆角方形或圆形深紫底（`#7B4B9A`），承载字母
- 中心：大写字母 `E`（白色或极淡紫 `#F7F2FA`，粗体无衬线），呼应 "Echo"
- 加 `<defs>` 渐变定义（`petalGrad`、`coreGrad`），保持与 `--orchid-main/soft/hover` 一致
- 加微妙 `drop-shadow` 提升立体感

### 2. 背景图案 SVG

**修改** `frontend/src/style.css`

在 `body` 背景上叠加一层内联 SVG data URL 的二月兰四瓣花散落图案：
- 保留现有 `linear-gradient(160deg, ...)` 作为底色
- `background-image` 叠加 SVG：用 `<pattern>` 定义一朵四瓣花（4 个椭圆瓣 + 中心小圆，`fill` 用 `#E8D5F0` 透明度 0.35、`#A87BC5` 透明度 0.18），`pattern` 间距约 120px，轻微旋转打破网格感
- `background-size: auto` 让 pattern 自身平铺
- 同步给 `:root` 加 `--orchid-pattern` 变量（SVG data URL 字符串）便于复用

### 3. 登录页背景同步

**修改** `frontend/src/views/LoginView.vue`

- `.login-wrap` 背景的 `radial-gradient` 叠加层引用全局 SVG 图案变量，与主站风格统一
- `<div class="logo">🌸</div>` → `<EchoLogo :size="64" />`

### 4. 主布局 Logo 替换

**修改** `frontend/src/views/MainView.vue`

- `.side-brand` 内 `<span class="logo">🌸</span>` → `<EchoLogo :size="36" />`
- 调整 `.logo` 样式：去掉 `font-size: 30px`（emoji 时代的遗留），改为 `display:flex; align-items:center`

### 5. Favicon 更新

**修改** `frontend/index.html`

`<link rel="icon" href="data:image/svg+xml,...">` 替换为新的抽象兰花 E 徽章 SVG（精简版，去掉渐变定义用纯色以兼容 favicon 渲染）。

### 6. ChatPanel Echo 头像（顺带统一）

**修改** `frontend/src/components/ChatPanel.vue`

对话区智能体气泡头像当前用渐变圆 + 文字。改为内嵌 EchoLogo（size 28），让品牌符号在最高频交互处重复曝光，强化商业识别。

## 关键文件清单

| 操作 | 文件 |
|---|---|
| 新建 | [frontend/src/components/EchoLogo.vue](file:///d:/ZHINAN_Echo2.0/frontend/src/components/EchoLogo.vue) |
| 修改 | [frontend/src/style.css](file:///d:/ZHINAN_Echo2.0/frontend/src/style.css)（body 背景 + 图案变量） |
| 修改 | [frontend/src/views/LoginView.vue](file:///d:/ZHINAN_Echo2.0/frontend/src/views/LoginView.vue#L31)（Logo 替换 + 背景引用） |
| 修改 | [frontend/src/views/MainView.vue](file:///d:/ZHINAN_Echo2.0/frontend/src/views/MainView.vue#L71)（侧边栏 Logo） |
| 修改 | [frontend/src/components/ChatPanel.vue](file:///d:/ZHINAN_Echo2.0/frontend/src/components/ChatPanel.vue)（Echo 头像） |
| 修改 | [frontend/index.html](file:///d:/ZHINAN_Echo2.0/frontend/index.html)（favicon） |

## 不做的事（避免范围蔓延）

- 不改主题色变量（#7B4B9A 系保持不变）
- 不替换菜单图标（Element Plus 的 ChatDotRound/Collection/AlarmClock/Notebook 已统一，重设计 ROI 低）
- 不引入 AI 生成图片或外部图片资源（保持零额外请求）
- 不动后端、不动布局结构、不动交互逻辑

## 验证方式

1. 重新构建前端：`cd frontend && npm run build`
2. 重启后端（一体化托管）：`cd backend && python run.py`
3. 浏览器访问 http://127.0.0.1:8000 验证：
   - 登录页：背景可见浅紫花朵图案 + 抽象兰花 E Logo
   - 主界面侧边栏：Logo 替换成功，背景图案透出
   - 对话页：Echo 头像为新 Logo
   - 浏览器标签页：favicon 更新
   - 移动端缩放：图案不变形、Logo 清晰
4. 检查无控制台报错（SVG data URL 转义正确）
