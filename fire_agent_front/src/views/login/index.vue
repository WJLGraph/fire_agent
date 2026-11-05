<script setup>
/**
 * 登录 / 注册页
 * 未登录访问任意页面会被路由守卫重定向到这里
 *
 * V5 视觉重做（§10.6 + 决策 D10）：
 *   - 全屏两栏：左 58% 视觉面（低饱和等高线 + 字标 + 一句价值主张），右 42% 表单
 *   - 登录态不再渲染侧栏（MainLayout 的 is-blank 分支）
 *   - 去金属渐变、去发光、去玻璃；分隔只用发丝线
 *
 * 交互与业务契约完全不变：字段、校验规则、错误提示、redirect 逻辑一字未改。
 *
 * V6 交互细化（仅表现层）：
 *   - 字段错误从 ElMessage toast 改为字段下方内联提示（预留槽位，不跳变）；
 *     校验条件、阈值、文案逐字保留，接口错误仍走 ElMessage.error
 *   - 聚焦态：描边 + 光晕双层；错误态：danger 描边 + 光晕
 *   - autocomplete 语义、回车提交覆盖全部输入、提交 spinner、autofocus
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { motionAllowed } from '@/composables/useMotionPreference'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref('login') // login / register
const loading = ref(false)
const form = ref({
  username: '',
  password: '',
  confirm: '',
  email: '',
})

// 密码显示/隐藏（眼睛按钮）
const showPwd = ref(false)
const showConfirm = ref(false)

// ====== 内联错误态（V6）：校验条件/文案与旧 ElMessage.warning 完全一致，仅呈现渠道改为字段下方 ======
const errors = ref({ username: '', password: '', confirm: '', form: '' })
const usernameRef = ref(null)

/** 输入即清除该字段错误（下次提交时按原规则重新校验） */
const clearErr = (k) => { errors.value[k] = '' }

/** 与旧版逐字同源的校验规则；返回是否存在错误 */
const applyValidate = () => {
  const u = form.value.username.trim()
  const p = form.value.password
  const e = { username: '', password: '', confirm: '', form: '' }
  if (!u || !p) {
    e.form = '请输入用户名和密码'
  } else {
    if (u.length < 2) e.username = '用户名至少 2 个字符'
    // 强度规则只在注册时判：登录侧加下限会把历史 6 位口令的账号挡在门外，
    // 让他们连「先登录再改密码」都做不到。服务端 auth._enforce_password_strength
    // 才是权威口径（注册/改密都会判），这里的文案与它保持一致。
    if (mode.value === 'register') {
      if (p.length < 8 || !/[A-Za-z]/.test(p) || !/\d/.test(p)) {
        e.password = '密码至少 8 位，且需同时包含字母和数字'
      }
    }
    if (mode.value === 'register' && p !== form.value.confirm) e.confirm = '两次输入的密码不一致'
  }
  errors.value = e
  return !!(e.form || e.username || e.password || e.confirm)
}

