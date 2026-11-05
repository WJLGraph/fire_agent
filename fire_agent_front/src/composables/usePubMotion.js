/**
 * 公开页组共享动效装配（/welcome 及其子页）
 *
 * GSAP ScrollTrigger + Lenis 官方引擎纪律的集中实现：
 *   - Lenis wrapper 模式接管页面根节点滚动容器，raf 由 gsap.ticker 驱动，
 *     lenis.on('scroll') 联动 ScrollTrigger.update；组件卸载 destroy + ticker 移除
 *   - 所有动画收拢在 gsap.context 内，卸载 ctx.revert() 统一还原并 kill
 *   - 纪律红线：不用 autoAlpha；不用 from()/fromTo()（一律 set 初始态 + to 终态）；
 *     不设 overwrite（靠目标拆分避免冲突）；只动 transform/opacity/filter
 *   - prefers-reduced-motion：不建 Lenis、不建任何动画，内容直接静态呈现
 *
 * 对外提供：scrolled（导航收缩态）、scrollToId（Lenis 平滑锚点）、scrollPct（全页滚动比例）
 * 通过 provide 向 PubHeader/PubFooter 等子组件下发滚动态；页面自身请用返回值
 * （Vue 的 inject 只查父级链，同组件内 provide 给自己用是取不到的）。
 */
import { ref, provide, inject, onMounted, onBeforeUnmount } from 'vue'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import { motionAllowed } from '@/composables/useMotionPreference'

gsap.registerPlugin(ScrollTrigger)

const SCROLLED_KEY = 'pub:scrolled'
const SCROLLTO_KEY = 'pub:scrollTo'
const SCROLLPCT_KEY = 'pub:scrollPct'

export function usePubScrolled() {
  return inject(SCROLLED_KEY, ref(false))
}
export function usePubScrollTo() {
  return inject(SCROLLTO_KEY, () => {})
}
export function usePubScrollPct() {
  return inject(SCROLLPCT_KEY, ref(0))
}

