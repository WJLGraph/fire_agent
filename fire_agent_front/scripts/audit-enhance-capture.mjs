/**
 * 临时验收脚本：headless Edge CDP 截图 + 断言 + 帧率采样
 * 用法：先启动 Edge（--headless --remote-debugging-port=9333），再 node scripts/audit-enhance-capture.mjs
 * 产物：preview/audit-enhance/
 */
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const OUT = fileURLToPath(new URL('../preview/audit-enhance/', import.meta.url))
const PORT = 9334
const BASE = 'http://[::1]:5173'
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

class CDP {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
      }
    }
  }
  send(method, params = {}) {
    const id = ++this.id
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }))
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + (r.exceptionDetails.exception?.description || ''))
    return r.result?.value
  }
}

const connect = async (url) => {
  const ws = new WebSocket(url)
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws fail')) })
  return new CDP(ws)
}

const pageInfo = async () => {
  const res = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })
  return res.json()
}

const shot = async (cdp, name) => {
  // 触发合成器重绘，避免 headless 白图
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 700, y: 400, deltaX: 0, deltaY: 40 })
  await wait(120)
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' })
  await writeFile(`${OUT}${name}.png`, Buffer.from(data, 'base64'))
}

const gotoPage = async (cdp, path, { width = 1440, height = 900 } = {}) => {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
  await cdp.send('Page.navigate', { url: BASE + path })
  await wait(2200)
}

const scrollToEl = async (cdp, selector, extra = 80) => {
  return cdp.eval(`(() => {
    const sc = document.querySelector('.wl') || document.scrollingElement;
    const el = document.querySelector('${selector}');
    if (!el) return 'no-el';
    const top = el.getBoundingClientRect().top + sc.scrollTop - ${extra};
    sc.scrollTo({ top, behavior: 'instant' });
    return 'ok:' + Math.round(top);
  })()`)
}

const fpsSample = (cdp, ms = 5000) => cdp.eval(`new Promise((res) => {
  let n = 0; const t0 = performance.now();
  const f = () => { n++; const dt = performance.now() - t0; if (dt < ${ms}) requestAnimationFrame(f); else res({ frames: n, fps: +(n / (dt / 1000)).toFixed(1), dt: Math.round(dt) }) };
  requestAnimationFrame(f);
})`)