// ====== 左侧视觉面：低饱和等高线（纯装饰，示意地形起伏） ======
const contourPath = (cx, cy, r, seed) => {
  const n = 56
  let d = ''
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2
    const wob =
      1 +
      0.16 * Math.sin(a * 3 + seed) +
      0.1 * Math.sin(a * 5 - seed * 1.7) +
      0.06 * Math.sin(a * 8 + seed * 0.6)
    const x = cx + Math.cos(a) * r * wob * 1.35
    const y = cy + Math.sin(a) * r * wob * 0.82
    d += `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return d + 'Z'
}

const contourPaths = computed(() => {
  const out = []
  const seeds = [
    { x: 300, y: 620, s: 0.5 },
    { x: 720, y: 240, s: 2.4 },
  ]
  seeds.forEach((sd) => {
    for (let i = 1; i <= 12; i++) out.push(contourPath(sd.x, sd.y, i * 17, sd.s + i * 0.28))
  })
  return out
})

const fireDots = [
  { x: 420, y: 300, lv: 3 }, { x: 505, y: 355, lv: 2 }, { x: 560, y: 250, lv: 3 },
  { x: 640, y: 400, lv: 2 }, { x: 700, y: 300, lv: 1 }, { x: 350, y: 450, lv: 2 },
  { x: 480, y: 520, lv: 1 }, { x: 610, y: 530, lv: 2 }, { x: 760, y: 460, lv: 1 },
  { x: 290, y: 240, lv: 1 },
]

// ====== 左侧统计数字已收敛为一条口径行；保留挂载即聚焦用户名的键盘可达性 ======
onMounted(() => {
  usernameRef.value?.focus?.()
})

// ====== 指针准星：只写两个 CSS 变量（合成器友好），静态偏好下模板层已不调用 ======
const visRef = ref(null)
const onVisMove = (e) => {
  const el = visRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${(e.clientX - r.left).toFixed(1)}px`)
  el.style.setProperty('--my', `${(e.clientY - r.top).toFixed(1)}px`)
}
const onVisLeave = () => {
  visRef.value?.style.setProperty('--mx', '-200px')
  visRef.value?.style.setProperty('--my', '-200px')
}

/** 登录/注册成功后的目标地址：仅接受站内绝对路径，避免 redirect 参数被空值/非法值覆盖 */
const redirectTarget = () => {
  const raw = route.query.redirect
  return typeof raw === 'string' && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/dashboard'
}

/**
 * 登录成功后的导航：必须 await 且失败必须可见。
 * 目标页组件/分片加载失败时 vue-router 会 abort 导航（URL 不变），
 * 若静默吞掉，用户会停在登录页并反复重试（表现为后端多条 200 登录日志）。
 * 此处提示后整页重载一次，让浏览器重新请求构建产物。
 */
const goAfterAuth = async () => {
  const target = redirectTarget()
  try {
    await router.replace(target)
  } catch {
    ElMessage.warning('目标页面加载失败，正在重新载入…')
    window.location.assign(target)
  }
}

const onSubmit = async () => {
  // loading 期间重复点击/回车一律忽略（disabled 属性更新要等下一帧，挡不住同帧连击）
  if (loading.value) return
  // V6：内联校验（规则/文案与旧版一致），不再弹 toast
  if (applyValidate()) return
  const u = form.value.username.trim()
  const p = form.value.password

  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(u, p)
      ElMessage.success('登录成功')
    } else {
      await auth.register(u, p, form.value.email.trim())
      ElMessage.success('注册成功，已自动登录')
    }
    await goAfterAuth()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    loading.value = false
  }
}

const switchMode = (m) => {
  mode.value = m
  form.value.confirm = ''
  // 切换模式后清空错误态，避免上一模式的提示残留
  errors.value = { username: '', password: '', confirm: '', form: '' }
}
</script>