export function usePubMotion(rootRef) {
  const scrolled = ref(false)
  const scrollPct = ref(0)
  let lenis = null
  let ctx = null
  let tickerFn = null

  provide(SCROLLED_KEY, scrolled)
  provide(SCROLLTO_KEY, (id) => scrollToId(id))
  provide(SCROLLPCT_KEY, scrollPct)

  let staticScrollFn = null
  let lineUnbinds = []

  const scrollToId = (id) => {
    const el = typeof id === 'string' ? document.getElementById(id) : id
    if (!el || !rootRef.value) return
    if (lenis) {
      lenis.scrollTo(el, { offset: -56, duration: 1.2, easing: (t) => 1 - Math.pow(1 - t, 3) })
    } else {
      el.scrollIntoView({ behavior: !motionAllowed.value ? 'auto' : 'smooth', block: 'start' })
    }
  }

  /** 通用显现：set 初始态 + 进入视口一次性 to（once），blur 收敛；
   *  onEnter 同时加 .on 类，供 qt.css 线条绘制（.rv.on）等 CSS 联动。
   *  线条头区（.sec__hd/.qsec__hd）单独走 IntersectionObserver（.on + 入场），
   *  与 ScrollTrigger 解耦：即使 ST 因 scroller 时序未触发，头区线条也保证出现 */
  const buildReveals = (root, scroller) => {
    const lineHeads = Array.from(root.querySelectorAll('.sec__hd.rv, .qsec__hd.rv'))
    const lineSet = new Set(lineHeads)
    let lineIO = null
    if (lineHeads.length && 'IntersectionObserver' in window) {
      lineIO = new IntersectionObserver((entries) => {
        entries.forEach((en) => {
          if (!en.isIntersecting) return
          const el = en.target
          lineIO.unobserve(el)
          el.classList.add('on')
          const delay = Number(el.dataset.rvDelay || 0)
          gsap.to(el, {
            opacity: 1, y: 0, filter: 'blur(0px)',
            duration: 0.85, ease: 'power3.out', delay,
            clearProps: 'transform',
          })
        })
      }, { threshold: 0.2, rootMargin: '0px 0px -6% 0px' })
      lineHeads.forEach((el) => lineIO.observe(el))
      lineUnbinds.push(() => { lineIO?.disconnect(); lineIO = null })
    }
    root.querySelectorAll('.rv').forEach((el) => {
      if (lineSet.has(el)) return
      const delay = Number(el.dataset.rvDelay || 0)
      gsap.set(el, { opacity: 0, y: 24, filter: 'blur(8px)' })
      ScrollTrigger.create({
        trigger: el, scroller, start: 'top 86%', once: true,
        onEnter: () => {
          el.classList.add('on')
          gsap.to(el, {
            opacity: 1, y: 0, filter: 'blur(0px)',
            duration: 0.85, ease: 'power3.out', delay,
            clearProps: 'transform',
          })
        },
      })
    })
  }

  /** 卡组错峰（.rv-group 内 .rv-item，等距 stagger） */
  const buildStagger = (root, scroller) => {
    root.querySelectorAll('[data-stagger]').forEach((group) => {
      const items = Array.from(group.querySelectorAll('.rv-item'))
      if (!items.length) return
      items.forEach((el) => gsap.set(el, { opacity: 0, y: 22, filter: 'blur(6px)' }))
      ScrollTrigger.create({
        trigger: group, scroller, start: 'top 84%', once: true,
        onEnter: () => items.forEach((el, i) => gsap.to(el, {
          opacity: 1, y: 0, filter: 'blur(0px)',
          duration: 0.8, ease: 'power3.out', delay: i * 0.07,
          clearProps: 'transform',
        })),
      })
    })
  }

  /** 章节线条真滚动绘制：scrub 驱动 --hd-line 0→1（start top 88% → end top 55%），
   *  随滚动展开、回滚回缩；默认 CSS var=1 静态满格，本函数仅在 motionAllowed 时运行。
   *  覆盖 .sec__hd / .qsec__hd / .phead__inner / .hero__rule 四类线条宿主 */
  const buildScrubLines = (root, scroller) => {
    root.querySelectorAll('.sec__hd, .qsec__hd, .phead__inner, .pg-head, .hero__rule').forEach((el) => {
      gsap.set(el, { '--hd-line': 0 })
      ScrollTrigger.create({
        trigger: el, scroller, start: 'top 88%', end: 'top 55%', scrub: 0.4,
        onUpdate: (self) => { el.style.setProperty('--hd-line', self.progress.toFixed(4)) },
      })
      lineUnbinds.push(() => el.style.removeProperty('--hd-line'))
    })
  }

  /** 章节大标题遮罩揭示：JS 包装（外层 overflow hidden + 内层 translateY 110%→0），
   *  整块揭示不拆字；一次性进入视口完成，块间错峰 0.12s。
   *  不改模板：mount 时把标题子节点移入内层 span，卸载时还原 */
  const buildTitleMasks = (root, scroller) => {
    const titles = root.querySelectorAll('.sec__t, .qsec__t, .phead__title, .pg-head__title')
    titles.forEach((el) => {
      if (el.dataset.maskWrapped) return
      el.dataset.maskWrapped = '1'
      const prevDisplay = getComputedStyle(el).display
      const inner = document.createElement('span')
      inner.className = 'tt-mask-in'
      inner.style.display = 'block'
      inner.style.willChange = 'transform'
      while (el.firstChild) inner.appendChild(el.firstChild)
      el.appendChild(inner)
      el.style.overflow = 'hidden'
      if (prevDisplay === 'inline') el.style.display = 'block'
      gsap.set(inner, { yPercent: 110 })
      ScrollTrigger.create({
        trigger: el, scroller, start: 'top 88%', once: true,
        onEnter: () => gsap.to(inner, { yPercent: 0, duration: 1.0, ease: 'power4.out', delay: 0.12 }),
      })
      lineUnbinds.push(() => {
        // 还原 DOM 结构（route 离开时）
        while (inner.firstChild) el.insertBefore(inner.firstChild, inner)
        inner.remove()
        el.style.overflow = ''
        el.style.display = ''
        delete el.dataset.maskWrapped
      })
    })
  }

  /** 磁吸按钮（pointer 跟随位移 + 光斑 CSS 变量；触屏无 pointermove 自然无感）。
   *  rect 在 pointerenter 缓存一次，move 内零 DOM 读取；监听全部 passive */
  const bindMagnetics = (root) => {
    const unbinds = []
    root.querySelectorAll('.magnetic').forEach((el) => {
      let r = null
      const onEnter = () => { r = el.getBoundingClientRect() }
      const onMove = (e) => {
        if (!r) r = el.getBoundingClientRect()
        gsap.to(el, {
          x: (e.clientX - (r.left + r.width / 2)) * 0.18,
          y: (e.clientY - (r.top + r.height / 2)) * 0.22,
          duration: 0.5, ease: 'power3.out',
        })
        el.style.setProperty('--mx', `${e.clientX - r.left}px`)
        el.style.setProperty('--my', `${e.clientY - r.top}px`)
      }
      const onLeave = () => { r = null; gsap.to(el, { x: 0, y: 0, duration: 0.8, ease: 'elastic.out(1, 0.5)' }) }
      el.addEventListener('pointerenter', onEnter, { passive: true })
      el.addEventListener('pointermove', onMove, { passive: true })
      el.addEventListener('pointerleave', onLeave, { passive: true })
      unbinds.push(() => {
        el.removeEventListener('pointerenter', onEnter)
        el.removeEventListener('pointermove', onMove)
        el.removeEventListener('pointerleave', onLeave)
      })
    })
    return unbinds
  }

  /** 首屏头区入场：eyebrow/标题/导语/动作条依次浮现 */
  const buildHeadIntro = (root) => {
    const head = root.querySelector('[data-head]')
    if (!head) return
    const parts = ['eyebrow', 'title', 'lead', 'acts', 'ctx'].map((k) => head.querySelector(`[data-h="${k}"]`)).filter(Boolean)
    parts.forEach((el, i) => gsap.set(el, { opacity: 0, y: i === 0 ? 12 : 20 }))
    gsap.to(parts, {
      opacity: 1, y: 0, duration: 0.85, ease: 'power3.out',
      stagger: 0.09, delay: 0.05,
    })
  }

  /** 卡片 3D 聚光：pointer 跟随 --mx/--my 光斑 + rotateX/Y ±4°（perspective 900，
   *  离开弹性回正 ≤400ms；触屏 / reduced-motion 不绑定，仅剩 CSS 光斑） */
  const bindSpotlights = (root) => {
    const unbinds = []
    const fine = window.matchMedia && window.matchMedia('(pointer: fine)').matches
    root.querySelectorAll('.qt-spot').forEach((el) => {
      let r = null
      const onEnter = () => { r = el.getBoundingClientRect() }
      const onMove = (e) => {
        if (!r) r = el.getBoundingClientRect()
        const px = (e.clientX - r.left) / r.width
        const py = (e.clientY - r.top) / r.height
        el.style.setProperty('--mx', `${(px * 100).toFixed(2)}%`)
        el.style.setProperty('--my', `${(py * 100).toFixed(2)}%`)
        if (!fine || !motionAllowed.value) return // off：保留聚光，去掉倾斜
        gsap.to(el, {
          rotationY: (px - 0.5) * 6,   // ±3°（动效纪律：弱化 3D）
          rotationX: -(py - 0.5) * 6,  // ±3°
          transformPerspective: 900,
          duration: 0.4, ease: 'power2.out',
        })
      }
      const onLeave = () => {
        r = null
        if (!fine || !motionAllowed.value) return
        gsap.to(el, { rotationX: 0, rotationY: 0, duration: 0.4, ease: 'back.out(1.4)' })
      }
      el.addEventListener('pointerenter', onEnter, { passive: true })
      el.addEventListener('pointermove', onMove, { passive: true })
      el.addEventListener('pointerleave', onLeave, { passive: true })
      unbinds.push(() => {
        el.removeEventListener('pointerenter', onEnter)
        el.removeEventListener('pointermove', onMove)
        el.removeEventListener('pointerleave', onLeave)
      })
    })
    return unbinds
  }

  /** 顶部滚动进度条 [data-progress] */
  const buildProgress = (root, scroller) => {
    const bar = root.querySelector('[data-progress]')
    if (!bar) return
    gsap.set(bar, { scaleX: 0 })
    ScrollTrigger.create({
      trigger: root, scroller, start: 'top top', end: 'bottom bottom',
      onUpdate: (self) => { bar.style.transform = `scaleX(${self.progress.toFixed(4)})` },
    })
  }

  onMounted(() => {
    const root = rootRef.value
    if (!root) return

    /* off（或 auto+系统减）：无 Lenis、无动画，仅保留导航收缩与进度读数所需的滚动监听 */
    if (!motionAllowed.value) {
      const bar = root.querySelector('[data-progress]')
      staticScrollFn = () => {
        scrolled.value = root.scrollTop > 24
        const p = Math.min(1, root.scrollTop / Math.max(1, root.scrollHeight - root.clientHeight))
        scrollPct.value = p
        /* 顶部进度条不走动画，直接按滚动比例写 transform（否则 off 态永远空条） */
        if (bar) bar.style.transform = `scaleX(${p.toFixed(4)})`
      }
      root.addEventListener('scroll', staticScrollFn, { passive: true })
      staticScrollFn()
      return
    }

    lenis = new Lenis({ wrapper: root, content: root.firstElementChild, duration: 1.05, autoRaf: false, smoothWheel: true })
    lenis.on('scroll', (e) => {
      scrolled.value = e.scroll > 24
      scrollPct.value = Math.min(1, e.scroll / Math.max(1, e.limit))
      ScrollTrigger.update()
    })
    tickerFn = (time) => lenis.raf(time * 1000)
    gsap.ticker.add(tickerFn)
    gsap.ticker.lagSmoothing(0)

    const unbinds = []
    ctx = gsap.context(() => {
      buildHeadIntro(root)
      buildReveals(root, root)
      buildStagger(root, root)
      buildProgress(root, root)
      buildScrubLines(root, root)
      buildTitleMasks(root, root)
      unbinds.push(...bindMagnetics(root))
      unbinds.push(...bindSpotlights(root))
    }, root)
    unbindAll = unbinds
  })

  let unbindAll = []

  onBeforeUnmount(() => {
    unbindAll.forEach((fn) => fn())
    unbindAll = []
    lineUnbinds.forEach((fn) => fn())
    lineUnbinds = []
    ctx?.revert()
    ctx = null
    if (tickerFn) { gsap.ticker.remove(tickerFn); tickerFn = null }
    lenis?.destroy()
    lenis = null
    if (staticScrollFn) {
      rootRef.value?.removeEventListener('scroll', staticScrollFn)
      staticScrollFn = null
    }
  })

  return { scrolled, scrollToId, scrollPct }
}
