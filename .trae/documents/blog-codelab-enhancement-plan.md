# 博客「代码实验室 CODE LAB」高端展示升级计划

## Context
现有博客（e:\Wjl-Mine-Blog，Vue3 + GSAP）已具备 Hero 逐字入场、About 逐字点亮、项目卡 3D 倾斜等效果，但**全站没有任何"代码本身"的展示**——文档页代码块无高亮。用户要求：增加高端现代化的展示手法，既能展现代码的高端性和真实示例，又简约又花哨。

方案核心：新增 **「02 — 代码实验室 / CODE LAB」** 区块——一个 macOS 风格 IDE 窗口，代码随滚动逐字打出（scrub 可倒带），配手写零依赖语法高亮器 + 全站 sec-label 解码乱码入场 + 详情页文档代码高亮。零新增依赖。

## 文件清单（4 新 + 6 改）

### 新增
1. **`src/composables/useCodeHighlight.js`** — 手写轻量 tokenizer（~90 行）
   - sticky 正则规则表，优先级：注释 > 字符串(含 f-string/三引号/模板串) > 装饰器 > 关键字 > 数字 > 函数调用(前瞻 `(`) > 标点
   - 对**原始源码** tokenize，输出阶段才逐段转义（esc: & → &lt; → &gt;，& 最先）
   - 导出：`tokenize(code, lang)`、`highlightCode(code, lang)`（全量 HTML）、`sliceHtml(segs, n)`（前 n 字符截断 HTML——打字机核心，tokenize 一次逐帧截断）
   - 支持 `python` / `javascript` 两种语言

2. **`src/data/codeLab.js`** — 3 个真实片段 `{ file, tab, lang, code, runOutput }`
   - `agent.py`：LangGraph StateGraph 多 Agent 编排（呼应 fire-agent，节点名 parse_task/query_data/route），runOutput: `✓ graph compiled · 8 nodes · 2 conditional edges`
   - `useGsap.js`：逐字摘自本站 `src/composables/useGsap.js` 的 splitToChars（自指彩蛋），runOutput: `✓ 你现在看到的打字动画，正由这段代码驱动`
   - `stream.py`：FastAPI SSE StreamingResponse + astream（呼应焰哨节点推送），runOutput: `✓ stream closed · 128 events · 0 dropped`
   - 每段 ≤22 行、行宽 <70 字符

3. **`src/components/CodeLabSection.vue`** — 主组件（~320 行）
   - 结构：sec-label `02 — 代码实验室 / CODE LAB` + sec-title `SHOW ME THE CODE / 代码，是最诚实的作品集。` + macOS 窗口（红黄绿点、3 个文件 tab 可点击切换、行号槽 + 代码区 + IDE 状态栏）
   - **滚动打字（方案 A）**：`gsap.to(proxy, { n: code.length, scrollTrigger: { trigger: winEl, start: 'top 78%', end: '+=60%', scrub: 0.8 }, onUpdate })`，onUpdate 里 `typedEl.innerHTML = sliceHtml(segs, floor(n)) + cursor`；与 AboutSection 数字滚动同惯用法
   - **布局零抖动**：隐形 sizer 层（visibility:hidden，white-space:pre）锁定最终高度；typed 层 absolute 叠加；行号层与代码层共享 padding/font/line-height
   - **完成态 CSS 驱动**：`done.value = n >= len` → `.cl-window.is-done` → 光标消失、状态栏 runOutput 淡入上浮
   - **tab 切换**：`typeTween?.scrollTrigger?.kill(); typeTween?.kill()` 后重建 + `ScrollTrigger.refresh()`；**onBeforeUnmount 手动 kill typeTween**（不在 gsap.context 捕获范围，这是最易踩的坑）
   - **降级**：`prefers-reduced-motion` → 静态全量高亮、无打字；`document.fonts.ready.then(() => ScrollTrigger.refresh())`
   - ≤900px：字号 11px、长行内层横向滚动（行号固定可见）、状态栏精简

4. **`src/composables/useScramble.js`** — 解码乱码（~45 行）
   - `scrambleIn(el, { duration })`：gsap.ticker 驱动，只打乱 A-Za-z0-9（池剔除 0/O/1/l），CJK/标点原位，逐帧收敛，完成还原后自清理

### 修改
5. **`src/views/HomeView.vue`**：
   - import + 插入 `<CodeLabSection />`（AboutSection 之后）
   - sec-label 编号 `02 — 精选项目` → `03 — 精选项目`
   - **动画拆分**：现 `.sec-label, .sec-title` 共用的 `gsap.from({x:-36})` 拆两段——sec-title 保持 x:-36 滑入；sec-label 改为仅 opacity 淡入 + `ScrollTrigger.create({ once: true, onEnter: () => scrambleIn(el) })`（同一 trigger 同一 start，淡入与解码同帧开始，不冲突）
6. **`src/components/SiteNav.vue`**：增加"代码"按钮 → `goSection('codelab')`；≤700px 时 links gap 收窄防溢出
7. **`src/components/TimelineSection.vue`**：编号 03 → 04
8. **`src/components/ContactSection.vue`**：编号 04 → 05
9. **`src/components/detail/DetailDocs.vue`**：在现有后处理链（L141 `marked.parse(md).replace(/<img /...)`）追加一环：正则匹配 `<pre><code(?: class="language-xxx")?>`，先反转义（&amp; 最后替换）再 `highlightCode`，只处理 python/javascript，其余语言（bash/sql/yaml/html…）原样保留
10. **`src/assets/styles/main.css`**：追加 7 个 token 类（两主题共用，全基于现有成对变量）：
    `.tk-cmt{--ink-faint;italic}` `.tk-str{--accent-2}` `.tk-kw{--accent}` `.tk-dec{--accent-2}` `.tk-num{--accent-2}` `.tk-fn{--ink}` `.tk-pun{--ink-dim}`

## 复用清单
- `useGsap.js` 的 gsap/ScrollTrigger 导出；AboutSection 的代理对象滚动惯用法
- main.css 现有令牌与 section 通用类（sec-label/sec-title/reveal），不新增光晕/新风格
- DetailDocs 现有 marked 后处理链模式

## 验证
1. `npm.cmd run build` 通过
2. 浏览器实测（dev server + browser_use agent）：
   - 区块顺序 01-05、导航"代码"平滑滚动到 #codelab
   - 代码随滚动逐字显现、上滚倒带、打完 runOutput 浮现光标消失
   - 快速连切 3 个 tab 无 tween 堆积、内容行号一致
   - 亮/暗主题切换 token 颜色正常；≤900px 横向滚动行号固定
   - 详情页 python 块高亮生效、bash/sql 块原样、`&&`/`->`/f-string 无实体残留
   - sec-label 全站"淡入+解码"只触发一次，sec-title 滑入不受影响
