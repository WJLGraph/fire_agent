<script setup>
/**
 * 个人中心 — v0 同构重建
 *
 * 结构（对齐 visual-v0.html §profile）：
 *   page-head（标题 + ID/会话徽标）→ pf-hero 账号卡（头像 + 名称 + 角色 + 退出登录）
 *   → adm-grid 双列（基本资料 / 修改密码，field 发丝输入行）→ 偏好设置（pf-row + seg + tg）
 *
 * 后端 API: PUT /api/v1/auth/me、PUT /api/v1/auth/me/password
 * 偏好设置纯本地持久化（localStorage）：主题接 stores/theme，播报/密度供各页读取。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { updateMe, changePassword as changePasswordApi } from '@/api/auth'

const auth = useAuthStore()
const themeStore = useThemeStore()
const router = useRouter()

const fmtTime = (t) => (t ? String(t).replace('T', ' ').slice(0, 19) : '—')
const avatarChar = (auth.user?.username || '用').slice(0, 1).toUpperCase()

// ====== 个人资料 ======
const profileForm = reactive({
  email: auth.user?.email || '',
})
const savingProfile = ref(false)

const saveProfile = async () => {
  savingProfile.value = true
  try {
    const json = await updateMe(profileForm.email.trim())
    if (json.code === 200) {
      auth.updateUser({ email: json.data.email })
      ElMessage.success('个人资料已更新')
    } else {
      ElMessage.error(json.detail || '保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingProfile.value = false
  }
}

// ====== 修改密码 ======
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const savingPwd = ref(false)

// 新密码强度：弱 / 中 / 强（长度 + 字符类别粗判）
const pwdStrength = ref('')
const judgeStrength = () => {
  const v = pwdForm.new_password
  if (!v) { pwdStrength.value = ''; return }
  let kinds = 0
  if (/[a-z]/.test(v)) kinds++
  if (/[A-Z]/.test(v)) kinds++
  if (/\d/.test(v)) kinds++
  if (/[^a-zA-Z0-9]/.test(v)) kinds++
  pwdStrength.value = v.length < 8 || kinds <= 1 ? '弱' : (kinds <= 2 ? '中' : '强')
}

const changePassword = async () => {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  // 与服务端 PUT /auth/me/password 的 _enforce_password_strength 同口径：
  // 前端先判是为了给出可读提示，否则用户只会看到一句 400 文案。
  if (pwdForm.new_password.length < 8 || !/[A-Za-z]/.test(pwdForm.new_password) || !/\d/.test(pwdForm.new_password)) {
    ElMessage.warning('新密码至少 8 位，且需同时包含字母和数字')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPwd.value = true
  try {
    const json = await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    if (json.code === 200) {
      ElMessage.success('密码已修改，请重新登录')
      // 修改密码后强制重新登录
      setTimeout(async () => {
        try { await ElMessageBox.close() } catch { /* ignore */ }
        // 后端改密码时已 bump token_version 吊销全部旧 token，这里只需清本地
        auth.logout()
        router.replace('/login')
      }, 1200)
    } else {
      ElMessage.error(json.detail || '修改失败')
    }
  } catch {
    ElMessage.error('修改失败')
  } finally {
    savingPwd.value = false
  }
}

// ====== 偏好设置（本地持久化） ======
const SPEAK_KEY = 'fire_agent_autospeak'
const DENSITY_KEY = 'fire_agent_table_density'
const autoSpeak = ref(localStorage.getItem(SPEAK_KEY) === 'on')
const tableDensity = ref(localStorage.getItem(DENSITY_KEY) === 'compact' ? 'compact' : 'cozy')

const toggleSpeak = () => {
  autoSpeak.value = !autoSpeak.value
  localStorage.setItem(SPEAK_KEY, autoSpeak.value ? 'on' : 'off')
}
const setDensity = (v) => {
  tableDensity.value = v
  localStorage.setItem(DENSITY_KEY, v)
}
</script>

