/**
 * 请求状态组合式函数
 *
 * 统一收敛页面里反复手写的三件套：loading / error / 竞态序号。
 * 竞态序号（seq）用于"快速切换目标时丢弃过期响应"，
 * 与 report-center 现有 detailSeq 的做法等价。
 *
 * 用法：
 *   const { loading, error, seq, run } = useRequest()
 *   const load = (id) => run(async (mySeq) => {
 *     const data = await api.getThing(id)
 *     if (mySeq !== seq.value) return   // 过期响应，丢弃
 *     thing.value = data
 *   })
 */
import { ref } from 'vue'

export function useRequest(options = {}) {
  const { onError } = options
  const loading = ref(false)
  const error = ref('')
  const seq = ref(0)

  /**
   * 执行一个异步任务；并发调用时只有最新一次的结果会被采纳
   * @param {(mySeq: number) => Promise<any>} task
   * @param {{ silent?: boolean }} [opts] silent=true 时不置 error（保留调用方自定义提示）
   */
  async function run(task, opts = {}) {
    const mySeq = ++seq.value
    loading.value = true
    if (!opts.silent) error.value = ''
    try {
      return await task(mySeq)
    } catch (e) {
      if (mySeq === seq.value && !opts.silent) {
        error.value = e && e.message ? e.message : String(e)
      }
      if (onError) onError(e, mySeq)
      return undefined
    } finally {
      if (mySeq === seq.value) loading.value = false
    }
  }

  return { loading, error, seq, run }
}

export default useRequest