<template>
  <div class="login-shell">
    <!-- ============ 左：视觉面 ============ -->
    <section
      ref="visRef"
      class="login-vis qt-grid--faint"
      @pointermove="motionAllowed && onVisMove($event)"
      @pointerleave="onVisLeave"
    >
      <div class="login-vis__bg" aria-hidden="true">
        <svg viewBox="0 0 840 900" preserveAspectRatio="xMidYMid slice">
          <path v-for="(d, i) in contourPaths" :key="i" :d="d" pathLength="1" :style="{ '--d': `${i * 26}ms` }" />
          <circle
            v-for="(p, i) in fireDots"
            :key="`d${i}`"
            :cx="p.x"
            :cy="p.y"
            :r="p.lv >= 3 ? 4 : 3"
            :class="[`lv-${p.lv}`, { 'mo-loop': p.lv >= 3 }]"
            :style="{ '--d': `${420 + i * 45}ms` }"
          />
          <circle cx="505" cy="355" r="14" class="ring" />
          <circle cx="505" cy="355" r="14" class="ring ring--echo mo-loop" />
        </svg>
      </div>

      <!-- 指针准星：跟随鼠标的十字定位线 + 圆环（纯装饰，静态偏好下不挂载监听） -->
      <div class="login-vis__reticle" aria-hidden="true"><i class="reticle-dot"></i></div>

      <div class="login-vis__top">
        <!-- 低权重返回入口：回公开站点首页（push 导航，不破坏历史栈） -->
        <router-link to="/welcome" class="login-back" aria-label="返回公开站点首页">← 返回首页</router-link>
        <div class="login-vis__mark">焰哨</div>
        <div class="login-vis__en">FLAME SENTRY · WILDFIRE INTELLIGENCE</div>
        <!-- 指挥台状态标识（与公开页/大屏同语言：访问边界 + 空间基准） -->
        <div class="login-vis__ctx">
          <span class="qt-status"><i></i>内部系统 · 需登录</span>
          <span class="qt-status"><i></i>EPSG:4326 · WGS84</span>
        </div>
      </div>

      <div class="login-vis__bottom">
        <h1 class="login-vis__claim">
          <span class="ln">在火情发生之前，</span>
          <span class="ln">把风险看清楚。</span>
        </h1>
        <p class="login-vis__desc">
          融合卫星火点、气象与行政区划边界数据，由多智能体协同完成火险研判、值班简报与归档发布的全链路闭环。
        </p>
        <ul class="login-vis__stats">
          <li><b class="qt-num">16</b><span>州市</span></li>
          <li><b class="qt-num">5,411</b><span>历史火点</span></li>
          <li><b class="qt-num">6</b><span>协作智能体</span></li>
          <li><b>五级</b><span>火险口径</span></li>
        </ul>
      </div>
    </section>

    <!-- ============ 右：表单 ============ -->
    <section class="login-form">
      <div class="login-card">
        <!-- 移动端返回入口（≤1024 左视觉面隐藏时可见） -->
        <router-link to="/welcome" class="login-back login-back--m" aria-label="返回公开站点首页">← 返回首页</router-link>
        <div class="login-card__hd">
          <p class="login-card__eyebrow qt-eyebrow">SECURE ACCESS · 值班入口</p>
          <h2>{{ mode === 'login' ? '登录焰哨' : '注册账号' }}</h2>
          <p>{{ mode === 'login' ? '使用值班账号进入指挥平台' : '创建账号后自动登录' }}</p>
        </div>

        <!-- 模式切换：滑块随选中项平移（共享指示器，非两块背景各自变色） -->
        <div class="mode-switch" role="tablist" aria-label="登录或注册" :style="{ '--i': mode === 'login' ? 0 : 1 }">
          <i class="mode-pill" aria-hidden="true"></i>
          <button type="button" role="tab" :class="{ active: mode === 'login' }" :aria-selected="mode === 'login'" @click="switchMode('login')">登 录</button>
          <button type="button" role="tab" :class="{ active: mode === 'register' }" :aria-selected="mode === 'register'" @click="switchMode('register')">注 册</button>
        </div>

        <!-- 表单 -->
        <div class="form-area">
          <label class="field" :class="{ 'has-err': errors.username }">
            <span class="field__lb">用户名</span>
            <input
              ref="usernameRef"
              v-model="form.username"
              type="text"
              placeholder="请输入用户名"
              autocomplete="username"
              :aria-invalid="!!errors.username"
              @input="clearErr('username')"
              @keyup.enter="onSubmit"
            />
            <span class="field__err" aria-live="polite">{{ errors.username }}</span>
          </label>

          <label v-if="mode === 'register'" class="field">
            <span class="field__lb">邮箱（可选）</span>
            <input v-model="form.email" type="email" placeholder="用于找回账号" autocomplete="email" @keyup.enter="onSubmit" />
          </label>

          <label class="field" :class="{ 'has-err': errors.password }">
            <span class="field__lb">密码</span>
            <div class="pwd-wrap">
              <input
                v-model="form.password"
                :type="showPwd ? 'text' : 'password'"
                placeholder="请输入密码"
                :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
                :aria-invalid="!!errors.password"
                @input="clearErr('password')"
                @keyup.enter="onSubmit"
              />
              <button type="button" class="eye-btn" :title="showPwd ? '隐藏密码' : '显示密码'" :aria-pressed="showPwd" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
                <svg v-if="showPwd" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
                <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
            <span class="field__err" aria-live="polite">{{ errors.password }}</span>
          </label>

          <label v-if="mode === 'register'" class="field" :class="{ 'has-err': errors.confirm }">
            <span class="field__lb">确认密码</span>
            <div class="pwd-wrap">
              <input
                v-model="form.confirm"
                :type="showConfirm ? 'text' : 'password'"
                placeholder="请再次输入密码"
                autocomplete="new-password"
                :aria-invalid="!!errors.confirm"
                @input="clearErr('confirm')"
                @keyup.enter="onSubmit"
              />
              <button type="button" class="eye-btn" :title="showConfirm ? '隐藏密码' : '显示密码'" :aria-pressed="showConfirm" :aria-label="showConfirm ? '隐藏密码' : '显示密码'" @click="showConfirm = !showConfirm">
                <svg v-if="showConfirm" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
                <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
            <span class="field__err" aria-live="polite">{{ errors.confirm }}</span>
          </label>

          <span class="form-err" aria-live="polite">{{ errors.form }}</span>

          <button class="submit-btn" :disabled="loading" :aria-busy="loading" @click="onSubmit">
            <span v-if="loading" class="spin" aria-hidden="true"></span>
            {{ loading ? '处理中...' : (mode === 'login' ? '登 录' : '注 册') }}
          </button>
        </div>

        <div class="login-foot">
          <p v-if="mode === 'login'">还没有账号？<a @click="switchMode('register')">立即注册</a></p>
          <p v-else>已有账号？<a @click="switchMode('login')">返回登录</a></p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-shell {
  display: flex;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  background: var(--fs-bg-canvas);
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ==================== 左：视觉面 ==================== */

.login-vis {
  position: relative;
  flex: none;
  width: 58%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--fs-s12);
  background: var(--fs-bg-sunken);
  overflow: hidden;
}
.login-vis__bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.login-vis__bg svg {
  width: 100%;
  height: 100%;
  display: block;
}
/* 等高线「画出来」：pathLength=1 让 dasharray 与真实长度解耦，24 条按 26ms 错峰。
   基线态是「已画完」（dashoffset 默认 0），所以关掉动画后图形依旧完整，不会留白 */
