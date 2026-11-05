<script setup>
/**
 * 系统管理 · 用户权限管理 Tab（仅管理员）— v0 同构
 *
 * kb-ans 面板 + v0 tbl 三线表 + adm-op 文字操作；角色变更仍走 el-select（保留交互）。
 * 角色变更 / 删除后需要刷新日志列表，通过 refresh-logs 事件上抛给父组件（父持有 fetchLogs）。
 */
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { fetchUsersRaw, changeRoleRaw, removeUserRaw } from '@/api/admin'

const auth = useAuthStore()

const emit = defineEmits(['refresh-logs'])

// ====== 用户管理（仅管理员） ======
const users = ref([])
const loadingUsers = ref(false)

const fetchUsers = async () => {
  loadingUsers.value = true
  try {
    const res = await fetchUsersRaw()
    const json = await res.json()
    if (res.status === 403) {
      ElMessage.warning(json.detail || '需要管理员权限')
      users.value = []
      return
    }
    if (json.code === 200) users.value = json.data
  } catch {
    /* api/http 已统一处理 401 */
  } finally {
    loadingUsers.value = false
  }
}

const changeRole = async (u, role) => {
  try {
    const res = await changeRoleRaw(u.id, role)
    const json = await res.json()
    if (res.ok && json.code === 200) {
      ElMessage.success(`已将 ${u.username} 的角色改为 ${role === 'admin' ? '管理员' : '普通用户'}`)
      fetchUsers()
      emit('refresh-logs')
    } else {
      ElMessage.error(json.detail || '修改失败')
      fetchUsers()
    }
  } catch {
    fetchUsers()
  }
}