<template>
  <div class="pf">
    <!-- v0 page-head（64px 单行） -->
    <header class="page-head">
      <div class="page-head__t">
        <h1 class="page-head__h1">个人中心</h1>
        <p class="page-head__sub">账号资料 · 安全设置 · 个性化偏好</p>
      </div>
      <BackHomeButton />
      <div class="page-head__sp"></div>
      <div class="page-head__ops">
        <span class="badge badge--muted mono">ID {{ auth.user?.id ?? '—' }}</span>
        <span class="badge"><i class="badge__dot" style="background:var(--fs-success)"></i>会话有效</span>
      </div>
    </header>

    <div class="pf__scroll">
      <!-- 账号卡（v0 pf-hero） -->
      <div class="pf-hero anim" style="--d:40ms">
        <span class="pf-hero__avatar">{{ avatarChar }}</span>
        <div class="pf-hero__b">
          <span class="pf-hero__n">{{ auth.user?.username }}<span class="pf-hero__role" :class="{ admin: auth.user?.role === 'admin' }">{{ auth.user?.role === 'admin' ? 'ADMIN' : 'USER' }}</span></span>
          <span class="pf-hero__m mono">注册 {{ fmtTime(auth.user?.created_at) }} · 最近登录 {{ fmtTime(auth.user?.last_login) }}</span>
        </div>
        <span class="pf-hero__sp"></span>
        <button class="vbtn vbtn--ghost" @click="auth.logoutRemote(); router.replace('/login')">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h6"/><path d="M15 10H9"/><path d="m13 7.5 2.5 2.5L13 12.5"/></svg>
          退出登录
        </button>
      </div>

      <div class="adm-grid anim" style="--d:80ms">
        <!-- 基本资料 -->
        <div class="kb-ans">
          <div class="kb-ans__hd"><span class="kb-ans__t">基本资料</span></div>
          <div class="kb-ans__bd">
            <!-- v0 field 发丝输入行 -->
            <label class="field">
              <span class="field__k">用户名</span>
              <input :value="auth.user?.username" disabled>
            </label>
            <label class="field">
              <span class="field__k">角色</span>
              <input :value="auth.user?.role === 'admin' ? 'ADMIN' : 'USER'" disabled>
            </label>
            <label class="field">
              <span class="field__k">邮箱</span>
              <input v-model="profileForm.email" type="email" maxlength="120" placeholder="用于找回密码与通知（可留空）">
            </label>
            <div class="kit-row">
              <span class="sq-panel__sp"></span>
              <button class="vbtn vbtn--primary" :disabled="savingProfile" @click="saveProfile">
                {{ savingProfile ? '保存中…' : '保存修改' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 修改密码 -->
        <div class="kb-ans">
          <div class="kb-ans__hd"><span class="kb-ans__t">修改密码</span></div>
          <div class="kb-ans__bd">
            <label class="field">
              <span class="field__k">原密码</span>
              <input v-model="pwdForm.old_password" type="password" placeholder="输入当前密码">
            </label>
            <label class="field">
              <span class="field__k">新密码</span>
              <input v-model="pwdForm.new_password" type="password" placeholder="至少 8 位，含字母和数字" @input="judgeStrength">
              <span v-if="pwdStrength" class="field__suffix" :class="{ ok: pwdStrength === '强', warn: pwdStrength === '中', bad: pwdStrength === '弱' }">{{ pwdStrength }}</span>
            </label>
            <label class="field">
              <span class="field__k">确认</span>
              <input v-model="pwdForm.confirm_password" type="password" placeholder="再次输入新密码">
            </label>
            <div class="kit-row">
              <span class="pf-tip">修改成功后将强制重新登录</span>
              <span class="sq-panel__sp"></span>
              <button class="vbtn vbtn--primary" :disabled="savingPwd" @click="changePassword">
                {{ savingPwd ? '提交中…' : '更新密码' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 偏好设置（v0 pf-row + seg + tg） -->
      <div class="kb-ans anim" style="--d:120ms">
        <div class="kb-ans__hd"><span class="kb-ans__t">偏好设置</span></div>
        <div class="kb-ans__bd" style="padding:0">
          <div class="pf-row">
            <div class="pf-row__b">
              <span class="pf-row__t">界面主题</span>
              <span class="pf-row__d">浅色 / 深色即时切换，刷新后保持</span>
            </div>
            <div class="seg">
              <button class="seg__i" :class="{ 'is-on': themeStore.mode === 'light' }" @click="themeStore.setMode('light')">浅色</button>
              <button class="seg__i" :class="{ 'is-on': themeStore.mode === 'dark' }" @click="themeStore.setMode('dark')">深色</button>
            </div>
          </div>
          <div class="pf-row">
            <div class="pf-row__b">
              <span class="pf-row__t">语音播报</span>
              <span class="pf-row__d">查询结果与识别结论自动朗读</span>
            </div>
            <button class="tg" :class="{ 'is-on': autoSpeak }" @click="toggleSpeak"><i></i></button>
          </div>
          <div class="pf-row" style="border-bottom:none">
            <div class="pf-row__b">
              <span class="pf-row__t">表格密度</span>
              <span class="pf-row__d">结果表格的行高与留白</span>
            </div>
            <div class="seg">
              <button class="seg__i" :class="{ 'is-on': tableDensity === 'compact' }" @click="setDensity('compact')">紧凑</button>
              <button class="seg__i" :class="{ 'is-on': tableDensity === 'cozy' }" @click="setDensity('cozy')">舒适</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pf {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
  /* 指挥台网格底纹（hairline 级，随亮暗主题取色） */
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ===== v0 page-head（64px 单行） ===== */
.page-head {
  flex-shrink: 0;
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--fs-hairline);
}
.page-head__t { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.page-head__h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.15;
  color: var(--fs-ink-900);
}
.page-head__sub { margin: 0; font-size: 12px; color: var(--fs-ink-500); }
.page-head__sp { flex: 1; }
.page-head__ops { display: flex; align-items: center; gap: 8px; }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.01em;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.badge--muted { color: var(--fs-ink-500); }
.badge__dot { width: 6px; height: 6px; border-radius: 999px; background: currentColor; }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

/* ===== 内容滚动区（居中 980px） ===== */
.pf__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.pf__scroll > * { max-width: 980px; width: 100%; margin: 0 auto; }

.anim {
  animation: rise 0.42s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .anim { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .anim { animation: none; }
}
/* ===== v0 pf-hero 账号卡 ===== */
.pf-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline), inset 0 1px 0 rgba(255, 255, 255, 0.14);
}
.pf-hero__avatar {
  flex: none;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-size: 18px;
  font-weight: 600;
}
.pf-hero__b { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.pf-hero__n { font-size: 15px; font-weight: 600; color: var(--fs-ink-900); }
.pf-hero__role {
  margin-left: 10px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  padding: 2px 8px;
  border-radius: var(--fs-r-xs, 3px);
  vertical-align: 2px;
}
.pf-hero__role.admin { color: var(--fs-accent); }
.pf-hero__m { font-size: 11px; color: var(--fs-ink-400); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pf-hero__sp { flex: 1; }

/* ===== v0 adm-grid 双列 ===== */
.adm-grid {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 1100px) { .adm-grid { grid-template-columns: 1fr; } }

/* ===== kb-ans 面板（v0 同构） ===== */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline), inset 0 1px 0 rgba(255, 255, 255, 0.14);
  overflow: hidden;
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.kb-ans:hover {
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong), inset 0 1px 0 rgba(255, 255, 255, 0.14), var(--fs-e1);
}
.kb-ans__hd {
  min-height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-ans__t { font-size: 13px; font-weight: 500; letter-spacing: 0.01em; color: var(--fs-ink-900); }
.kb-ans__t::before {
  content: '';
  display: inline-block;
  width: 2px;
  height: 11px;
  margin-right: 7px;
  vertical-align: -1px;
  border-radius: 1px;
  background: var(--fs-accent);
}
.kb-ans__bd {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sq-panel__sp { flex: 1; }

/* ===== v0 field 发丝输入行 ===== */
.field {
  height: 32px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease);
  cursor: text;
}
.field:hover { box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.field:focus-within { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.field__k {
  flex: none;
  width: 64px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
}
.field input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: none;
  font: inherit;
  font-size: 13px;
  color: var(--fs-ink-900);
  caret-color: var(--fs-accent);
}
.field input::placeholder { color: var(--fs-ink-400); }
/* 禁用字段是真实值（用户名/角色），比 placeholder 深一档才不像空框 */
.field input:disabled { color: var(--fs-ink-500); cursor: not-allowed; }
.field__suffix { flex: none; font-size: 11px; color: var(--fs-ink-400); }
.field__suffix.ok { color: var(--fs-success); }
.field__suffix.warn { color: var(--fs-warning); }
.field__suffix.bad { color: var(--fs-danger); }

/* kit-row 底部按钮行 */
.kit-row { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.pf-tip { font-size: 11px; color: var(--fs-ink-400); }

/* v0 btn 同构 */
.vbtn {
  height: 28px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.01em;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.vbtn svg { width: 13px; height: 13px; }
.vbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.vbtn:not(.vbtn--ghost):hover:not(:disabled) { transform: translateY(-1px); }
.vbtn:active:not(.vbtn--ghost):not(:disabled) { transform: translateY(0.5px); box-shadow: none; }
.vbtn--ghost { background: transparent; box-shadow: none; }
.vbtn--ghost:hover:not(:disabled) { background: var(--fs-bg-sunken); box-shadow: none; color: var(--fs-danger); }
.vbtn--primary { background: var(--fs-accent); color: var(--fs-on-accent); font-weight: 600; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1); }
.vbtn--primary:hover:not(:disabled) { background: var(--fs-accent-hover); color: var(--fs-on-accent); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e2); }
.vbtn:disabled { color: var(--fs-ink-400); cursor: not-allowed; }
.vbtn--primary:disabled { background: var(--fs-bg-sunken); box-shadow: none; }

/* ===== v0 pf-row 偏好行 ===== */
.pf-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.pf-row:hover { background-color: rgba(var(--fs-ink-900-rgb), 0.02); }
.pf-row__b { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.pf-row__t { font-size: 12px; font-weight: 500; color: var(--fs-ink-900); }
.pf-row__d { font-size: 11px; color: var(--fs-ink-400); }

/* ===== v0 seg 分段 ===== */
.seg {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm, 6px);
  flex: none;
}
.seg__i {
  height: 26px;
  padding: 0 12px;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: var(--fs-ink-500);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.seg__i:hover:not(.is-on) { color: var(--fs-ink-900); background-color: rgba(var(--fs-ink-900-rgb), 0.05); }
.seg__i.is-on {
  background: var(--fs-bg-surface);
  color: var(--fs-ink-900);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14), var(--fs-e1);
  font-weight: 600;
}

/* ===== v0 tg 迷你开关 ===== */
.tg {
  flex: none;
  width: 34px;
  height: 19px;
  border: none;
  border-radius: 999px;
  background: var(--fs-hairline-strong);
  position: relative;
  cursor: pointer;
  padding: 0;
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.tg i {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--fs-bg-surface);
  box-shadow: var(--fs-e1);
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.tg:hover { background-color: var(--fs-ink-400); }
.tg.is-on { background: var(--fs-accent); }
.tg.is-on:hover { background-color: var(--fs-accent-hover); }
.tg.is-on i { transform: translateX(15px); }

html[data-motion-allowed="false"] .vbtn:hover:not(:disabled),
html[data-motion-allowed="false"] .vbtn:active:not(:disabled) { transform: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .vbtn:hover:not(:disabled),
  html:not([data-motion="on"]) .vbtn:active:not(:disabled) { transform: none; }
}
</style>