.login-vis__bg path {
  fill: none;
  stroke: var(--fs-ink-400);
  stroke-width: 0.7;
  opacity: 0.4;
  stroke-dasharray: 1;
  animation: contour-draw 1.4s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes contour-draw {
  from { stroke-dashoffset: 1; }
  to { stroke-dashoffset: 0; }
}

/* 火点：缩放淡入（transform-box: fill-box 让 SVG 图形以自身几何中心为原点） */
.login-vis__bg circle:not(.ring--echo) {
  transform-box: fill-box;
  transform-origin: center;
  animation: dot-pop 0.5s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes dot-pop {
  from { opacity: 0; transform: scale(0.2); }
  to { opacity: 1; transform: scale(1); }
}
.login-vis__bg circle.lv-1 { fill: var(--fs-risk-low); }
.login-vis__bg circle.lv-2 { fill: var(--fs-risk-mid); }
.login-vis__bg circle.lv-3 { fill: var(--fs-risk-high); }
/* 三级及以上火点：入场后进入低幅呼吸（.mo-loop 受三态闸门管控） */
.login-vis__bg circle.lv-3.mo-loop {
  animation:
    dot-pop 0.5s var(--fs-ease-out) both,
    lv3-breathe 2.8s var(--fs-ease) infinite;
  animation-delay: var(--d, 0ms), calc(var(--d, 0ms) + 0.5s);
}
@keyframes lv3-breathe {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.45); opacity: 0.72; }
}
.login-vis__bg circle.ring {
  fill: none;
  stroke: var(--fs-accent);
  stroke-width: 1;
  opacity: 0.55;
}
/* 雷达回波：一圈强调色环从火点扩散出去（纯装饰，静态偏好下整体不渲染） */
.login-vis__bg circle.ring--echo {
  fill: none;
  stroke: var(--fs-accent);
  stroke-width: 1;
  opacity: 0;
  transform-box: fill-box;
  transform-origin: center;
}
.login-vis__bg circle.ring--echo.mo-loop {
  animation: ring-echo 3.4s var(--fs-ease-out) infinite;
}
@keyframes ring-echo {
  0% { opacity: 0.45; transform: scale(1); }
  72% { opacity: 0; transform: scale(3.4); }
  100% { opacity: 0; transform: scale(3.4); }
}