const removeUser = async (u) => {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${u.username}」吗？该操作不可恢复`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res = await removeUserRaw(u.id)
    const json = await res.json()
    if (res.ok && json.code === 200) {
      ElMessage.success('用户已删除')
      fetchUsers()
      emit('refresh-logs')
    } else {
      ElMessage.error(json.detail || '删除失败')
    }
  } catch {
    ElMessage.error('删除失败')
  }
}

const roleLabel = (r) => (r === 'admin' ? 'ADMIN' : 'USER')

onMounted(() => {
  fetchUsers()
})

// 供父组件的「刷新」按钮调用
defineExpose({ fetchUsers })
</script>

<template>
  <div class="au">
    <!-- v0 kb-ans 面板：标题行 + 三线表 -->
    <div class="kb-ans anim" style="--d:80ms" v-loading="loadingUsers">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">用户权限管理</span>
        <span class="badge badge--muted mono">{{ users.length }} users</span>
        <span class="sq-panel__sp"></span>
        <button class="vbtn vbtn--ghost" :disabled="loadingUsers" @click="fetchUsers">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 10a6.5 6.5 0 1 1-1.9-4.6"/><path d="M16.5 3.5v3h-3"/></svg>
          刷新
        </button>
      </div>
      <!-- 横向可滚容器：窄屏下操作列不再被面板 overflow:hidden 裁掉（删除/角色入口始终可达） -->
      <div class="tbl-scroll">
      <table class="tbl row-fade">
        <thead>
          <tr>
            <th style="width:52px">ID</th>
            <th>用户名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>注册时间</th>
            <th style="width:200px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="mono">{{ u.id }}</td>
            <td>
              <span class="au__uname">{{ u.username }}</span>
              <span v-if="u.username === auth.user?.username" class="au__self">当前账号</span>
            </td>
            <td class="au__dim">{{ u.email || '—' }}</td>
            <td>
              <span class="au__role" :class="{ admin: u.role === 'admin' }">{{ roleLabel(u.role) }}</span>
            </td>
            <td class="mono au__dim">{{ u.created_at || '—' }}</td>
            <td>
              <div class="au__ops">
                <el-select
                  :model-value="u.role"
                  size="small"
                  style="width: 104px"
                  :disabled="u.username === auth.user?.username"
                  @change="(v) => changeRole(u, v)"
                >
                  <el-option label="普通用户" value="user" />
                  <el-option label="管理员" value="admin" />
                </el-select>
                <span
                  class="adm-op"
                  :class="{ 'is-disabled': u.username === auth.user?.username }"
                  @click="u.username !== auth.user?.username && removeUser(u)"
                >删除</span>
              </div>
            </td>
          </tr>
          <tr v-if="users.length === 0 && !loadingUsers">
            <td colspan="6" class="au__empty">暂无用户数据</td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- 权限说明（v0 accent 注记） -->
    <div class="au__note">
      <b>权限说明</b>管理员可访问全部页面（含系统管理/用户管理）；普通用户仅可访问作战大屏、智能查询、知识库、Agent 中心、报告中心。系统内置默认管理员账号 admin（不可删除、不可降级自己的角色）。
    </div>
  </div>
</template>

<style scoped>
.au {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0; /* 禁止纵向压缩（原 min-height:100% 会导致卡片被压矮、内容被裁） */
}

.anim {
  animation: rise 0.4s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
/* ===== kb-ans 面板（v0 同构） ===== */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.kb-ans__hd {
  min-height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-ans__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-900);
}
.kb-ans__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 2px;
  background: var(--fs-accent);
  opacity: 0.7;
}
.sq-panel__sp { flex: 1; }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.badge--muted { color: var(--fs-ink-500); }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

/* v0 btn（ghost）同构 */
.vbtn {
  height: 26px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.vbtn svg { width: 12px; height: 12px; }
.vbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.vbtn--ghost { background: transparent; box-shadow: none; }
.vbtn--ghost:hover:not(:disabled) { background: var(--fs-bg-sunken); box-shadow: none; }
.vbtn:disabled { color: var(--fs-ink-400); cursor: not-allowed; }

/* ===== v0 tbl 三线表 ===== */
/* 横向兜底滚动：面板 overflow:hidden 只服务圆角，窄屏下表格可滚而非裁掉操作列
   overflow-y 显式 hidden：行入场有 translateY 位移，否则会瞬时被算成 auto 顶出竖向滚动条 */
.tbl-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.tbl { width: 100%; min-width: 720px; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.tbl th {
  text-align: left;
  font-family: var(--fs-font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--fs-ink-500);
  padding: 8px 14px;
  background: var(--fs-bg-sunken);
  border-bottom: 1px solid var(--fs-hairline);
  white-space: nowrap;
}
.tbl td {
  padding: 0 14px;
  height: 44px;
  line-height: 1.5;
  border-bottom: 1px solid var(--fs-hairline);
  color: var(--fs-ink-700);
}
/* ID 与注册时间整行显示，不因列宽挤压折成三行破坏表格节奏 */
.tbl td.mono { white-space: nowrap; }
.tbl tbody tr:last-child td { border-bottom: none; }
.tbl tbody tr { transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)); }
.tbl tbody tr:hover { background: var(--fs-bg-sunken); }
.au__uname { color: var(--fs-ink-900); font-weight: 500; }
.au__self {
  margin-left: 8px;
  font-size: 10px;
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  padding: 1px 7px;
  border-radius: var(--fs-r-xs, 3px);
}
.au__dim { color: var(--fs-ink-400); font-size: 12px; }
.au__role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
  padding: 2px 8px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
}
.au__role::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: currentColor;
}
.au__role.admin { color: var(--fs-accent); background: var(--fs-accent-soft); }
.au__ops { display: flex; align-items: center; gap: 12px; }

/* v0 adm-op 文字操作（危险动作：只用 danger 描边与淡底，不加发光） */
.adm-op {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid color-mix(in srgb, var(--fs-danger) 26%, transparent);
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  letter-spacing: 0.02em;
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 8%, transparent);
  cursor: pointer;
  white-space: nowrap;
  transition:
    color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    border-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.adm-op:hover:not(.is-disabled) {
  color: var(--fs-danger);
  border-color: color-mix(in srgb, var(--fs-danger) 46%, transparent);
  background: color-mix(in srgb, var(--fs-danger) 14%, transparent);
}
.adm-op.is-disabled {
  color: var(--fs-ink-400);
  border-color: var(--fs-hairline);
  background: var(--fs-bg-sunken);
  cursor: not-allowed;
  text-decoration: none;
}
.au__empty { padding: 40px; text-align: center; color: var(--fs-ink-400); font-size: 12px; }

/* 权限说明（v0 accent 注记） */
.au__note {
  padding: 12px 16px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--fs-ink-500);
  border-left: 2px solid var(--fs-accent);
  background: var(--fs-accent-soft);
  border-radius: 0 var(--fs-r-sm, 6px) var(--fs-r-sm, 6px) 0;
}
.au__note b {
  color: var(--fs-accent);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-right: 10px;
}

html[data-motion-allowed="false"] .anim { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .anim { animation: none; }
}
</style>
