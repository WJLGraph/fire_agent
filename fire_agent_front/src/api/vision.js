/**
 * 视觉与语音 API — /api/v1/vision/*
 *
 * 迁移自 views/dashboard/index.vue（火情识别）与 utils/speech.js（TTS / ASR）
 *
 * 说明：图片与音频响应均为二进制（blob / audio），故提供 *Raw 版本返回原始 Response，
 * 由调用方按需 res.blob()，行为与迁移前一致。
 */
import { get, getRaw, del, postRaw, postFormJson } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/vision`

/** GET /vision/history — 火情识别历史列表 */
export function fetchHistory() {
  return get(`${BASE}/history`)
}

/** DELETE /vision/history/{id} — 删除识别记录 */
export function deleteHistory(id) {
  return del(`${BASE}/history/${id}`)
}

/** GET /vision/image/{id} — 识别图片（二进制），返回原始 Response */
export function fetchImageRaw(id) {
  return getRaw(`${BASE}/image/${id}`)
}

/** POST /vision/analyze — 上传图片识别火情，body: FormData{ file } */
export function analyze(formData) {
  return postFormJson(`${BASE}/analyze`, formData)
}

/** POST /vision/audio/speech — 语音合成（TTS），返回原始 Response（音频二进制） */
export function textToSpeechRaw(text) {
  return postRaw(`${BASE}/audio/speech`, { text })
}

/** POST /vision/audio/transcriptions — 语音识别（ASR），body: FormData{ file } */
export function transcribe(formData) {
  return postFormJson(`${BASE}/audio/transcriptions`, formData)
}