/* 指针准星：两条 1px 交叉线 + 交点圆环，全部走 transform（不触发 layout） */
.login-vis__reticle {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--fs-dur-panel) var(--fs-ease);
}
.login-vis:hover .login-vis__reticle { opacity: 1; }
.login-vis__reticle::before,
.login-vis__reticle::after {
  content: '';
  position: absolute;
  background: rgba(var(--fs-accent-rgb), 0.26);
}
.login-vis__reticle::before {
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  transform: translateY(var(--my, -200px));
}
.login-vis__reticle::after {
  top: 0;
  bottom: 0;
  left: 0;
  width: 1px;
  transform: translateX(var(--mx, -200px));
}
.reticle-dot {
  position: absolute;
  top: 0;
  left: 0;
  width: 20px;
  height: 20px;
  margin: -10px 0 0 -10px;
  border: 1px solid rgba(var(--fs-accent-rgb), 0.5);
  border-radius: 50%;
  transform: translate3d(var(--mx, -200px), var(--my, -200px), 0);
}
.reticle-dot::after {
  content: '';
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: var(--fs-accent);
  opacity: 0.7;
}

.login-vis__top { position: relative; }
/* 低权重返回入口：mono 小字幽灵样式，不抢表单主按钮 */
.login-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 var(--fs-s4);
  font-family: var(--fs-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
  text-decoration: none;
  transition: color 0.16s var(--fs-ease);
}
.login-back:hover { color: var(--fs-accent); }
.login-back:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 2px;
  border-radius: 2px;
}
/* 卡内实例默认隐藏（桌面由左栏品牌行承担），移动端显示 */
.login-back--m { display: none; }
.login-vis__mark {
  font-size: 30px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--fs-ink-900);
}
.login-vis__en {
  margin-top: 4px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  color: var(--fs-ink-400);
}
/* 指挥台状态标识行（与公开页同语言） */
.login-vis__ctx {
  margin-top: var(--fs-s4);
  display: flex;
  gap: var(--fs-s4);
  flex-wrap: wrap;
}

