/**
 * 最小静态检查：解析涉改 SFC，编译模板并比对标识符与 <script setup> 绑定。
 * 输出两类问题：
 *   1) 模板中使用但 setup 未定义/未导入的标识符（运行时 _ctx.xxx → undefined → 渲染崩溃）
 *   2) 模板中的组件若未在 setup 绑定，会被编译为 resolveComponent —— 同样报告
 * 用法：node scripts/check-sfc-bindings.mjs
 */
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const files = [
  'src/views/agent-center/index.vue',
  'src/views/agent-center/AgentStreamView.vue',
  'src/views/agent-center/AgentPipeline.vue',
  'src/views/agent-center/AgentReportView.vue',
  'src/views/agent-center/ApprovalPanel.vue',
  'src/components/agent-center/AgentThinkPanel.vue',
]

// 模板里合法的非绑定标识符（Vue 内置 / 字面量）
const ALLOW = new Set(['true', 'false', 'null', 'undefined', 'NaN', 'Infinity',
  'Math', 'Date', 'JSON', 'Number', 'String', 'Boolean', 'Array', 'Object',
  'isFinite', 'isNaN', 'parseFloat', 'parseInt', 'console', 'window', 'document'])

let bad = 0
for (const rel of files) {
  const abs = resolve(root, rel)
  const source = readFileSync(abs, 'utf8')
  const { descriptor, errors } = parse(source, { filename: abs })
  if (errors.length) { console.log(`[parse-error] ${rel}: ${errors.map(e => e.message).join('; ')}`); bad++; continue }
  let bindings = {}
  try {
    const script = compileScript(descriptor, { id: rel })
    bindings = script.bindings || {}
  } catch (e) { console.log(`[script-error] ${rel}: ${e.message}`); bad++; continue }
  const tpl = descriptor.template
  if (!tpl) continue
  const result = compileTemplate({
    id: rel,
    filename: abs,
    source: tpl.content,
    compilerOptions: { mode: 'module', bindingMetadata: bindings, prefixIdentifiers: true },
  })
  if (result.errors.length) { console.log(`[template-error] ${rel}: ${result.errors.map(e => e.message || e).join('; ')}`); bad++; continue }
  const code = result.code
  const used = new Set()
  for (const m of code.matchAll(/_ctx\.([A-Za-z_$][\w$]*)/g)) used.add(m[1])
  for (const m of code.matchAll(/_resolveComponent\("([^"]+)"\)/g)) used.add(`[component]${m[1]}`)
  const missing = []
  for (const name of used) {
    if (name.startsWith('[component]')) {
      const comp = name.slice('[component]'.length)
      // el-* / El* 为 Element Plus 全局注册组件（app.use(ElementPlus)），运行时可解析
      if (/^(el-|El)/.test(comp)) continue
      // 组件：setup 绑定（PascalCase 或 kebab→Pascal）或全局注册（MainLayout 等在 app 层）
      const pascal = comp.split(/[-_]/).map(s => s[0].toUpperCase() + s.slice(1)).join('')
      if (!(pascal in bindings)) missing.push(`${comp} (resolveComponent → 未在 setup 绑定)`)
      continue
    }
    if (ALLOW.has(name)) continue
    if (!(name in bindings)) missing.push(name)
  }
  if (missing.length) { console.log(`[missing-bindings] ${rel}:`); missing.forEach(m => console.log(`  - ${m}`)); bad++ }
  else console.log(`[ok] ${rel}`)
}
console.log(bad ? `\nFAIL: ${bad} file(s) with problems` : '\nPASS: all SFC template bindings resolved')
process.exit(bad ? 1 : 0)