const run = async () => {
  await mkdir(OUT, { recursive: true })
  const info = await pageInfo()
  const cdp = await connect(info.webSocketDebuggerUrl)
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')

  const report = { pages: {}, blocks: {}, fps: {}, assertions: {} }
  const desktop = [{ path: '/welcome', name: 'welcome' }, { path: '/welcome/features', name: 'features' }, { path: '/welcome/workflow', name: 'workflow' }, { path: '/welcome/technology', name: 'technology' }, { path: '/welcome/about', name: 'about' }, { path: '/login', name: 'login' }]

  for (const p of desktop) {
    await gotoPage(cdp, p.path)
    await shot(cdp, `${p.name}-1440x900`)
    report.pages[p.name] = await cdp.eval(`({
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      text: document.body.innerText.length,
      canonical: !!document.querySelector('h1'),
      badText: /GLM|SQLite|MySQL|2s 轮询|前端零密钥|无外部依赖|七节点/.test(document.body.innerText)
    })`)
  }

  // 关键区块：地形（含 bloom / 火星 / 指针）
  await gotoPage(cdp, '/welcome')
  await scrollToEl(cdp, '.terr__stage')
  await wait(2400)
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 980, y: 480 })
  await wait(900)
  await shot(cdp, 'terrain-bloom')
  report.blocks.terrain = await cdp.eval(`(() => {
    const c = document.querySelector('.terr__stage canvas');
    const g = window.__terrainGl || null;
    return { canvas: !!c, w: c?.width || 0, h: c?.height || 0, composer: !!g?.composer, bloom: !!g?.bloom, embers: g?.embers || 0, pointer: g?.pointer || null, running: !!g?.running };
  })()`)
  // 地形段帧率：泛光开 / 关 各 5s（该段才是后处理真实负载所在）
  report.fps.terrainOn = await fpsSample(cdp, 5000)
  await cdp.eval(`window.__terrainGl?.setPost(false)`)
  await wait(600)
  report.fps.terrainOff = await fpsSample(cdp, 5000)
  await cdp.eval(`window.__terrainGl?.setPost(true)`)
  await wait(700)
  await shot(cdp, 'terrain-embers')

  // 智能体网络：按需分支注记 + 图形
  await gotoPage(cdp, '/welcome/technology')
  await scrollToEl(cdp, '.anet-stage')
  await wait(1600)
  await shot(cdp, 'anet-optional')
  report.blocks.anet = await cdp.eval(`({
    note: !!document.querySelector('.anet__note'),
    noteText: document.querySelector('.anet__note')?.innerText || '',
    canvas: !!document.querySelector('.anet-stage canvas')
  })`)

  // VT：从 features 点进 workflow，抓 data-vt-dir 与过渡帧
  await gotoPage(cdp, '/welcome/features')
  const clicked = await cdp.eval(`(() => {
    const a = [...document.querySelectorAll('a')].find((x) => x.getAttribute('href') === '/welcome/workflow' || x.getAttribute('href') === '#/welcome/workflow');
    if (a) { a.click(); return 'clicked'; }
    history.pushState(null, '', '#/welcome/workflow');
    location.hash = '#/welcome/workflow';
    return 'hash';
  })()`)
  let dir = null
  for (let i = 0; i < 20; i++) {
    await wait(40)
    dir = await cdp.eval(`document.documentElement.dataset.vtDir || null`)
    if (dir) break
  }
  await shot(cdp, 'vt-clip')
  await wait(900)
  report.blocks.vt = { clicked, dir, path: await cdp.eval('location.pathname') }

  // 2560 不测；移动端 390×844
  for (const p of desktop) {
    await gotoPage(cdp, p.path, { width: 390, height: 844 })
    await shot(cdp, `${p.name}-390x844`)
  }

  // off 态：welcome 顶部 + 地形段
  await gotoPage(cdp, '/welcome')
  await cdp.eval(`localStorage.setItem('wl-motion-pref','off')`)
  await cdp.send('Page.navigate', { url: BASE + '/welcome' })
  await wait(2200)
  await shot(cdp, 'off-welcome')
  await scrollToEl(cdp, '.terr__stage')
  await wait(1000)
  await shot(cdp, 'off-welcome-terr')
  report.assertions.off = await cdp.eval(`({
    motion: document.documentElement.dataset.motion,
    allowed: document.documentElement.dataset.motionAllowed,
    fallbackSvg: !!document.querySelector('.terr__stage svg'),
    canvasVisible: !!document.querySelector('.terr__stage canvas'),
    probe: !!window.__terrainGl
  })`)

  // 帧率：on（welcome 顶部 5s） / off 对照 / technology
  await cdp.eval(`localStorage.setItem('wl-motion-pref','auto')`)
  await gotoPage(cdp, '/welcome')
  await wait(1800)
  report.fps.welcome = await fpsSample(cdp)
  report.blocks.terrainFps = await cdp.eval(`(() => {
    const c = document.querySelector('.terr__stage canvas');
    return c ? { w: c.width, h: c.height, ratio: +(c.width / c.clientWidth).toFixed(2) } : null;
  })()`)
  await gotoPage(cdp, '/welcome/technology')
  await wait(1500)
  report.fps.technology = await fpsSample(cdp)
  await cdp.eval(`localStorage.setItem('wl-motion-pref','off')`)
  await gotoPage(cdp, '/welcome')
  report.fps.welcomeOff = await fpsSample(cdp)
  await cdp.eval(`localStorage.setItem('wl-motion-pref','auto')`)

  await writeFile(`${OUT}assertions.json`, JSON.stringify(report, null, 2), 'utf8')
  console.log(JSON.stringify(report, null, 2))
  cdp.ws.close()
}

run().catch((e) => { console.error(e); process.exit(1) })