.login-vis__bottom { position: relative; max-width: 460px; }
.login-vis__claim {
  margin: 0;
  font-size: 26px;
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: -0.01em;
  color: var(--fs-ink-900);
  text-wrap: pretty;
}
.login-vis__claim .ln {
  display: block;
  animation: ln-rise 0.62s var(--fs-ease-out) both;
}
.login-vis__claim .ln:nth-child(2) { animation-delay: 0.1s; }
@keyframes ln-rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: none; }
}
.login-vis__desc {
  margin-top: var(--fs-s3);
  font-size: 13px;
  line-height: 1.8;
  color: var(--fs-ink-500);
  animation: ln-rise 0.62s 0.18s var(--fs-ease-out) both;
}
/* 口径行：从一句 mono 文本升级为「数字 + 单位」的数据条，项间用发丝竖线分隔 */
.login-vis__stats {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  margin: var(--fs-s6) 0 0;
  padding: 0;
  list-style: none;
  animation: ln-rise 0.62s 0.26s var(--fs-ease-out) both;
}
.login-vis__stats li {
  display: flex;
  align-items: baseline;
  gap: 5px;
  padding: 0 14px;
  border-left: 1px solid var(--fs-hairline-strong);
}
.login-vis__stats li:first-child {
  padding-left: 0;
  border-left: 0;
}
/* common.css 的 reset 把 b 的字重抹平了，这里必须显式补回 */
.login-vis__stats b {
  font-family: var(--fs-font-mono);
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
  color: var(--fs-ink-900);
}
.login-vis__stats span {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}

/* ==================== 右：表单 ==================== */

.login-form {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--fs-bg-surface);
  border-left: 1px solid var(--fs-hairline);
}
/* 表单侧的图纸底纹：48px 网格 + 径向遮罩淡出，只在卡片周围留一圈「工程纸」气息 */
.login-form::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  -webkit-mask-image: radial-gradient(ellipse 62% 56% at 50% 50%, #000 24%, transparent 100%);
  mask-image: radial-gradient(ellipse 62% 56% at 50% 50%, #000 24%, transparent 100%);
}
.login-card {
  position: relative;
  z-index: 1;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: var(--fs-s5);
}
.login-card__hd h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--fs-ink-900);
}
.login-card__hd p {
  margin-top: 4px;
  font-size: 12px;
  color: var(--fs-ink-500);
}
/* mono 眉标：与公开页 .qt-eyebrow 同语言，给表单一个「档案抬头」 */
.login-card__hd .login-card__eyebrow {
  margin: 0 0 12px;
  font-size: 10px;
  color: var(--fs-ink-400);
}

.mode-switch {
  position: relative;
  display: inline-flex;
  align-self: flex-start;
  gap: 2px;
  padding: 2px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm);
}
/* 共享滑块：两等分栅格 + translateX(100%) 换位，切换时是「滑过去」而不是「各自变色」 */
.mode-pill {
  position: absolute;
  inset: 2px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  pointer-events: none;
}
.mode-pill::before {
  content: '';
  grid-area: 1 / 1;
  border-radius: 4px;
  background: var(--fs-bg-surface);
  box-shadow: var(--fs-e1);
  transform: translateX(calc(var(--i, 0) * 100%));
  transition: transform var(--fs-dur-panel) var(--fs-ease);
}
.mode-switch button {
  position: relative;
  z-index: 1;
  min-width: 62px;
  height: 28px;
  font-size: 12px;
  font-weight: 500;
  color: var(--fs-ink-500);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.16s var(--fs-ease);
}
.mode-switch button:hover { color: var(--fs-ink-900); }
.mode-switch button.active {
  color: var(--fs-ink-900);
  font-weight: 600;
}

.form-area { display: flex; flex-direction: column; gap: var(--fs-s4); }
.field { position: relative; display: flex; flex-direction: column; gap: 6px; }
/* 浮动 label：静息时在输入框内（兼占位符），聚焦/有值时上浮骑缝 */
.field__lb {
  position: absolute;
  left: 9px;
  top: 19px;
  transform: translateY(-50%);
  z-index: 1;
  padding: 0 4px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-400);
  background: transparent;
  pointer-events: none;
  transition: top 0.16s var(--fs-ease), font-size 0.16s var(--fs-ease), color 0.16s var(--fs-ease), background-color 0.16s var(--fs-ease);
}
.field:focus-within .field__lb,
.field:has(input:not(:placeholder-shown)) .field__lb {
  top: 1px;
  font-size: 10px;
  color: var(--fs-accent);
  background: var(--fs-bg-surface);
}
.field input {
  height: var(--fs-control-h);
  padding: 0 10px;
  font: inherit;
  font-size: 13px;
  color: var(--fs-ink-900);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline-strong);
  border-radius: var(--fs-r-sm);
  outline: none;
  caret-color: var(--fs-accent);
  transition: border-color 0.16s var(--fs-ease), box-shadow 0.16s var(--fs-ease);
}
/* 静息时 label 就在框内兼作占位符，真 placeholder 必须透明，否则两段文字叠在同一位置。
   显形条件必须和 label 上浮条件（:focus-within / :has）逐字同源：
   一个用 :focus 一个用 :focus-within 看似等价，实际两者在部分实现里并不同步，
   不同步的瞬间就是「label 没走 + placeholder 已出现」的叠字。 */
.field input::placeholder { color: transparent; }
.field:focus-within input::placeholder,
.field:has(input:not(:placeholder-shown)) input::placeholder { color: var(--fs-ink-400); }
.field input:hover { border-color: var(--fs-ink-400); }
/* 聚焦态：描边 + 光晕双层（键盘可达性由描边+光晕承担，去掉全局 outline 双环） */
.field input:focus {
  border-color: var(--fs-accent);
  box-shadow: 0 0 0 3px var(--fs-accent-soft);
}
.field input:focus-visible { outline: none; }
/* 错误态：danger 描边；聚焦时仅换光晕色，不叠加双环 */
.field.has-err input { border-color: var(--fs-danger); }
.field.has-err input:focus { box-shadow: 0 0 0 3px rgba(142, 47, 42, 0.14); }
html.dark .field.has-err input:focus { box-shadow: 0 0 0 3px rgba(196, 72, 63, 0.18); }

/* 错误提示：预留槽位（min-height 恒占位），出现/消失不引起布局跳变 */
.field__err {
  min-height: 16px;
  font-size: 11px;
  line-height: 16px;
  color: var(--fs-danger);
}
/* 表单级错误（用户名/密码为空的合并提示）：同样预留槽位 */
.form-err {
  min-height: 16px;
  font-size: 11px;
  line-height: 16px;
  color: var(--fs-danger);
}

.pwd-wrap { position: relative; }
.pwd-wrap input { width: 100%; padding-right: 34px; }
.eye-btn {
  position: absolute;
  top: 50%;
  right: 6px;
  transform: translateY(-50%);
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--fs-ink-500);
  border-radius: var(--fs-r-xs);
  transition: color 0.16s var(--fs-ease), background-color 0.16s var(--fs-ease);
}
.eye-btn:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }

.submit-btn {
  position: relative;
  overflow: hidden;
  height: 36px;
  margin-top: var(--fs-s2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-on-accent);
  background: var(--fs-accent);
  border: none;
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
  transition: background-color 0.16s var(--fs-ease), transform 0.16s var(--fs-ease), box-shadow 0.16s var(--fs-ease);
}
/* hover 扫光（一次 0.6s；off 静止） */
.submit-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, 0.3) 50%, transparent 65%);
  transform: translateX(-160%);
  pointer-events: none;
}
.submit-btn:hover:not(:disabled)::before { animation: btn-sweep 0.6s var(--fs-ease); }
@keyframes btn-sweep { to { transform: translateX(160%); } }
.submit-btn:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  transform: translateY(-1px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e2);
}
.submit-btn:active:not(:disabled) {
  transform: translateY(0.5px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.submit-btn:disabled { background: var(--fs-ink-400); box-shadow: none; cursor: not-allowed; }

/* 提交 spinner：currentColor 跟随按钮文字色，双主题成立 */
.spin {
  width: 12px;
  height: 12px;
  flex: none;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  opacity: 0.85;
  animation: spin-rotate 0.7s linear infinite;
}
@keyframes spin-rotate {
  to { transform: rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .spin { animation-duration: 1.6s; }
}

.login-foot { font-size: 12px; color: var(--fs-ink-500); }
.login-foot p { margin: 0; }
.login-foot a {
  color: var(--fs-accent);
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
}

@media (max-width: 1024px) {
  .login-vis { display: none; }
  .login-back--m { display: inline-flex; }
}

/* 小屏防溢出：卡片不贴边、不超视口 */
@media (max-width: 480px) {
  .login-form { padding: var(--fs-s6) var(--fs-s5); }
  .login-card { width: 100%; max-width: 320px; }
  .mode-switch { align-self: stretch; }
  .mode-switch button { flex: 1; }
}
/* ==================== V7 入场与微动效（挂载即播，零 JS；reduced 全静态） ==================== */
/* 左视觉面：等高线缓慢漂移（transform only） */
.login-vis__bg { animation: vis-drift 16s ease-in-out infinite alternate; }
@keyframes vis-drift {
  from { transform: translate3d(0, -6px, 0); }
  to { transform: translate3d(0, 8px, 0); }
}
/* 右卡片入场 + 字段 40ms 错峰 */
.login-card { animation: card-in 0.55s var(--fs-ease-out) both; }
@keyframes card-in {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: none; }
}
.form-area > * { animation: field-in 0.4s var(--fs-ease-out) both; }
/* 字段位移幅度小于卡片本体（8 < 14），两层入场叠加才不显得各自甩动 */
@keyframes field-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.form-area > :nth-child(1) { animation-delay: 0.04s; }
.form-area > :nth-child(2) { animation-delay: 0.08s; }
.form-area > :nth-child(3) { animation-delay: 0.12s; }
.form-area > :nth-child(4) { animation-delay: 0.16s; }
.form-area > :nth-child(5) { animation-delay: 0.2s; }
/* 模式切换：注册字段 v-if 重挂载时 120ms 交叉淡入 */
.form-area .field { animation-duration: 0.12s; }
/* 错误态：轻微 shake（类挂载时播放一次） */
.field.has-err input { animation: err-shake 0.3s var(--fs-ease); }
@keyframes err-shake {
  20% { transform: translateX(-3px); }
  50% { transform: translateX(3px); }
  80% { transform: translateX(-1.5px); }
}
/* 三态降级：off 或 auto+系统 reduce 时全部静止。
   入场类动画一律 both 填充 + 基线态即可见，animation:none 后图形完整不留白 */
html[data-motion-allowed="false"] .login-vis__bg,
html[data-motion-allowed="false"] .login-vis__bg path,
html[data-motion-allowed="false"] .login-vis__bg circle,
html[data-motion-allowed="false"] .login-vis__claim .ln,
html[data-motion-allowed="false"] .login-vis__desc,
html[data-motion-allowed="false"] .login-vis__stats,
html[data-motion-allowed="false"] .login-card,
html[data-motion-allowed="false"] .form-area > *,
html[data-motion-allowed="false"] .field.has-err input,
html[data-motion-allowed="false"] .submit-btn:hover::before { animation: none; }
html[data-motion-allowed="false"] .login-vis__reticle { display: none; }
html[data-motion-allowed="false"] .mode-pill::before { transition: none; }
html[data-motion-allowed="false"] .submit-btn:hover:not(:disabled) { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .login-vis__bg,
  html:not([data-motion="on"]) .login-vis__claim .ln,
  html:not([data-motion="on"]) .login-vis__desc,
  html:not([data-motion="on"]) .login-vis__stats,
  html:not([data-motion="on"]) .login-card,
  html:not([data-motion="on"]) .form-area > *,
  html:not([data-motion="on"]) .field.has-err input,
  html:not([data-motion="on"]) .submit-btn:hover::before { animation: none; }
  html:not([data-motion="on"]) .login-vis__reticle { display: none; }
  html:not([data-motion="on"]) .mode-pill::before { transition: none; }
}
</style>
